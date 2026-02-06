#!/usr/bin/env python3
"""
General-purpose Docker container monitoring.
Discovers all running containers and collects metrics for each.
"""

import json
import logging
import subprocess
import requests
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone


class DockerMonitor:
    """
    Discovers and monitors all Docker containers on the host.
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.docker_available = self._check_docker_availability()

    def _check_docker_availability(self) -> bool:
        """Check if Docker is available and accessible"""
        try:
            result = subprocess.run(
                ['docker', 'version', '--format', '{{.Server.Version}}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.logger.info(f"Docker detected: {result.stdout.strip()}")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        self.logger.debug("Docker not available or not accessible")
        return False

    def collect_all_containers(self) -> List[Dict]:
        """
        Discover ALL running containers and collect metrics for each.
        Returns list of container metric dicts.
        """
        if not self.docker_available:
            return []

        containers = []

        try:
            # List all containers (running + stopped)
            cmd = [
                'docker', 'ps', '-a', '--format',
                '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.State}}'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                self.logger.warning(f"Docker ps failed: {result.stderr}")
                return containers

            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue

                parts = line.split('\t')
                if len(parts) >= 5:
                    container_id = parts[0]
                    name = parts[1]
                    image = parts[2]
                    container_state = parts[4]  # running, exited, paused, etc.

                    metrics = self._collect_container_metrics(
                        container_id, name, image, container_state
                    )
                    if metrics:
                        containers.append(metrics)

        except subprocess.TimeoutExpired:
            self.logger.warning("Docker ps command timed out")
        except Exception as e:
            self.logger.error(f"Error collecting container list: {e}")

        return containers

    def _collect_container_metrics(self, container_id: str, name: str, image: str, state: str) -> Optional[Dict]:
        """
        Collect full metrics for a single container.
        Combines docker inspect + docker stats.
        """
        try:
            metrics = {
                'container_id': container_id,
                'container_name': name,
                'image': image,
                'status': state,
                'health_status': 'none',
                'exit_code': None,
                'started_at': None,
                'finished_at': None,
                'uptime_seconds': None,
                'restart_count': 0,
                'last_restart_reason': '',
                'cpu_usage_percent': None,
                'memory_usage_bytes': None,
                'memory_limit_bytes': None,
                'memory_usage_percent': None,
                'network_rx_bytes': None,
                'network_tx_bytes': None,
                'block_read_bytes': None,
                'block_write_bytes': None,
                'pids': None,
            }

            # Get inspect data (works for all containers)
            inspect_data = self._get_container_inspect(container_id)
            if inspect_data:
                metrics.update(inspect_data)

            # Get stats (only works for running containers)
            if state == 'running':
                stats_data = self._get_container_stats(container_id)
                if stats_data:
                    metrics.update(stats_data)

            return metrics

        except Exception as e:
            self.logger.error(f"Error collecting metrics for container {name}: {e}")
            return None

    def _get_container_inspect(self, container_id: str) -> Optional[Dict]:
        """
        Run docker inspect and extract state, health, restarts info.
        """
        try:
            cmd = ['docker', 'inspect', container_id]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)[0]
            state = data.get('State', {})
            config = data.get('Config', {})

            info = {}

            # Health status
            health = state.get('Health', {})
            if health:
                info['health_status'] = health.get('Status', 'none')
            else:
                info['health_status'] = 'none'

            # Timestamps
            started_at = state.get('StartedAt')
            if started_at and started_at != '0001-01-01T00:00:00Z':
                info['started_at'] = started_at
                # Calculate uptime
                try:
                    start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    uptime = (datetime.now(timezone.utc) - start_dt).total_seconds()
                    if uptime > 0:
                        info['uptime_seconds'] = int(uptime)
                except (ValueError, TypeError):
                    pass

            finished_at = state.get('FinishedAt')
            if finished_at and finished_at != '0001-01-01T00:00:00Z':
                info['finished_at'] = finished_at

            # Exit code
            info['exit_code'] = state.get('ExitCode')

            # Restart count
            info['restart_count'] = data.get('RestartCount', 0)

            # Last restart reason
            reasons = []
            if state.get('OOMKilled'):
                reasons.append('OOMKilled')
            if state.get('Error'):
                reasons.append(state['Error'])
            info['last_restart_reason'] = '; '.join(reasons)

            return info

        except Exception as e:
            self.logger.debug(f"Error inspecting container {container_id}: {e}")
            return None

    def _get_container_stats(self, container_id: str) -> Optional[Dict]:
        """
        Run docker stats --no-stream and parse CPU, memory, network, block I/O, PIDs.
        """
        try:
            cmd = [
                'docker', 'stats', '--no-stream', '--format',
                '{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}',
                container_id
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return None

            line = result.stdout.strip()
            if not line:
                return None

            parts = line.split('\t')
            if len(parts) < 6:
                return None

            stats = {}

            # CPU
            stats['cpu_usage_percent'] = self._parse_percentage(parts[0])

            # Memory usage/limit
            mem_parts = parts[1].split('/')
            if len(mem_parts) == 2:
                stats['memory_usage_bytes'] = self._parse_size_string(mem_parts[0].strip())
                stats['memory_limit_bytes'] = self._parse_size_string(mem_parts[1].strip())

            # Memory percent
            stats['memory_usage_percent'] = self._parse_percentage(parts[2])

            # Network I/O
            rx, tx = self._parse_io_pair(parts[3])
            stats['network_rx_bytes'] = rx
            stats['network_tx_bytes'] = tx

            # Block I/O
            bread, bwrite = self._parse_io_pair(parts[4])
            stats['block_read_bytes'] = bread
            stats['block_write_bytes'] = bwrite

            # PIDs
            try:
                stats['pids'] = int(parts[5].strip())
            except (ValueError, TypeError):
                pass

            return stats

        except subprocess.TimeoutExpired:
            self.logger.debug(f"Stats timeout for container {container_id}")
            return None
        except Exception as e:
            self.logger.debug(f"Error getting container stats: {e}")
            return None

    def _parse_percentage(self, perc_str: str) -> Optional[float]:
        """Parse percentage string like '15.34%' to float"""
        try:
            return float(perc_str.strip().rstrip('%'))
        except (ValueError, TypeError, AttributeError):
            return None

    def _parse_size_string(self, size_str: str) -> Optional[int]:
        """Parse Docker size strings like '1.5GiB', '500MiB', '2.3kB' to bytes"""
        try:
            size_str = size_str.strip()
            match = re.match(r'^([\d.]+)\s*([A-Za-z]+)$', size_str)
            if not match:
                return None

            value = float(match.group(1))
            unit = match.group(2).lower()

            multipliers = {
                'b': 1,
                'kb': 1000,
                'kib': 1024,
                'mb': 1000**2,
                'mib': 1024**2,
                'gb': 1000**3,
                'gib': 1024**3,
                'tb': 1000**4,
                'tib': 1024**4,
            }

            multiplier = multipliers.get(unit, 1)
            return int(value * multiplier)

        except (ValueError, TypeError, AttributeError):
            return None

    def _parse_io_pair(self, io_str: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse Docker I/O strings like '1.2MB / 3.4MB' into (in_bytes, out_bytes)"""
        try:
            parts = io_str.split('/')
            if len(parts) == 2:
                return (
                    self._parse_size_string(parts[0].strip()),
                    self._parse_size_string(parts[1].strip())
                )
        except (ValueError, TypeError, AttributeError):
            pass
        return (None, None)

    def send_container_metrics(self, containers: List[Dict]) -> bool:
        """
        POST container metrics to the platform API.
        """
        try:
            api_token = self.config.get('api_token')
            api_endpoint = self.config.get('api_endpoint')
            log_source_id = self.config.get('log_source_id')

            payload = {
                'log_source_id': log_source_id,
                'collected_at': datetime.now(timezone.utc).isoformat(),
                'containers': containers,
            }

            response = requests.post(
                f"{api_endpoint}/core/agent/docker-metrics/",
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_token}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )

            if response.status_code in (200, 201):
                self.logger.debug(f"Docker metrics sent: {len(containers)} containers")
                return True
            else:
                self.logger.warning(f"Failed to send Docker metrics: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending Docker metrics: {e}")
            return False
