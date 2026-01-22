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
    
    def __init__(self, name="KinetixAgent"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # File Handler
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        log_dir = os.path.join(base_dir, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "agent.log"),
            maxBytes=10*1024*1024,
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

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
