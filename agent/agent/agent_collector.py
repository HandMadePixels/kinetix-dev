import platform
import socket
import winreg
import win32service
import json
from agent_logger import agent_log

class InventoryCollector:
    """Collects system information, services, and installed applications"""
    
    @staticmethod
    def get_system_info():
        """Retrieve basic system metadata"""
        hostname = socket.gethostname()
        
        # Better way to get primary local IP
        try:
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Doesn't need to be reachable, just needs to trigger interface selection
            temp_socket.connect(("8.8.8.8", 80))
            ip_address = temp_socket.getsockname()[0]
            temp_socket.close()
        except:
            try:
                ip_address = socket.gethostbyname(hostname)
            except:
                ip_address = "127.0.0.1"
            
        return {
            "hostname": hostname,
            "ip_address": ip_address,
            "os_version": f"{platform.system()} {platform.release()} ({platform.version()})",
            "architecture": platform.machine(),
            "cpu_count": platform.processor(),
        }

    @staticmethod
    def get_logged_in_user():
        """Retrieve currently logged in user on Windows"""
        try:
            # Method 1: psutil (usually more reliable for interactive users)
            import psutil
            users = psutil.users()
            for user in users:
                if user.name:
                    return user.name
        except:
            pass

        try:
            # Method 2: WMI
            import wmi
            import pythoncom
            pythoncom.CoInitialize()
            c = wmi.WMI()
            for user in c.Win32_ComputerSystem():
                if user.UserName:
                    return user.UserName
        except:
            pass
            
        # Fallback to environment variables
        import os
        user = os.environ.get('USERNAME')
        domain = os.environ.get('USERDOMAIN')
        if user and domain:
            return f"{domain}\\{user}"
        return user or "Unknown"

    @staticmethod
    def get_uptime_info():
        """Retrieve last boot time and calculate uptime with multiple fallbacks"""
        import datetime
        
        # Helper to make datetime timezone-aware (UTC)
        def make_aware(dt):
            if dt is None: return None
            if dt.tzinfo is not None: return dt
            return dt.replace(tzinfo=datetime.timezone.utc)

        # Method 1: psutil (Recommended)
        try:
            import psutil
            boot_timestamp = psutil.boot_time()
            boot_dt = datetime.datetime.fromtimestamp(boot_timestamp, tz=datetime.timezone.utc)
            
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = now - boot_dt
            
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            uptime_str = f"{days}d {hours}h {minutes}m"
            return boot_dt.isoformat(), uptime_str
        except Exception as e:
            agent_log.warning(f"psutil uptime method failed: {e}")

        # Method 2: WMI
        try:
            import wmi
            import pythoncom
            pythoncom.CoInitialize()
            c = wmi.WMI()
            for os_obj in c.Win32_OperatingSystem():
                # Format: 20260122110924.500000+330
                boot_str = os_obj.LastBootUpTime.split('.')[0]
                boot_dt_naive = datetime.datetime.strptime(boot_str, "%Y%m%d%H%M%S")
                boot_dt = make_aware(boot_dt_naive)
                
                now = datetime.datetime.now(datetime.timezone.utc)
                delta = now - boot_dt
                
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                uptime_str = f"{days}d {hours}h {minutes}m"
                return boot_dt.isoformat(), uptime_str
        except Exception as e:
            agent_log.warning(f"WMI uptime method failed: {e}")
            
        # Method 3: ctypes (Direct Windows API call - Very reliable fallback)
        try:
            import ctypes
            # kernel32.GetTickCount64 returns milliseconds since boot
            lib = ctypes.windll.kernel32
            millis = lib.GetTickCount64()
            seconds = millis // 1000
            
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            minutes = (seconds % 3600) // 60
            
            uptime_str = f"{days}d {hours}h {minutes}m"
            
            # Estimate boot time (UTC)
            boot_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds)
            return boot_dt.isoformat(), uptime_str
        except Exception as e:
            agent_log.error(f"Failed to get uptime with all methods (psutil, WMI, ctypes): {e}")
            return None, "Unknown"

    @staticmethod
    def collect_services():
        """Enumerate Windows services"""
        services = []
        try:
            resume = 0
            access = win32service.SC_MANAGER_ALL_ACCESS
            hscm = win32service.OpenSCManager(None, None, access)
            
            # Type: Service, State: All
            type_filter = win32service.SERVICE_WIN32
            state_filter = win32service.SERVICE_STATE_ALL
            
            statuses = win32service.EnumServicesStatusEx(hscm, type_filter, state_filter)
            
            for status in statuses:
                svc_name = status.get('ServiceName', '')
                
                # Get more details for each service to get startup type
                startup_type = "unknown"
                try:
                    hsvc = win32service.OpenService(hscm, svc_name, win32service.SERVICE_QUERY_CONFIG)
                    config = win32service.QueryServiceConfig(hsvc)
                    # Mapping: 2=Auto, 3=Manual, 4=Disabled, 0=Boot, 1=System
                    type_map_startup = {
                        win32service.SERVICE_AUTO_START: "Automatic",
                        win32service.SERVICE_DEMAND_START: "Manual",
                        win32service.SERVICE_DISABLED: "Disabled",
                        win32service.SERVICE_BOOT_START: "Boot",
                        win32service.SERVICE_SYSTEM_START: "System"
                    }
                    startup_type = type_map_startup.get(config[1], "unknown")
                    
                    # Check for Delayed Start if it's Automatic
                    if config[1] == win32service.SERVICE_AUTO_START:
                        try:
                            delayed_info = win32service.QueryServiceConfig2(hsvc, win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO)
                            if delayed_info:
                                startup_type = "Automatic (Delayed Start)"
                        except:
                            pass
                            
                    win32service.CloseServiceHandle(hsvc)
                except:
                    pass

                # Map state to string (matching inventory.ServiceInventory choices)
                state_map = {
                    1: "stopped",
                    2: "running", # start_pending
                    3: "stopped", # stop_pending
                    4: "running",
                    5: "running", # continue_pending
                    6: "paused",  # pause_pending
                    7: "paused"
                }
                services.append({
                    "name": svc_name,
                    "display_name": status.get('DisplayName', ''),
                    "status": state_map.get(status.get('CurrentState'), "unknown"),
                    "startup_type": startup_type
                })
            
            win32service.CloseServiceHandle(hscm)
        except Exception as e:
            agent_log.error(f"Failed to collect services: {e}")
            
        return services

    @staticmethod
    def collect_applications():
        """Query registry for installed applications"""
        apps = []
        paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        ]
        
        for hkey, path in paths:
            try:
                # Use KEY_READ to ensure we have permission
                reg_key = winreg.OpenKey(hkey, path, 0, winreg.KEY_READ)
                for i in range(winreg.QueryInfoKey(reg_key)[0]):
                    try:
                        sub_key_name = winreg.EnumKey(reg_key, i)
                        sub_key = winreg.OpenKey(reg_key, sub_key_name)
                        
                        try:
                            try:
                                name = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                            except:
                                continue # Name is required
                                
                            try:
                                version = winreg.QueryValueEx(sub_key, "DisplayVersion")[0]
                            except:
                                version = "Unknown"
                                
                            try:
                                publisher = winreg.QueryValueEx(sub_key, "Publisher")[0]
                            except:
                                publisher = "Unknown"
                            
                            try:
                                # Try to get QuietUninstallString first
                                try:
                                    uninstall = winreg.QueryValueEx(sub_key, "QuietUninstallString")[0]
                                except:
                                    uninstall = winreg.QueryValueEx(sub_key, "UninstallString")[0]
                            except:
                                uninstall = ""
                            
                            apps.append({
                                "display_name": str(name)[:255],
                                "version": str(version)[:100],
                                "publisher": str(publisher)[:255],
                                "uninstall_string": str(uninstall)
                            })
                        except Exception:
                            continue
                        finally:
                            winreg.CloseKey(sub_key)
                    except EnvironmentError:
                        continue
                winreg.CloseKey(reg_key)
            except Exception as e:
                # Silently skip if path doesn't exist
                pass

        # Deduplicate
        unique_apps = {f"{a['display_name']}-{a['version']}": a for a in apps}.values()
        return list(unique_apps)

    @staticmethod
    def collect_windows_updates():
        """Retrieve Windows Update history (KBs)"""
        updates = []
        try:
            import win32com.client
            import pythoncom
            import re
            
            pythoncom.CoInitialize()
            session = win32com.client.Dispatch("Microsoft.Update.Session")
            searcher = session.CreateUpdateSearcher()
            
            # Get total history count
            count = searcher.GetTotalHistoryCount()
            if count == 0:
                return []
                
            # Query history (get last 50 updates for performance)
            start_index = max(0, count - 50)
            history = searcher.QueryHistory(start_index, 50)
            
            for item in history:
                title = str(item.Title)
                # Extract KB ID using regex (e.g., KB5034441)
                kb_match = re.search(r'(KB\d+)', title)
                kb_id = kb_match.group(1) if kb_match else ""
                
                # Convert pywintypes.datetime to isoformat
                # item.Date is a pywintypes.datetime which behaves like datetime but might need conversion
                installed_at = str(item.Date)
                try:
                    # Usually it's already in a good string format or can be converted
                    # Format: 2024-01-26 12:34:56+00:00
                    pass
                except:
                    installed_at = None

                updates.append({
                    "title": title[:500],
                    "kb_id": kb_id,
                    "installed_at": installed_at,
                    "description": str(item.Description)[:1000] if hasattr(item, 'Description') else "",
                    "support_url": str(item.SupportUrl)[:500] if hasattr(item, 'SupportUrl') else ""
                })
        except Exception as e:
            agent_log.error(f"Failed to collect Windows Updates: {e}")
            
        return updates

    def collect_full_inventory(self):
        """Prepare complete inventory payload"""
        info = self.get_system_info()
        boot_time, uptime = self.get_uptime_info()
        return {
            "hostname": info["hostname"],
            "ip_address": info["ip_address"],
            "os_version": info["os_version"],
            "current_user": self.get_logged_in_user(),
            "last_boot_time": boot_time,
            "uptime": uptime,
            "services": self.collect_services(),
            "installed_apps": self.collect_applications(),
            "windows_updates": self.collect_windows_updates()
        }
