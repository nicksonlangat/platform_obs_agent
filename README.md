# Platform Observability Agent

A lightweight Python agent that runs on your VPS/server to collect and forward system metrics, Docker container data, HTTP service availability, and log data to the Platform Observability dashboard.

## What It Monitors

### VPS Host Metrics (via psutil)
- CPU usage, core count, load averages (1m/5m/15m)
- Memory and swap usage
- Disk usage (root partition)
- Network bytes sent/received
- Process count, uptime, OS info, public/private IP

### Docker Containers (auto-discovered)
- Automatically discovers **all** containers on the host (no config needed)
- Per container: status, health, CPU %, memory usage/limit, network I/O, block I/O, PIDs
- Restart count, last restart reason (OOMKilled, errors), exit codes
- Uptime, start/finish timestamps
- Stale containers are automatically cleaned up when they disappear

### HTTP Service Checks (user-configured)
- Response time in milliseconds
- Status codes and availability (up/down)
- TLS certificate validity and days until expiry
- Error details (timeouts, connection refused, SSL errors)

### Log File Monitoring
- Tails configured log files in real time
- Parses timestamps and log levels automatically
- Batched delivery for efficiency
- Handles log rotation gracefully

## Requirements

- Python 3.8+
- `psutil` (for VPS metrics)
- `requests` (for API communication)
- Docker CLI accessible (for container monitoring, optional)

## Quick Start

```bash
# Clone into /opt
sudo git clone <repo-url> /opt/platform-obs-agent
cd /opt/platform-obs-agent

# Set up virtualenv
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Configure
cp agent_config.json.example agent_config.json
nano agent_config.json  # Fill in api_token, log_source_id, api_endpoint

# Test connectivity
./venv/bin/python agent.py --test-config

# Run
./venv/bin/python agent.py
```

## Configuration

Edit `agent_config.json`:

### Required
| Key | Description |
|---|---|
| `api_endpoint` | Platform API URL (e.g. `https://your-domain.com/api`) |
| `api_token` | Organization API token (starts with `pos_`) |
| `log_source_id` | UUID of your log source from the dashboard |

### Log Monitoring
| Key | Default | Description |
|---|---|---|
| `log_files` | `[]` | Array of log file paths to tail |
| `batch_size` | `100` | Logs per batch |
| `flush_interval` | `10` | Seconds between batch flushes |
| `poll_interval` | `2` | Seconds between file polls |

### VPS Metrics
| Key | Default | Description |
|---|---|---|
| `collect_metrics` | `true` | Enable/disable host metrics |
| `metrics_interval` | `300` | Seconds between collections (5 min) |

### Docker Monitoring
| Key | Default | Description |
|---|---|---|
| `collect_docker_metrics` | `true` | Enable/disable container monitoring |
| `docker_metrics_interval` | `60` | Seconds between collections |

### HTTP Service Checks
| Key | Default | Description |
|---|---|---|
| `collect_http_checks` | `true` | Enable/disable HTTP checks |
| `http_check_interval` | `60` | Seconds between check rounds |
| `http_services` | `[]` | Array of services to check (see below) |

### HTTP Service Format
```json
"http_services": [
  {
    "name": "My Web App",
    "url": "https://example.com",
    "method": "GET",
    "timeout": 10,
    "expected_status": 200,
    "headers": {}
  }
]
```

Only `name` and `url` are required. Defaults: method=GET, timeout=10s, expected_status=200.

### General
| Key | Default | Description |
|---|---|---|
| `heartbeat_interval` | `60` | Seconds between heartbeats |
| `log_level` | `INFO` | Agent log verbosity (DEBUG, INFO, WARNING, ERROR) |

## Daemon Threads

The agent runs 5 concurrent daemon threads:

1. **File Monitor** - Tails log files, buffers parsed entries
2. **Flush** - Sends buffered logs to the API in batches
3. **Heartbeat** - Pings the API so the dashboard knows the server is online
4. **VPS Metrics** - Collects and sends host system metrics
5. **Docker Monitor** - Discovers all containers and sends per-container metrics
6. **HTTP Monitor** - Checks configured endpoints and sends results

## Deployment

### Systemd Service (recommended)

```ini
[Unit]
Description=Platform Observability Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/platform-obs-agent
ExecStart=/opt/platform-obs-agent/venv/bin/python /opt/platform-obs-agent/agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo cp platform-obs-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable platform-obs-agent
sudo systemctl start platform-obs-agent
```

### Using install.sh

```bash
chmod +x install.sh
sudo ./install.sh
```

## API Endpoints Used

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/agent/log-sources/<id>/heartbeat/` | Heartbeat |
| POST | `/api/logs/ingest/` | Log entries |
| POST | `/api/core/agent/metrics/` | VPS host metrics |
| POST | `/api/core/agent/docker-metrics/` | Docker container metrics |
| POST | `/api/core/agent/http-checks/` | HTTP check results |
| GET | `/api/agent/log-sources/<id>/` | Config verification |

All agent endpoints authenticate via `Authorization: Bearer <api_token>`.

## Files

| File | Purpose |
|---|---|
| `agent.py` | Main agent with daemon threads and orchestration |
| `config.py` | JSON config loader with defaults and validation |
| `docker_monitor.py` | Docker container discovery and metrics collection |
| `http_monitor.py` | HTTP service availability checks with TLS inspection |
| `log_parser.py` | Log line parser (timestamp, level extraction) |
| `requirements.txt` | Python dependencies |
| `agent_config.json.example` | Example configuration file |
