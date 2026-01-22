import socket
import sys
import os

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

print("--- Diagnostic Tool ---")
print(f"Directory: {os.getcwd()}")
print(f"Python: {sys.executable}")

# Check Port 8000
if check_port(8000):
    print("[WAIT] Port 8000 is occupied. Something is already running there.")
else:
    print("[OK] Port 8000 is free.")

# Check Redis
if check_port(6379):
    print("[OK] Redis is running on 6379.")
else:
    print("[FAIL] Redis is NOT running on 6379.")

# Check for WSGI file
wsgi_path = os.path.join("command_center", "wsgi.py")
if os.path.exists(wsgi_path):
    print(f"[OK] Found WSGI file at {wsgi_path}")
else:
    print(f"[FAIL] WSGI file NOT found at {wsgi_path}")

print("-----------------------")
