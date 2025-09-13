#!/usr/bin/env python3

import os
import time
import threading
import requests
import logging
import signal
import sys
import argparse
from datetime import datetime
from typing import List, Dict
from config import Config
from log_parser import LogParser

class ObservabilityAgent:
    def __init__(self):
        self.config = Config()
        self.parser = LogParser()
        self.running = False
        self.log_buffer = []
        self.file_positions = {}  # Track file positions for reliable reading
        
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
                        parsed_log['log_source_id'] = self.config.get('log_source_id')
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
        while self.running:
            try:
                api_token = self.config.get("api_token")
                response = requests.post(
                    f"{self.config.get('api_endpoint')}/agent/log-sources/{self.config.get('log_source_id')}/heartbeat/",
                    headers={'Authorization': f'Bearer {api_token}'},
                    timeout=10
                )

                # If authentication fails, try query parameter approach
                if response.status_code == 401:
                    response = requests.post(
                        f"{self.config.get('api_endpoint')}/agent/log-sources/{self.config.get('log_source_id')}/heartbeat/",
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
    
    def _signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}")
        self.stop()

def test_configuration():
    """Test agent configuration and connectivity"""
    try:
        # Test configuration loading
        config = Config()
        print("✓ Configuration file loaded successfully")

        # Test required fields
        required_fields = ['api_endpoint', 'api_token', 'log_source_id', 'log_files']
        for field in required_fields:
            if not config.get(field):
                print(f"✗ Missing required field: {field}")
                return False
        print("✓ All required fields present")

        # Test API connectivity
        print("Testing API connectivity...")
        api_token = config.get("api_token")

        # Try the new agent-specific endpoint first
        response = requests.get(
            f"{config.get('api_endpoint')}/agent/log-sources/{config.get('log_source_id')}/",
            headers={'Authorization': f'Bearer {api_token}'},
            timeout=10
        )

        # If that fails with 401/404, try query parameter approach
        if response.status_code in [401, 404]:
            print("Trying query parameter authentication...")
            response = requests.get(
                f"{config.get('api_endpoint')}/agent/log-sources/{config.get('log_source_id')}/",
                params={'api_key': api_token},
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