import json
import os
import socket
import uuid
from typing import Dict, Any

class Config:
    def __init__(self, config_file: str = "agent_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        self._machine_id = None
        self._hostname = None

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)

        default_config = {
            "api_endpoint": "http://localhost:8000/api",
            "api_token": "",
            "log_files": [],
            "heartbeat_interval": 60,
            "batch_size": 100,
            "flush_interval": 10,
            "log_level": "INFO",
            "collect_metrics": True,
            "metrics_interval": 300,
            "collect_docker_metrics": True,
            "docker_metrics_interval": 60,
            "collect_http_checks": True,
            "http_check_interval": 60,
            "http_services": []
        }

        self._save_config(default_config)
        return default_config

    def _save_config(self, config: Dict[str, Any]):
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self._save_config(self.config)

    def get_machine_id(self) -> str:
        """
        Get unique machine identifier. Tries multiple methods:
        1. /etc/machine-id (Linux)
        2. /var/lib/dbus/machine-id (Linux)
        3. Generated UUID based on hostname + MAC address (fallback)
        """
        if self._machine_id:
            return self._machine_id

        # Try Linux machine-id files
        machine_id_paths = ['/etc/machine-id', '/var/lib/dbus/machine-id']
        for path in machine_id_paths:
            try:
                with open(path, 'r') as f:
                    self._machine_id = f.read().strip()
                    return self._machine_id
            except (FileNotFoundError, PermissionError):
                continue

        # Fallback: Generate stable ID from hostname
        hostname = self.get_hostname()
        self._machine_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, hostname))
        return self._machine_id

    def get_hostname(self) -> str:
        """Get the system hostname"""
        if self._hostname:
            return self._hostname

        # Check config first
        hostname = self.config.get('hostname')
        if hostname:
            self._hostname = hostname
            return hostname

        # Get from system
        try:
            self._hostname = socket.gethostname()
        except Exception:
            self._hostname = 'unknown-host'

        return self._hostname

    def validate(self) -> bool:
        """Validate only api_token is required now (auto-discovery handles the rest)"""
        required_fields = ["api_endpoint", "api_token"]
        for field in required_fields:
            if not self.config.get(field):
                print(f"Missing required configuration: {field}")
                return False
        return True