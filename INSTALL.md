# Platform Observability Agent - Install Guide

## Prerequisites

- Linux VPS (Ubuntu 18.04+, Debian 9+, CentOS 7+, RHEL 7+, Amazon Linux 2, Rocky Linux 8+)
- Python 3.8+
- Docker installed (for container monitoring)
- Root or sudo access

## Getting Your Configuration Values

### 1. API Token
- Login to your Platform Observability dashboard
- Go to **Settings** > **API Token**
- Copy the token (starts with `pos_`)

### 2. Log Source ID
- In dashboard, go to **Projects** > **Log Sources**
- Create a new log source for your server
- Copy the UUID

### 3. API Endpoint
- Use your platform's domain: `https://your-domain.com/api`
- For local development: `http://localhost:8200/api`

---

## Installation

### Step 1: Download the Agent

```bash
sudo mkdir -p /opt/platform-obs-agent
sudo git clone <repo-url> /opt/platform-obs-agent
cd /opt/platform-obs-agent
```

### Step 2: Set Up Python Environment

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### Step 3: Configure

```bash
cp agent_config.json.example agent_config.json
nano agent_config.json
```

Fill in your values:

```json
{
  "api_endpoint": "https://your-platform-domain.com/api",
  "api_token": "pos_your-api-token-from-dashboard",
  "log_source_id": "your-log-source-uuid-from-dashboard",
  "log_files": [
    "/var/log/nginx/access.log",
    "/var/log/nginx/error.log"
  ]
}
```

Docker monitoring and VPS metrics are enabled by default with no extra config needed.

To add HTTP service checks, add the `http_services` array:

```json
{
  "http_services": [
    {
      "name": "My Web App",
      "url": "https://example.com",
      "timeout": 10,
      "expected_status": 200
    },
    {
      "name": "API Health",
      "url": "https://api.example.com/health"
    }
  ]
}
```

### Step 4: Test Configuration

```bash
./venv/bin/python agent.py --test-config
```

### Step 5: Install as Systemd Service

Create the service file:

```bash
sudo tee /etc/systemd/system/platform-obs-agent.service > /dev/null <<EOF
[Unit]
Description=Platform Observability Agent
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/platform-obs-agent
ExecStart=/opt/platform-obs-agent/venv/bin/python /opt/platform-obs-agent/agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable platform-obs-agent
sudo systemctl start platform-obs-agent
```

---

## Using install.sh (Alternative)

```bash
chmod +x install.sh
sudo ./install.sh
```

---

## Management Commands

```bash
# Check agent status
sudo systemctl status platform-obs-agent

# View live logs
sudo journalctl -u platform-obs-agent -f

# Restart agent
sudo systemctl restart platform-obs-agent

# Stop agent
sudo systemctl stop platform-obs-agent

# Uninstall
sudo systemctl stop platform-obs-agent
sudo systemctl disable platform-obs-agent
sudo rm /etc/systemd/system/platform-obs-agent.service
sudo rm -rf /opt/platform-obs-agent
sudo systemctl daemon-reload
```

---

## What Gets Monitored Automatically

Once installed, the agent automatically collects:

| Data | Interval | Config Required |
|---|---|---|
| VPS host metrics (CPU, memory, disk, network, load) | 5 min | None |
| Docker container metrics (all containers) | 60s | None (Docker must be installed) |
| Heartbeat (online/offline status) | 60s | None |
| Log file tailing | 2s poll | `log_files` paths |
| HTTP service checks | 60s | `http_services` array |

---

## Common Log File Locations

### Web Servers
```json
"log_files": [
  "/var/log/nginx/access.log",
  "/var/log/nginx/error.log",
  "/var/log/apache2/access.log",
  "/var/log/apache2/error.log"
]
```

### Application Servers
```json
"log_files": [
  "/var/log/gunicorn/access.log",
  "/var/log/gunicorn/error.log",
  "/var/log/supervisor/supervisord.log"
]
```

### System Logs
```json
"log_files": [
  "/var/log/syslog",
  "/var/log/auth.log",
  "/var/log/kern.log"
]
```

---

## Docker Permissions

The agent needs access to the Docker CLI to monitor containers. If running as root (recommended for systemd), this works out of the box.

If running as a non-root user, add the user to the `docker` group:

```bash
sudo usermod -aG docker <agent-user>
```

---

## Troubleshooting

### Agent Not Starting
```bash
sudo systemctl status platform-obs-agent
sudo journalctl -u platform-obs-agent --no-pager -n 50
./venv/bin/python agent.py --test-config
```

### No Docker Metrics
```bash
# Verify Docker is accessible
docker ps
# Check agent logs for "Docker container monitoring enabled"
sudo journalctl -u platform-obs-agent | grep -i docker
```

### No VPS Metrics
```bash
# Verify psutil is installed
./venv/bin/python -c "import psutil; print(psutil.cpu_percent())"
```

### Permission Issues
```bash
# Log files must be readable by the agent
sudo chmod 644 /var/log/nginx/*.log
# Or add agent user to the adm group
sudo usermod -aG adm <agent-user>
```

### Network Issues
```bash
# Test API connectivity
curl -H "Authorization: Bearer pos_your-token" \
  https://your-domain.com/api/agent/log-sources/<log-source-id>/
```

---

## Security Notes

- The agent runs as root to access system logs and Docker
- Uses HTTPS for all API communication
- API tokens can be regenerated anytime from the dashboard
- Only `agent_config.json` contains sensitive data (the API token) - restrict its permissions:

```bash
sudo chmod 600 /opt/platform-obs-agent/agent_config.json
```

---

## Supported Systems

- Ubuntu 18.04+
- Debian 9+
- CentOS 7+
- RHEL 7+
- Amazon Linux 2
- Rocky Linux 8+
