#!/usr/bin/env python3

import os
import time
import threading
import requests
import logging
import signal
import sys
import argparse
import platform
import socket
from datetime import datetime, timezone
from typing import List, Dict
from config import Config
from log_parser import LogParser

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Server metrics collection will be disabled.")
    print("Install psutil with: pip install psutil")

try:
    from docker_monitor import DockerMonitor
    DOCKER_MONITOR_AVAILABLE = True
except ImportError:
    DOCKER_MONITOR_AVAILABLE = False
    print("Warning: Docker monitor not available.")

class ObservabilityAgent:
    def __init__(self):
        self.config = Config()
        self.parser = LogParser()
        self.running = False
        self.log_buffer = []
        self.file_positions = {}  # Track file positions for reliable reading

        # Initialize Docker monitor if available
        if DOCKER_MONITOR_AVAILABLE:
            self.docker_monitor = DockerMonitor(self.config)
        else:
            self.docker_monitor = None

        logging.basicConfig(
            level=getattr(logging, self.config.get('log_level', 'INFO')),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def start(self):
        if not self.config.validate():
            self.logger.error("Invalid configuration. Please check agent_config.json")
            sys.exit(1)
        
        self.running = True
        self.logger.info("Starting Observability Agent...")
        
        # Initialize file positions
        self._initialize_file_positions()

        # Start file monitoring thread
        monitor_thread = threading.Thread(target=self._monitor_files)
        monitor_thread.daemon = True
        monitor_thread.start()

        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()

        # Start flush thread
        flush_thread = threading.Thread(target=self._flush_loop)
        flush_thread.daemon = True
        flush_thread.start()

        # Start metrics collection thread (if enabled and psutil available)
        if self.config.get('collect_metrics', True) and PSUTIL_AVAILABLE:
            metrics_thread = threading.Thread(target=self._metrics_loop)
            metrics_thread.daemon = True
            metrics_thread.start()
            self.logger.info("Server metrics collection enabled")
        else:
            self.logger.info("Server metrics collection disabled")

        # Start Docker monitoring thread (if enabled and available)
        if (self.config.get('collect_docker_metrics', True) and
            DOCKER_MONITOR_AVAILABLE and self.docker_monitor and
            self.docker_monitor.docker_available):
            docker_thread = threading.Thread(target=self._docker_monitoring_loop)
            docker_thread.daemon = True
            docker_thread.start()
            self.logger.info("Docker container monitoring enabled")
        else:
            self.logger.info("Docker container monitoring disabled")

        # Main loop
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        self.logger.info("Stopping Observability Agent...")
        self.running = False

        # Final flush
        self._flush_logs()

        self.logger.info("Agent stopped")
    
    def _initialize_file_positions(self):
        """Initialize file positions - start from end for existing files"""
        log_files = self.config.get('log_files', [])
        for log_file in log_files:
            try:
                if os.path.exists(log_file) and os.access(log_file, os.R_OK):
                    with open(log_file, 'r') as f:
                        f.seek(0, 2)  # Go to end of file
                        self.file_positions[log_file] = f.tell()
                    self.logger.info(f"Monitoring log file: {log_file}")
                else:
                    self.logger.warning(f"Log file not accessible: {log_file}")
                    self.file_positions[log_file] = 0
            except Exception as e:
                self.logger.error(f"Error initializing file position for {log_file}: {e}")
                self.file_positions[log_file] = 0

    def _monitor_files(self):
        """Continuously monitor log files for new content"""
        poll_interval = self.config.get('poll_interval', 2)  # Poll every 2 seconds

        while self.running:
            try:
                for log_file in self.config.get('log_files', []):
                    self._check_file_for_new_content(log_file)

                time.sleep(poll_interval)
            except Exception as e:
                self.logger.error(f"Error in file monitoring loop: {e}")
                time.sleep(5)  # Back off on error

    def _check_file_for_new_content(self, file_path: str):
        """Check a single file for new content and process new lines"""
        try:
            if not os.path.exists(file_path):
                return

            current_size = os.path.getsize(file_path)
            last_position = self.file_positions.get(file_path, 0)

            # Check if file was truncated (log rotation)
            if current_size < last_position:
                self.logger.info(f"Log rotation detected for {file_path}")
                last_position = 0

            # No new content
            if current_size <= last_position:
                return

            # Read new content
            with open(file_path, 'r') as f:
                f.seek(last_position)

                lines_processed = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parsed_log = self.parser.parse_line(line)
                        parsed_log['machine_id'] = self.config.get_machine_id()
                        parsed_log['hostname'] = self.config.get_hostname()

                        # Add source file to metadata
                        if 'metadata' not in parsed_log:
                            parsed_log['metadata'] = {}
                        parsed_log['metadata']['source_file'] = file_path

                        self.log_buffer.append(parsed_log)
                        lines_processed += 1

                        # Flush if buffer is full
                        if len(self.log_buffer) >= self.config.get('batch_size', 100):
                            self._flush_logs()

                    except Exception as e:
                        self.logger.debug(f"Failed to parse log line: {e}")

                # Update file position
                self.file_positions[file_path] = f.tell()

                if lines_processed > 0:
                    self.logger.debug(f"Processed {lines_processed} new log lines from {file_path}")

        except Exception as e:
            self.logger.error(f"Error checking file {file_path}: {e}")
    
    def _flush_logs(self):
        if not self.log_buffer:
            return
        
        try:
            logs_to_send = self.log_buffer.copy()
            self.log_buffer.clear()
            
            # Convert datetime objects to ISO format strings
            for log in logs_to_send:
                if isinstance(log['timestamp'], datetime):
                    log['timestamp'] = log['timestamp'].isoformat()
            
            api_token = self.config.get("api_token")
            response = requests.post(
                f"{self.config.get('api_endpoint')}/logs/ingest/",
                json=logs_to_send,
                headers={
                    'Authorization': f'Bearer {api_token}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )

            # If authentication fails, try query parameter approach
            if response.status_code == 401:
                response = requests.post(
                    f"{self.config.get('api_endpoint')}/logs/ingest/",
                    json=logs_to_send,
                    params={'api_key': api_token},
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
            
            if response.status_code == 201:
                self.logger.debug(f"Successfully sent {len(logs_to_send)} log entries")
            else:
                self.logger.error(f"Failed to send logs: {response.status_code} - {response.text}")
                # Re-add logs to buffer for retry
                self.log_buffer.extend(logs_to_send)
        
        except Exception as e:
            self.logger.error(f"Error sending logs: {e}")
            # Re-add logs to buffer for retry
            self.log_buffer.extend(logs_to_send)
    
    def _flush_loop(self):
        while self.running:
            time.sleep(self.config.get('flush_interval', 10))
            self._flush_logs()
    
    def _heartbeat_loop(self):
        """Legacy heartbeat (only used if log_source_id is configured)"""
        # Skip heartbeat if using auto-discovery (machine_id mode)
        # Metrics endpoint already updates last_seen
        log_source_id = self.config.get('log_source_id')
        if not log_source_id:
            self.logger.info("Heartbeat disabled (using auto-discovery mode)")
            return

        while self.running:
            try:
                api_token = self.config.get("api_token")
                response = requests.post(
                    f"{self.config.get('api_endpoint')}/agent/log-sources/{log_source_id}/heartbeat/",
                    headers={'Authorization': f'Bearer {api_token}'},
                    timeout=10
                )

                # If authentication fails, try query parameter approach
                if response.status_code == 401:
                    response = requests.post(
                        f"{self.config.get('api_endpoint')}/agent/log-sources/{log_source_id}/heartbeat/",
                        params={'api_key': api_token},
                        timeout=10
                    )

                if response.status_code == 200:
                    self.logger.debug("Heartbeat sent successfully")
                else:
                    self.logger.warning(f"Heartbeat failed: {response.status_code}")

            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")

            time.sleep(self.config.get('heartbeat_interval', 60))

    def _collect_server_metrics(self) -> Dict:
        """Collect server metrics using psutil"""
        if not PSUTIL_AVAILABLE:
            return {}

        metrics = {
            'machine_id': self.config.get_machine_id(),
            'hostname': self.config.get_hostname(),
            'collected_at': datetime.now(timezone.utc).isoformat(),
            'agent_version': '1.0.0'
        }

        try:
            # Network information
            try:
                # Get the actual server IP (the one that would be used for SSH)
                server_ip = self._get_server_ip()
                if server_ip:
                    metrics['ip_address'] = server_ip

                # Get public IP
                public_ip = self._get_public_ip()
                if public_ip:
                    metrics['public_ip'] = public_ip
            except Exception as e:
                self.logger.debug(f"Error collecting network info: {e}")

            # System information
            try:
                uname = platform.uname()
                boot_time = psutil.boot_time()
                uptime_seconds = int(time.time() - boot_time)

                metrics.update({
                    'os_name': uname.system,
                    'os_version': uname.release,
                    'kernel_version': uname.version,
                    'architecture': uname.machine,
                    'uptime_seconds': uptime_seconds
                })
            except Exception as e:
                self.logger.debug(f"Error collecting system info: {e}")

            # CPU metrics
            try:
                metrics.update({
                    'cpu_count': psutil.cpu_count(),
                    'cpu_usage_percent': psutil.cpu_percent(interval=1)
                })

                # Load averages (Unix-like systems only)
                try:
                    load_avg = psutil.getloadavg()
                    metrics.update({
                        'load_average_1m': load_avg[0],
                        'load_average_5m': load_avg[1],
                        'load_average_15m': load_avg[2]
                    })
                except (AttributeError, OSError):
                    pass
            except Exception as e:
                self.logger.debug(f"Error collecting CPU metrics: {e}")

            # Memory metrics
            try:
                memory = psutil.virtual_memory()
                metrics.update({
                    'memory_total': memory.total,
                    'memory_available': memory.available,
                    'memory_used': memory.used,
                    'memory_usage_percent': memory.percent
                })
            except Exception as e:
                self.logger.debug(f"Error collecting memory metrics: {e}")

            # Swap metrics
            try:
                swap = psutil.swap_memory()
                metrics.update({
                    'swap_total': swap.total,
                    'swap_used': swap.used,
                    'swap_usage_percent': swap.percent
                })
            except Exception as e:
                self.logger.debug(f"Error collecting swap metrics: {e}")

            # Disk metrics
            try:
                # Use root directory, or C:\ on Windows
                path = 'C:\\' if platform.system() == 'Windows' else '/'
                disk = psutil.disk_usage(path)
                metrics.update({
                    'disk_total': disk.total,
                    'disk_used': disk.used,
                    'disk_available': disk.free,
                    'disk_usage_percent': (disk.used / disk.total) * 100 if disk.total > 0 else 0
                })
            except Exception as e:
                self.logger.debug(f"Error collecting disk metrics: {e}")

            # Process and network metrics
            try:
                metrics['process_count'] = len(psutil.pids())

                net_io = psutil.net_io_counters()
                metrics.update({
                    'network_bytes_sent': net_io.bytes_sent,
                    'network_bytes_received': net_io.bytes_recv
                })
            except Exception as e:
                self.logger.debug(f"Error collecting process/network metrics: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting server metrics: {e}")

        return metrics

    def _send_server_metrics(self):
        """Send server metrics to the API"""
        try:
            metrics = self._collect_server_metrics()
            if not metrics:
                return

            api_token = self.config.get("api_token")
            response = requests.post(
                f"{self.config.get('api_endpoint')}/core/agent/metrics/",
                json=metrics,
                headers={
                    'Authorization': f'Bearer {api_token}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )

            if response.status_code == 201:
                self.logger.debug("Server metrics sent successfully")
            else:
                self.logger.warning(f"Failed to send metrics: {response.status_code} - {response.text}")

        except Exception as e:
            self.logger.error(f"Error sending server metrics: {e}")

    def _metrics_loop(self):
        """Periodically send server metrics"""
        metrics_interval = self.config.get('metrics_interval', 300)  # Default 5 minutes
        self.logger.info(f"Starting metrics collection loop (interval: {metrics_interval}s)")

        while self.running:
            try:
                self._send_server_metrics()
                time.sleep(metrics_interval)
            except Exception as e:
                self.logger.error(f"Error in metrics loop: {e}")
                time.sleep(60)  # Back off on error

    def _get_server_ip(self) -> str:
        """Get the actual server IP address that would be used for external connections"""
        try:
            # Method 1: Connect to a remote address to see which local IP is used
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Use Google's DNS server as target (doesn't actually send data)
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            pass

        try:
            # Method 2: Get all network interfaces and find the first non-loopback IP
            if PSUTIL_AVAILABLE:
                for interface, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if (addr.family == socket.AF_INET and
                            not addr.address.startswith('127.') and
                            not addr.address.startswith('169.254.')):  # Skip loopback and link-local
                            return addr.address
        except:
            pass

        try:
            # Method 3: Fallback to hostname resolution
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except:
            return None

    def _get_public_ip(self) -> str:
        """Get the public IP address using external services"""
        services = [
            'https://api.ipify.org?format=text',
            'https://checkip.amazonaws.com',
            'https://ipecho.net/plain',
            'https://icanhazip.com'
        ]

        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    ip = response.text.strip()
                    # Basic validation that it looks like an IP
                    if len(ip.split('.')) == 4:
                        return ip
            except:
                continue

        return None

    def _docker_monitoring_loop(self):
        """Periodically collect and send Docker container metrics"""
        interval = self.config.get('docker_metrics_interval', 60)
        self.logger.info(f"Starting Docker monitoring loop (interval: {interval}s)")

        while self.running:
            try:
                containers = self.docker_monitor.collect_all_containers()
                if containers:
                    self.docker_monitor.send_container_metrics(containers)
                    self.logger.debug(f"Sent metrics for {len(containers)} containers")
            except Exception as e:
                self.logger.error(f"Error in Docker monitoring loop: {e}")
            time.sleep(interval)

    def _signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}")
        self.stop()

def test_configuration():
    """Test agent configuration and connectivity"""
    try:
        # Test configuration loading
        config = Config()
        print("✓ Configuration file loaded successfully")

        # Test required fields (log_source_id no longer required - using auto-discovery)
        required_fields = ['api_endpoint', 'api_token']
        for field in required_fields:
            if not config.get(field):
                print(f"✗ Missing required field: {field}")
                return False
        print("✓ All required fields present")

        # Show machine identification
        print(f"  Machine ID: {config.get_machine_id()}")
        print(f"  Hostname: {config.get_hostname()}")

        # Test API connectivity by sending a test metric
        print("Testing API connectivity...")
        api_token = config.get("api_token")

        # Test with a simple metrics payload (auto-discovery will create log source)
        test_payload = {
            'machine_id': config.get_machine_id(),
            'hostname': config.get_hostname(),
            'collected_at': datetime.now(timezone.utc).isoformat(),
            'cpu_usage_percent': 0,
            'memory_usage_percent': 0,
            'disk_usage_percent': 0
        }

        response = requests.post(
            f"{config.get('api_endpoint')}/core/agent/metrics/",
            headers={'Authorization': f'Bearer {api_token}'},
            json=test_payload,
            timeout=10
        )

        # If that fails with 401, try query parameter approach
        if response.status_code == 401:
            print("Trying query parameter authentication...")
            response = requests.post(
                f"{config.get('api_endpoint')}/core/agent/metrics/",
                params={'api_key': api_token},
                json=test_payload,
                timeout=10
            )

        if response.status_code == 200:
            print("✓ API connection successful")
        else:
            print(f"✗ API connection failed: {response.status_code}")
            return False

        # Test log files access
        log_files = config.get('log_files', [])
        accessible_files = 0
        for log_file in log_files:
            if os.path.exists(log_file) and os.access(log_file, os.R_OK):
                print(f"✓ Log file accessible: {log_file}")
                accessible_files += 1
            else:
                print(f"⚠ Log file not accessible: {log_file}")

        if accessible_files == 0:
            print("✗ No log files are accessible")
            return False

        print(f"✓ Configuration test passed ({accessible_files}/{len(log_files)} log files accessible)")
        return True

    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Platform Observability Agent')
    parser.add_argument('--test-config', action='store_true',
                       help='Test configuration and exit')
    parser.add_argument('--config', default='agent_config.json',
                       help='Configuration file path (default: agent_config.json)')

    args = parser.parse_args()

    if args.test_config:
        success = test_configuration()
        sys.exit(0 if success else 1)

    # Normal operation
    agent = ObservabilityAgent()
    agent.start()

if __name__ == "__main__":
    main()