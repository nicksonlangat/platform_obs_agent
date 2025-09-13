# Observability Platform Agent

A lightweight Python agent for collecting and forwarding log data to the Observability Platform.

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Copy and configure the agent:
```bash
cp agent_config.json.example agent_config.json
# Edit agent_config.json with your settings
```

3. Run the agent:
```bash
python agent.py
```

## Configuration

Edit `agent_config.json`:

- `api_endpoint`: Platform API URL
- `api_token`: JWT authentication token
- `log_source_id`: UUID of your log source (get from platform)
- `log_files`: Array of log file paths to monitor
- `heartbeat_interval`: Seconds between heartbeats (default: 60)
- `batch_size`: Logs per batch (default: 100)
- `flush_interval`: Seconds between flushes (default: 10)
- `log_level`: Agent logging level

## Features

- Real-time log file monitoring
- Automatic log parsing (timestamp, level extraction)
- Batch processing for efficiency
- Heartbeat monitoring for uptime tracking
- Configurable retry logic
- Signal handling for graceful shutdown

## Deployment

### Systemd Service (Linux)
```bash
sudo cp observability-agent.service /etc/systemd/system/
sudo systemctl enable observability-agent
sudo systemctl start observability-agent
```

### Docker
```bash
docker build -t observability-agent .
docker run -d --name agent -v /var/log:/var/log:ro observability-agent
```