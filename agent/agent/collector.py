import platform
import socket
import winreg
import win32service
import json
from logger import agent_log

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
                    "name": status.get('ServiceName', ''),
                    "display_name": status.get('DisplayName', ''),
                    "status": state_map.get(status.get('CurrentState'), "unknown")
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
                            
                            apps.append({
                                "display_name": str(name)[:255],
                                "version": str(version)[:100],
                                "publisher": str(publisher)[:255]
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

    def collect_full_inventory(self):
        """Prepare complete inventory payload"""
        info = self.get_system_info()
        return {
            "hostname": info["hostname"],
            "ip_address": info["ip_address"],
            "os_version": info["os_version"],
            "services": self.collect_services(),
            "installed_apps": self.collect_applications()
        }
