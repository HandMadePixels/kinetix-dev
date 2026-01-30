# Kinetix: Enterprise Endpoint Management

## Overview
Kinetix is a professional-grade, Django-based endpoint management system designed for secure Windows update delivery, real-time device monitoring, and remote software management. It features a high-performance **pull-based architecture** where remote agents poll the command center for instructions, ensuring compatibility with strict corporate firewalls without compromising security.

---

## 🚀 Key Features

### 💻 Device Management & Insights
- **Advanced Device Table:** Enhanced visibility with **Group**, **Status**, and **Connectivity** indicators.
- **Real-Time Inventory Status:** New **Inventory Status** column tracking refresh cycles (Idle -> Requested -> Processing -> Completed).
- **Asynchronous Data Updates:** Tables and status indicators refresh automatically via targeted AJAX polls, eliminating jarring page reloads.
- **Edit & Organize:** Remotely edit device hostnames, assign groups, and manage operational status with full RBAC protection (`change_device` permission).
- **Mass Refresh:** Trigger a fleet-wide inventory update with a single click using the **"Refresh All Devices"** feature.

### 📦 Software Deployment & Update Center
- **Granular RBAC:** Access to Update Center is restricted to authorized personnel. Separate permissions for uploading (`add_update`) and deploying (`can_deploy_updates`).
- **Real-Time Progress:** Deployment table polls automatically to show success/failure status as agents report back in real-time.
- **RSA Signing & Malware Scanning:** Integrated VirusTotal and ClamAV scanning with RSA-4096 (PSS) signature verification.

### 🛠️ Remote Administration & GUI
- **Server Manager GUI:** A new dedicated management tool (`server-manager/start_manager.bat`) to control Redis, the production server, and agent builds from a centralized dashboard.
- **Interactive Remote Reboot:** Trigger managed restarts with custom admin messages. Uses a robust `schtasks` bypass to display GUIs across Session 0 boundaries.
- **Diagnostic Resilience:** Multi-layered fallback strategies for data collection, including PowerShell `Get-HotFix` fallback when COM interfaces are unavailable.

### 🛡️ Enterprise-Grade Security
- **Persistent Authentication:** Upgraded to **Access + Refresh Token** flow. Agents stay authenticated for up to 7 days without re-registration, with automatic token rotation for maximum security.
- **Hardened RBAC:** Fine-grained permissions for all remote actions, integrated with Django's standard permission system.
- **Encrypted Communication:** Full JWT authentication for agents and AES-256 field encryption for sensitive configuration.

---

## 🏗️ Architecture
- **Backend:** Django 5.x + Django REST Framework + SimpleJWT.
- **Task Queue:** Celery + Redis for asynchronous deployment and scanning.
- **Frontend:** Bootstrap 5 + DataTables.js + Chart.js.
- **Management GUI:** Python Tkinter-based Server Manager.
- **Agent:** Python-based Windows Service (compiled to EXE/MSI) with Tkinter-based interactive UI.

---

## 🛠️ Installation & Setup

### Server Manager 🖥️
The easiest way to manage the system is via the new **Server Manager**:
1. Run `server-manager\start_manager.bat`.
2. Use the **Control Panel** to start Redis and the Production Server.
3. Use the **Configuration** tab to edit `.env` settings.

---

## 🤖 Agent Management

The Kinetix Agent runs as a silent Windows Service.

**Manual Commands (from agent directory):**
- `kinetix_agent.exe inventory`: Force immediate inventory upload.
- `kinetix_agent.exe register`: Force manual re-registration.
- `kinetix_agent.exe restart`: Restart the agent service.
- `kinetix_agent.exe set-server <url>`: Update the Command Center address.

**Log Management:**
Log storage is automatically capped (Default: 5MB per file, 3 backups) to protect endpoint disk space. These limits are configurable via `agent.ini`.

---

## 📁 Project Structure
```text
Kinetix/
├── server-manager/      # Centralized Management GUI and launchers
├── agent/               # Windows Agent source, GUI, and spec files
├── api/                 # REST API (Agent-to-Server communication)
├── core/                # Core logic, Models (Device, AuditLog), and Security
├── inventory/           # Inventory data models (Snapshot, Service, WindowsUpdate)
├── updates/             # Software update management and deployment tasks
└── logs/                # Server and Agent log files
```

---

## 🏷️ Version
1.5.0 (January 2026) - *Persistent Auth & Centralized Management*