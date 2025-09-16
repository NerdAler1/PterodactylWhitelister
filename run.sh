#!/bin/bash
set -e
# Find out where we are
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Script directory: $SCRIPT_DIR"

# Change to the script directory
cd "$SCRIPT_DIR"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Error: .venv directory not found in $SCRIPT_DIR, attempting to create one..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment. Please ensure Python 3 and venv are installed."
        exit 1
    fi
    echo "Virtual environment created."
fi

# Activate the venv
source .venv/bin/activate
echo "Venv activated."

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt


# Check if main.py exists
if [ ! -f "app.py" ]; then
    echo "Error: app.py not found in $SCRIPT_DIR"
    exit 1
fi

# Run the Python script
python app.py