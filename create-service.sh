#!/bin/bash

# Script to create a systemd service for running run.sh

# Get the current directory (where this script and run.sh are located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SCRIPT="$SCRIPT_DIR/run.sh"

# Check if run.sh exists
if [[ ! -f "$RUN_SCRIPT" ]]; then
    echo "Error: run.sh not found in $SCRIPT_DIR"
    exit 1
fi

# Make run.sh executable if it isn't already
if [[ ! -x "$RUN_SCRIPT" ]]; then
    echo "Making run.sh executable..."
    chmod +x "$RUN_SCRIPT"
fi

# Get service name (default to directory name)
PROJECT_NAME=$(basename "$SCRIPT_DIR")
read -p "Enter service name (default: $PROJECT_NAME): " SERVICE_NAME
SERVICE_NAME=${SERVICE_NAME:-$PROJECT_NAME}

# Get user to run the service as
CURRENT_USER=$(whoami)
read -p "Enter user to run service as (default: $CURRENT_USER): " RUN_USER
RUN_USER=${RUN_USER:-$CURRENT_USER}

# Get service description 
read -p "Enter service description (default: $SERVICE_NAME service): " DESCRIPTION
DESCRIPTION=${DESCRIPTION:-"$SERVICE_NAME service"}

# Create the service file
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "Creating systemd service file..."

# Create the service file (requires sudo)
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=$DESCRIPTION
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$RUN_SCRIPT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

if [[ $? -eq 0 ]]; then
    echo "Service file created successfully at: $SERVICE_FILE"
    
    # Reload systemd to recognize the new service
    echo "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    echo "Service '$SERVICE_NAME' has been created!"

    # Ask if user wants to enable and start the service
    read -p "Do you want to enable and start the service now? (y/N): " START_NOW
    if [[ "$START_NOW" =~ ^[Yy]$ ]]; then
        echo "Enabling service..."
        sudo systemctl enable "$SERVICE_NAME"
        echo "Starting service..."
        sudo systemctl start "$SERVICE_NAME"
        echo "Service status:"
        sudo systemctl status "$SERVICE_NAME" --no-pager
    fi
else
    echo "Error: Failed to create service file. Make sure you have sudo privileges."
    exit 1
fi