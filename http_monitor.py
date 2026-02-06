#!/usr/bin/env python3
"""
HTTP service availability monitoring.
Checks configured HTTP endpoints and reports response time, status, and TLS info.
"""

import logging
import requests
import ssl
import socket
from typing import List, Dict, Optional
from datetime import datetime, timezone
from urllib.parse import urlparse


class HttpMonitor:
    """
    Checks configured HTTP endpoints for availability, response time, and TLS status.
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def check_all_services(self) -> List[Dict]:
        """
        Check all configured HTTP endpoints.
        Config format in agent_config.json:
        "http_services": [
            {
                "name": "My API",
                "url": "https://api.example.com/health",
                "method": "GET",
                "timeout": 10,
                "expected_status": 200,
                "headers": {}
            }
        ]
        """
        services = self.config.get('http_services', [])
        results = []

        for service in services:
            try:
                result = self._check_service(service)
                if result:
                    results.append(result)
            except Exception as e:
                self.logger.error(f"Error checking service {service.get('name', 'unknown')}: {e}")

        return results

    def _check_service(self, service: Dict) -> Optional[Dict]:
        """
        Perform a single HTTP check.
        """
        name = service.get('name', 'Unnamed')
        url = service.get('url')
        method = service.get('method', 'GET').upper()
        timeout = service.get('timeout', 10)
        expected_status = service.get('expected_status', 200)
        headers = service.get('headers', {})

        if not url:
            self.logger.warning(f"Skipping service '{name}': no URL configured")
            return None

        result = {
            'service_name': name,
            'url': url,
            'method': method,
            'is_available': False,
            'status_code': None,
            'status_category': 'error',
            'response_time_ms': None,
            'error_message': '',
            'tls_valid': None,
            'tls_expiry_days': None,
            'checked_at': datetime.now(timezone.utc).isoformat(),
        }

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                verify=True,
            )

            result['status_code'] = response.status_code
            result['response_time_ms'] = round(response.elapsed.total_seconds() * 1000, 2)
            result['status_category'] = self._get_status_category(response.status_code)
            result['is_available'] = response.status_code == expected_status

        except requests.exceptions.SSLError as e:
            result['error_message'] = f"SSL Error: {str(e)[:200]}"
            result['tls_valid'] = False

        except requests.exceptions.ConnectionError as e:
            result['error_message'] = f"Connection Error: {str(e)[:200]}"

        except requests.exceptions.Timeout:
            result['error_message'] = f"Timeout after {timeout}s"

        except requests.exceptions.RequestException as e:
            result['error_message'] = f"Request Error: {str(e)[:200]}"

        # Check TLS info for HTTPS URLs
        parsed = urlparse(url)
        if parsed.scheme == 'https':
            tls_info = self._get_tls_info(parsed.hostname, parsed.port or 443)
            if tls_info:
                result['tls_valid'] = tls_info.get('valid')
                result['tls_expiry_days'] = tls_info.get('expiry_days')

        return result

    def _get_status_category(self, status_code: int) -> str:
        """Categorize HTTP status code"""
        if 200 <= status_code < 300:
            return '2xx'
        elif 300 <= status_code < 400:
            return '3xx'
        elif 400 <= status_code < 500:
            return '4xx'
        elif 500 <= status_code < 600:
            return '5xx'
        return 'error'

    def _get_tls_info(self, hostname: str, port: int) -> Optional[Dict]:
        """Get TLS certificate information"""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    if cert:
                        # Parse expiry date
                        not_after = cert.get('notAfter')
                        if not_after:
                            expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                            expiry_days = (expiry - datetime.utcnow()).days
                            return {
                                'valid': True,
                                'expiry_days': expiry_days,
                            }
                        return {'valid': True, 'expiry_days': None}
        except ssl.SSLError:
            return {'valid': False, 'expiry_days': None}
        except Exception as e:
            self.logger.debug(f"Error getting TLS info for {hostname}: {e}")
            return None

    def send_check_results(self, results: List[Dict]) -> bool:
        """
        POST HTTP check results to the platform API.
        """
        try:
            api_token = self.config.get('api_token')
            api_endpoint = self.config.get('api_endpoint')
            log_source_id = self.config.get('log_source_id')

            payload = {
                'log_source_id': log_source_id,
                'collected_at': datetime.now(timezone.utc).isoformat(),
                'checks': results,
            }

            response = requests.post(
                f"{api_endpoint}/core/agent/http-checks/",
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_token}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )

            if response.status_code in (200, 201):
                self.logger.debug(f"HTTP check results sent: {len(results)} checks")
                return True
            else:
                self.logger.warning(f"Failed to send HTTP check results: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending HTTP check results: {e}")
            return False
