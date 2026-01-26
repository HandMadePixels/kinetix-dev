# 🛠️ Building the Kinetix Agent

This guide explains how to package the Python agent as a standalone Windows MSI installer.

## 📋 Prerequisites

1.  **Python 3.11+**
2.  **WiX Toolset v3.11+** (Download from [wixtoolset.org](https://wixtoolset.org/releases/))
3.  **Visual Studio** (Optional, for signing)

## 🏗️ Step 1: Install Dependencies

```bash
cd agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## ❄️ Step 2: Freeze with PyInstaller

We bundle all Python code and libraries into a single executable.

```bash
# Ensure you have the public_key.pem from the server
copy ..\keys\public_key.pem .

# Package the agent
pyinstaller agent.spec
```

The executable will be generated at `dist\cc_agent.exe`.

## 📦 Step 3: Create MSI with WiX

1.  Open a command prompt in `agent\installer`.
2.  Run the following commands:

```bash
# Compile
candle.exe product.wxs

# Link
light.exe product.wixobj -o cc_agent_setup.msi
```

## 🛂 Manual Management

The `cc_agent.exe` supports CLI commands:

- `cc_agent.exe install` - Install the service manually
- `cc_agent.exe start` - Start the service
- `cc_agent.exe debug` - Run in console for troubleshooting
- `cc_agent.exe inventory` - Force immediate inventory collection
