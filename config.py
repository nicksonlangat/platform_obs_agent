import json
import os
from typing import Dict, Any

class Config:
    def __init__(self, config_file: str = "agent_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        
        default_config = {
            "api_endpoint": "http://localhost:8000/api",
            "api_token": "",
            "log_source_id": "",
            "log_files": [],
            "heartbeat_interval": 60,
            "batch_size": 100,
            "flush_interval": 10,
            "log_level": "INFO"
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
    
    def validate(self) -> bool:
        required_fields = ["api_endpoint", "api_token", "log_source_id"]
        for field in required_fields:
            if not self.config.get(field):
                print(f"Missing required configuration: {field}")
                return False
        return True