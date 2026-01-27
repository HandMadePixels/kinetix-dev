import logging
import logging.handlers
import os
import sys

try:
    import servicemanager
    import win32evtlogutil
    import win32evtlog
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

class AgentLogger:
    """Handles logging to file and Windows Event Log"""
    
    def __init__(self, name="KinetixAgent", config=None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.name = name
        
        # Formatter
        self.formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Console Handler (always add)
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.console_handler)
        
        if config:
            self.setup_file_handler(config)
        else:
            # Add a placeholder file handler or wait for reconfiguration
            pass

    def setup_file_handler(self, config):
        """Configure or reconfigure the file rotation handler"""
        # Remove existing file handlers if any
        for handler in self.logger.handlers[:]:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                self.logger.removeHandler(handler)

        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        log_dir = os.path.join(base_dir, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Use values from config
        max_bytes = getattr(config, 'max_log_size', 5*1024*1024)
        backup_count = getattr(config, 'max_log_backups', 3)

        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "agent.log"),
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(self.formatter)
        self.logger.addHandler(file_handler)

    def info(self, msg):
        self.logger.info(msg)
        if HAS_WIN32:
            try:
                servicemanager.LogInfoMsg(str(msg))
            except: pass

    def error(self, msg):
        self.logger.error(msg)
        if HAS_WIN32:
            try:
                servicemanager.LogErrorMsg(str(msg))
            except: pass

    def warning(self, msg):
        self.logger.warning(msg)
        if HAS_WIN32:
            try:
                servicemanager.LogWarningMsg(str(msg))
            except: pass

    def security(self, msg):
        """Special log for security events"""
        msg = f"[SECURITY] {msg}"
        self.logger.critical(msg)
        if HAS_WIN32:
            try:
                # Log to periodic security log if possible
                servicemanager.LogErrorMsg(str(msg))
            except: pass

agent_log = AgentLogger()
