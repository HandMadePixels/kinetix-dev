import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import subprocess
import os
import sys
import threading
import shutil
import datetime
import glob
import zipfile
import json
import time


# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE     = os.path.join(PROJECT_ROOT, '.env')

# ─────────────────────────────────────────────
#  Design Tokens  (dark, professional palette)
# ─────────────────────────────────────────────
C = {
    "bg":         "#0f1117",   # main background
    "surface":    "#1a1d27",   # card / panel surface
    "surface2":   "#22263a",   # slightly lighter surface
    "border":     "#2e3250",   # subtle borders
    "accent":     "#4f7dff",   # primary blue accent
    "accent2":    "#7c53e8",   # purple accent
    "success":    "#22c55e",   # green
    "warning":    "#f59e0b",   # amber
    "danger":     "#ef4444",   # red
    "text":       "#e2e8f0",   # primary text
    "text_dim":   "#8892a4",   # secondary text
    "sidebar":    "#13161f",   # sidebar bg
    "sel":        "#1e2540",   # sidebar selected item
    "log_bg":     "#0b0d15",   # log area bg
    "log_text":   "#7ee787",   # log text (terminal green)
}

FONT_TITLE  = ("Segoe UI", 13, "bold")
FONT_HEAD   = ("Segoe UI", 10, "bold")
FONT_BODY   = ("Segoe UI", 9)
FONT_SMALL  = ("Segoe UI", 8)
FONT_MONO   = ("Consolas", 9)


# ─────────────────────────────────────────────
#  Custom Widgets
# ─────────────────────────────────────────────

class StatusDot(tk.Canvas):
    """An animated pulsing circle that indicates service state."""
    def __init__(self, parent, size=12, **kw):
        bg = kw.pop("bg", C["surface"])  # avoid duplicate keyword if caller passes bg=
        super().__init__(parent, width=size, height=size, highlightthickness=0,
                         bg=bg, **kw)
        self._size = size
        self._color = C["text_dim"]
        self._pulse_id = None
        self._alpha = 1.0
        self._direction = -1
        self._draw()

    def _draw(self):
        self.delete("all")
        pad = 1
        self.create_oval(pad, pad, self._size - pad, self._size - pad,
                         fill=self._color, outline="")

    def set_state(self, running: bool):
        self._color = C["success"] if running else C["danger"]
        self._draw()
        if running:
            self._start_pulse()
        else:
            self._stop_pulse()

    def set_checking(self):
        self._color = C["warning"]
        self._draw()
        self._stop_pulse()

    def _start_pulse(self):
        self._stop_pulse()
        self._animate()

    def _stop_pulse(self):
        if self._pulse_id:
            self.after_cancel(self._pulse_id)
            self._pulse_id = None

    def _animate(self):
        """Simple scale-pulse by redrawing with varying padding."""
        self._alpha += self._direction * 0.04
        if self._alpha <= 0.3:
            self._direction = 1
        elif self._alpha >= 1.0:
            self._direction = -1
        pad = int((1 - self._alpha) * (self._size * 0.35)) + 1
        self.delete("all")
        self.create_oval(pad, pad, self._size - pad, self._size - pad,
                         fill=self._color, outline="")
        self._pulse_id = self.after(50, self._animate)


class ModernButton(tk.Frame):
    """A custom styled button with hover animation."""
    def __init__(self, parent, text, command=None, style="default",
                 icon="", width=0, **kw):
        bg = {
            "default": C["accent"],
            "danger":  C["danger"],
            "success": C["success"],
            "ghost":   C["surface2"],
            "warning": C["warning"],
        }.get(style, C["accent"])

        hover_bg = {
            "default": "#6b93ff",
            "danger":  "#f87171",
            "success": "#4ade80",
            "ghost":   "#2d3249",
            "warning": "#fbbf24",
        }.get(style, "#6b93ff")

        super().__init__(parent, bg=bg, cursor="hand2", **kw)
        self._bg = bg
        self._hover = hover_bg
        self._cmd = command

        inner_text = f"{icon}  {text}" if icon else text
        self._lbl = tk.Label(self, text=inner_text, font=FONT_BODY,
                             bg=bg, fg="white", padx=12, pady=6)
        if width:
            self._lbl.config(width=width)
        self._lbl.pack(fill='both', expand=True)

        for w in (self, self._lbl):
            w.bind("<Enter>",    self._on_enter)
            w.bind("<Leave>",    self._on_leave)
            w.bind("<Button-1>", self._on_click)

    def _on_enter(self, _=None):
        self.config(bg=self._hover)
        self._lbl.config(bg=self._hover)

    def _on_leave(self, _=None):
        self.config(bg=self._bg)
        self._lbl.config(bg=self._bg)

    def _on_click(self, _=None):
        if self._cmd:
            self._cmd()


class Card(tk.Frame):
    """A styled card with a title bar."""
    def __init__(self, parent, title="", **kw):
        super().__init__(parent, bg=C["surface"], bd=0,
                         highlightbackground=C["border"], highlightthickness=1, **kw)
        if title:
            hdr = tk.Frame(self, bg=C["surface2"])
            hdr.pack(fill='x')
            tk.Label(hdr, text=title, font=FONT_HEAD,
                     bg=C["surface2"], fg=C["text"], padx=12, pady=7).pack(side='left')
        self.body = tk.Frame(self, bg=C["surface"])
        self.body.pack(fill='both', expand=True, padx=10, pady=10)


class ServiceCard(tk.Frame):
    """A compact service status + control card."""
    def __init__(self, parent, label, start_cmd, stop_cmd, **kw):
        super().__init__(parent, bg=C["surface"],
                         highlightbackground=C["border"], highlightthickness=1, **kw)
        self.dot = StatusDot(self, size=14, bg=C["surface"])
        self.dot.grid(row=0, column=0, padx=(10, 6), pady=10)
        self.dot.set_checking()

        self._lbl = tk.Label(self, text=label, font=FONT_HEAD,
                             bg=C["surface"], fg=C["text"])
        self._lbl.grid(row=0, column=1, sticky='w', pady=10)

        self._status = tk.Label(self, text="Checking…", font=FONT_SMALL,
                                bg=C["surface"], fg=C["text_dim"])
        self._status.grid(row=1, column=1, sticky='w', pady=(0, 6))

        btn_frame = tk.Frame(self, bg=C["surface"])
        btn_frame.grid(row=0, column=2, rowspan=2, padx=10, pady=6, sticky='e')

        ModernButton(btn_frame, "Start", command=start_cmd, style="success").pack(side='left', padx=2)
        ModernButton(btn_frame, "Stop",  command=stop_cmd,  style="danger").pack(side='left', padx=2)

        self.columnconfigure(1, weight=1)

    def update_state(self, running: bool):
        self.dot.set_state(running)
        if running:
            self._status.config(text="● RUNNING", fg=C["success"])
        else:
            self._status.config(text="○ STOPPED", fg=C["danger"])


class SidebarItem(tk.Frame):
    """A clickable sidebar nav item."""
    def __init__(self, parent, text, icon, on_select, **kw):
        super().__init__(parent, bg=C["sidebar"], cursor="hand2", **kw)
        self._on_select = on_select
        self._selected = False

        self._icon_lbl = tk.Label(self, text=icon, font=("Segoe UI Emoji", 16),
                                  bg=C["sidebar"], fg=C["text_dim"], width=3)
        self._icon_lbl.pack(side='left', padx=(8, 0), pady=10)
        self._txt_lbl  = tk.Label(self, text=text, font=FONT_BODY,
                                  bg=C["sidebar"], fg=C["text_dim"], anchor='w')
        self._txt_lbl.pack(side='left', fill='x', expand=True, pady=10)

        self._indicator = tk.Frame(self, bg=C["sidebar"], width=3)
        self._indicator.pack(side='right', fill='y')

        for w in (self, self._icon_lbl, self._txt_lbl, self._indicator):
            w.bind("<Enter>",    self._on_enter)
            w.bind("<Leave>",    self._on_leave)
            w.bind("<Button-1>", self._click)

    def select(self):
        self._selected = True
        for w in (self, self._icon_lbl, self._txt_lbl, self._indicator):
            w.config(bg=C["sel"])
        self._indicator.config(bg=C["accent"])
        self._txt_lbl.config(fg=C["text"])
        self._icon_lbl.config(fg=C["accent"])

    def deselect(self):
        self._selected = False
        for w in (self, self._icon_lbl, self._txt_lbl, self._indicator):
            w.config(bg=C["sidebar"])
        self._indicator.config(bg=C["sidebar"])
        self._txt_lbl.config(fg=C["text_dim"])
        self._icon_lbl.config(fg=C["text_dim"])

    def _on_enter(self, _=None):
        if not self._selected:
            for w in (self, self._icon_lbl, self._txt_lbl, self._indicator):
                w.config(bg=C["sel"])

    def _on_leave(self, _=None):
        if not self._selected:
            for w in (self, self._icon_lbl, self._txt_lbl, self._indicator):
                w.config(bg=C["sidebar"])

    def _click(self, _=None):
        self._on_select()


# ─────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────

class ServerManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Kinetix Server Manager")
        self.root.geometry("1060x720")
        self.root.minsize(900, 600)
        self.root.configure(bg=C["bg"])

        # Hide default titlebar decorations on Windows for a cleaner look
        # (uses a standard frame so it still works on all platforms)
        self.root.resizable(True, True)

        # State
        self.active_processes = {}
        self.last_env_mode    = "prod" # Track if last start was dev or prod
        self.headless_var     = tk.BooleanVar(value=True)
        self.env_vars         = {}
        self.entries          = {}
        self.status_labels    = {}
        self.monitor_running  = True
        self.status_data      = {"redis": False, "web": False, "celery": False}

        # Logging
        os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)
        self.gui_log_file = os.path.join(PROJECT_ROOT, "logs", "manager_gui.log")

        # Ensure env keys
        try:
            from ensure_keys import ensure_keys
            ensure_keys()
        except Exception as e:
            print(f"Warning: Failed to verify security keys: {e}")

        self._build_layout()
        self._start_monitor()
        self.update_status_loop()

        self.log("Kinetix Server Manager started.")
        self.log(f"Project root: {PROJECT_ROOT}")

        # Fresh system → go to Setup tab
        if not os.path.exists(ENV_FILE) or not os.path.exists(os.path.join(PROJECT_ROOT, "db.sqlite3")):
            self._switch_page("setup")
            self.log("Fresh system detected — please complete the setup.")
        else:
            self.log("System state verified.")

    # ─── Layout ──────────────────────────────────────────────────────────

    def _build_layout(self):
        # ── Topbar ──────────────────────────────────────────────────────
        topbar = tk.Frame(self.root, bg=C["surface"], height=52,
                          highlightbackground=C["border"], highlightthickness=1)
        topbar.pack(side='top', fill='x')
        topbar.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(topbar, bg=C["accent"], width=52, height=52)
        logo_frame.pack(side='left')
        logo_frame.pack_propagate(False)
        tk.Label(logo_frame, text="⚡", font=("Segoe UI Emoji", 20),
                 bg=C["accent"], fg="white").place(relx=.5, rely=.5, anchor='center')

        tk.Label(topbar, text="Kinetix", font=("Segoe UI", 14, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(side='left', padx=(14, 4))
        tk.Label(topbar, text="Server Manager", font=("Segoe UI", 10),
                 bg=C["surface"], fg=C["text_dim"]).pack(side='left')

        # Project path
        tk.Label(topbar, text=f"  🗂  {PROJECT_ROOT}",
                 font=FONT_SMALL, bg=C["surface"], fg=C["text_dim"]).pack(side='right', padx=16)

        # ── Main body ────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(side='top', fill='both', expand=True)

        # Sidebar
        sidebar = tk.Frame(body, bg=C["sidebar"], width=190)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)

        tk.Frame(sidebar, bg=C["border"], height=1).pack(fill='x')

        self._pages       = {}
        self._sidebar_items = {}
        self._current_page  = None

        # Content pane
        self._content = tk.Frame(body, bg=C["bg"])
        self._content.pack(side='left', fill='both', expand=True)

        # Build sidebar + pages
        nav_items = [
            ("control",     "⚙",  "Control Panel"),
            ("config",      "🔧", "Configuration"),
            ("backup",      "💾", "Backup & Restore"),
            ("maintenance", "🛠", "Maintenance"),
            ("setup",       "🚀", "System Setup"),
        ]

        tk.Label(sidebar, text="NAVIGATION", font=("Segoe UI", 7, "bold"),
                 bg=C["sidebar"], fg=C["text_dim"]).pack(anchor='w', padx=12, pady=(14, 2))

        for page_id, icon, label in nav_items:
            item = SidebarItem(sidebar, label, icon,
                               on_select=lambda pid=page_id: self._switch_page(pid))
            item.pack(fill='x')
            self._sidebar_items[page_id] = item

        # Spacer + headless toggle at bottom of sidebar
        tk.Frame(sidebar, bg=C["sidebar"]).pack(fill='y', expand=True)
        tk.Frame(sidebar, bg=C["border"], height=1).pack(fill='x')
        self._build_sidebar_footer(sidebar)

        # Build all pages (hidden initially)
        self._build_control_page()
        self._build_config_page()
        self._build_backup_page()
        self._build_maintenance_page()
        self._build_setup_page()

        # ── Activity Log ─────────────────────────────────────────────────
        log_frame = tk.Frame(self.root, bg=C["surface"],
                             highlightbackground=C["border"], highlightthickness=1)
        log_frame.pack(side='bottom', fill='x')

        log_title = tk.Frame(log_frame, bg=C["surface2"])
        log_title.pack(fill='x')
        tk.Label(log_title, text="  📋  Activity Log", font=FONT_SMALL,
                 bg=C["surface2"], fg=C["text_dim"]).pack(side='left', pady=4)
        ModernButton(log_title, "Clear", command=self._clear_log,
                     style="ghost").pack(side='right', padx=6, pady=2)

        self.log_text = tk.Text(log_frame, height=7, font=FONT_MONO,
                                bg=C["log_bg"], fg=C["log_text"],
                                insertbackground=C["log_text"],
                                bd=0, relief='flat', padx=8, pady=6)
        sb = tk.Scrollbar(log_frame, command=self.log_text.yview)
        sb.pack(side='right', fill='y')
        self.log_text.config(yscrollcommand=sb.set)
        self.log_text.pack(fill='x')

        # Show first page
        self._switch_page("control")

    def _build_sidebar_footer(self, parent):
        foot = tk.Frame(parent, bg=C["sidebar"])
        foot.pack(fill='x', padx=8, pady=8)

        toggle_frame = tk.Frame(foot, bg=C["sidebar"])
        toggle_frame.pack(fill='x')

        tk.Label(toggle_frame, text="Headless Mode", font=FONT_SMALL,
                 bg=C["sidebar"], fg=C["text_dim"]).pack(side='left')

        chk = tk.Checkbutton(toggle_frame, variable=self.headless_var,
                              bg=C["sidebar"], fg=C["text"],
                              activebackground=C["sidebar"],
                              selectcolor=C["accent"],
                              relief='flat', bd=0)
        chk.pack(side='right')

    def _switch_page(self, page_id):
        # Deselect all sidebar items
        for pid, item in self._sidebar_items.items():
            item.deselect()
        # Hide all pages
        for page in self._pages.values():
            page.pack_forget()
        # Show selected
        self._sidebar_items[page_id].select()
        self._pages[page_id].pack(fill='both', expand=True)
        self._current_page = page_id

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def _make_page(self, page_id):
        """Create a scrollable page frame and register it."""
        outer = tk.Frame(self._content, bg=C["bg"])
        self._pages[page_id] = outer
        return outer

    # ─── Utility ─────────────────────────────────────────────────────────

    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}]  {message}"
        try:
            self.log_text.insert(tk.END, entry + "\n")
            self.log_text.see(tk.END)
        except Exception:
            pass
        try:
            with open(self.gui_log_file, "a") as f:
                f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]  {message}\n")
        except Exception:
            pass

    def _section(self, parent, title):
        """Helper: returns a Card widget packed into parent."""
        card = Card(parent, title=title)
        card.pack(fill='x', padx=16, pady=6)
        return card.body

    def _label(self, parent, text, style="body"):
        font = {"title": FONT_TITLE, "head": FONT_HEAD, "small": FONT_SMALL}.get(style, FONT_BODY)
        fg   = C["text_dim"] if style == "small" else C["text"]
        return tk.Label(parent, text=text, font=font, bg=C["surface"], fg=fg, anchor='w')

    # ─── Background monitor ───────────────────────────────────────────────

    def _start_monitor(self):
        self.monitor_thread = threading.Thread(target=self._bg_monitor, daemon=True)
        self.monitor_thread.start()

    def _bg_monitor(self):
        import socket, time
        while self.monitor_running:
            self.status_data["redis"] = self.check_redis()
            web_up = False
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    web_up = s.connect_ex(('127.0.0.1', 8000)) == 0
            except Exception:
                pass
            self.status_data["web"] = web_up
            self.status_data["celery"] = any("Celery" in n for n in self.active_processes)
            time.sleep(2)

    def update_status_loop(self):
        try:
            # Prune dead processes
            for name, proc in list(self.active_processes.items()):
                rc = proc.poll()
                if rc is not None:
                    del self.active_processes[name]
                    if rc == 0:
                        # Success exit - common for tasks
                        if name in ("Migrations", "CollectStatic", "Backup", "Clean"):
                            self.log(f"Task completed: {name}")
                        else:
                            self.log(f"Service finished: {name}")
                    else:
                        # Error exit
                        self.log(f"Service stopped: {name} (Code {rc})")

            # Update service cards
            if hasattr(self, 'card_redis'):
                self.card_redis.update_state(self.status_data["redis"])
            if hasattr(self, 'card_web'):
                self.card_web.update_state(self.status_data["web"])
            if hasattr(self, 'card_celery'):
                self.card_celery.update_state(self.status_data["celery"])

            # Update setup status dots if visible
            if self._current_page == "setup":
                self.update_setup_status()

        except Exception:
            pass
        self.root.after(1500, self.update_status_loop)

    # ─── Control Panel ───────────────────────────────────────────────────

    def _build_control_page(self):
        page = self._make_page("control")

        # Page header
        hdr = tk.Frame(page, bg=C["bg"])
        hdr.pack(fill='x', padx=16, pady=(16, 4))
        tk.Label(hdr, text="Control Panel", font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(side='left')

        # ── Service Status Cards ─────────────────────────────────────────
        status_card = Card(page, title="Service Status")
        status_card.pack(fill='x', padx=16, pady=6)

        self.card_redis = ServiceCard(status_card.body, "Redis",
                                      start_cmd=self.start_redis,
                                      stop_cmd=self.stop_redis)
        self.card_redis.pack(fill='x', pady=4)

        self.card_web = ServiceCard(status_card.body, "Web Server",
                                    start_cmd=self.smart_start_services,
                                    stop_cmd=self.stop_web_server)
        self.card_web.pack(fill='x', pady=4)

        self.card_celery = ServiceCard(status_card.body, "Celery Workers",
                                       start_cmd=self.smart_start_services,
                                       stop_cmd=self.stop_celery)
        self.card_celery.pack(fill='x', pady=4)

        # ── Launch Controls ──────────────────────────────────────────────
        launch_card = Card(page, title="Launch Services")
        launch_card.pack(fill='x', padx=16, pady=6)

        row1 = tk.Frame(launch_card.body, bg=C["surface"])
        row1.pack(fill='x', pady=4)

        ModernButton(row1, "▶  Start Dev Environment",  command=self.start_dev_services,
                     style="default").pack(side='left', padx=(0, 8))
        ModernButton(row1, "🏭  Start Production Server", command=self.start_production_server,
                     style="default").pack(side='left', padx=(0, 8))

        row2 = tk.Frame(launch_card.body, bg=C["surface"])
        row2.pack(fill='x', pady=4)

        ModernButton(row2, "⛔  STOP ALL SERVICES", command=self.stop_all_services,
                     style="danger").pack(side='left', padx=(0, 8))

        # Headless toggle inline
        chk = tk.Checkbutton(row2, text="Headless (no windows)",
                             variable=self.headless_var,
                             font=FONT_SMALL,
                             bg=C["surface"], fg=C["text_dim"],
                             activebackground=C["surface"],
                             selectcolor=C["bg"],
                             relief='flat', bd=0)
        chk.pack(side='left', padx=12)

        # ── Agent Controls ───────────────────────────────────────────────
        agent_card = Card(page, title="Agent Management")
        agent_card.pack(fill='x', padx=16, pady=6)

        row3 = tk.Frame(agent_card.body, bg=C["surface"])
        row3.pack(fill='x', pady=4)
        ModernButton(row3, "🔨  Build Agent MSI", command=self.build_agent_msi,
                     style="ghost").pack(side='left', padx=(0, 8))
        ModernButton(row3, "✖  Stop Agent Service", command=self.stop_agent_service,
                     style="danger").pack(side='left')

    # ─── Configuration Page ──────────────────────────────────────────────

    def _build_config_page(self):
        page = self._make_page("config")

        hdr = tk.Frame(page, bg=C["bg"])
        hdr.pack(fill='x', padx=16, pady=(16, 4))
        tk.Label(hdr, text="Configuration", font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(side='left')
        ModernButton(hdr, "💾  Save Changes", command=self.save_config,
                     style="success").pack(side='right')

        # Scrollable canvas
        outer = tk.Frame(page, bg=C["bg"])
        outer.pack(fill='both', expand=True, padx=16, pady=6)

        canvas = tk.Canvas(outer, bg=C["bg"], bd=0, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self._cfg_frame = tk.Frame(canvas, bg=C["surface"])

        self._cfg_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=self._cfg_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Bind mouse-wheel
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.load_env()
        self._populate_config_fields()

    def _populate_config_fields(self):
        parent = self._cfg_frame

        fields = [
            ("General",  [
                ("DEBUG",              "Debug Mode", "True/False"),
                ("ALLOWED_HOSTS",      "Allowed Hosts", "comma separated"),
                ("CSRF_TRUSTED_ORIGINS","CSRF Trusted Origins", "comma separated"),
                ("SECURE_SSL_REDIRECT","Force HTTPS", "True/False"),
            ]),
            ("Security", [
                ("SECRET_KEY",      "Secret Key", "do not share"),
                ("ENCRYPTION_KEY",  "Encryption Key", "⚠ Do Not Change!"),
            ]),
            ("Services", [
                ("REDIS_URL",             "Redis URL", "e.g. redis://localhost:6379"),
                ("DATABASE_URL",          "Database URL", "leave blank for SQLite"),
                ("VIRUSTOTAL_API_KEY",    "VirusTotal API Key", ""),
                ("CLAMAV_ENABLED",        "Enable ClamAV", "True/False"),
                ("AGENT_UPDATE_INTERVAL", "Agent Update Interval (s)", "seconds"),
            ]),
        ]

        row = 0
        for group_title, group_fields in fields:
            # Group header
            grp = tk.Label(parent, text=group_title.upper(),
                           font=("Segoe UI", 8, "bold"),
                           bg=C["surface"], fg=C["accent"], anchor='w')
            grp.grid(row=row, column=0, columnspan=3, sticky='w', padx=12, pady=(14, 4))
            row += 1

            for key, label, hint in group_fields:
                tk.Label(parent, text=label, font=FONT_BODY,
                         bg=C["surface"], fg=C["text"], anchor='w',
                         width=26).grid(row=row, column=0, sticky='w', padx=12, pady=5)

                val = self.env_vars.get(key, "")
                show = "*" if key in ("SECRET_KEY", "ENCRYPTION_KEY") else ""
                ent = tk.Entry(parent, font=FONT_MONO,
                               bg=C["surface2"], fg=C["text"],
                               insertbackground=C["text"],
                               relief='flat', bd=4,
                               show=show, width=44)
                ent.insert(0, val)
                ent.grid(row=row, column=1, sticky='ew', padx=8, pady=5)
                self.entries[key] = ent

                if hint:
                    tk.Label(parent, text=hint, font=FONT_SMALL,
                             bg=C["surface"], fg=C["text_dim"],
                             anchor='w').grid(row=row, column=2, sticky='w', padx=4)
                row += 1

            # Separator
            sep = tk.Frame(parent, bg=C["border"], height=1)
            sep.grid(row=row, column=0, columnspan=3, sticky='ew', padx=10, pady=4)
            row += 1

        parent.columnconfigure(1, weight=1)

        note = tk.Label(parent,
            text="ℹ  Token lifetimes are hardcoded in settings.py and cannot be changed here.",
            font=FONT_SMALL, bg=C["surface"], fg=C["warning"], anchor='w', wraplength=500)
        note.grid(row=row, column=0, columnspan=3, sticky='w', padx=12, pady=10)

    # ─── Backup & Restore ────────────────────────────────────────────────

    def _build_backup_page(self):
        page = self._make_page("backup")

        hdr = tk.Frame(page, bg=C["bg"])
        hdr.pack(fill='x', padx=16, pady=(16, 4))
        tk.Label(hdr, text="Backup & Restore", font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(side='left')

        # Action buttons
        act_card = Card(page, title="Actions")
        act_card.pack(fill='x', padx=16, pady=6)
        row = tk.Frame(act_card.body, bg=C["surface"])
        row.pack(fill='x')
        ModernButton(row, "📦  Create Full Backup", command=self.create_backup,
                     style="default").pack(side='left', padx=(0, 8))
        ModernButton(row, "🔄  Refresh List", command=self.refresh_backup_list,
                     style="ghost").pack(side='left')

        # List
        list_card = Card(page, title="Available Backups")
        list_card.pack(fill='both', expand=True, padx=16, pady=6)

        list_frame = tk.Frame(list_card.body, bg=C["surface"])
        list_frame.pack(fill='both', expand=True)

        self.backup_listbox = tk.Listbox(
            list_frame, font=FONT_MONO,
            bg=C["surface2"], fg=C["text"],
            selectbackground=C["accent"], selectforeground="white",
            relief='flat', bd=0, activestyle='none')
        lb_sb = tk.Scrollbar(list_frame, command=self.backup_listbox.yview)
        lb_sb.pack(side='right', fill='y')
        self.backup_listbox.config(yscrollcommand=lb_sb.set)
        self.backup_listbox.pack(fill='both', expand=True)

        ModernButton(list_card.body, "⏪  Restore Selected", command=self.restore_backup,
                     style="warning").pack(pady=8)

        self.refresh_backup_list()

    # ─── Maintenance ─────────────────────────────────────────────────────

    def _build_maintenance_page(self):
        page = self._make_page("maintenance")

        hdr = tk.Frame(page, bg=C["bg"])
        hdr.pack(fill='x', padx=16, pady=(16, 4))
        tk.Label(hdr, text="Maintenance", font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(side='left')

        # Diagnostics
        diag = Card(page, title="Diagnostics & Verification")
        diag.pack(fill='x', padx=16, pady=6)
        tk.Label(diag.body, text="Runs full API, Security, Collector, and Updater test suites.",
                 font=FONT_SMALL, bg=C["surface"], fg=C["text_dim"]).pack(anchor='w', pady=(0, 6))
        ModernButton(diag.body, "🧪  Run All System Tests", command=self.run_tests,
                     style="default").pack(anchor='w')

        # Safe Cleanup
        clean = Card(page, title="System Cleanup")
        clean.pack(fill='x', padx=16, pady=6)
        tk.Label(clean.body,
                 text="Removes logs, temp files, __pycache__, and build artefacts.",
                 font=FONT_SMALL, bg=C["surface"], fg=C["text_dim"]).pack(anchor='w', pady=(0, 6))
        ModernButton(clean.body, "🧹  Safe System Clean", command=self.safe_clean,
                     style="ghost").pack(anchor='w')

        # Danger zone
        danger = Card(page, title="⚠  Danger Zone")
        danger.pack(fill='x', padx=16, pady=6)

        warn_frame = tk.Frame(danger.body, bg="#2a1010",
                              highlightbackground=C["danger"], highlightthickness=1)
        warn_frame.pack(fill='x', pady=4)
        tk.Label(warn_frame,
                 text="FULL SYSTEM RESET — Wipes database, .env, media files, RSA keys and venv.\n"
                      "A backup will be taken automatically before wiping.",
                 font=FONT_SMALL, bg="#2a1010", fg="#fca5a5",
                 justify='left', padx=10, pady=8).pack(anchor='w')
        ModernButton(warn_frame, "💥  FULL SYSTEM RESET", command=self.full_reset,
                     style="danger").pack(anchor='w', padx=10, pady=(0, 8))

    # ─── Setup Page ──────────────────────────────────────────────────────

    def _build_setup_page(self):
        page = self._make_page("setup")

        hdr = tk.Frame(page, bg=C["bg"])
        hdr.pack(fill='x', padx=16, pady=(16, 4))
        tk.Label(hdr, text="System Setup", font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(side='left')

        # Status checklist
        status_card = Card(page, title="Setup Checklist")
        status_card.pack(fill='x', padx=16, pady=6)

        self.status_labels = {}
        setup_items = [
            ("Python ≥ 3.11",    self.check_python_version),
            ("Virtual Env",      lambda: os.path.exists(os.path.join(PROJECT_ROOT, "venv"))),
            ("Environment (.env)", lambda: os.path.exists(ENV_FILE)),
            ("Database (SQLite)", lambda: os.path.exists(os.path.join(PROJECT_ROOT, "db.sqlite3"))),
            ("RSA Keys (/keys)", lambda: os.path.exists(os.path.join(PROJECT_ROOT, "keys"))),
            ("Django Package",   lambda: os.path.exists(os.path.join(PROJECT_ROOT, "venv", "Lib", "site-packages", "django"))),
            ("Redis Connection", self.check_redis),
        ]

        grid = tk.Frame(status_card.body, bg=C["surface"])
        grid.pack(fill='x')

        for i, (name, fn) in enumerate(setup_items):
            col = i % 2
            ro  = i // 2
            cell = tk.Frame(grid, bg=C["surface2"],
                            highlightbackground=C["border"], highlightthickness=1)
            cell.grid(row=ro, column=col, padx=5, pady=5, sticky='ew')

            dot = StatusDot(cell, size=12, bg=C["surface2"])
            dot.grid(row=0, column=0, padx=(10, 6), pady=10)

            tk.Label(cell, text=name, font=FONT_BODY,
                     bg=C["surface2"], fg=C["text"]).grid(row=0, column=1, sticky='w', pady=10)

            status_lbl = tk.Label(cell, text="…", font=FONT_SMALL,
                                  bg=C["surface2"], fg=C["text_dim"])
            status_lbl.grid(row=1, column=1, sticky='w', pady=(0, 6))

            self.status_labels[name] = (status_lbl, fn, dot)

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        ModernButton(status_card.body, "🔄  Refresh Status",
                     command=self.update_setup_status,
                     style="ghost").pack(anchor='w', pady=(6, 0))

        # Step buttons
        steps_card = Card(page, title="Setup Steps")
        steps_card.pack(fill='x', padx=16, pady=6)

        steps = [
            ("0. Create venv",       self.setup_venv,         "ghost"),
            ("1. Init Env & Folders", self.setup_env,          "ghost"),
            ("2. Install Packages",   self.setup_requirements, "ghost"),
            ("3. Run Migrations",     self.setup_migrations,   "ghost"),
            ("4. Generate RSA Keys",  self.setup_keys,         "ghost"),
            ("5. Collect Static",     self.setup_static,       "ghost"),
            ("6. Create Superuser",   self.setup_superuser,    "default"),
            ("Start Redis",           self.start_redis,        "success"),
        ]

        row1 = tk.Frame(steps_card.body, bg=C["surface"])
        row1.pack(fill='x', pady=2)
        row2 = tk.Frame(steps_card.body, bg=C["surface"])
        row2.pack(fill='x', pady=2)

        for idx, (label, cmd, sty) in enumerate(steps):
            parent = row1 if idx < 4 else row2
            ModernButton(parent, label, command=cmd, style=sty).pack(side='left', padx=4, pady=4)

        # Full auto setup
        sep = tk.Frame(steps_card.body, bg=C["border"], height=1)
        sep.pack(fill='x', pady=10)

        ModernButton(steps_card.body, "🚀  Run FULL AUTOMATED SETUP",
                     command=self.run_full_setup,
                     style="accent" if False else "default").pack(pady=4)


        # Hidden Dependency Check Button (toggled by update_setup_status)
        self.dep_check_btn = ModernButton(steps_card.body, "🔍  Check venv Dependencies",
                                          command=self.check_venv_dependencies,
                                          style="ghost")
        # Position it after the step rows
        self.dep_check_btn.pack(anchor='w', padx=4, pady=(10, 0))
        self.dep_check_btn.pack_forget() # Hide initially

        self.update_setup_status()


    # ─────────────────────────────────────────────────────────────────────
    #  Business Logic  (unchanged from original)
    # ─────────────────────────────────────────────────────────────────────

    # ── Config ────────────────────────────────────────────────────────────

    def load_env(self):
        self.env_vars = {}
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
        for key, entry in self.entries.items():
            val = entry.get().strip()
            if not val and key == "AGENT_UPDATE_INTERVAL":
                continue
            self.env_vars[key] = val

        try:
            with open(ENV_FILE, 'r') as f:
                lines = f.readlines()
            new_lines, processed = [], set()
            for line in lines:
                if line.strip().startswith('#') or not line.strip():
                    new_lines.append(line)
                    continue
                if '=' in line:
                    key = line.split('=')[0].strip()
                    if key in self.env_vars:
                        new_lines.append(f"{key}={self.env_vars[key]}\n")
                        processed.add(key)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            for key, val in self.env_vars.items():
                if key not in processed:
                    new_lines.append(f"\n{key}={val}\n")
            with open(ENV_FILE, 'w') as f:
                f.writelines(new_lines)
            self.log("Configuration saved to .env")
            messagebox.showinfo("Saved", "Configuration saved. Restart services to apply changes.")
        except Exception as e:
            self.log(f"Error saving config: {e}")
            messagebox.showerror("Error", f"Failed to save config: {e}")

    # ── Process management ────────────────────────────────────────────────

    def run_command(self, cmd_str, title="Running Command", force_window=False, is_service=True):
        if not force_window and self.headless_var.get():
            self.log(f"Launching background: {title}…")
            try:
                # Redirect output to log files instead of DEVNULL for better debugging
                log_dir = os.path.join(PROJECT_ROOT, "logs")
                os.makedirs(log_dir, exist_ok=True)
                safe_title = title.lower().replace(" ", "_").replace("(", "").replace(")", "")
                out_path = os.path.join(log_dir, f"{safe_title}_out.log")
                err_path = os.path.join(log_dir, f"{safe_title}_err.log")

                out_file = open(out_path, "a")
                err_file = open(err_path, "a")
                out_file.write(f"\n--- Starting {title} at {datetime.datetime.now()} ---\n")
                err_file.write(f"\n--- Starting {title} at {datetime.datetime.now()} ---\n")

                proc = subprocess.Popen(
                    cmd_str, shell=True, cwd=PROJECT_ROOT,
                    creationflags=0x08000000,
                    stdout=out_file, stderr=err_file)

                if is_service:
                    self.active_processes[title] = proc

                self.log(f"Started: {title} (PID {proc.pid})")
                return proc
            except Exception as e:
                self.log(f"Error starting {title}: {e}")
                messagebox.showerror("Error", f"Failed to start: {e}")
                return None
        else:
            self.log(f"Launching window: {title}…")
            try:
                # For non-headless, we use start cmd which handles its own window
                subprocess.Popen(['cmd', '/c', 'start', title, 'cmd', '/k', cmd_str],
                                  shell=False, cwd=PROJECT_ROOT)
            except Exception as e:
                self.log(f"Error starting {title}: {e}")
                messagebox.showerror("Error", f"Failed to start command: {e}")
                return None

    def start_redis(self):
        self.log("Starting Redis…")
        self.run_command("redis-server", "Redis Server")

    def stop_redis(self):
        if messagebox.askyesno("Confirm", "Kill all redis-server processes?"):
            try:
                # 1. Try clean shutdown via redis-cli if possible
                subprocess.run(["redis-cli", "shutdown"], capture_output=True, timeout=2)
                # 2. Force kill as fallback
                subprocess.run(["taskkill", "/F", "/IM", "redis-server.exe"], capture_output=True)
                self.log("Stopped Redis.")
            except Exception as e:
                self.log(f"Error stopping Redis: {e}")

    def stop_web_server(self):
        self.log("Stopping Web Server (Deep Kill)…")
        # 1. Kill tracked headless processes
        for name in ["Django Server", "Production Web Server"]:
            if name in self.active_processes:
                proc = self.active_processes[name]
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                    self.log(f"Terminated tracked process: {name}")
                except Exception as e:
                    self.log(f"Error killing {name}: {e}")
        
        # 2. Deep kill via PowerShell (targets python.exe processes by command line content)
        # This catches waitress, django runserver, etc. even if untracked or mislabeled
        ps_cmd = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -like '*waitress*' -or $_.CommandLine -like '*manage.py runserver*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        try:
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
        except:
            pass

        # 3. Kill known window titles (fallback for non-headless)
        try:
            subprocess.run(["taskkill", "/FI", "WINDOWTITLE eq Kinetix - Django Server*", "/T", "/F"], capture_output=True)
            subprocess.run(["taskkill", "/FI", "WINDOWTITLE eq Kinetix - Production Web Server*", "/T", "/F"], capture_output=True)
            subprocess.run(["taskkill", "/IM", "waitress-serve.exe", "/F"], capture_output=True)
        except:
            pass
        self.log("Web server stop request processed.")

    def stop_celery(self):
        self.log("Stopping Celery Workers (Deep Kill)…")
        # 1. Kill tracked headless processes
        for name in ["Celery Worker", "Celery Beat"]:
            if name in self.active_processes:
                proc = self.active_processes[name]
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                    self.log(f"Terminated tracked process: {name}")
                except:
                    pass

        # 2. Deep kill via PowerShell
        ps_cmd = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -like '*celery*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        try:
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
        except:
            pass

        # 3. Kill known window titles (fallback for non-headless)
        try:
            subprocess.run(["taskkill", "/FI", "WINDOWTITLE eq Kinetix - Celery Worker*", "/T", "/F"], capture_output=True)
            subprocess.run(["taskkill", "/FI", "WINDOWTITLE eq Kinetix - Celery Beat*", "/T", "/F"], capture_output=True)
            subprocess.run(["taskkill", "/IM", "celery.exe", "/F"], capture_output=True)
        except:
            pass
        self.log("Celery stop request processed.")

    def start_dev_services(self):
        self.last_env_mode = "dev"
        self.log("Starting Development Services…")
        self.start_redis()
        if self.headless_var.get():
            venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
            venv_celery = os.path.join(PROJECT_ROOT, "venv", "Scripts", "celery.exe")
            py  = f'"{venv_python}"' if os.path.exists(venv_python) else "python"
            cel = f'"{venv_celery}"' if os.path.exists(venv_celery) else "celery"
            self.run_command(f"{py} manage.py runserver", "Django Server")
            self.run_command(f"{cel} -A command_center worker -l info --pool=solo", "Celery Worker")
            self.run_command(f"{cel} -A command_center beat -l info", "Celery Beat")
            self.log("Dev services started in background.")
        else:
            self.run_command(r"server-manager\run_dev.bat", "Kinetix Dev Environment", force_window=True)

    def start_production_server(self):
        self.last_env_mode = "prod"
        self.log("Starting Production Server…")
        if self.headless_var.get():
            # Run the production sequence in a background thread to avoid hanging the UI
            threading.Thread(target=self._start_prod_headless_thread, daemon=True).start()
        else:
            self.start_redis()
            self.run_command(r"server-manager\production_server.bat", "Kinetix Production Server", force_window=True)

    def _start_prod_headless_thread(self):
        """Sequential startup for production in headless mode."""
        try:
            # 1. Redis
            if not self.status_data["redis"]:
                self.start_redis()
                # Wait for Redis up to 5s
                for _ in range(10):
                    time.sleep(0.5)
                    if self.check_redis(): break

            venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
            py = f'"{venv_python}"' if os.path.exists(venv_python) else "python"

            # 2. Migrations (Block until done)
            self.log("Running migrations…")
            proc = self.run_command(f"{py} manage.py migrate --noinput", "Migrations", is_service=False)
            if proc:
                while proc.poll() is None: time.sleep(0.5)
                if proc.returncode != 0:
                    self.log(f"Critical Error: Migrations failed with code {proc.returncode}")
                    return

            # 3. Collect Static (Block until done)
            self.log("Collecting static files…")
            proc = self.run_command(f"{py} manage.py collectstatic --noinput", "CollectStatic", is_service=False)
            if proc:
                while proc.poll() is None: time.sleep(0.5)

            # 4. Web Server
            self.run_command(f"{py} -m waitress --listen=0.0.0.0:8000 command_center.wsgi:application", "Production Web Server")

            # 5. Celery Workers
            venv_celery = os.path.join(PROJECT_ROOT, "venv", "Scripts", "celery.exe")
            cel = f'"{venv_celery}"' if os.path.exists(venv_celery) else "celery"
            self.run_command(f"{cel} -A command_center worker -l info --pool=solo", "Celery Worker")
            self.run_command(f"{cel} -A command_center beat -l info", "Celery Beat")

            self.log("Production services started in background.")

        except Exception as e:
            self.log(f"Error in production startup thread: {e}")

    def smart_start_services(self):
        """Restarts services using the last used mode (dev or prod)"""
        if self.last_env_mode == "prod":
            self.start_production_server()
        else:
            self.start_dev_services()

    def build_agent_msi(self):
        # Create a build progress dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Building Agent MSI")
        dialog.geometry("480x260")
        dialog.configure(bg=C["surface"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center on screen
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width()  // 2) - 240
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 130
        dialog.geometry(f"+{x}+{y}")

        # Title/Icon
        tk.Label(dialog, text="🛠  Agent MSI Builder", font=FONT_HEAD,
                 bg=C["surface"], fg=C["text"], pady=15).pack()

        tk.Label(dialog, text="Compiling agent binaries and packaging into an installer.\nThis may take several minutes depending on your hardware.",
                 font=FONT_SMALL, bg=C["surface"], fg=C["text_dim"], justify='center').pack(padx=20)

        # Progress bar
        pframe = tk.Frame(dialog, bg=C["surface"], pady=20)
        pframe.pack(fill='x', padx=40)
        progress = ttk.Progressbar(pframe, mode='indeterminate', length=350)
        progress.pack(fill='x')
        progress.start(15)

        status_lbl = tk.Label(dialog, text="Build in progress…", font=FONT_SMALL,
                              bg=C["surface"], fg=C["accent"])
        status_lbl.pack()

        # Control area (buttons appear when done)
        btn_frame = tk.Frame(dialog, bg=C["surface"])
        btn_frame.pack(side='bottom', fill='x', padx=20, pady=20)

        def open_drops():
            path = os.path.join(PROJECT_ROOT, "media", "agent_drops")
            if not os.path.exists(path): os.makedirs(path, exist_ok=True)
            os.startfile(path)

        def run_build():
            try:
                self.log("Initiating Agent MSI Build sequence…")
                # We force direct Popen here to ensure we can track the process regardless of Headless toggle.
                # Build output is redirected to logs for cleaner tracking in the GUI.
                log_dir = os.path.join(PROJECT_ROOT, "logs")
                os.makedirs(log_dir, exist_ok=True)
                out_path = os.path.join(log_dir, "agent_build_out.log")
                err_path = os.path.join(log_dir, "agent_build_err.log")
                
                with open(out_path, "a") as out_f, open(err_path, "a") as err_f:
                    out_f.write(f"\n--- Build started at {datetime.datetime.now()} ---\n")
                    proc = subprocess.Popen(
                        [r"server-manager\build_agent_msi.bat"],
                        shell=True, cwd=PROJECT_ROOT,
                        creationflags=0x08000000, # Always hide build window to track it reliably
                        stdout=out_f, stderr=err_f
                    )

                    while proc.poll() is None:
                        time.sleep(0.5)

                    def update_ui():
                        try:
                            if not dialog.winfo_exists(): return
                            if proc.returncode == 0:
                                status_lbl.config(text="✓ Build Successful!", fg=C["success"])
                                self.log("Agent MSI build completed successfully.")
                                # SUCCESS: Stop and Close (Hide) the bar
                                progress.stop()
                                progress.pack_forget()
                                ModernButton(btn_frame, "📂  Open Drops Folder", command=open_drops,
                                             style="success").pack(side='left', padx=4)
                            else:
                                status_lbl.config(text=f"✗ Build Failed (Code {proc.returncode})", fg=C["danger"])
                                self.log(f"Agent MSI build failed with exit code {proc.returncode}. Check logs/agent_build_out.log")
                                # FAILURE: Stop it but DO NOT close/hide it
                                progress.stop()
                                
                                def view_log():
                                    if os.path.exists(out_path):
                                        os.startfile(out_path)
                                        
                                ModernButton(btn_frame, "📄  View Build Log", command=view_log,
                                             style="danger").pack(side='left', padx=4)
                        except Exception: pass
                    self.root.after(0, update_ui)
            except Exception as e:
                self.log(f"Build error: {e}")
                def show_error():
                    try:
                        if dialog.winfo_exists():
                            status_lbl.config(text=f"✗ Error: {str(e)[:40]}...", fg=C["danger"])
                            progress.stop()
                    except Exception: pass
                self.root.after(0, show_error)
            finally:
                def safe_cleanup():
                    try:
                        if dialog.winfo_exists():
                            # Ensure Close button is always available at the end
                            has_close = any(isinstance(w, ModernButton) and w.cget("text") == "Close" 
                                          for w in btn_frame.winfo_children())
                            if not has_close:
                                ModernButton(btn_frame, "Close", command=dialog.destroy, style="ghost").pack(side='right', padx=4)
                    except Exception:
                        pass
                self.root.after(100, safe_cleanup)

        threading.Thread(target=run_build, daemon=True).start()

    def stop_agent_service(self):
        self.run_command(r"server-manager\stop_agent.bat", "Stop Kinetix Agent")

    def stop_all_services(self, confirm=True):
        if confirm:
            if not messagebox.askyesno("Confirm Stop", "Stop ALL running services?"):
                return
        self.log("Stopping all services…")
        
        # 1. Specific group stops (handles both tracked and untracked)
        self.stop_web_server()
        self.stop_celery()
        
        # 2. Kill any other remaining tracked processes (e.g. Redis if explicitly tracked)
        for name, proc in list(self.active_processes.items()):
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True, check=False)
                self.log(f"Killed: {name} (PID {proc.pid})")
            except Exception as e:
                self.log(f"Failed to kill {name}: {e}")
        self.active_processes.clear()

        # 3. Run the generic stop batch as a final safety measure
        self.run_command(r"server-manager\stop_server.bat", "Final Service Cleanup", is_service=False)

    def on_closing(self):
        self.monitor_running = False
        if self.active_processes:
            if messagebox.askyesno("Confirm Exit", "Services are running. Stop them and exit?"):
                self.stop_all_services(confirm=False)
                self.root.destroy()
        else:
            self.root.destroy()

    # ── Setup ─────────────────────────────────────────────────────────────

    def update_setup_status(self):
        for name, (lbl, fn, dot) in self.status_labels.items():
            ok = fn()
            dot.set_state(ok)
            if ok:
                lbl.config(text="✓ Ready", fg=C["success"])
            else:
                lbl.config(text="✗ Missing", fg=C["danger"])

        # Toggle Dependency Check Button visibility
        venv_path = os.path.join(PROJECT_ROOT, "venv")
        if os.path.exists(venv_path):
            if not self.dep_check_btn.winfo_viewable():
                self.dep_check_btn.pack(anchor='w', padx=4, pady=(10, 0))
        else:
            self.dep_check_btn.pack_forget()

    def check_venv_dependencies(self):
        self.log("Checking venv dependencies…")
        venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
        if not os.path.exists(venv_python):
            messagebox.showerror("Error", "Virtual environment not found.")
            return

        requirements_file = os.path.join(PROJECT_ROOT, "requirements.txt")
        if not os.path.exists(requirements_file):
            messagebox.showerror("Error", "requirements.txt not found.")
            return

        # 1. Read requirements
        reqs = []
        try:
            with open(requirements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    # Simple parsing: extract name before == or >=
                    name = line.split('==')[0].split('>=')[0].split(';')[0].split('#')[0].strip()
                    if name:
                        reqs.append(name.lower())
        except Exception as e:
            self.log(f"Error reading requirements.txt: {e}")
            messagebox.showerror("Error", f"Failed to read requirements.txt: {e}")
            return

        # 2. Get installed packages from venv
        try:
            self.log("Running pip list…")
            res = subprocess.run([venv_python, "-m", "pip", "list", "--format=json"],
                                 capture_output=True, text=True, check=True)
            installed_data = json.loads(res.stdout)
            installed = {item['name'].lower() for item in installed_data}
        except Exception as e:
            self.log(f"Dependency check failed: {e}")
            messagebox.showerror("Error", f"Failed to get installed packages from venv:\n{e}")
            return

        # 3. Compare
        missing = [r for r in reqs if r not in installed]

        if not missing:
            self.log("All dependencies are installed.")
            messagebox.showinfo("Dependencies OK",
                                "All dependencies from requirements.txt are installed in the venv.")
        else:
            msg = f"Found {len(missing)} missing packages:\n\n" + "\n".join(missing)
            self.log(f"Missing dependencies: {', '.join(missing)}")

            # Show in a scrollable dialog if there are many
            if len(missing) > 10:
                top = tk.Toplevel(self.root)
                top.title("Missing Dependencies")
                top.geometry("450x450")
                top.configure(bg=C["surface"])
                top.transient(self.root)

                tk.Label(top, text="❌ Missing Dependencies", font=FONT_HEAD,
                         bg=C["surface"], fg=C["danger"], pady=10).pack()

                txt = scrolledtext.ScrolledText(top, wrap='word', bg=C["log_bg"],
                                                fg=C["log_text"], font=FONT_MONO,
                                                padx=10, pady=10)
                txt.pack(fill='both', expand=True, padx=15, pady=5)
                txt.insert('1.0', msg)
                txt.config(state='disabled')

                ModernButton(top, "Close", command=top.destroy,
                             style="ghost").pack(pady=10)
            else:
                messagebox.showwarning("Missing Dependencies", msg)

    def setup_env(self):
        self.log("Initialising environment…")
        try:
            for d in ["logs", "media", "media/updates", "staticfiles", "keys", "backups"]:
                path = os.path.join(PROJECT_ROOT, d)
                if not os.path.exists(path):
                    os.makedirs(path)
                    self.log(f"Created: {d}")
            from ensure_keys import ensure_keys
            ensure_keys()
            self.log("Environment verified.")
            self.update_setup_status()
            messagebox.showinfo("Done", "Directories created and .env initialised.")
        except Exception as e:
            self.log(f"Setup Env failed: {e}")
            messagebox.showerror("Error", f"Failed: {e}")

    def setup_venv(self):
        self.run_command("python -m venv venv", "Creating Virtual Environment")

    def setup_requirements(self):
        venv_pip = os.path.join(PROJECT_ROOT, "venv", "Scripts", "pip.exe")
        if os.path.exists(venv_pip):
            self.run_command(f'"{venv_pip}" install -r requirements.txt', "Installing Dependencies (Venv)")
        else:
            self.run_command("pip install -r requirements.txt", "Installing Dependencies (System)")

    def setup_migrations(self):
        venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
        py = f'"{venv_python}"' if os.path.exists(venv_python) else "python"
        self.run_command(f"{py} manage.py migrate", "Running Migrations")

    def setup_keys(self):
        venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
        py = f'"{venv_python}"' if os.path.exists(venv_python) else "python"
        self.run_command(f"{py} manage.py generate_keypair", "Generating RSA Keys")

    def setup_static(self):
        venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
        py = f'"{venv_python}"' if os.path.exists(venv_python) else "python"
        self.run_command(f"{py} manage.py collectstatic --noinput", "Collecting Static Files")

    def setup_superuser(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Admin Superuser")
        dialog.geometry("400x320")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=C["surface"])

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width()  // 2) - 200
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 160
        dialog.geometry(f"+{x}+{y}")

        # Header
        hdr = tk.Frame(dialog, bg=C["accent"])
        hdr.pack(fill='x')
        tk.Label(hdr, text="  👤  Create Django Superuser", font=FONT_HEAD,
                 bg=C["accent"], fg="white", pady=10).pack(side='left')

        form = tk.Frame(dialog, bg=C["surface"])
        form.pack(padx=20, pady=16, fill='x')
        form.columnconfigure(1, weight=1)

        def _field(r, label, default="", show=""):
            tk.Label(form, text=label, font=FONT_BODY,
                     bg=C["surface"], fg=C["text_dim"], anchor='w').grid(
                         row=r, column=0, sticky='w', pady=6)
            ent = tk.Entry(form, font=FONT_BODY,
                           bg=C["surface2"], fg=C["text"],
                           insertbackground=C["text"],
                           relief='flat', bd=4, show=show)
            ent.insert(0, default)
            ent.grid(row=r, column=1, sticky='ew', padx=(10, 0), pady=6)
            return ent

        user_ent  = _field(0, "Username",  "admin")
        email_ent = _field(1, "Email",     "admin@example.com")
        pass_ent  = _field(2, "Password",  show="*")

        pass_ent.focus_set()

        def commit():
            username = user_ent.get().strip()
            email    = email_ent.get().strip()
            password = pass_ent.get().strip()
            if not username or not password:
                messagebox.showerror("Error", "Username and Password are required.", parent=dialog)
                return
            self.run_superuser_command(username, email, password, dialog=dialog)

        ModernButton(dialog, "CREATE ADMIN USER", command=commit,
                     style="default").pack(pady=12, padx=20, fill='x')

    def run_superuser_command(self, username, email, password, dialog=None):
        self.log(f"Validating superuser: {username}…")
        venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
        python_exe  = venv_python if os.path.exists(venv_python) else "python"

        # 1. Username existence check
        try:
            check_script = (
                f"from django.contrib.auth import get_user_model; "
                f"print('EXISTS' if get_user_model().objects.filter(username='{username}').exists() else 'OK')"
            )
            res = subprocess.run([python_exe, "manage.py", "shell", "-c", check_script],
                                 capture_output=True, text=True, cwd=PROJECT_ROOT)
            if "EXISTS" in res.stdout:
                self.log(f"Aborted: '{username}' already exists.")
                messagebox.showerror("User Exists",
                    f"The username '{username}' is already taken.\nPlease choose a different username.",
                    parent=dialog)
                return False
        except Exception as e:
            self.log(f"Pre-check warning: {e}")

        # 2. Env vars for --no-input
        env = os.environ.copy()
        env["DJANGO_SUPERUSER_PASSWORD"] = password
        env["DJANGO_SUPERUSER_USERNAME"] = username
        env["DJANGO_SUPERUSER_EMAIL"]    = email

        try:
            self.log(f"Creating superuser '{username}' (non-interactive)…")
            result = subprocess.run(
                [python_exe, "manage.py", "createsuperuser", "--no-input"],
                env=env, capture_output=True, text=True, cwd=PROJECT_ROOT, check=False)

            if result.returncode == 0:
                self.log(f"Superuser '{username}' created successfully.")
                messagebox.showinfo("Success",
                    f"Superuser '{username}' created.\nYou can now log in to the admin panel.",
                    parent=dialog)
                if dialog:
                    dialog.destroy()
                return True
            else:
                error_msg = result.stderr or result.stdout
                self.log(f"Creation failed: {error_msg}")

                if "password" in error_msg.lower():
                    display = error_msg.replace("Error: ", "").strip()
                    if messagebox.askyesno("Password Complexity",
                        f"Password did not meet requirements:\n\n{display}\n\n"
                        "Bypass validation and create anyway?", parent=dialog):
                        self.log("Bypassing validation via shell…")
                        create_script = (
                            "import os; from django.contrib.auth import get_user_model; "
                            "User = get_user_model(); "
                            "User.objects.create_superuser("
                            "os.environ['DJANGO_SUPERUSER_USERNAME'], "
                            "os.environ['DJANGO_SUPERUSER_EMAIL'], "
                            "os.environ['DJANGO_SUPERUSER_PASSWORD'])"
                        )
                        fr = subprocess.run([python_exe, "manage.py", "shell", "-c", create_script],
                                            env=env, capture_output=True, text=True, cwd=PROJECT_ROOT)
                        if fr.returncode == 0:
                            self.log(f"Superuser '{username}' created (bypass).")
                            messagebox.showinfo("Success",
                                f"Superuser '{username}' created (validation bypassed).", parent=dialog)
                            if dialog:
                                dialog.destroy()
                            return True
                        else:
                            err = fr.stderr or fr.stdout
                            self.log(f"Bypass also failed: {err}")
                            messagebox.showerror("Error", f"Creation failed even with bypass:\n\n{err}", parent=dialog)
                    else:
                        self.log("Aborted by user (password requirements).")
                else:
                    messagebox.showerror("Creation Failed",
                        f"Django rejected the creation:\n\n{error_msg}", parent=dialog)
        except Exception as e:
            self.log(f"Exception during superuser creation: {e}")
            messagebox.showerror("Error", f"Unexpected error: {e}", parent=dialog)

        return False

    def run_full_setup(self):
        if not messagebox.askyesno("Confirm", "Run all setup steps in sequence? Continue?"):
            return
        full_cmd = (
            "python -m venv venv && "
            "venv\\Scripts\\python server-manager\\ensure_keys.py && "
            "venv\\Scripts\\pip install -r requirements.txt && "
            "venv\\Scripts\\python manage.py migrate && "
            "venv\\Scripts\\python manage.py generate_keypair && "
            "venv\\Scripts\\python manage.py collectstatic --noinput && "
            "venv\\Scripts\\python manage.py createsuperuser"
        )
        self.run_command(full_cmd, "Full Kinetix Setup", force_window=True)
        try:
            for d in ["logs", "media", "media/updates", "staticfiles", "keys", "backups"]:
                os.makedirs(os.path.join(PROJECT_ROOT, d), exist_ok=True)
        except Exception:
            pass

    # ── Maintenance ────────────────────────────────────────────────────────

    def run_tests(self):
        self.run_command(r"server-manager\run_all_tests.bat", "Running System Tests")

    def safe_clean(self):
        if messagebox.askyesno("Confirm Clean",
                               "Perform safe cleanup? (Removes logs, temp files, __pycache__)"):
            self.perform_cleanup(full_reset=False)

    def full_reset(self):
        confirm = simpledialog.askstring(
            "Confirm FULL RESET",
            "⚠ This will wipe ALL database records, .env, media files, and security keys.\n\n"
            "This action is IRREVERSIBLE.\n\n"
            "Type 'RESET' to confirm:", parent=self.root)
        if confirm == "RESET":
            self.perform_cleanup(full_reset=True)
            self.update_setup_status()
        elif confirm is not None:
            messagebox.showwarning("Cancelled", "Incorrect confirmation text. Reset aborted.")
        else:
            self.log("Reset cancelled.")

    def perform_cleanup(self, full_reset=False):
        self.log(f"Initiating {'FULL RESET' if full_reset else 'Safe Cleanup'}…")

        # 1. Backup first
        timestamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"pre_clean_{timestamp}"
        backup_path = os.path.join(PROJECT_ROOT, "backups", backup_name)
        try:
            os.makedirs(backup_path, exist_ok=True)
            for f in [".env", "db.sqlite3"]:
                src = os.path.join(PROJECT_ROOT, f)
                if os.path.exists(src):
                    shutil.copy2(src, backup_path)
            keys_src = os.path.join(PROJECT_ROOT, "keys")
            if os.path.exists(keys_src):
                shutil.copytree(keys_src, os.path.join(backup_path, "keys"), dirs_exist_ok=True)
            self.log(f"Backup saved: backups/{backup_name}")
        except Exception as e:
            self.log(f"Backup warning: {e}")

        # 2. Stop services
        self.stop_all_services(confirm=False)

        # 3. Deletions
        self.log("Removing files…")
        folders = ["staticfiles", "build", "dist", "agent/agent/build", "agent/agent/dist", "logs"]
        if full_reset:
            # Expanded folder list for true FULL RESET
            folders.extend([
                "keys", "venv", "agent/agent/venv",
                "media/updates", "media/agent_updates", "media/agent_drops/processed"
            ])

        for folder in folders:
            path = os.path.normpath(os.path.join(PROJECT_ROOT, folder))
            if os.path.exists(path):
                self.log(f"Deleting: {folder}")
                # Use a slightly more robust rmtree for venvs which often have locked files
                # if we just killed the processes, but Windows can be slow.
                shutil.rmtree(path, ignore_errors=True)

        for p in glob.glob(os.path.join(PROJECT_ROOT, "**/__pycache__"), recursive=True):
            shutil.rmtree(p, ignore_errors=True)
        for ext in ["*.pyc", "*.pyo", "*.log"]:
            for p in glob.glob(os.path.join(PROJECT_ROOT, "**", ext), recursive=True):
                try:
                    os.remove(p)
                except Exception:
                    pass

        if full_reset:
            self.log("Wiping database and config…")
            
            # Clear Agent-side security keys specifically
            for key_file in ["agent/agent/public_key.pem", "agent/agent/.device_key"]:
                kp = os.path.join(PROJECT_ROOT, key_file)
                if os.path.exists(kp):
                    try:
                        os.remove(kp)
                        self.log(f"Removed agent key: {key_file}")
                    except Exception as e:
                        self.log(f"Error removing {key_file}: {e}")

            db_path = os.path.join(PROJECT_ROOT, "db.sqlite3")
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

            env_file = os.path.join(PROJECT_ROOT, ".env")
            if os.path.exists(env_file):
                try:
                    os.remove(env_file)
                    self.log("Deleted .env configuration file.")
                except Exception as e:
                    self.log(f"Error deleting .env: {e}")

            version_file = os.path.join(PROJECT_ROOT, "agent", "VERSION")
            if os.path.exists(version_file):
                try:
                    with open(version_file, 'w') as f:
                        f.write("1.0.0.0\n")
                except Exception:
                    pass

        # 4. Recreate structure
        recreate = [
            "logs", "keys", "staticfiles", "backups",
            "media/updates", "media/agent_updates", "media/agent_drops/processed"
        ]
        for d in recreate:
            os.makedirs(os.path.join(PROJECT_ROOT, d), exist_ok=True)

        self.log("Cleanup complete.")
        messagebox.showinfo("Done",
            f"{'Full Reset' if full_reset else 'Safe Cleanup'} completed successfully.")
        self.load_env()

    # ── Backup ────────────────────────────────────────────────────────────

    def check_python_version(self):
        return sys.version_info >= (3, 11)

    def check_redis(self):
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1)
            return r.ping()
        except Exception:
            return False

    def get_backup_dir(self):
        d = os.path.join(PROJECT_ROOT, "backups")
        os.makedirs(d, exist_ok=True)
        return d

    def refresh_backup_list(self):
        self.backup_listbox.delete(0, tk.END)
        files = glob.glob(os.path.join(self.get_backup_dir(), "*.zip"))
        files.sort(key=os.path.getmtime, reverse=True)
        for f in files:
            self.backup_listbox.insert(tk.END, os.path.basename(f))

    def create_backup(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"kinetix_backup_{timestamp}.zip"
        filepath  = os.path.join(self.get_backup_dir(), filename)
        self.log(f"Creating backup: {filename}")
        try:
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                for relpath in ["db.sqlite3", ".env"]:
                    src = os.path.join(PROJECT_ROOT, relpath)
                    if os.path.exists(src):
                        zf.write(src, relpath)
                for folder in ["keys", "media"]:
                    src_dir = os.path.join(PROJECT_ROOT, folder)
                    if os.path.exists(src_dir):
                        for root, _, files in os.walk(src_dir):
                            if 'processed' in root:
                                continue
                            for file in files:
                                full = os.path.join(root, file)
                                zf.write(full, os.path.relpath(full, PROJECT_ROOT))
            self.log(f"Backup created: {filename}")
            messagebox.showinfo("Success", f"Backup created:\n{filename}")
            self.refresh_backup_list()
        except Exception as e:
            self.log(f"Backup failed: {e}")
            messagebox.showerror("Error", f"Backup failed: {e}")

    def restore_backup(self):
        sel = self.backup_listbox.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a backup to restore.")
            return
        filename = self.backup_listbox.get(sel[0])
        if not messagebox.askyesno("Confirm Restore",
                f"Overwrite current database and settings with:\n{filename}\n\nContinue?"):
            return
        filepath = os.path.join(self.get_backup_dir(), filename)
        try:
            self.log(f"Restoring: {filename}")
            with zipfile.ZipFile(filepath, 'r') as zf:
                zf.extractall(PROJECT_ROOT)
            self.log("Restore complete.")
            messagebox.showinfo("Success", "System restored. Please restart services.")
            self.load_env()
        except Exception as e:
            self.log(f"Restore failed: {e}")
            messagebox.showerror("Error", f"Restore failed: {e}")


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app  = ServerManagerApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        input("Press Enter to exit…")
