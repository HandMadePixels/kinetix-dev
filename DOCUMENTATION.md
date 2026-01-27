# 🌐 Kinetix & Agent: Comprehensive Technical Documentation

Welcome to the **Kinetix** ecosystem. This document provides an in-depth technical overview of the system architecture, security implementation, and management workflows.

---

## 🏗️ 1. System Architecture

Kinetix is built on a **Pull-Based Architecture**, designed to work seamlessly within strict corporate networks and behind NAT/Firewalls without requiring inbound port mapping on client devices.

### Components
-   **Kinetix Command Center**: A Django-based central management server (CMS) providing a RESTful API and a modern web dashboard.
-   **Kinetix Endpoint Agent**: A Python-based Windows Service that polls the Command Center for instructions.
-   **Task Engine**: Powered by **Celery** and **Redis**, handling asynchronous malware scanning, update processing, and deployment scheduling.
-   **Database**: SQLite by default (production-ready via `production_server.bat`), with built-in support for PostgreSQL migration.

---

## 🛡️ 2. Security & Integrity Model

Security is baked into every layer of Kinetix, from communication to execution.

### Communication
-   **Persistent JWT Flow**: Kinetix uses a dual-token authentication model (Access + Refresh).
    -   **Access Tokens**: Short-lived (15 min) for all standard API requests.
    -   **Refresh Tokens**: Long-lived (7 days) stored securely in the Windows Credential Manager.
    -   **Automatic Rotation**: Agents automatically renew access tokens upon expiration. Refresh tokens are rotated by the server to prevent replay attacks.
-   **AES-256 (Fernet) Encryption**: Sensitive data such as API keys, service credentials, and internal auth tokens are stored encrypted at rest using the Fernet symmetric encryption standard.

### Software Integrity
-   **RSA-4096 Signing**: All updates uploaded to the Command Center are automatically hashed (SHA-256) and signed using an RSA-4096 private key.
-   **Client-Side Verification**: Before installation, the Agent verifies the update's hash and ensures the RSA signature matches its local `public_key.pem`.
-   **Automatic Malware Defense**: Integrated **VirusTotal** and **ClamAV** scanners automatically inspect every upload. Deployments are restricted until a "Clean" status is achieved.

### Administrative Control
-   **Granular RBAC**: Integration with Django's permission system allows for fine-grained control:
    -   `updates.add_update`: Permission to upload new software.
    -   `updates.can_deploy_updates`: Permission to push software to devices.
    -   `core.can_trigger_reboot`: Permission to restart remote endpoints.
-   **Audit Logging**: Every action—from a user login to a remote shell execution—is logged with severity, timestamp, and metadata in the `AuditLog`.

---

## 🤖 3. The Endpoint Agent

The agent is the silent worker on every managed device.

### Core Capabilities
-   **Windows Service Integration**: Runs as `SYSTEM`, ensuring it starts before user login and remains persistent.
-   **Diagnostic Resilience**: Multi-layered fallback strategies for data collection. If primary COM interfaces fail (e.g., Windows Update Session), the agent automatically falls back to PowerShell-based collection (`Get-HotFix`).
-   **Storage Management**: Logs are managed via a strict **Rotating File Handler**. By default, logs rotate at 5MB with 3 backups, ensuring agent diagnostics never consume excessive disk space. Limits are configurable via `agent.ini`.
-   **Session 0 Isolation Bypass**: Kinetix uses a proprietary mechanism involving `schtasks` and temporary batch wrappers to display interactive UI components (like reboot notifications) from the non-interactive SYSTEM session into the active user's desktop.
-   **Asynchronous Command Execution**: Long-running tasks (uninstalls, large updates) are executed in background threads, allowing the agent to continue sending heartbeats and polling for new commands.
-   **Reliable Metrics**: System uptime and boot times are collected using a multi-layered fallback strategy: `psutil` -> `WMI` -> `ctypes (GetTickCount64)`.

### Local Troubleshooting
-   **Logs**: Located in the `logs/` subdirectory of the agent installation.
    -   `agent.log`: Main operational logs.
    -   `command_history.log`: A JSON-structured record of every command received from the server.
-   **Manual Control**:
    -   `kinetix_agent.exe debug`: Run in the console to see real-time output.
    -   `kinetix_agent.exe inventory`: Trigger a manual sync.

---

## 📦 4. Management Workflows

### Inventory Management
Kinetix maintains a deep inventory of every device:
-   **Installed Applications**: Enumerated from HKLM, HKCU, and WOW6432Node registry hives.
-   **Windows Services**: Real-time status and startup configuration (`Automatic`, `Delayed`, `Manual`, `Disabled`).
-   **OS Patches**: Full history of installed Windows Update KBs.
-   **Inventory Pruning**: To maintain performance, the system automatically prunes old snapshots, keeping only the most recent three per device.

### Software Deployment
-   **Update Center**: A centralized hub for managing MSI and EXE packages.
-   **Group Operations**: Deploy updates to specific `DeviceGroups`. Groups must contain at least one device to be eligible for bulk deployment.
-   **Smart Retries**: Failed deployments can be retried with a single click. Full error logs (stdout/stderr) from the remote installer are captured and viewable in the dashboard.

### Remote Administration
-   **Service Control**: Start, stop, or restart any Windows service remotely.
-   **Registry Management**: Remotely set or delete keys and values across the registry hives.
-   **Managed Reboot**: Prompt users to restart with a branded UI, allowing them to postpone if they are in the middle of critical work.

---

## 📦 4. Administrative GUI (Server Manager)

Kinetix provides a dedicated **Server Manager GUI** for centralized administration of the Command Center environment.

-   **Location**: `server_manager/start_manager.bat`
-   **Capabilities**:
    -   **Service Control**: One-click start/stop for Redis and the Production Web Server.
    -   **Build Automation**: Trigger the MSI builder for updated agents.
    -   **Environment Configuration**: Edit and save `.env` settings (Debug mode, Allowed Hosts, HTTPS Enforcement) directly from the UI.

## ⚙️ 5. Technical Reference

### Asynchronous Dashboard
The Command Center dashboard is optimized for real-time visibility without page reloads:
-   **Targeted Polling**: Specific table cells (Connectivity, Inventory Status, Deployment Progress) are updated via asynchronous AJAX calls.
-   **State Management**: Status indicators transition smoothly from "Requested" to "In Progress" to "Completed" as agents report back.

### Key API Endpoints
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/v1/register/` | POST | Initial device registration. |
| `/api/v1/commands/` | GET | Polled by agents to receive pending tasks. |
| `/api/v1/inventory/` | POST | Submission of system snapshots. |
| `/api/v1/update-status/` | POST | Reporting deployment success/failure. |

### Database Schema Highlights
-   **Device**: Primary endpoint record with status and metadata.
-   **InventorySnapshot**: Parent record for services, apps, and KBs.
-   **UpdatePush**: Junction tracking the state of a software deployment.
-   **RemoteCommand**: Tracks generic remote actions (Shell, Reboot, Registry).

---

## 🛠️ 6. Maintenance & Deployment

### Quick Reset
To completely clear the environment and start from scratch:
```cmd
clean.bat
```

### Production Start
To launch the system in a production-hardened state:
```cmd
production_server.bat
```
This script handles dependency checks, port clearing, database migrations, and static file collection automatically.

---

**🏷️ Version 1.5.0** | *Persistent Auth & Centralized Management*