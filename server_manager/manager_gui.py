import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import os
import sys
import threading
import shutil

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(PROJECT_ROOT, '.env')

class ServerManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Kinetix Server Manager")
        self.root.geometry("800x600")
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.create_control_panel()
        self.create_config_panel()
        
        # Log Area
        self.log_frame = ttk.LabelFrame(root, text="Activity Log")
        self.log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=10)
        self.log_text.pack(fill='both', expand=True)
        
        self.log("Server Manager Started.")
        self.log(f"Project Root: {PROJECT_ROOT}")

    def log(self, message):
        self.log_text.insert(tk.END, f"> {message}\n")
        self.log_text.see(tk.END)

    def create_control_panel(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Control Panel")
        
        # Grid layout
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        
        # --- Redis Control ---
        redis_group = ttk.LabelFrame(frame, text="Redis Management")
        redis_group.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ttk.Button(redis_group, text="Start Redis Server", command=self.start_redis).pack(fill='x', padx=5, pady=5)
        ttk.Button(redis_group, text="Stop Redis Server", command=self.stop_redis).pack(fill='x', padx=5, pady=5)
        
        # --- Server Control ---
        server_group = ttk.LabelFrame(frame, text="Server Management")
        server_group.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        ttk.Button(server_group, text="Start Production Server", command=self.start_production_server).pack(fill='x', padx=5, pady=5)
        ttk.Label(server_group, text="(Triggers Quickstart -> Production)", font=("Arial", 8, "italic")).pack()
        
        # --- Agent Control ---
        agent_group = ttk.LabelFrame(frame, text="Agent Management")
        agent_group.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        
        ttk.Button(agent_group, text="Build Agent MSI", command=self.build_agent_msi).pack(fill='x', padx=5, pady=5)

    def create_config_panel(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Configuration")
        
        self.env_vars = {}
        self.entries = {}
        
        # Scrollable Frame for Config
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Load .env
        self.load_env()
        
        row = 0
        
        # Define fields to show
        fields = [
            ("DEBUG", "Debug Mode (True/False)"),
            ("ALLOWED_HOSTS", "Allowed Hosts (comma separated)"),
            ("SECURE_SSL_REDIRECT", "Force HTTPS (True/False)"),
            ("SECRET_KEY", "Secret Key"),
            ("REDIS_URL", "Redis URL"),
            ("DATABASE_URL", "Database URL"),
            ("VIRUSTOTAL_API_KEY", "VirusTotal API Key"),
            ("CLAMAV_ENABLED", "Enable ClamAV (True/False)"),
            ("ENCRYPTION_KEY", "Encryption Key (Do Not Change!)"),
        ]
        
        for key, label in fields:
            ttk.Label(scrollable_frame, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            val = self.env_vars.get(key, "")
            entry = ttk.Entry(scrollable_frame, width=50)
            entry.insert(0, val)
            entry.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            self.entries[key] = entry
            row += 1
            
        # Save Button
        ttk.Button(scrollable_frame, text="Save Configuration", command=self.save_config).grid(row=row, column=0, columnspan=2, pady=20)
        
        # Note about settings.py
        note = "Note: Token lifetimes are currently hardcoded in settings.py and cannot be changed here."
        ttk.Label(scrollable_frame, text=note, foreground="red").grid(row=row+1, column=0, columnspan=2, pady=5)

    def load_env(self):
        if not os.path.exists(ENV_FILE):
            self.log("No .env file found.")
            return

        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    self.env_vars[key.strip()] = val.strip()

    def save_config(self):
        # Update self.env_vars from entries
        for key, entry in self.entries.items():
            self.env_vars[key] = entry.get()
            
        # Write back to .env, preserving comments if possible? 
        # For simplicity, we'll rewrite cleanly or append. 
        # To be safe and preserve structure, let's read the file and replace lines. 
        
        try:
            with open(ENV_FILE, 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            keys_processed = set()
            
            for line in lines:
                if line.strip().startswith('#') or not line.strip():
                    new_lines.append(line)
                    continue
                
                if '=' in line:
                    key = line.split('=')[0].strip()
                    if key in self.env_vars:
                        new_lines.append(f"{key}={self.env_vars[key]}\n")
                        keys_processed.add(key)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            # Add missing keys
            for key, val in self.env_vars.items():
                if key not in keys_processed:
                    new_lines.append(f"\n{key}={val}\n")
            
            with open(ENV_FILE, 'w') as f:
                f.writelines(new_lines)
                
            self.log("Configuration saved to .env")
            messagebox.showinfo("Success", "Configuration saved successfully. restart server to apply changes.")
            
        except Exception as e:
            self.log(f"Error saving config: {e}")
            messagebox.showerror("Error", f"Failed to save config: {e}")

    def run_command(self, cmd_str, title="Running Command"):
        self.log(f"Launching: {title}...")
        try:
            # Run in new window
            subprocess.Popen(f'start "{title}" cmd /k "{cmd_str}"', shell=True, cwd=PROJECT_ROOT)
            self.log(f"Started: {title}")
        except Exception as e:
            self.log(f"Error starting {title}: {e}")
            messagebox.showerror("Error", f"Failed to start command: {e}")

    def start_redis(self):
        # Attempt to find redis-server
        # We assume it's in PATH or we can try to start it via cmd
        self.log("Attempting to start Redis...")
        self.run_command("redis-server", "Redis Server")

    def stop_redis(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to kill all redis-server processes?"):
            try:
                subprocess.run(["taskkill", "/F", "/IM", "redis-server.exe"], capture_output=True)
                self.log("Stopped Redis Server (if running).")
            except Exception as e:
                self.log(f"Error stopping Redis: {e}")

    def start_production_server(self):
        # triggers quickstart.bat and then production_server.bat
        # We can chain them in one command
        cmd = "quickstart.bat && production_server.bat"
        self.run_command(cmd, "Kinetix Production Server")

    def build_agent_msi(self):
        cmd = r"agent\build_agent_msi.bat"
        self.run_command(cmd, "Build Agent MSI")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = ServerManagerApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        input("Press Enter to exit...")
