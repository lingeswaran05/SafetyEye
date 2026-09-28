#!/usr/bin/env bash
# ==============================================================================
# SafetyEye GCP VM Automated Deployment Script
# Target OS: Ubuntu 22.04 LTS / 24.04 LTS on Google Cloud Compute Engine
# ==============================================================================

set -e

echo "=========================================================="
echo " 🛡️ Starting SafetyEye Production VM Setup"
echo "=========================================================="

# 1. Update OS packages and install required system libraries for OpenCV & Python
echo "[1/6] Updating system and installing dependencies..."
sudo apt-get update -y
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    nginx \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev

# 2. Setup project directory
APP_DIR="/opt/SafetyEye"
echo "[2/6] Setting up project directory at $APP_DIR..."
if [ ! -d "$APP_DIR" ]; then
    echo "Cloning repository..."
    sudo git clone https://github.com/lingeswaran05/SafetyEye.git "$APP_DIR"
else
    echo "Pulling latest changes from repository..."
    cd "$APP_DIR"
    sudo git pull origin main
fi

cd "$APP_DIR"
sudo chown -R $USER:$USER "$APP_DIR"

# 3. Create virtual environment and install Python packages
echo "[3/6] Setting up Python virtual environment..."
if [ ! -d "$APP_DIR/.venv" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi

"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# 4. Configure systemd service for 24/7 background operation
echo "[4/6] Installing systemd background service..."
sudo cp "$APP_DIR/deployment/safetyeye.service" /etc/systemd/system/safetyeye.service
sudo systemctl daemon-reload
sudo systemctl enable safetyeye
sudo systemctl restart safetyeye

# 5. Configure NGINX reverse proxy on port 80
echo "[5/6] Configuring NGINX reverse proxy..."
sudo cp "$APP_DIR/deployment/nginx_safetyeye.conf" /etc/nginx/sites-available/safetyeye
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/safetyeye /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 6. Verify Service Status
echo "[6/6] Verifying services..."
sleep 3
sudo systemctl status safetyeye --no-pager

echo "=========================================================="
echo " ✅ SafetyEye is now live in production!"
echo " Access your dashboard at: http://$(curl -s ifconfig.me)"
echo "=========================================================="
