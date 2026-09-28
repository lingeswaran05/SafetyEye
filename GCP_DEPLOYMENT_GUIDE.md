# 🚀 Step-by-Step Manual GCP Production Deployment Guide for SafetyEye

This guide provides the complete, end-to-end instructions to manually set up **Google Cloud Platform (GCP)**, launch a **Compute Engine VM**, configure **Persistent Storage & Firewall**, and deploy **SafetyEye** with 24/7 background execution and NGINX reverse proxy.

---

## 📑 Table of Contents
1. [Step 1: Create a Google Cloud Project](#step-1-create-a-google-cloud-project)
2. [Step 2: Create a Compute Engine VM Instance](#step-2-create-a-compute-engine-vm-instance)
3. [Step 3: Configure GCP Firewall Rules (Allow Port 80 / 8501)](#step-3-configure-gcp-firewall-rules)
4. [Step 4: Create Cloud Storage Bucket for Evidence Archiving (Optional)](#step-4-create-cloud-storage-bucket)
5. [Step 5: Connect to the VM & Run 1-Click Production Setup](#step-5-connect-to-the-vm--deploy)
6. [Step 6: Configure Email Alerts on the Server](#step-6-configure-email-alerts)
7. [Step 7: Verification, Monitoring & Maintenance](#step-7-verification--maintenance)

---

## 🛠️ Step 1: Create a Google Cloud Project

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. In the top navigation bar, click the project dropdown and select **New Project**.
3. Name your project (e.g. `safetyeye-production`).
4. Select your billing account and click **Create**.
5. Ensure your new project is selected in the top bar.

---

## 🖥️ Step 2: Create a Compute Engine VM Instance

1. In the GCP Console navigation menu (☰), go to **Compute Engine** > **VM instances**.
2. Click **Create Instance**.
3. Configure the VM with the following recommended production settings:
   * **Name**: `safetyeye-server`
   * **Region & Zone**: Select a region close to your users (e.g. `us-central1-a` or `asia-south1-a`).
   * **Machine configuration**:
     * **Machine type**: `e2-standard-4` (4 vCPUs, 16 GB memory) — *optimal for fast real-time YOLOv8 inference*.
     * *(Cost-effective alternative: `e2-medium` 2 vCPU, 4 GB memory)*.
   * **Boot disk**:
     * Click **Change**.
     * **Operating System**: `Ubuntu`
     * **Version**: `Ubuntu 22.04 LTS x86/64`
     * **Boot disk type**: `Balanced Persistent Disk` (or `SSD Persistent Disk`)
     * **Size (GB)**: `50 GB` (provides ample space for video snapshots and models).
     * Click **Select**.
   * **Firewall**:
     * Check **✅ Allow HTTP traffic**
     * Check **✅ Allow HTTPS traffic**
4. Click **Create** at the bottom.
5. Wait ~30 seconds for the green checkmark indicating the VM is running. Note down the **External IP** address.

---

## 🛡️ Step 3: Configure GCP Firewall Rules

We need to make sure web traffic (Port 80 and optionally Streamlit direct port 8501) can reach the server:

1. In the GCP Console search bar, type **VPC network** and select **Firewall**.
2. Click **+ CREATE FIREWALL RULE** at the top.
3. Set the following fields:
   * **Name**: `allow-safetyeye-web`
   * **Network**: `default`
   * **Direction of traffic**: `Ingress`
   * **Action on match**: `Allow`
   * **Targets**: `All instances in the network`
   * **Source IPv4 ranges**: `0.0.0.0/0`
   * **Protocols and ports**:
     * Check **Specified protocols and ports**
     * Check **TCP** and enter: `80, 443, 8501`
4. Click **Create**.

---

## 🗄️ Step 4: Create Cloud Storage Bucket (Optional Archive)

If you want long-term cloud backups of captured violation frames:

1. In the search bar, navigate to **Cloud Storage** > **Buckets**.
2. Click **+ CREATE**.
3. Choose a globally unique name: `safetyeye-violations-<your-project-id>`.
4. **Location type**: `Region` (same region as your VM).
5. **Storage class**: `Standard`.
6. Click **Create**.

---

## ⚡ Step 5: Connect to the VM & Deploy

1. Return to **Compute Engine** > **VM instances**.
2. In the row for `safetyeye-server`, click the **SSH** button under the *Connect* column. A browser terminal window will open.
3. In the SSH terminal, run the following automated setup command:

```bash
# Download and execute the automated production setup script
curl -sSL https://raw.githubusercontent.com/lingeswaran05/SafetyEye/main/deployment/setup_vm.sh | bash
```

*This automated script performs everything for you:*
- Installs Python 3, pip, Git, NGINX, and OpenCV graphical libraries (`libgl1`, etc.).
- Clones your latest repository from GitHub.
- Creates a dedicated Python virtual environment and installs all dependencies.
- Configures a **systemd service** (`safetyeye.service`) so the dashboard runs continuously in the background and auto-restarts if rebooted.
- Configures **NGINX** as a reverse proxy on Port 80 with WebSocket support.

---

## 📧 Step 6: Configure Email Alerts on the Server

To ensure the live email alert service works on the VM:

1. In the SSH terminal, navigate to the app directory:
   ```bash
   cd /opt/SafetyEye
   ```
2. Verify or edit the `.env` file:
   ```bash
   nano .env
   ```
3. Ensure your credentials are set:
   ```env
   SAFETYEYE_SMTP_SERVER=smtp.gmail.com
   SAFETYEYE_SMTP_PORT=587
   SAFETYEYE_SENDER_EMAIL=your_email@gmail.com
   SAFETYEYE_SENDER_PASSWORD=your_16_digit_app_password
   SAFETYEYE_RECEIVER_EMAILS=safety_officer@company.com
   SAFETYEYE_EMAIL_COOLDOWN=60
   ```
4. Press `Ctrl + O` then `Enter` to save, and `Ctrl + X` to exit.
5. Test the email service directly:
   ```bash
   .venv/bin/python scripts/test_email.py
   ```
   *(You should see `[+] Success! Test email sent to...`)*
6. Restart the service to apply any updated `.env` settings:
   ```bash
   sudo systemctl restart safetyeye
   ```

---

## 🌐 Step 7: Access Your Live Application

Open any web browser and navigate to:
```
http://<YOUR_VM_EXTERNAL_IP>
```
*(Example: `http://34.136.42.108`)*

---

## 🔧 Useful Maintenance Commands

| Task | Command on VM SSH |
| :--- | :--- |
| **Check service status** | `sudo systemctl status safetyeye` |
| **Restart application** | `sudo systemctl restart safetyeye` |
| **Stop application** | `sudo systemctl stop safetyeye` |
| **View live logs** | `sudo journalctl -u safetyeye -f` |
| **Update code from GitHub** | `cd /opt/SafetyEye && git pull origin main && sudo systemctl restart safetyeye` |
| **Check NGINX status** | `sudo systemctl status nginx` |
