#!/usr/bin/env python3
"""
Docker container log collector.
Tails all container logs (stdout + stderr), detects tracebacks,
and sends them to the WatchDock backend for processing and incident creation.
"""

import logging
import re
import subprocess
import requests
from datetime import datetime, timezone
from typing import Dict, List, Tuple


class ContainerLogCollector:
    """
    Collects all Docker container logs (stdout + stderr).
    Groups multiline Python tracebacks into single entries.
    """

    # Pattern to detect start of a Python traceback
    TRACEBACK_START = re.compile(r'^Traceback \(most recent call last\):')

    # Pattern to detect the exception line at the end of a traceback
    EXCEPTION_LINE = re.compile(r'^(\w[\w.]*(?:Error|Exception|Warning|Fault))\b')

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        # Track last read time per container to only fetch new logs
        self._last_timestamps: Dict[str, str] = {}

    def collect_logs(self) -> List[Dict]:
        """
        Discover running containers and collect relevant log lines from each.
        Returns a list of log entry dicts ready to send to the backend.
        """
        containers = self._get_running_containers()
        all_logs = []

        max_lines = self.config.get('container_log_max_lines', 500)

        for container_id, name, image in containers:
            try:
                logs = self._collect_container_logs(container_id, name, image, max_lines)
                all_logs.extend(logs)
            except Exception as e:
                self.logger.error(f"Error collecting logs from {name}: {e}")

        return all_logs

    def _get_running_containers(self) -> List[Tuple[str, str, str]]:
        """Get list of running containers: (id, name, image)"""
        try:
            cmd = [
                'docker', 'ps', '--format',
                '{{.ID}}\t{{.Names}}\t{{.Image}}'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                self.logger.warning(f"docker ps failed: {result.stderr}")
                return []

            containers = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                parts = line.split('\t')
                if len(parts) >= 3:
                    containers.append((parts[0], parts[1], parts[2]))
            return containers

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.warning(f"Failed to list containers: {e}")
            return []

    def _collect_container_logs(
        self, container_id: str, name: str, image: str, max_lines: int
    ) -> List[Dict]:
        """
        Collect logs from a single container using docker logs.
        Uses --since to only get new logs since last collection.
        """
        # Build the docker logs command
        cmd = ['docker', 'logs', '--timestamps']

        # Use --since to only get new logs
        last_ts = self._last_timestamps.get(container_id)
        if last_ts:
            cmd.extend(['--since', last_ts])
        else:
            # First run: only get last 30 seconds of logs
            cmd.extend(['--since', '30s'])

        cmd.extend(['--tail', str(max_lines), container_id])

        try:
            # Run docker logs, capturing stdout and stderr separately
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired:
            self.logger.warning(f"docker logs timed out for {name}")
            return []

        # Update last timestamp for next collection
        self._last_timestamps[container_id] = datetime.now(timezone.utc).isoformat()

        entries = []

        if result.stderr:
            entries.extend(self._process_log_output(
                result.stderr, container_id, name, image, stream="stderr"
            ))

        if result.stdout:
            entries.extend(self._process_log_output(
                result.stdout, container_id, name, image, stream="stdout"
            ))

        return entries

    def _process_log_output(
        self,
        output: str,
        container_id: str,
        name: str,
        image: str,
        stream: str,
    ) -> List[Dict]:
        """
        Process raw docker logs output into structured entries.
        Groups multiline tracebacks into single entries.
        """
        lines = output.strip().split('\n')
        entries = []

        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue

            # Extract timestamp from docker logs --timestamps format
            # Format: 2026-02-17T10:30:00.123456789Z log message here
            timestamp, log_text = self._extract_timestamp(line)

            # Check if this starts a traceback
            if self.TRACEBACK_START.search(log_text):
                # Collect the full traceback
                traceback_lines = [log_text]
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    _, next_text = self._extract_timestamp(next_line)

                    # Continue collecting until we hit the exception line
                    traceback_lines.append(next_text)

                    if self.EXCEPTION_LINE.match(next_text.strip()):
                        i += 1
                        break
                    i += 1

                full_traceback = '\n'.join(traceback_lines)
                entries.append({
                    'container_id': container_id,
                    'container_name': name,
                    'image': image,
                    'log': full_traceback,
                    'stream': stream,
                    'timestamp': timestamp,
                    'is_traceback': True,
                })
                continue

            entries.append({
                'container_id': container_id,
                'container_name': name,
                'image': image,
                'log': log_text,
                'stream': stream,
                'timestamp': timestamp,
                'is_traceback': False,
            })

            i += 1

        return entries

    def _extract_timestamp(self, line: str) -> Tuple[str, str]:
        """
        Extract timestamp from a docker logs --timestamps line.
        Returns (iso_timestamp, log_text).
        """
        # Docker timestamp format: 2026-02-17T10:30:00.123456789Z
        ts_pattern = re.compile(
            r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?)\s+(.*)'
        )
        match = ts_pattern.match(line)
        if match:
            ts_str = match.group(1)
            log_text = match.group(2)
            # Truncate nanoseconds to microseconds for Python compatibility
            if '.' in ts_str:
                base, frac = ts_str.rstrip('Z').split('.')
                frac = frac[:6]  # Keep only 6 decimal places
                ts_str = f"{base}.{frac}Z"
            return ts_str, log_text

        # No timestamp found, use current time
        return datetime.now(timezone.utc).isoformat(), line

    def send_logs(self, logs: List[Dict]) -> bool:
        """
        Send collected logs to the WatchDock backend.
        POST /core/agent/container-logs/
        """
        if not logs:
            return True

        try:
            api_token = self.config.get('api_token')
            api_endpoint = self.config.get('api_endpoint')

            payload = {
                'machine_id': self.config.get_machine_id(),
                'hostname': self.config.get_hostname(),
                'logs': logs,
            }

            response = requests.post(
                f"{api_endpoint}/core/agent/container-logs/",
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_token}',
                    'Content-Type': 'application/json'
                },
                timeout=30,
            )

            if response.status_code in (200, 201):
                self.logger.debug(f"Container logs sent: {len(logs)} entries")
                return True
            else:
                self.logger.warning(
                    f"Failed to send container logs: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Error sending container logs: {e}")
            return False
