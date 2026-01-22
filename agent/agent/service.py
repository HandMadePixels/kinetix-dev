import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import threading
import time

from logger import agent_log
from config import AgentConfig
from client import AgentClient
from collector import InventoryCollector
from updater import AgentUpdater

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
                commands = self.client.get_commands()
                
                if commands and "error" in commands and commands["error"] == "unauthorized":
                    # Re-register if token is invalid
                    sys_info = self.collector.get_system_info()
                    self.client.register(sys_info['hostname'], sys_info['ip_address'], sys_info['os_version'])
                    # Remove continue to allow waiting for next poll interval if registration failed


                if commands and "commands" in commands:
                    for cmd in commands["commands"]:
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

if __name__ == '__main__':
    if len(sys.argv) > 1:
        win32serviceutil.HandleCommandLine(KinetixAgentService)
    else:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(KinetixAgentService)
        servicemanager.StartServiceCtrlDispatcher()
