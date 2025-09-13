import re
from datetime import datetime
from typing import Dict, Optional
from dateutil import parser as date_parser

class LogParser:
    def __init__(self):
        self.patterns = {
            'timestamp': [
                r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
                r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
                r'(\w{3} \d{2} \d{2}:\d{2}:\d{2})',
            ],
            'level': [
                r'\b(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\b',
                r'\[(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\]',
            ]
        }
    
    def parse_line(self, line: str) -> Dict[str, any]:
        parsed = {
            'timestamp': datetime.now(),
            'level': 'INFO',
            'message': line.strip(),
            'raw_message': line.strip(),
            'metadata': {}
        }
        
        timestamp = self._extract_timestamp(line)
        if timestamp:
            parsed['timestamp'] = timestamp
        
        level = self._extract_level(line)
        if level:
            parsed['level'] = level
        
        return parsed
    
    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        for pattern in self.patterns['timestamp']:
            match = re.search(pattern, line)
            if match:
                try:
                    return date_parser.parse(match.group(1))
                except:
                    continue
        return None
    
    def _extract_level(self, line: str) -> Optional[str]:
        for pattern in self.patterns['level']:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                level = match.group(1).upper()
                if level == 'WARN':
                    level = 'WARNING'
                elif level == 'FATAL':
                    level = 'CRITICAL'
                return level
        return None