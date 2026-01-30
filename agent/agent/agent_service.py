import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import threading
import time
import subprocess
import json

from agent_logger import agent_log
from agent_config import AgentConfig
from agent_client import AgentClient
from agent_collector import InventoryCollector
from agent_updater import AgentUpdater
from packaging import version as py_version

class KinetixAgentService(win32serviceutil.ServiceFramework):
    """Windows Service wrapper for the Kinetix Agent"""
    
    _svc_name_ = "KinetixAgent"
    _svc_display_name_ = "Kinetix Endpoint Agent"
    _svc_description_ = "Ensures secure update delivery and inventory reporting for Kinetix."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.running = True
        
        # Initialize components
        self.config = AgentConfig()
        
        # Configure logger with actual settings
        agent_log.setup_file_handler(self.config)
        
        self.client = AgentClient(self.config)
        self.collector = InventoryCollector()
        
        # Resolve absolute path for public key
        key_filename = self.config.config.get('Security', 'PublicKeyFile', fallback='public_key.pem')
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        public_key_path = os.path.join(base_dir, key_filename)
        self.updater = AgentUpdater(public_key_path)
        
        # Command log initialization
        self.cmd_log_path = os.path.join(base_dir, "logs", "command_history.log")

    def _scrub_data(self, data):
        """Redact sensitive keys from dictionaries or strings"""
        if isinstance(data, str):
            # If it's a JSON string, try to parse and scrub it
            try:
                parsed = json.loads(data)
                return json.dumps(self._scrub_data(parsed))
            except:
                return data
        
        if not isinstance(data, (dict, list)):
            return data
            
        sensitive_keys = {'token', 'refresh', 'password', 'key', 'secret', 'signature'}
        
        if isinstance(data, list):
            return [self._scrub_data(item) for item in data]
            
        scrubbed = {}
        for k, v in data.items():
            if any(sk in k.lower() for sk in sensitive_keys):
                scrubbed[k] = "********"
            elif isinstance(v, (dict, list)):
                scrubbed[k] = self._scrub_data(v)
            else:
                scrubbed[k] = v
        return scrubbed

    def log_command(self, cmd):
        """Log received command to history file with sanitization"""
        try:
            # Ensure log directory exists
            log_dir = os.path.dirname(self.cmd_log_path)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            
            # SECURITY FIX: Scrub sensitive data before logging locally
            scrubbed_cmd = self._scrub_data(cmd)
            
            log_entry = {
                "timestamp": timestamp,
                "command": scrubbed_cmd.get('command'),
                "id": scrubbed_cmd.get('command_id') or scrubbed_cmd.get('push_id'),
                "payload": scrubbed_cmd.get('payload') or scrubbed_cmd.get('update_url', 'N/A')
            }
            with open(self.cmd_log_path, 'a') as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            agent_log.error(f"Failed to log command: {e}")

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False
        agent_log.info("Service stopping...")

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def main(self):
        agent_log.info("Agent main loop started")
        
        # Initial registration if needed
        if not self.config.agent_id or not self.config.get_token():
            sys_info = self.collector.get_system_info()
            self.client.register(sys_info['hostname'], sys_info['ip_address'], sys_info['os_version'])

        last_inventory_time = 0
        inventory_interval = 86400  # daily
        last_update_check = 0
        
        while self.running:
            try:
                # 0. Check for Agent Self-Update
                now = time.time()
                if now - last_update_check > self.config.update_check_interval:
                    update_res = self.check_for_self_update()
                    if update_res == "network_error":
                        # Don't update timestamp, try again next cycle
                        agent_log.warning("Update check skipped due to network error, will retry next poll.")
                    else:
                        if update_res is True:
                            agent_log.info("Self-update triggered. Exiting main loop to allow installer to proceed.")
                            break # Exit loop immediately
                        last_update_check = now

                # 1. Poll for commands
                response = self.client.get_commands()
                
                if response and "error" in response and response["error"] == "unauthorized":
                    # Re-register if token is invalid
                    sys_info = self.collector.get_system_info()
                    self.client.register(sys_info['hostname'], sys_info['ip_address'], sys_info['os_version'])
                elif response is None:
                    # Network error, will retry next poll
                    agent_log.warning("Command poll failed (network), skipping this cycle.")
                elif response:
                    # Sync poll interval if provided
                    server_poll_interval = response.get('poll_interval')
                    if server_poll_interval and server_poll_interval != self.config.poll_interval:
                        agent_log.info(f"Syncing poll interval with server: {server_poll_interval}s")
                        self.config.poll_interval = server_poll_interval

                    has_commands = False
                    if "commands" in response and response["commands"]:
                        has_commands = True
                        for cmd in response["commands"]:
                            self.process_command(cmd)
                    
                    # SECURITY OPTIMIZATION: "Chain Polling"
                    if has_commands:
                        agent_log.info("Commands received, triggering immediate re-poll...")
                        continue 

                # 2. Check if it's time for inventory
                now = time.time()
                if now - last_inventory_time > inventory_interval:
                    agent_log.info("Collecting and sending inventory...")
                    inventory_data = self.collector.collect_full_inventory()
                    response = self.client.send_inventory(inventory_data)
                    if response is True:
                        last_inventory_time = now
                    elif response is None:
                        agent_log.warning("Inventory submission failed (network), will retry next poll.")
                    elif isinstance(response, dict) and response.get("error") == "unauthorized":
                        agent_log.warning("Inventory submission unauthorized, re-registering...")
                        sys_info = self.collector.get_system_info()
                        self.client.register(sys_info['hostname'], sys_info['ip_address'], sys_info['os_version'])

            except Exception as e:
                import traceback
                error_msg = f"Error in main loop: {e}\n{traceback.format_exc()}"
                agent_log.error(error_msg)

            # Wait for poll interval or stop event
            rc = win32event.WaitForSingleObject(self.stop_event, self.config.poll_interval * 1000)
            if rc == win32event.WAIT_OBJECT_0:
                break

        # If we exited the loop but are still running (e.g. self-update), 
        # inform SCM that we are stopping so it doesn't report a crash.
        if not self.running:
            return

        agent_log.info("Service process terminating gracefully for update...")
        try:
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        except:
            pass
            
        # Exit. sys.exit is cleaner than os._exit for a graceful stop
        sys.exit(0)

    def check_for_self_update(self):
        """Check for and apply agent self-updates"""
        agent_log.info(f"Checking for agent self-update (Current version: {self.config.version})...")
        update_info = self.client.get_latest_agent_info()
        
        if update_info is None:
            return "network_error"

        if isinstance(update_info, dict) and update_info.get("error") == "unauthorized":
            agent_log.warning("Update check unauthorized, re-registering...")
            sys_info = self.collector.get_system_info()
            self.client.register(sys_info['hostname'], sys_info['ip_address'], sys_info['os_version'])
            return "unauthorized"

        # Sync update check interval if provided
        server_interval = update_info.get('update_interval')
        if server_interval and server_interval != self.config.update_check_interval:
            agent_log.info(f"Syncing agent update interval with server: {server_interval}s")
            self.config.update_check_interval = server_interval

        if 'latest_version' not in update_info:
            return

        latest_version = update_info['latest_version']
        try:
            if py_version.parse(latest_version) <= py_version.parse(self.config.version):
                agent_log.info(f"Agent is up to date (Current: {self.config.version}, Server: {latest_version}).")
                return
        except Exception as e:
            agent_log.error(f"Version comparison error: {e}")
            if latest_version == self.config.version:
                return

        agent_log.info(f"New agent version available: {latest_version}. Starting auto-update...")
        
        url = update_info['url']
        expected_hash = update_info['sha256']
        
        temp_path = os.path.join(self.updater.temp_dir, f"agent_update_{latest_version}.msi")
        
        if self.updater.download_file(url, temp_path):
            if self.updater.verify_hash(temp_path, expected_hash):
                agent_log.info("Agent update verified. Triggering installation...")
                
                # Report start of update
                self.client.send_command_status("AGENT_SELF_UPDATE", "in_progress", f"Updating to {latest_version}")
                
                # Give the system 3 seconds to flush logs and send the status message
                time.sleep(3)

                # Run the installer. Since we are a service, msiexec will stop us, 
                # update files, and restart us if WiX is configured correctly.
                # Use REINSTALLMODE=amus to force overwrite same files.
                if self.updater.install_update(temp_path):
                    agent_log.info("Agent update installer launched successfully.")
                    return True # Indicate that update is in progress
                else:
                    agent_log.error("Failed to launch agent update installer.")
                    self.client.send_command_status("AGENT_SELF_UPDATE", "failed", "Installer launch failed")
            else:
                agent_log.security("Agent update hash verification failed!")
                self.client.send_command_status("AGENT_SELF_UPDATE", "failed", "Hash verification failed")
        else:
            agent_log.error("Failed to download agent update.")
        
        return False # No update started

    def process_command(self, cmd):
        """Dispatch command to a background thread to prevent blocking"""
        thread = threading.Thread(target=self._execute_command, args=(cmd,))
        thread.daemon = True
        thread.start()

    def _execute_command(self, cmd):
        """Execute received command (internal threaded method)"""
        cmd_type = cmd.get('command')
        push_id = cmd.get('push_id')
        agent_log.info(f"Processing command in background: {cmd_type}")
        self.log_command(cmd)
        
        if cmd_type == 'update':
            url = cmd.get('update_url')
            expected_hash = cmd.get('sha256')
            signature = cmd.get('signature')
            
            # Download and verify
            temp_path = os.path.join(self.updater.temp_dir, os.path.basename(url))
            if self.updater.download_file(url, temp_path):
                hash_ok = self.updater.verify_hash(temp_path, expected_hash)
                sig_ok = self.updater.verify_signature(temp_path, signature, expected_hash)
                mime_ok = self.updater.verify_mime(temp_path)
                
                if hash_ok and sig_ok and mime_ok:
                    if self.updater.install_update(temp_path):
                        self.client.send_update_status(push_id, 'completed')
                        # Trigger immediate inventory update after successful install
                        agent_log.info("Update successful, triggering proactive inventory sync")
                        inventory_data = self.collector.collect_full_inventory()
                        self.client.send_inventory(inventory_data)
                    else:
                        self.client.send_update_status(push_id, 'failed', 'Installation failed')
                else:
                    error_msg = "Verification failed: "
                    if not hash_ok: error_msg += "Hash mismatch "
                    if not sig_ok: error_msg += "Signature invalid"
                    
                    agent_log.security(error_msg)
                    self.client.send_update_status(push_id, 'failed', error_msg.strip())
            else:
                agent_log.error("Failed to download update")
                self.client.send_update_status(push_id, 'failed', 'Download failed')
        
        elif cmd_type == 'collect_inventory':
            agent_log.info("Forced inventory collection requested by server")
            inventory_data = self.collector.collect_full_inventory()
            if self.client.send_inventory(inventory_data):
                agent_log.info("Inventory successfully sent")
        
        elif cmd_type == 'uninstall':
            command_id = cmd.get('command_id')
            uninstall_string = cmd.get('payload', '')
            agent_log.info(f"Uninstallation requested for: {uninstall_string}")
            
            try:
                # 1. Handle quoting for paths with spaces if not already quoted
                # We look for the first .exe or .exe" to find the split point
                adjusted_cmd = uninstall_string.strip()
                if adjusted_cmd and not adjusted_cmd.startswith('"'):
                    if '.exe' in adjusted_cmd.lower():
                        exe_idx = adjusted_cmd.lower().find('.exe') + 4
                        exe_path = adjusted_cmd[:exe_idx]
                        args = adjusted_cmd[exe_idx:]
                        if ' ' in exe_path:
                            adjusted_cmd = f'"{exe_path}"{args}'
                
                # 2. Automatically add silent flags for common installers if missing
                lower_cmd = adjusted_cmd.lower()
                if 'msiexec.exe' in lower_cmd:
                    if '/qn' not in lower_cmd and '/quiet' not in lower_cmd:
                        adjusted_cmd = adjusted_cmd.replace('/I', '/X').replace('/i', '/X')
                        if '/X' not in adjusted_cmd and '/x' not in lower_cmd:
                            adjusted_cmd += " /X"
                        adjusted_cmd += " /qn /norestart"
                elif 'setup.exe' in lower_cmd or 'uninstall.exe' in lower_cmd:
                    # Common silent flags for custom uninstallers
                    if not any(flag in lower_cmd for flag in ['/s', '/S', '-s', '-S', '/quiet', '/silent']):
                        adjusted_cmd += " /S"

                agent_log.info(f"Executing adjusted command: {adjusted_cmd}")
                
                process = subprocess.run(
                    adjusted_cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=300
                )
                
                if process.returncode in [0, 1641, 3010]:
                    msg = "Success" + (" (Reboot required)" if process.returncode != 0 else "")
                    self.client.send_command_status(command_id, 'completed', msg)
                else:
                    error_msg = f"Uninstaller returned code {process.returncode}. Output: {process.stdout} Error: {process.stderr}"
                    agent_log.error(f"Uninstall failed: {error_msg}")
                    self.client.send_command_status(command_id, 'failed', error_msg)
            except subprocess.TimeoutExpired:
                error_msg = "Uninstallation timed out after 5 minutes"
                agent_log.error(error_msg)
                self.client.send_command_status(command_id, 'failed', error_msg)
            except Exception as e:
                error_msg = f"Failed to execute uninstall command: {e}"
                agent_log.error(error_msg)
                self.client.send_command_status(command_id, 'failed', error_msg)
        
        elif cmd_type == 'registry':
            command_id = cmd.get('command_id')
            payload_str = cmd.get('payload')
            try:
                import winreg
                data = json.loads(payload_str)
                
                hive_map = {
                    'HKLM': winreg.HKEY_LOCAL_MACHINE,
                    'HKCU': winreg.HKEY_CURRENT_USER,
                    'HKU': winreg.HKEY_USERS,
                    'HKCR': winreg.HKEY_CLASSES_ROOT
                }
                
                type_map = {
                    'REG_SZ': winreg.REG_SZ,
                    'REG_DWORD': winreg.REG_DWORD,
                    'REG_BINARY': winreg.REG_BINARY,
                    'REG_MULTI_SZ': winreg.REG_MULTI_SZ,
                    'REG_EXPAND_SZ': winreg.REG_EXPAND_SZ
                }
                
                hive = hive_map.get(data.get('hive'))
                path = data.get('path')
                value_name = data.get('value_name')
                value = data.get('value')
                vtype = type_map.get(data.get('type', 'REG_SZ'))
                
                if hive is None:
                    raise ValueError(f"Invalid Hive: {data.get('hive')}")

                key = winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE)
                if vtype == winreg.REG_DWORD:
                    value = int(value)
                
                winreg.SetValueEx(key, value_name, 0, vtype, value)
                winreg.CloseKey(key)
                
                self.client.send_command_status(command_id, 'completed', f"Successfully set {value_name}")
            except Exception as e:
                self.client.send_command_status(command_id, 'failed', f"Registry error: {e}")
        
        elif cmd_type == 'service_control':
            command_id = cmd.get('command_id')
            payload_str = cmd.get('payload')
            try:
                import win32serviceutil
                import pywintypes
                data = json.loads(payload_str)
                service_name = data.get('service_name')
                action = data.get('action') # 'start', 'stop', 'restart'
                
                try:
                    if action == 'start':
                        win32serviceutil.StartService(service_name)
                        msg = f"Started service {service_name}"
                    elif action == 'stop':
                        win32serviceutil.StopService(service_name, None)
                        msg = f"Stopped service {service_name}"
                    elif action == 'restart':
                        win32serviceutil.RestartService(service_name)
                        msg = f"Restarted service {service_name}"
                    else:
                        raise ValueError(f"Invalid action: {action}")
                except pywintypes.error as e:
                    # Handle already running (1056) or already stopped (1062)
                    if e.winerror == 1056 and action == 'start':
                        msg = f"Service {service_name} is already running"
                    elif e.winerror == 1062 and action == 'stop':
                        msg = f"Service {service_name} is already stopped"
                    else:
                        raise
                
                self.client.send_command_status(command_id, 'completed', msg)
                agent_log.info(msg)
            except Exception as e:
                error_msg = f"Service control error: {e}"
                agent_log.error(error_msg)
                self.client.send_command_status(command_id, 'failed', error_msg)

        elif cmd_type == 'service_config':
            command_id = cmd.get('command_id')
            payload_str = cmd.get('payload')
            try:
                import win32service
                data = json.loads(payload_str)
                service_name = data.get('service_name')
                startup_type = data.get('startup_type') # 'automatic', 'manual', 'disabled', 'delayed'
                
                hscm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
                hsvc = win32service.OpenService(hscm, service_name, win32service.SERVICE_CHANGE_CONFIG | win32service.SERVICE_QUERY_CONFIG)
                
                startup_map = {
                    'automatic': win32service.SERVICE_AUTO_START,
                    'manual': win32service.SERVICE_DEMAND_START,
                    'disabled': win32service.SERVICE_DISABLED,
                    'delayed': win32service.SERVICE_AUTO_START
                }
                
                dwStartType = startup_map.get(startup_type)
                if dwStartType is None:
                    raise ValueError(f"Invalid startup type: {startup_type}")
                
                # Change basic config
                win32service.ChangeServiceConfig(
                    hsvc, win32service.SERVICE_NO_CHANGE, dwStartType, 
                    win32service.SERVICE_NO_CHANGE, None, None, 0, None, None, None, None
                )
                
                # Handle Delayed Start if requested
                if startup_type == 'delayed':
                    win32service.ChangeServiceConfig2(hsvc, win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO, True)
                elif startup_type == 'automatic':
                    win32service.ChangeServiceConfig2(hsvc, win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO, False)
                
                win32service.CloseServiceHandle(hsvc)
                win32service.CloseServiceHandle(hscm)
                
                msg = f"Changed {service_name} startup to {startup_type}"
                self.client.send_command_status(command_id, 'completed', msg)
                agent_log.info(msg)
            except Exception as e:
                error_msg = f"Service config error: {e}"
                agent_log.error(error_msg)
                self.client.send_command_status(command_id, 'failed', error_msg)

        elif cmd_type == 'shell':
            command_id = cmd.get('command_id')
            command_to_run = cmd.get('payload')
            agent_log.info(f"Executing shell command: {command_to_run}")
            try:
                import shlex
                # SECURITY: Split command into arguments and run without shell=True if possible
                # This prevents shell operators (like ;) from working if they somehow slipped past the server.
                args = shlex.split(command_to_run)
                
                process = subprocess.run(
                    args,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                status = 'completed' if process.returncode == 0 else 'failed'
                result = process.stdout if process.returncode == 0 else process.stderr
                self.client.send_command_status(command_id, status, result)
            except Exception as e:
                # If direct execution fails, try fallback but log it
                agent_log.warning(f"Direct execution failed, fallback to shell for compat: {e}")
                try:
                    process = subprocess.run(command_to_run, shell=True, capture_output=True, text=True, timeout=60)
                    status = 'completed' if process.returncode == 0 else 'failed'
                    result = process.stdout if process.returncode == 0 else process.stderr
                    self.client.send_command_status(command_id, status, result)
                except Exception as e2:
                    self.client.send_command_status(command_id, 'failed', f"Shell execution error: {e2}")
        
        elif cmd_type == 'reboot':
            command_id = cmd.get('command_id')
            message = cmd.get('payload', 'The restart has been requested by administrator.')
            try:
                # Use absolute paths for everything
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                    exe_path = sys.executable
                    run_cmd = f'"{exe_path}" "{message}" "{socket.gethostname()}" "0"'
                else:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    python_exe = sys.executable
                    gui_path = os.path.join(base_dir, "gui.py")
                    run_cmd = f'"{python_exe}" "{gui_path}" "{message}" "{socket.gethostname()}" "0"'
                
                # To bypass schtasks quoting hell, we write the command to a temporary batch file
                system_drive = os.environ.get('SystemDrive', 'C:')
                if not system_drive.endswith('\\'):
                    system_drive += '\\'
                
                public_temp = os.path.join(system_drive, 'Users', 'Public', 'KinetixAgent')
                if not os.path.exists(public_temp):
                    os.makedirs(public_temp)
                    # Ensure the interactive user can actually see/run things in this folder
                    subprocess.run(f'icacls "{public_temp}" /grant Everyone:(OI)(CI)F /T', shell=True, capture_output=True)
                
                temp_bat = os.path.join(public_temp, f"reboot_{int(time.time())}.bat")
                temp_log = temp_bat + ".log"
                
                with open(temp_bat, 'w') as f:
                    f.write("@echo off\n")
                    f.write(f"cd /d \"{public_temp}\"\n")
                    f.write(f"echo [%date% %time%] Starting Reboot UI > \"{temp_log}\"\n")
                    f.write(f"echo Command: {run_cmd} >> \"{temp_log}\"\n")
                    f.write(f"{run_cmd} >> \"{temp_log}\" 2>&1\n")
                    f.write(f"echo [%date% %time%] UI process exited with code %errorlevel% >> \"{temp_log}\"\n")
                    f.write(f"del \"%~f0\" & exit\n")

                # Ensure the batch file itself is accessible/executable by Everyone
                subprocess.run(f'icacls "{temp_bat}" /grant Everyone:F /T', shell=True, capture_output=True)

                # To bypass Session 0 isolation, we use schtasks to run the process in the interactive session.
                # Use a shorter, cleaner task name
                task_id = int(time.time() % 100000)
                task_name = f"KinetixReboot_{task_id}"
                
                # We use /sd 01/01/2099 to ensure the task isn't "expired" at creation.
                # Use cmd.exe /c to launch the batch file. This is more robust than relying on file associations
                # directly in the task scheduler, especially across different OS versions.
                # Quoting: /tr "cmd.exe /c \"path_to_bat\""
                full_task_cmd = f'schtasks /create /tn "{task_name}" /tr "cmd.exe /c \\"{temp_bat}\\"" /sc once /st 00:00 /sd 01/01/2099 /ru "INTERACTIVE" /it /f /rl highest'
                agent_log.info(f"Creating interactive task: {full_task_cmd}")
                
                create_res = subprocess.run(full_task_cmd, shell=True, capture_output=True, text=True)
                if create_res.returncode != 0:
                    agent_log.error(f"Task creation failed: {create_res.stdout} {create_res.stderr}")
                    # KEEPING THE BAT FILE FOR DEBUGGING
                    raise Exception(f"schtasks create failed: {create_res.stderr}")
                
                agent_log.info(f"Task created successfully: {create_res.stdout.strip()}")
                time.sleep(1)
                    
                # Trigger the task immediately
                run_res = subprocess.run(f'schtasks /run /tn "{task_name}"', shell=True, capture_output=True, text=True)
                if run_res.returncode != 0:
                    agent_log.error(f"Task run failed: {run_res.stdout} {run_res.stderr}")
                    # KEEPING THE BAT FILE FOR DEBUGGING
                    raise Exception(f"schtasks run failed: {run_res.stderr}")
                
                agent_log.info("Reboot UI task triggered successfully.")
                
                # Cleanup the task after 5 minutes (instead of 60s) to give it room to breathe
                threading.Timer(300, lambda: subprocess.run(f'schtasks /delete /tn "{task_name}" /f', shell=True, capture_output=True)).start()

                self.client.send_command_status(command_id, 'completed', "Interactive UI triggered via scheduled task batch wrapper")
                agent_log.info("Triggered reboot UI via scheduled task batch wrapper")
            except Exception as e:
                error_msg = f"Failed to launch reboot UI: {e}"
                agent_log.error(error_msg)
                self.client.send_command_status(command_id, 'failed', error_msg)

        elif cmd_type == 'restart_agent':
            command_id = cmd.get('command_id')
            agent_log.info("Agent self-restart requested")
            try:
                # Send success status before we actually stop the service
                self.client.send_command_status(command_id, 'completed', "Agent restart initiated")
                
                # Use sc instead of net for better service control compatibility
                # We add a short delay to ensure the status message is fully sent
                restart_cmd = 'timeout /t 3 /nobreak && sc stop KinetixAgent && timeout /t 2 /nobreak && sc start KinetixAgent'
                subprocess.Popen(f'cmd /c "{restart_cmd}"', shell=True)
                
                agent_log.info("Restart command dispatched to external process")
            except Exception as e:
                error_msg = f"Failed to initiate agent restart: {e}"
                agent_log.error(error_msg)
                self.client.send_command_status(command_id, 'failed', error_msg)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        win32serviceutil.HandleCommandLine(KinetixAgentService)
    else:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(KinetixAgentService)
        servicemanager.StartServiceCtrlDispatcher()