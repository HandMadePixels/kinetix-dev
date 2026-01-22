# 🔰 Beginner's Guide: Step-by-Step Setup

If you are new to the project, follow these steps in order to get the **Command Center** (Brain) and the **Agent** (Worker) running and talking to each other.

---

## 🧠 Phase 1: The Command Center (The Brain)
This is the central dashboard where you manage all your devices.

1.  **Open your terminal** (Command Prompt or PowerShell).
2.  **Navigate to the server folder**:
    ```cmd
    cd F:\EndpointSoln\command_center
    ```
3.  **Run the Setup**:
    ```cmd
    quickstart.bat
    ```
    *   **What it does**: Sets up your Python environment, installs libraries, and creates your **RSA Security Keys**.
    *   **Crucial Step**: It will ask: *"Create superuser now? (y/n)"*. Type **`y`** and create a username and password. You will need these to log in later!
4.  **Start the Server**:
    While still in the `command_center` folder, run:
    ```cmd
    production_server.bat
    ```
    *   **What it does**: Starts the website and all background services.
    *   **Result**: Keep this window open. Your Brain is now alive at **`http://127.0.0.1:8000`**.

---

## ⚙️ Phase 2: The Agent (The Worker)
Now we build the installer that gets put on the computers you want to control.

1.  **Open a NEW terminal window.**
2.  **Go to the root folder**:
    ```cmd
    cd F:\EndpointSoln
    ```
3.  **Run the MSI Builder**:
    ```cmd
    build_agent_msi.bat
    ```
    *   **What it does**: It bundles the Python code into an EXE and wraps it in a professional Windows Installer (`.msi`).
    *   **Result**: When finished, you will find **`cc_agent_setup.msi`** inside your **`agent/`** folder.

---

## 🔗 Phase 3: Connecting Them
Now we install the worker and watch it check in at headquarters.

1.  **Install the Agent**:
    Double-click the **`cc_agent_setup.msi`** file you just created and follow the installation steps.
2.  **Log in to the Dashboard**:
    Open your browser and go to:
    **`http://127.0.0.1:8000/admin`**
3.  **Check for Devices**:
    Log in with the username/password you created in Phase 1. Click on **"Devices"**.
    *   *Within 5 minutes, your computer will appear automatically in the list!*

---

## 🛠️ Daily Workflow
Once you have finished the setup above, here is how you use it every day:

1.  **Start the Brain**: Go to `command_center/` and run `production_server.bat`.
2.  **The Worker (Agent)**: You don't need to do anything! Because you installed it as a Windows Service, it starts itself every time your computer turns on.
3.  **Stopping everything**: When you're done for the day, go to `command_center/` and run `stop_dev.bat`.

---

## 🚦 Troubleshooting for Newbies

### "Redis server not found"
The system needs a tool called **Redis** to pass messages between the website and the background workers.
*   If `production_server.bat` says Redis is missing, [download the Redis Zip here](https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip).
*   Extract it and add the folder to your Windows **System PATH**.

### "This site can't be reached"
*   Make sure you are using **`http://127.0.0.1:8000`** (not https).
*   If your browser forces you to HTTPS, open the site in **Incognito/Private Mode**.

---
**Happy Managing!** 🚀
