# 🔰 Beginner's Guide: Step-by-Step Setup

If you are new to the project, follow these steps in order to get the **Command Center** (Brain) and the **Agent** (Worker) running and talking to each other.

---

## 🧠 Phase 1: The Command Center (The Brain)
This is the central dashboard where you manage all your devices.

1.  **Open your terminal** (Command Prompt or PowerShell).
2.  **Navigate to the project folder**:
    ```cmd
    cd F:\Kinetix
    ```
3.  **Run the Setup**:
    ```cmd
    quickstart.bat
    ```
    *   **What it does**: Sets up your Python environment, installs libraries, and creates your **RSA Security Keys**.
    *   **Crucial Step**: It will ask: *"Create superuser now? (y/n)"*. Type **`y`** and create a username and password. You will need these to log in later!
4.  **Start the Server**:
    Run:
    ```cmd
    production_server.bat
    ```
    *   **What it does**: Starts the website and all background services (Redis, Celery).
    *   **Result**: Keep this window open. Your Brain is now alive at **`http://localhost:8000`**.

---

## ⚙️ Phase 2: The Agent (The Worker)
Now we build the installer that gets put on the computers you want to control.

1.  **Open a NEW terminal window.**
2.  **Go to the agent folder**:
    ```cmd
    cd F:\Kinetix\agent
    ```
3.  **Run the MSI Builder**:
    ```cmd
    build_agent_msi.bat
    ```
    *   **What it does**: It bundles the Python code into an EXE and wraps it in a professional Windows Installer (`.msi`).
    *   **Result**: When finished, you will find **`kinetix_agent_setup.msi`** inside the folder.

---

## 🔗 Phase 3: Connecting Them
Now we install the worker and watch it check in at headquarters.

1.  **Install the Agent**:
    Double-click the **`kinetix_agent_setup.msi`** file you just created and follow the installation steps.
2.  **Log in to the Dashboard**:
    Open your browser and go to:
    **`http://localhost:8000`**
3.  **Check for Devices**:
    Log in with the username/password you created in Phase 1. Click on **"Devices"**.
    *   *Within 5 minutes, your computer will appear automatically in the list!*

---

## 🛠️ Daily Workflow
Once you have finished the setup above, here is how you use it every day:

1.  **Start the Brain**: Go to the root and run `production_server.bat` (or `run_dev.bat` for testing).
2.  **The Worker (Agent)**: You don't need to do anything! Because you installed it as a Windows Service, it starts itself every time your computer turns on.
3.  **Stopping everything**: Close the terminal windows or run `stop_server.bat`.

---

## 🚦 Troubleshooting for Newbies

### "Redis server not found"
The system needs **Redis** for background tasks.
*   The `production_server.bat` tries to start it automatically.
*   If it fails, ensure Redis is installed and in your PATH.

### "Site can't be reached"
*   Make sure you are using **`http://localhost:8000`**.
*   Check `logs/server_err.log` if the page won't load.

---
**Happy Managing!** 🚀