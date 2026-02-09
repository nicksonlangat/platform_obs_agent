# Platform Observability Agent - Installation & Upgrade Guide

Complete guide for installing and managing the Platform Observability Agent on your servers.

---

## 📋 Table of Contents

- [First Time Installation](#first-time-installation)
- [Upgrading Existing Installation](#upgrading-existing-installation)
- [Configuration](#configuration)
- [Management Commands](#management-commands)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

---

## 🚀 First Time Installation

### Prerequisites

- **Operating System**: Linux (Ubuntu 20.04+, Debian 10+, CentOS 7+, RHEL 8+, Amazon Linux 2)
- **Python**: Version 3.7 or higher (usually pre-installed)
- **Root Access**: Required for installation
- **Internet Connection**: To download the agent and send metrics

### Step 1: Get Your API Token

1. Log in to your Platform Observability dashboard
2. Navigate to **Settings** → **API Tokens**
3. Copy your organization API token (starts with `pos_`)

### Step 2: Download the Agent

```bash
# SSH into your server
ssh user@your-server-ip

# Download the latest release
wget https://github.com/nicksonlangat/platform_obs_agent/releases/latest/download/platform-obs-agent-1.0.3.tar.gz

# Extract the archive
tar -xzf platform-obs-agent-1.0.3.tar.gz

# Navigate to the agent directory
cd platform-obs-agent-1.0.3
```

### Step 3: Configure the Agent

Create the configuration file with your API credentials:

```bash
cat > agent_config.json << 'EOF'
{
  "api_endpoint": "https://api.watchdock.cc/api",
  "api_token": "pos_YOUR_API_TOKEN_HERE"
}
EOF
```

**Replace:**
- `pos_YOUR_API_TOKEN_HERE` with your API token from Step 1

**That's it!** The agent will automatically:
- ✅ Detect your server's unique ID
- ✅ Register itself in your dashboard
- ✅ Start collecting metrics

### Step 4: Install the Agent

```bash
# Run the installer (requires sudo/root)
sudo ./install.sh
```

The installer will:
1. Check system dependencies
2. Install Python packages
3. Set up systemd service
4. Configure log rotation
5. Start the agent automatically

**Expected output:**
```
================================
 Platform Observability Agent
     Automated Installer
================================

[INFO] Detected OS: Ubuntu 22.04
[INFO] Checking system dependencies...
[INFO] Using existing Python 3: Python 3.10.6
...
✓ Installation completed successfully!

Service status: active (running)
To view logs: journalctl -u platform-obs-agent -f
```

### Step 5: Verify Installation

```bash
# Check service status
sudo systemctl status platform-obs-agent

# View live logs
sudo journalctl -u platform-obs-agent -f
```

**You should see:**
- Service status: **Active: active (running)**
- Logs showing: "Machine ID detected", "Sending metrics", "Success"

### Step 6: Check Dashboard

Within **60 seconds**, your server should appear in the dashboard with:
- Server name (your hostname)
- Real-time metrics (CPU, Memory, Disk)
- Status: Active

---

## 🔄 Upgrading Existing Installation

### Why Upgrade?

- Bug fixes
- New features
- Security patches
- Performance improvements

### One-Command Upgrade (Recommended)

**No need to reconfigure!** Your settings are automatically preserved.

```bash
# Upgrade to latest version
curl -sSL https://raw.githubusercontent.com/nicksonlangat/platform_obs_agent/main/upgrade.sh | sudo bash
```

**That's it!** The upgrade script will:
1. ✅ Backup your current installation
2. ✅ Preserve your configuration (API token stays)
3. ✅ Download and install the new version
4. ✅ Restart the service automatically
5. ✅ Roll back if anything fails

**Expected output:**
```
════════════════════════════════════════════════════════
  Platform Observability Agent - Upgrade Tool
════════════════════════════════════════════════════════

[UPGRADE] Current version: 1.0.2
[UPGRADE] Upgrading to: 1.0.3
[UPGRADE] Stopping agent service...
[UPGRADE] Creating backup at: /opt/platform-obs-agent-backup-20260207-123456
[UPGRADE] Downloading version 1.0.3...
[UPGRADE] Updating agent files...
[UPGRADE] Restoring configuration...
[UPGRADE] Starting agent service...
[UPGRADE] Agent restarted successfully!

════════════════════════════════════════════════════════
✓ Upgrade completed successfully!
════════════════════════════════════════════════════════

Previous version: 1.0.2
Current version:  1.0.3

Backup location: /opt/platform-obs-agent-backup-20260207-123456
View logs: journalctl -u platform-obs-agent -f
```

### Manual Upgrade (Alternative)

If you prefer to download the upgrade script first:

```bash
# Download upgrade script
wget https://github.com/nicksonlangat/platform_obs_agent/releases/latest/download/upgrade.sh

# Make it executable
chmod +x upgrade.sh

# Run upgrade
sudo ./upgrade.sh
```

### Upgrade to Specific Version

```bash
# Upgrade to a specific version
sudo bash upgrade.sh 1.0.3
```

### Verify Upgrade

```bash
# Check service is running
sudo systemctl status platform-obs-agent

# View recent logs
sudo journalctl -u platform-obs-agent -n 50

# Check version
cat /opt/platform-obs-agent/VERSION
```

---

## ⚙️ Configuration

### Basic Configuration (Minimal)

The simplest configuration - just API token:

```json
{
  "api_endpoint": "https://api.watchdock.cc/api",
  "api_token": "pos_YOUR_TOKEN"
}
```

### Advanced Configuration (Optional)

Add monitoring for logs and Docker:

```json
{
  "api_endpoint": "https://api.watchdock.cc/api",
  "api_token": "pos_YOUR_TOKEN",

  "log_files": [
    "/var/log/nginx/access.log",
    "/var/log/nginx/error.log",
    "/var/log/application.log"
  ],

  "collect_metrics": true,
  "metrics_interval": 300,

  "collect_docker_metrics": true,
  "docker_metrics_interval": 60,

  "log_level": "INFO"
}
```

**Note:** HTTP health checks are now managed through the WatchDock dashboard, not the agent configuration. Add and configure HTTP monitors directly in your dashboard under Monitoring → HTTP Checks.

### Configuration Options

| Option | Description | Default | Required |
|--------|-------------|---------|----------|
| `api_endpoint` | Platform API URL (https://api.watchdock.cc/api) | - | ✅ Yes |
| `api_token` | Organization API token | - | ✅ Yes |
| `log_files` | Array of log file paths to monitor | `[]` | No |
| `collect_metrics` | Enable server metrics collection | `true` | No |
| `metrics_interval` | Seconds between metric collections | `300` | No |
| `collect_docker_metrics` | Enable Docker monitoring | `true` | No |
| `docker_metrics_interval` | Seconds between Docker checks | `60` | No |
| `log_level` | Logging verbosity | `INFO` | No |

### Update Configuration

After changing configuration:

```bash
# Edit config
sudo nano /opt/platform-obs-agent/agent_config.json

# Restart agent to apply changes
sudo systemctl restart platform-obs-agent

# Verify it's working
sudo journalctl -u platform-obs-agent -f
```

---

## 🛠️ Management Commands

### Service Control

```bash
# Start the agent
sudo systemctl start platform-obs-agent

# Stop the agent
sudo systemctl stop platform-obs-agent

# Restart the agent
sudo systemctl restart platform-obs-agent

# Check status
sudo systemctl status platform-obs-agent

# Enable auto-start on boot (done by installer)
sudo systemctl enable platform-obs-agent

# Disable auto-start on boot
sudo systemctl disable platform-obs-agent
```

### View Logs

```bash
# View live logs (follow mode)
sudo journalctl -u platform-obs-agent -f

# View last 50 lines
sudo journalctl -u platform-obs-agent -n 50

# View logs from today
sudo journalctl -u platform-obs-agent --since today

# View logs from specific time
sudo journalctl -u platform-obs-agent --since "2024-01-01 10:00:00"

# Search logs for errors
sudo journalctl -u platform-obs-agent | grep -i error

# View logs without pager
sudo journalctl -u platform-obs-agent --no-pager
```

### Check Version

```bash
# View installed version
cat /opt/platform-obs-agent/VERSION
```

### Test Configuration

```bash
# Test config without starting service
cd /opt/platform-obs-agent
python3 agent.py --test-config
```

---

## 🔧 Troubleshooting

### Agent Not Showing in Dashboard

**Symptoms:**
- Service is running
- No server appearing in dashboard after 2+ minutes

**Solutions:**

1. **Check logs for errors:**
   ```bash
   sudo journalctl -u platform-obs-agent -n 100 | grep -i error
   ```

2. **Verify API endpoint is reachable:**
   ```bash
   curl -I https://your-api-endpoint.com/api/
   ```
   Should return `HTTP/1.1 200 OK` or similar.

3. **Check API token:**
   ```bash
   # View current config
   sudo cat /opt/platform-obs-agent/agent_config.json

   # Verify token format (should start with "pos_")
   ```

4. **Check network connectivity:**
   ```bash
   ping your-api-domain.com
   ```

5. **Test API connection manually:**
   ```bash
   cd /opt/platform-obs-agent
   python3 agent.py --test-config
   ```

### Service Won't Start

**Symptoms:**
- `systemctl status` shows "inactive (dead)" or "failed"

**Solutions:**

1. **View error details:**
   ```bash
   sudo systemctl status platform-obs-agent -l
   sudo journalctl -u platform-obs-agent -n 50
   ```

2. **Check for missing files:**
   ```bash
   ls -la /opt/platform-obs-agent/
   # Should show: agent.py, config.py, docker_monitor.py, http_monitor.py, etc.
   ```

3. **Check permissions:**
   ```bash
   ls -la /opt/platform-obs-agent/agent.py
   # Should be executable
   ```

4. **Try running manually to see error:**
   ```bash
   cd /opt/platform-obs-agent
   python3 agent.py
   # This will show the actual error
   ```

5. **Reinstall if corrupted:**
   ```bash
   sudo ./install.sh --uninstall
   sudo ./install.sh
   ```

### High CPU/Memory Usage

**Solutions:**

1. **Check resource usage:**
   ```bash
   ps aux | grep agent.py
   ```

2. **Increase metric collection interval:**
   ```bash
   sudo nano /opt/platform-obs-agent/agent_config.json
   # Change "metrics_interval": 300 to a higher value (e.g., 600)
   sudo systemctl restart platform-obs-agent
   ```

3. **Disable unnecessary features:**
   ```json
   {
     "collect_docker_metrics": false
   }
   ```

### Permission Denied Errors

**Symptoms:**
- Logs show "Permission denied" when reading log files

**Solutions:**

```bash
# Give agent access to log files
sudo chmod 644 /var/log/nginx/*.log

# Or add to appropriate group
sudo usermod -aG adm root
```

### Connection Timeouts

**Symptoms:**
- Logs show "Connection timeout" or "Request timeout"

**Solutions:**

1. **Check firewall rules:**
   ```bash
   sudo ufw status
   # Ensure outbound HTTPS is allowed
   ```

2. **Check if API is behind a proxy:**
   ```bash
   # Add proxy settings to config if needed
   export https_proxy=http://proxy:port
   ```

3. **Increase timeout in code** (contact support for custom builds)

### Upgrade Failed

**Symptoms:**
- Upgrade script reported errors

**Solutions:**

1. **Check backup location:**
   ```bash
   ls -la /opt/platform-obs-agent-backup-*
   ```

2. **Restore from backup:**
   ```bash
   sudo systemctl stop platform-obs-agent
   sudo rm -rf /opt/platform-obs-agent
   sudo mv /opt/platform-obs-agent-backup-TIMESTAMP /opt/platform-obs-agent
   sudo systemctl start platform-obs-agent
   ```

3. **Try upgrade again:**
   ```bash
   curl -sSL https://raw.githubusercontent.com/nicksonlangat/platform_obs_agent/main/upgrade.sh | sudo bash
   ```

---

## 🗑️ Uninstallation

### Complete Removal

```bash
# Navigate to agent directory
cd /opt/platform-obs-agent-*

# Run uninstaller
sudo ./install.sh --uninstall
```

This will:
- Stop the service
- Remove systemd service file
- Delete agent directory
- Remove log rotation config
- Keep backup at `/opt/platform-obs-agent-backup-*` (optional to delete manually)

### Manual Removal

If the uninstaller isn't available:

```bash
# Stop and disable service
sudo systemctl stop platform-obs-agent
sudo systemctl disable platform-obs-agent

# Remove service file
sudo rm /etc/systemd/system/platform-obs-agent.service
sudo systemctl daemon-reload

# Remove agent directory
sudo rm -rf /opt/platform-obs-agent

# Remove log rotation
sudo rm /etc/logrotate.d/platform-obs-agent

# Remove agent logs (optional)
sudo rm -rf /var/log/platform-obs-agent
```

---

## 📞 Support

### Getting Help

1. **Check logs first:**
   ```bash
   sudo journalctl -u platform-obs-agent -n 100
   ```

2. **Test configuration:**
   ```bash
   cd /opt/platform-obs-agent
   python3 agent.py --test-config
   ```

3. **Check service status:**
   ```bash
   sudo systemctl status platform-obs-agent -l
   ```

### Contact Support

- **Email**: support@your-platform.com
- **Documentation**: https://docs.your-platform.com
- **GitHub Issues**: https://github.com/nicksonlangat/platform_obs_agent/issues

When reporting issues, please include:
- Agent version: `cat /opt/platform-obs-agent/VERSION`
- OS version: `cat /etc/os-release`
- Service status: `systemctl status platform-obs-agent`
- Recent logs: `journalctl -u platform-obs-agent -n 100`

---

## 🔐 Security Notes

- The agent runs as `root` to access system metrics and log files
- API token is stored in `/opt/platform-obs-agent/agent_config.json` (readable only by root)
- All communication with the API is over HTTPS
- Agent is sandboxed with systemd security features:
  - `NoNewPrivileges=true`
  - `PrivateTmp=true`
  - `ProtectHome=true`
  - `ProtectSystem=strict`

---

## 📊 What Data is Collected?

The agent collects:
- **Server Metrics**: CPU, memory, disk usage, network stats
- **System Info**: OS, hostname, uptime
- **Docker Metrics**: Container status, resource usage (if Docker is installed)
- **Log Files**: Application logs (if configured)

**HTTP Health Checks** are managed separately from the dashboard and run from the WatchDock backend, not from the agent.

**Not collected:**
- File contents (except specified log files)
- Environment variables
- User credentials
- SSH keys
- Personal data

---

## 📝 Changelog

### v1.0.9 (Latest)
- ✅ Removed HTTP checks from agent (now managed via WatchDock dashboard)
- ✅ Updated API endpoint to api.watchdock.cc
- ✅ Simplified agent configuration

### v1.0.8
- ✅ Previous release

### v1.0.7
- ✅ Fixed API endpoint in configuration test
- ✅ Fixed authentication header format

### v1.0.3
- ✅ Fix: Include all required Python modules during installation
- ✅ Improved error handling

### v1.0.2
- ✅ Added seamless upgrade script
- ✅ Zero-downtime updates

### v1.0.1
- ✅ Fix: Directory creation before config copy

### v1.0.0
- 🎉 Initial release
- ✅ Auto-discovery (no manual log source creation)
- ✅ Server metrics monitoring
- ✅ Docker monitoring

---

**Last Updated**: February 2026
**Agent Version**: 1.0.9
