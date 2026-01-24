#!/bin/bash

# --- Configuration ---
VENV_DIR=".venv"
APP_FILE="explorer.py"
REQ_PKG="psutil"

echo "--- MacExplorer Pro Launcher ---"

# 1. Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    exit 1
fi

# 2. Check for Tkinter (Critical for GUI)
# Reason: macOS Homebrew Python often lacks the _tkinter module by default.
if ! python3 -c "import tkinter" &> /dev/null; then
    echo "Error: Tkinter is missing."
    echo "Please run: brew install python-tk@3.14"
    exit 1
fi

# 3. Setup Virtual Environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# 4. Activate the venv
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 5. Check/Install dependencies
if ! python3 -c "import $REQ_PKG" &> /dev/null; then
    echo "Dependency '$REQ_PKG' missing. Installing..."
    pip install --upgrade pip
    pip install "$REQ_PKG"
else
    echo "All dependencies ($REQ_PKG) are satisfied."
fi

# 6. Run the Application
echo "Launching $APP_FILE..."
python3 "$APP_FILE"

# 7. Deactivate and Exit
echo "App closed. Deactivating virtual environment..."
deactivate

echo "Done."