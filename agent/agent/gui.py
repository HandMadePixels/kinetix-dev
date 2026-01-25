import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import subprocess
import time
import json

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import subprocess
import time
import json
from PIL import Image, ImageTk

class RestartUI:
    def __init__(self, message, hostname, app_name="Kinetix Endpoint Agent", postpone_count=0):
        self.message = message
        self.hostname = hostname
        self.app_name = app_name
        self.postpone_count = int(postpone_count)
        self.max_postpones = 3
        
        self.root = tk.Tk()
        self.root.title(self.app_name)
        self.root.geometry("500x450")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        
        # Center the window
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (500 // 2)
        y = (screen_height // 2) - (450 // 2)
        self.root.geometry(f"500x450+{x}+{y}")

        # Resolve paths
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.setup_ui()

    def setup_ui(self):
        # Clear existing widgets if any (for refresh)
        for widget in self.root.winfo_children():
            widget.destroy()

        # Main container
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Logo and Title Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        logo_path = os.path.join(self.base_dir, "logo.png")
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                img = img.resize((40, 40), Image.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                logo_label = tk.Label(header_frame, image=self.logo_img)
                logo_label.pack(side=tk.LEFT, padx=(0, 10))
            except Exception as e:
                print(f"Logo error: {e}")

        title_info_frame = ttk.Frame(header_frame)
        title_info_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        ttk.Label(title_info_frame, text=self.app_name, font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(title_info_frame, text=f"Device: {self.hostname}", font=("Segoe UI", 9)).pack(anchor=tk.W)

        # Warning Title
        header_label = ttk.Label(main_frame, text="🔄 Restart Required", font=("Segoe UI", 16, "bold"), foreground="#d32f2f")
        header_label.pack(pady=(0, 10))

        # Admin Message
        msg_frame = ttk.LabelFrame(main_frame, text="Administrator Message", padding="10")
        msg_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        ttk.Label(msg_frame, text=self.message, wraplength=420, font=("Segoe UI", 10)).pack(fill=tk.BOTH)

        # Postpone Section
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)

        if self.postpone_count < self.max_postpones:
            ttk.Label(action_frame, text="You can postpone this restart:").pack(side=tk.LEFT)
            self.later_var = tk.StringVar(value="30 minutes")
            self.later_dropdown = ttk.Combobox(action_frame, textvariable=self.later_var, width=15, state="readonly")
            self.later_dropdown['values'] = ("30 minutes", "1 hour", "2 hours", "4 hours")
            self.later_dropdown.pack(side=tk.LEFT, padx=10)
            
            self.postpone_label = ttk.Label(main_frame, text=f"Postponed {self.postpone_count}/{self.max_postpones} times", font=("Segoe UI", 8))
            self.postpone_label.pack(pady=2)
        else:
            ttk.Label(main_frame, text="Maximum postpones reached. Please save your work and restart now.", foreground="red", font=("Segoe UI", 10, "bold")).pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        self.btn_restart = ttk.Button(button_frame, text="Restart Now", command=self.restart_now)
        self.btn_restart.pack(side=tk.RIGHT, padx=5)

        if self.postpone_count < self.max_postpones:
            self.btn_later = ttk.Button(button_frame, text="Restart Later", command=self.restart_later)
            self.btn_later.pack(side=tk.RIGHT, padx=5)

    def restart_now(self):
        if messagebox.askyesno("Confirm Restart", "Your computer will restart immediately. Please ensure all your work is saved."):
            subprocess.run(["shutdown", "/r", "/t", "0"], shell=True)
            self.root.destroy()

    def restart_later(self):
        val_str = self.later_var.get()
        minutes = 30
        if "hour" in val_str:
            minutes = int(val_str.split()[0]) * 60
        else:
            minutes = int(val_str.split()[0])

        self.root.withdraw() # Hide UI
        
        # Increment postpone count
        self.postpone_count += 1
        
        # Schedule showing again using root.after (non-blocking)
        # Convert minutes to milliseconds
        wait_ms = minutes * 60 * 1000
        self.root.after(wait_ms, self.show_ui)

    def show_ui(self):
        self.setup_ui() # Refresh UI state
        self.root.deiconify()
        self.root.attributes("-topmost", True)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    # Expects: gui.py "message" "hostname" "postpone_count"
    msg = sys.argv[1] if len(sys.argv) > 1 else "The restart has been requested by administrator."
    host = sys.argv[2] if len(sys.argv) > 2 else "Unknown Device"
    count = sys.argv[3] if len(sys.argv) > 3 else 0
    
    app = RestartUI(msg, host, postpone_count=count)
    app.run()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    # Expects: gui.py "message" "hostname" "postpone_count"
    msg = sys.argv[1] if len(sys.argv) > 1 else "The restart has been requested by administrator."
    host = sys.argv[2] if len(sys.argv) > 2 else "Unknown Device"
    count = sys.argv[3] if len(sys.argv) > 3 else 0
    
    app = RestartUI(msg, host, postpone_count=count)
    app.run()
