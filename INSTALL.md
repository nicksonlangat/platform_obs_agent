# Platform Observability Agent - Quick Install Guide

## Super Simple 3-Step Installation

### Step 1: Download the Agent
```bash
# Download and extract the agent
git clone https://github.com/your-org/platform-observability-platform.git
cd platform-observability-platform/agent

# Or download as ZIP and extract
```

### Step 2: Configure the Agent
Edit the `agent_config.json` file with your details:

```bash
cp agent_config.json.example agent_config.json
nano agent_config.json
```

**Required Configuration:**
```json
{
  "api_endpoint": "https://your-platform-domain.com/api",
  "api_token": "pos_your-api-token-from-dashboard",
  "log_source_id": "your-log-source-uuid-from-dashboard",
  "log_files": [
    "/var/log/nginx/access.log",
    "/var/log/nginx/error.log",
    "/var/log/your-app.log"
  ]
}
```

### Step 3: Install and Start
```bash
# Make installer executable
chmod +x install.sh

# Run the automated installer
sudo ./install.sh
```

**That's it!** 🎉 The agent is now running and sending logs to your platform.

---

## Getting Your Configuration Values

### 1. API Token
- Login to your Platform Observability dashboard
- Go to **Settings** → **API Token**
- Copy the token (starts with `pos_`)

### 2. Log Source ID
- In dashboard, go to **Projects** → **Log Sources**
- Create a new log source for your server
- Copy the UUID

### 3. API Endpoint
- Use your platform's domain: `https://your-domain.com/api`
- For local development: `http://localhost:8002/api`

---

## Management Commands

```bash
# Check agent status
sudo ./install.sh --status

# View live logs
sudo ./install.sh --logs

# Restart agent
sudo ./install.sh --restart

# Uninstall agent
sudo ./install.sh --uninstall
```

---

## Supported Systems

- ✅ Ubuntu 18.04+
- ✅ Debian 9+
- ✅ CentOS 7+
- ✅ RHEL 7+
- ✅ Amazon Linux 2
- ✅ Rocky Linux 8+

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
  "/var/log/uwsgi/uwsgi.log",
  "/var/log/supervisor/supervisord.log"
]
```

### System Logs
```json
"log_files": [
  "/var/log/syslog",
  "/var/log/daemon.log",
  "/var/log/kern.log",
  "/var/log/auth.log"
]
```

### Docker Applications
```json
"log_files": [
  "/var/lib/docker/containers/*/*-json.log",
  "/var/log/docker.log"
]
```

---

## Troubleshooting

### Agent Not Starting
```bash
# Check service status
sudo systemctl status platform-obs-agent

# View detailed logs
sudo journalctl -u platform-obs-agent -f

# Test configuration
sudo python3 /opt/platform-obs-agent/agent.py --test-config
```

### Permission Issues
```bash
# Fix log file permissions
sudo chmod 644 /var/log/nginx/*.log
sudo chmod 644 /var/log/your-app.log

# Add agent to log groups
sudo usermod -a -G adm root
```

### Network Issues
```bash
# Test API connectivity
curl -X GET "your-api-endpoint/health" \
  -H "Authorization: Bearer your-api-token"
```

---

## Security Notes

- The agent runs as root to access system logs
- Uses secure HTTPS connections to your platform
- API tokens can be regenerated anytime in the dashboard
- No sensitive data is stored locally except the config file

---

## Need Help?

- 📧 Email: support@yourplatform.com
- 📖 Documentation: https://docs.yourplatform.com
- 🐛 Issues: https://github.com/your-org/platform-observability-platform/issues