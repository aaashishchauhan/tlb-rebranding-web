# 🚀 Deployment Guide (Queue Architecture)

This guide covers how to deploy the new **Queue-Based Email Processor** on a Linux server (e.g., DigitalOcean Droplet, AWS EC2).

## 1. Prerequisites

Ensure your server has:
- Python 3.8+
- Node.js (for PM2, optional but recommended)

## 2. Setup

### Clone & Install Dependencies
```bash
# Clone repo
git clone <your-repo-url>
cd reportsauto

# Create Virtual Env
python3 -m venv venv
source venv/bin/activate

# Install Python Packages
pip install -r requirements.txt

# Note: SQLite is built-into Python, so no separate installation is needed! 

# Install Playwright Browsers (Required for Link fetching)
playwright install chromium
playwright install-deps
```

## 3. Configuration

Ensure `config.json`, `service_account.json` (Google Drive), and branding images (`firstpage.png`, etc.) are present in the folder.

## 4. Running with PM2 (Recommended)

PM2 is a process manager that keeps your scripts running in the background and restarts them if they crash.

### Install PM2
```bash
npm install -g pm2
```

### Start Processes
We will start the Producer and Worker as separate processes.

```bash
# Start Producer
pm2 start producer.py --name "email-producer" --interpreter ./venv/bin/python

# Start Worker
pm2 start worker.py --name "email-worker" --interpreter ./venv/bin/python
```

### Save PM2 List
To ensure they restart on server reboot:
```bash
pm2 save
pm2 startup
```

## 5. Monitoring

- **View Logs**:
  ```bash
  pm2 logs
  ```
- **Check Status**:
  ```bash
  pm2 status
  ```
- **Stop System**:
  ```bash
  pm2 stop all
  ```

## 6. Manual Run (Simplified)

You can also use the unified launcher which starts both processes in one window:

```bash
source venv/bin/activate
python main.py
```

## 7. Manual Run (Old School)

If you don't want to use PM2 or main.py, you can run them in `screen` or `tmux` sessions.

```bash
# Session 1
source venv/bin/activate
python producer.py

# Session 2
source venv/bin/activate
python worker.py
```
