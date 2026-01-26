# Kinetix: Enterprise Endpoint Management

## Overview
Kinetix is a professional-grade, Django-based endpoint management system designed for secure Windows update delivery, real-time device monitoring, and remote software management. It features a high-performance **pull-based architecture** where remote agents poll the command center for instructions, ensuring compatibility with strict corporate firewalls without compromising security.

---

## 🚀 Key Features

### 💻 Device Management & Insights
- **Advanced Device Table:** Enhanced visibility with **Group**, **Status**, and **Connectivity** indicators.
- **Real-Time Inventory Status:** New **Inventory Status** column tracking refresh cycles (Idle -> Requested -> Processing -> Completed).
- **Edit & Organize:** Remotely edit device hostnames, assign groups, and manage operational status with full RBAC protection (`change_device` permission).
- **Mass Refresh:** Trigger a fleet-wide inventory update with a single click using the **"Refresh All Devices"** feature.
- **Deep Insights:** Detailed modals showing **Last Boot Time**, **System Uptime**, **Logged-in User**, and internal management notes.
- **Automatic Polling:** Dashboard automatically refreshes connectivity and status indicators without manual page reloads.

### 📦 Software Deployment & Update Center
- **Granular RBAC:** Access to Update Center is restricted to authorized personnel. Separate permissions for uploading (`add_update`) and deploying (`can_deploy_updates`).
- **Device Group Deployment:** Deploy software to entire groups with a single click. (Requires groups to have $\ge 1$ device).
- **Deployment Logs:** Detailed per-deployment log viewer showing agent execution status and server-side task results.
- **Real-Time Progress:** Deployment table polls automatically to show success/failure status as agents report back.
- **RSA Signing & Malware Scanning:** Integrated VirusTotal and ClamAV scanning with RSA-4096 (PSS) signature verification.

### ⚙️ Deep Inventory & OS Insights
- **Fleet-Wide Services:** Dedicated **Services Tab** to view and search all Windows services across all managed devices.
- **Update History Tabs:** Separated device history into **Kinetix Deployments** and **Windows Updates (OS KBs)**.
- **OS Update Tracking:** Automatically retrieves and logs the history of installed Windows Update KBs directly from the device.
- **System Metrics:** Reliable collection of **Boot Time** and **System Uptime** using a multi-layered fallback strategy (`psutil`, WMI, `ctypes`).

### 🛠️ Remote Administration (Remote Actions)
- **Asynchronous Execution:** Agent processes commands in background threads to ensure the service remains responsive during long-running tasks.
- **Interactive Remote Reboot:** Trigger managed restarts with custom admin messages. Uses a robust `schtasks` bypass to display GUIs across Session 0 boundaries.
- **Automatic Inventory Sync:** Any action (editing details, changing services, uninstalling apps, reboots) automatically triggers a proactive inventory refresh.
- **Agent Self-Management:** Remotely restart the Kinetix Agent service directly from the dashboard.
- **Command Traceability:** Structured command logging on the agent (`logs/command_history.log`) for full auditability.

### 🛡️ Enterprise-Grade Security
- **Hardened RBAC:** Fine-grained permissions for all remote actions, integrated with Django's standard permission system.
- **Encrypted Communication:** Full JWT authentication for agents and AES-256 field encryption for sensitive configuration.
- **CSRF Protection:** Secure AJAX communication for all dashboard remote actions.

---

## 🏗️ Architecture
- **Backend:** Django 5.x + Django REST Framework.
- **Task Queue:** Celery + Redis for asynchronous deployment and scanning.
- **Frontend:** Bootstrap 5 + DataTables.js + Chart.js.
- **Agent:** Python-based Windows Service (compiled to EXE/MSI) with Tkinter-based interactive UI.
- **Dependencies:** `psutil`, `WMI`, `pywin32`, `python-decouple`.

---

## 🛠️ Installation & Setup

### Quick Start (Windows Development) ⚡
1. **Setup Environment:** Run `quickstart.bat` to automate virtual environment and dependency installation.
2. **Start Services:** Run `run_dev.bat`. This launches the Django server, Celery worker, and Celery beat.
3. **Access Dashboard:** Open `http://localhost:8000` (Default credentials: `admin` / `admin`).

### Production Deployment
1. **Launch:** Use `production_server.bat`. This automatically handles database migrations (`makemigrations` + `migrate`) and starts the Waitress WSGI server.

---

## 🤖 Agent Management

The Kinetix Agent runs as a silent Windows Service.

**Manual Commands (from agent directory):**
- `kinetix_agent.exe inventory`: Force immediate inventory upload.
- `kinetix_agent.exe register`: Force manual re-registration.
- `kinetix_agent.exe restart`: Restart the agent service.
- `kinetix_agent.exe set-server <url>`: Update the Command Center address.

**Build Instructions:**
Run `.\build.bat` in the `agent/agent` directory to sync dependencies and compile the latest executable using `agent.spec`.

---

## 📁 Project Structure
```text
Kinetix/
├── agent/               # Windows Agent source, GUI, and spec files
├── api/                 # REST API (Agent-to-Server communication)
├── core/                # Core logic, Models (Device, AuditLog), and Security
├── inventory/           # Inventory data models (Snapshot, Service, WindowsUpdate)
├── updates/             # Software update management and deployment tasks
└── logs/                # Server and Agent log files
```

---

## 🏷️ Version
1.3.0 (January 2026) - *Enhanced Deployment Visibility & OS Patch Management*