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
        self.create_backup_panel()
        
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
            ("AGENT_UPDATE_INTERVAL", "Agent Self-Update Check Interval (seconds)"),
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
        cmd = r"server-manager\quickstart.bat && server-manager\production_server.bat"
        self.run_command(cmd, "Kinetix Production Server")

    def build_agent_msi(self):
        cmd = r"server-manager\build_agent_msi.bat"
        self.run_command(cmd, "Build Agent MSI")

    def create_backup_panel(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Backup & Restore")
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="Create New Full Backup", command=self.create_backup).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh List", command=self.refresh_backup_list).pack(side='left', padx=5)
        
        # List of backups
        list_label = ttk.Label(frame, text="Available Backups (in /backups folder):")
        list_label.pack(anchor='w', padx=15)
        
        self.backup_listbox = tk.Listbox(frame, height=15)
        self.backup_listbox.pack(fill='both', expand=True, padx=15, pady=5)
        
        # Restore button
        restore_btn = ttk.Button(frame, text="Restore Selected Backup", command=self.restore_backup)
        restore_btn.pack(pady=10)
        
        self.refresh_backup_list()

    def get_backup_dir(self):
        bck_dir = os.path.join(PROJECT_ROOT, "backups")
        if not os.path.exists(bck_dir):
            os.makedirs(bck_dir)
        return bck_dir

    def refresh_backup_list(self):
        self.backup_listbox.delete(0, tk.END)
        import glob
        files = glob.glob(os.path.join(self.get_backup_dir(), "*.zip"))
        files.sort(key=os.path.getmtime, reverse=True)
        for f in files:
            self.backup_listbox.insert(tk.END, os.path.basename(f))

    def create_backup(self):
        import zipfile
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"kinetix_backup_{timestamp}.zip"
        filepath = os.path.join(self.get_backup_dir(), filename)
        
        self.log(f"Starting backup: {filename}")
        
        try:
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 1. Database
                db_path = os.path.join(PROJECT_ROOT, "db.sqlite3")
                if os.path.exists(db_path):
                    zipf.write(db_path, "db.sqlite3")
                
                # 2. Config
                env_path = os.path.join(PROJECT_ROOT, ".env")
                if os.path.exists(env_path):
                    zipf.write(env_path, ".env")
                
                # 3. Keys
                keys_dir = os.path.join(PROJECT_ROOT, "keys")
                if os.path.exists(keys_dir):
                    for root, dirs, files in os.walk(keys_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arc_name = os.path.relpath(full_path, PROJECT_ROOT)
                            zipf.write(full_path, arc_name)
                
                # 4. Media
                media_dir = os.path.join(PROJECT_ROOT, "media")
                if os.path.exists(media_dir):
                    for root, dirs, files in os.walk(media_dir):
                        if 'processed' in root: continue
                        for file in files:
                            full_path = os.path.join(root, file)
                            arc_name = os.path.relpath(full_path, PROJECT_ROOT)
                            zipf.write(full_path, arc_name)

            self.log(f"Backup successful: {filename}")
            messagebox.showinfo("Success", f"Backup created successfully:\n{filename}")
            self.refresh_backup_list()
        except Exception as e:
            self.log(f"Backup failed: {e}")
            messagebox.showerror("Error", f"Backup failed: {e}")

    def restore_backup(self):
        selection = self.backup_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a backup to restore.")
            return
            
        filename = self.backup_listbox.get(selection[0])
        if not messagebox.askyesno("Confirm Restore", f"This will OVERWRITE current database and settings with {filename}.\n\nContinue?"):
            return
            
        import zipfile
        filepath = os.path.join(self.get_backup_dir(), filename)
        
        try:
            self.log(f"Restoring backup: {filename}")
            with zipfile.ZipFile(filepath, 'r') as zipf:
                zipf.extractall(PROJECT_ROOT)
            
            self.log("Restore complete.")
            messagebox.showinfo("Success", "System restored. Please restart services.")
            self.load_env()
        except Exception as e:
            self.log(f"Restore failed: {e}")
            messagebox.showerror("Error", f"Restore failed: {e}")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = ServerManagerApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        input("Press Enter to exit...")
