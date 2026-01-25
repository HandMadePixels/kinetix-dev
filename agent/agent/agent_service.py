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
        
        while self.running:
            try:
                # 1. Poll for commands
                response = self.client.get_commands()
                
                if response and "error" in response and response["error"] == "unauthorized":
                    # Re-register if token is invalid
                    sys_info = self.collector.get_system_info()
                    self.client.register(sys_info['hostname'], sys_info['ip_address'], sys_info['os_version'])

                if response:
                    # Sync poll interval if provided
                    server_poll_interval = response.get('poll_interval')
                    if server_poll_interval and server_poll_interval != self.config.poll_interval:
                        agent_log.info(f"Syncing poll interval with server: {server_poll_interval}s")
                        self.config.poll_interval = server_poll_interval

                    if "commands" in response:
                        for cmd in response["commands"]:
                            self.process_command(cmd)

                # 2. Check if it's time for inventory
                now = time.time()
                if now - last_inventory_time > inventory_interval:
                    agent_log.info("Collecting and sending inventory...")
                    inventory_data = self.collector.collect_full_inventory()
                    if self.client.send_inventory(inventory_data):
                        last_inventory_time = now

            except Exception as e:
                agent_log.error(f"Error in main loop: {e}")

            # Wait for poll interval or stop event
            rc = win32event.WaitForSingleObject(self.stop_event, self.config.poll_interval * 1000)
            if rc == win32event.WAIT_OBJECT_0:
                break

    def process_command(self, cmd):
        """Execute received command"""
        cmd_type = cmd.get('command')
        push_id = cmd.get('push_id')
        agent_log.info(f"Received command: {cmd_type} (Push ID: {push_id})")
        
        if cmd_type == 'update':
            url = cmd.get('update_url')
            expected_hash = cmd.get('sha256')
            signature = cmd.get('signature')
            
            # Download and verify
            temp_path = os.path.join(self.updater.temp_dir, os.path.basename(url))
            if self.updater.download_file(url, temp_path):
                hash_ok = self.updater.verify_hash(temp_path, expected_hash)
                sig_ok = self.updater.verify_signature(temp_path, signature, expected_hash)
                
                if hash_ok and sig_ok:
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
            uninstall_string = cmd.get('payload')
            agent_log.info(f"Uninstallation requested for: {uninstall_string}")
            
            try:
                # Automatically add silent flags for common installers if missing
                if 'msiexec.exe' in uninstall_string.lower():
                    if '/qn' not in uninstall_string and '/quiet' not in uninstall_string:
                        uninstall_string = uninstall_string.replace('/I', '/X').replace('/i', '/X')
                        if '/X' not in uninstall_string:
                            uninstall_string += " /X"
                        uninstall_string += " /qn /norestart"
                elif 'setup.exe' in uninstall_string.lower():
                    if '/S' not in uninstall_string and '/s' not in uninstall_string:
                        uninstall_string += " /S"

                agent_log.info(f"Executing adjusted command: {uninstall_string}")
                
                process = subprocess.run(
                    uninstall_string, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=300
                )
                
                if process.returncode in [0, 1641, 3010]:
                    msg = "Success" + (" (Reboot required)" if process.returncode != 0 else "")
                    self.client.send_command_status(command_id, 'completed', msg)
                else:
                    error_msg = f"Uninstaller returned code {process.returncode}. Error: {process.stderr}"
                    self.client.send_command_status(command_id, 'failed', error_msg)
            except subprocess.TimeoutExpired:
                error_msg = "Uninstallation timed out after 5 minutes"
                self.client.send_command_status(command_id, 'failed', error_msg)
            except Exception as e:
                error_msg = f"Failed to execute uninstall command: {e}"
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
                action = data.get('action') # 'start' or 'stop'
                
                try:
                    if action == 'start':
                        win32serviceutil.StartService(service_name)
                        msg = f"Started service {service_name}"
                    elif action == 'stop':
                        win32serviceutil.StopService(service_name, None)
                        msg = f"Stopped service {service_name}"
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

        elif cmd_type == 'shell':
            command_id = cmd.get('command_id')
            command_to_run = cmd.get('payload')
            agent_log.info(f"Executing shell command: {command_to_run}")
            try:
                process = subprocess.run(
                    command_to_run,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                status = 'completed' if process.returncode == 0 else 'failed'
                result = process.stdout if process.returncode == 0 else process.stderr
                self.client.send_command_status(command_id, status, result)
            except Exception as e:
                self.client.send_command_status(command_id, 'failed', f"Shell execution error: {e}")
        
        elif cmd_type == 'reboot':
            command_id = cmd.get('command_id')
            message = cmd.get('payload', 'The restart has been requested by administrator.')
            try:
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                
                gui_path = os.path.join(base_dir, "gui.py")
                python_exe = sys.executable
                
                # To bypass Session 0 isolation, we use schtasks to run the process in the interactive session.
                # We create a temporary task that runs as the currently logged-on user.
                task_name = f"KinetixRebootUI_{int(time.time())}"
                
                # Command to run: python.exe gui.py "message" "hostname" "0"
                # We need to escape double quotes for the schtasks command
                escaped_msg = message.replace('"', '\\"')
                run_cmd = f'"{python_exe}" "{gui_path}" "{escaped_msg}" "{socket.gethostname()}" "0"'
                
                # Create and run the task immediately in the interactive session
                # /sc once /st 00:00 is just to satisfy requirements, /it makes it interactive
                subprocess.run(
                    f'schtasks /create /tn "{task_name}" /tr "{run_cmd}" /sc once /st 00:00 /it /f /rl highest',
                    shell=True, capture_output=True, text=True
                )
                subprocess.run(f'schtasks /run /tn "{task_name}"', shell=True, capture_output=True)
                
                # Clean up the task after a short delay (it stays running, just the registration is removed)
                threading.Timer(10, lambda: subprocess.run(f'schtasks /delete /tn "{task_name}" /f', shell=True, capture_output=True)).start()

                self.client.send_command_status(command_id, 'completed', "Interactive UI triggered via scheduled task")
                agent_log.info("Triggered reboot UI via scheduled task")
            except Exception as e:
                error_msg = f"Failed to launch reboot UI: {e}"
                agent_log.error(error_msg)
                self.client.send_command_status(command_id, 'failed', error_msg)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        win32serviceutil.HandleCommandLine(KinetixAgentService)
    else:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(KinetixAgentService)
        servicemanager.StartServiceCtrlDispatcher()