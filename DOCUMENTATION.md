
# 🌐 Kinetix & Agent: Comprehensive Documentation

Welcome to the **Kinetix** project. This documentation provides a complete guide to setting up, running, and managing the entire ecosystem, including the server and the endpoint agent.

---

## ✨ Features

- **Interactive Dashboard**: Real-time visualization of device status, OS distribution, and deployment history using Chart.js.
- **Secure Updates**: End-to-end encrypted and signed update delivery (RSA-2048 & SHA-256).
- **Device Inventory**: Automated collection of installed applications and running services.
- **Agent Management**: Remote command execution (updates) and heartbeat monitoring.
- **Audit Logging**: Comprehensive tracking of all system actions for compliance and security.
- **Robust API**: RESTful API for device registration, inventory submission, and command polling.

---

## 🏗️ 1. Server Setup (Kinetix)

The Kinetix is the brain of the operation. It manages devices, audits, and software updates.

### Prerequisites
- Python 3.11+
- Redis Server (Native Windows, Docker, or WSL)
- WiX Toolset v3.11 (for building Agent MSI)

### Step-by-Step Setup
1.  **Clone the project** to your desired directory.
2.  Open a terminal in the project root.
3.  **Initial Setup**: Run the automated setup script.
    ```cmd
    quickstart.bat
    ```
    *   Creates virtual environment (`venv`).
    *   Installs Python dependencies.
    *   Generates secure keys (`.env` and `keys/` directory).
    *   Initializes the database.
    *   Prompts to create a Superuser (Admin).

### Running the Server
You have two options for running the server:

-   **Option A: Production-Grade (Recommended)**
    ```cmd
    production_server.bat
    ```
    *   Enforces `DEBUG=False`.
    *   Starts Redis automatically (if installed locally).
    *   Launches Waitress (WSGI Server) for high performance.
    *   Starts Celery Worker and Beat for background tasks.

-   **Option B: Development Mode**
    ```cmd
    run_dev.bat
    ```
    *   Starts standard Django development server with hot-reloading.

---

## 🤖 2. The Endpoint Agent

The Agent is a secure background service installed on client devices.

### Building the Agent (MSI Installer)
To distribute the agent, you need to build a Windows Installer (MSI).

1.  Navigate to the `agent/` directory:
    ```cmd
    cd agent
    ```
2.  Run the **MSI Builder**:
    ```cmd
    build_agent_msi.bat
    ```
    *   **Compiles** Python code into a standalone executable (`cc_agent.exe`) using PyInstaller.
    *   **Bundles** the executable, configuration, and public key.
    *   **Generates** a `.msi` installer using WiX Toolset.
    *   **Output**: `agent/cc_agent_setup.msi`.

### Deploying the Agent
1.  Copy `cc_agent_setup.msi` to the target machine.
2.  Run the installer (double-click or via GPO/SCCM).
    *   Installs to `C:\Program Files\KinetixAgent`.
    *   Registers as a Windows Service (`KinetixAgent`).
    *   Starts automatically.

### Configuration & Management
The agent is designed to be zero-touch, but can be managed via CLI if needed.

-   **Set Server URL**: If the Kinetix IP changes.
    ```cmd
    cd "C:\Program Files\KinetixAgent"
    agent.exe set-server http://192.168.1.50:8000
    agent.exe restart
    ```

-   **Manual Inventory**: Force immediate inventory collection.
    ```cmd
    agent.exe inventory
    ```

-   **Check Status**:
    ```cmd
    sc query KinetixAgent
    ```

---

## 📦 3. Managing Updates

The Kinetix allows you to distribute software updates securely.

### Uploading an Update
1.  Log in to the **Admin Panel** or **Dashboard**.
2.  Navigate to **Updates** section.
3.  Upload your installer (`.msi` or `.exe`).
4.  **Automatic Signing**: The server automatically calculates the SHA-256 hash and signs the update using the stored RSA Private Key (`keys/private_key.pem`).

### Pushing an Update
1.  Select the **Update** and the **Target Device(s)**.
2.  Schedule the deployment.
3.  The Agent will pick up the "Update Command" on its next poll cycle (default: 5 minutes).
4.  **Verification**: The Agent downloads the file, verifies the Hash and Signature against the embedded Public Key.
5.  **Installation**: If valid, the update is installed silently.

---

## 🛡️ 4. Security Practices & Threat Model

The system is designed with a "Security First" approach.

### Security Controls
-   **Transport Security**: All communication is over HTTPS.
-   **Data Integrity**: SHA-256 Hashing ensures files are not corrupted or tampered with.
-   **Non-Repudiation**: RSA-2048 Signatures verify the update came from the trusted server.
-   **Secret Storage**: Agent stores Auth Tokens in Windows Credential Manager (DPAPI). Server uses `.env` for secrets.
-   **Least Privilege**: Agent runs as `LocalSystem` (required for software installation) but drops privileges where possible for network tasks (future roadmap).

### Threat Model

| Threat | Description | Mitigation Strategy |
| :--- | :--- | :--- |
| **Server Spoofing** | Attacker impersonates the Kinetix. | Agents verify SSL/TLS certificates. Public Key Pinning (future). |
| **Update Tampering** | Attacker modifies an update file in transit (MITM) or on disk. | **Critical Defense**: Agents verify RSA Signature using the embedded Public Key. Modification breaks the signature. |
| **Rogue Agent** | Attacker registers a fake device. | Devices must authenticate. Admins can block/revoke devices from the Dashboard. |
| **Token Theft** | Malware steals the Agent's auth token. | Tokens are stored in Windows Credential Manager, not plain text files. |
| **Replay Attack** | Attacker replays an old update command. | Commands have unique IDs and timestamps (server-side tracking). |

---

## 🧹 5. Maintenance (Factory Reset)

To completely reset the environment (Server & Agent artifacts):

```cmd
clean.bat
```
**WARNING**: This deletes the database, keys, logs, and virtual environments. Use only when you want to start fresh.

---

**Developed with ❤️ by Antigravity**
