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
- **Server Manager GUI:** A centralized management dashboard to control Redis, Production services, and Agent builds.
    - **Smart Environment Memory:** Remembers if you prefer Dev or Production mode for service restarts.
    - **Hardened MSI Builder:** Tracks build progress reliably, handles window closure events gracefully, and provides direct "View Build Log" access on failure.
- **Interactive Remote Reboot:** Trigger managed restarts with custom messages using a robust `schtasks` bypass to cross Session 0 boundaries.
- **Diagnostic Resilience:** PowerShell fallbacks for hotfix collection when COM interfaces are unavailable.

### 🤖 Automated Maintenance & Updates
- **Silent Execution Policy:** All agent maintenance tasks (restarts, folder permissions, task scheduling) run invisibly without command prompt "flashes."
- **Robust Self-Updates:** 
    - **Detached Installation:** Uses `DETACHED_PROCESS` flags so the MSI installer survives the Agent's service termination during upgrades.
    - **Lock-Release Logic:** Automated 3-second grace periods ensure all file locks on the binary are released before an upgrade begins.
- **Intelligent Update Server:**
    - **Auto-Version Detection:** Server automatically extracts the version and security hash from uploaded MSI filenames (e.g., `kinetix_agent_1.0.0.8.msi`).
    - **Config Sync:** Agents automatically update their local `agent.ini` to reflect the current running version after a successful upgrade.

### 🛡️ Enterprise-Grade Security
- **Persistent Authentication:** Access + Refresh Token flow allowing 7-day authentication without re-registration.
- **Hardened RBAC:** Fine-grained permissions for all remote actions, integrated with Django's native permission system.
- **Secure MIME Validation:** Native support for MSI (`CDFV2`) file validation in the update pipeline.
- **Encrypted Communication:** Full JWT authentication for agents and AES-256 field encryption for sensitive data.

---

## 🏗️ Architecture
- **Backend:** Django 5.x + Django REST Framework + SimpleJWT.
- **Task Queue:** Celery + Redis for asynchronous deployment and scanning.
- **Frontend:** Bootstrap 5 + DataTables.js + Chart.js.
- **Management GUI:** Python Tkinter-based Server Manager.
- **Agent:** Python-based Windows Service (compiled to EXE/MSI) with DETACHED_PROCESS update resilience.

---

## 🛠️ Installation & Setup

1. Python 3.11+
2. Redis server
3. WiX Toolset v3.14 (For MSI creation)

---

## 🤖 Agent Management

The Kinetix Agent runs as a silent Windows Service. It automatically maintains its own version and configuration.

**Manual Commands (from agent directory):**
- `kinetix_agent.exe inventory`: Force immediate inventory upload.
- `kinetix_agent.exe register`: Force manual re-registration.
- `kinetix_agent.exe restart`: Restart the agent service.
- `kinetix_agent.exe set-server <url>`: Update the Command Center address.

**Log Management:**
Log storage is automatically capped (Default: 5MB per file, 3 backups). Limits are configurable via `agent.ini`. Detailed update logs can be found in `C:\Windows\TEMP\kinetix_install_*.log`.

---

## 📁 Project Structure
```text
Kinetix/
├── server-manager/      # Centralized Management GUI, Build Tools, and Launchers
├── agent/               # Windows Agent source, WiX installers, and service logic
├── api/                 # REST API (Agent-to-Server communication)
├── core/                # Core logic, Models (Device, AuditLog), and Security
├── inventory/           # Inventory data models (Snapshot, Service, Apps)
├── updates/             # Software update management and deployment tasks
└── logs/                # Server and Agent log files
```

---

## 🏷️ Version
1.6.0 (April 2026) - *Silent Maintenance & Robust Update Infrastructure*