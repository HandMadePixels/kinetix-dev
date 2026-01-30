import sys
import os
import time

# Ensure the agent directory is in the path for internal imports (when running as a script)
if not getattr(sys, 'frozen', False):
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

import win32serviceutil
import servicemanager
from agent_service import KinetixAgentService
from agent_logger import agent_log
from agent_config import AgentConfig
from agent_client import AgentClient
from agent_collector import InventoryCollector

def print_help():
    print("""
Kinetix Agent CLI
Usage: kinetix_agent.exe [command]

Commands:
  install      Install as Windows Service
  remove       Remove Windows Service
  start        Start the service
  stop         Stop the service
  restart      Restart the service
  debug        Run in console (interactive mode)
  register     Force manual registration
  inventory    Collect and send inventory immediately
  set-server   Set the Kinetix Server URL
    """)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Check if running interactively (double-clicked) or as a service
        # StartServiceCtrlDispatcher will fail if double-clicked
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(KinetixAgentService)
            servicemanager.StartServiceCtrlDispatcher()
        except Exception as e:
            # Check if this is a real error or just the expected failure when running interactively
            # ERROR_FAILED_SERVICE_CONTROLLER_CONNECT (1063) indicates it's not being run by the Service Control Manager
            is_interactive = False
            try:
                import pywintypes
                if isinstance(e, pywintypes.error) and e.winerror == 1063:
                    is_interactive = True
            except:
                pass
            
            if is_interactive:
                print("Kinetix Agent is designed to run as a Windows Service.")
                print_help()
                # Only wait for input if we have a valid stdin
                if sys.stdin and hasattr(sys.stdin, 'readline'):
                    try:
                        input("\nPress Enter to exit...")
                    except (EOFError, RuntimeError):
                        pass
                else:
                    # Non-console environment, wait briefly so user can see output if any
                    time.sleep(2)
            else:
                # Log the actual error to help troubleshoot
                agent_log.error(f"Service startup error: {e}")
                import traceback
                agent_log.error(traceback.format_exc())
                print(f"Error starting service: {e}")
                time.sleep(5) # Give user a moment to read the console error if visible
    else:
        cmd = sys.argv[1].lower()
        if cmd == "set-server":
            if len(sys.argv) > 2:
                new_url = sys.argv[2]
                if not new_url.startswith("http"):
                    new_url = "http://" + new_url
                config = AgentConfig()
                agent_log.setup_file_handler(config)
                config.server_url = new_url
                print(f"Server URL updated to: {new_url}")
                print("Please restart the service for changes to take effect: kinetix_agent.exe restart")
            else:
                print("Usage: kinetix_agent.exe set-server <url>")
        elif cmd == "register":
            config = AgentConfig()
            agent_log.setup_file_handler(config)
            client = AgentClient(config)
            coll = InventoryCollector()
            sys_info = coll.get_system_info()
            if client.register(sys_info['hostname'], sys_info['ip_address'], sys_info['os_version']):
                print("Registration successful.")
            else:
                print("Registration failed.")
        elif cmd == "inventory":
            config = AgentConfig()
            agent_log.setup_file_handler(config)
            client = AgentClient(config)
            coll = InventoryCollector()
            print("Collecting inventory...")
            data = coll.collect_full_inventory()
            if client.send_inventory(data):
                print("Inventory sent successfully.")
            else:
                print("Failed to send inventory.")
        elif cmd in ["install", "remove", "start", "stop", "restart", "update", "debug"]:
            # Pass to pywin32 service utility
            win32serviceutil.HandleCommandLine(KinetixAgentService)
        elif len(sys.argv) >= 4:
            # Handle GUI Restart Arguments: kinetix_agent.exe "message" "hostname" "postpone_count"
            try:
                from gui import RestartUI
                msg = sys.argv[1]
                host = sys.argv[2]
                count = sys.argv[3]
                try:
                    count = int(count)
                except:
                    count = 0
                
                app = RestartUI(msg, host, postpone_count=count)
                app.run()
            except Exception as e:
                agent_log.error(f"Error launching UI: {e}")
        else:
            print_help()