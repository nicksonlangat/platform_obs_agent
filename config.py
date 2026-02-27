import json
import logging
import os
import socket
import uuid
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

AGENT_CONFIG_KEYS = (
    "metrics_interval",
    "docker_metrics_interval",
    "container_log_interval",
    "nginx_interval",
    "nginx_sources",
)

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
            "api_endpoint": "https://api.watchdock.cc/api",
            "api_token": "",
            "log_level": "INFO",
            "collect_metrics": True,
            "metrics_interval": 300,
            "collect_docker_metrics": True,
            "docker_metrics_interval": 60,
            "collect_container_logs": True,
            "container_log_interval": 30,
            "container_log_max_lines": 500,
            "nginx_interval": 60,
            "nginx_sources": []
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

    def fetch_server_config(self) -> bool:
        api_endpoint = self.config.get("api_endpoint", "").rstrip("/")
        api_token = self.config.get("api_token", "")
        if not api_endpoint or not api_token:
            return False

        try:
            response = requests.get(
                f"{api_endpoint}/agent/config/",
                headers={"Authorization": f"Bearer {api_token}"},
                params={"machine_id": self.get_machine_id()},
                timeout=10,
            )
            response.raise_for_status()
            server_config = response.json()

            updated = False
            for key in AGENT_CONFIG_KEYS:
                if key in server_config:
                    self.config[key] = server_config[key]
                    updated = True

            if updated:
                self._save_config(self.config)
                logger.info("Agent config updated from server (plan: %s)", server_config.get("plan", "unknown"))

            return True

        except Exception as exc:
            logger.warning("Could not fetch server config, using local defaults: %s", exc)
            return False

    def validate(self) -> bool:
        """Validate only api_token is required now (auto-discovery handles the rest)"""
        required_fields = ["api_endpoint", "api_token"]
        for field in required_fields:
            if not self.config.get(field):
                print(f"Missing required configuration: {field}")
                return False
        return True