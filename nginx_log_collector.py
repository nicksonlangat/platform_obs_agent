#!/usr/bin/env python3
"""
Nginx log collector.
Tails nginx access and error log files, parses lines using the watchdock log format,
aggregates access data into 1-minute buckets per endpoint, and sends to WatchDock.
"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests


# Watchdock access log format:
# $remote_addr [$time_local] "$request" $status $body_bytes_sent $request_time $upstream_response_time
# Example: 203.0.113.1 [26/Feb/2026:10:23:01 +0000] "GET /api/ HTTP/1.1" 200 1234 0.043 0.041
ACCESS_LOG_RE = re.compile(
    r'^(\S+) \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d+) (\d+) ([\d.]+|-) ([\d.]+|-)'
)

# Nginx error log format:
# 2026/02/26 10:23:01 [error] 12345#0: *1 message
# 2026/02/26 10:23:01 [warn]  12345#0: message (no asterisk prefix)
ERROR_LOG_RE = re.compile(
    r'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] \d+#\d+: (?:\*\d+ )?(.+)$'
)


class NginxLogCollector:
    """
    Reads nginx access and error log files for each configured NginxLogSource,
    parses new lines since the last collection, aggregates access data into
    1-minute buckets, and sends them to the WatchDock backend.
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        # Byte offsets keyed by file path. Each unique path is read once per
        # cycle and its lines distributed to all sources that reference it.
        self._file_positions: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def collect_and_send(self) -> None:
        """
        Called once per nginx_interval. For every configured NginxLogSource,
        reads new lines from its access and error log files, aggregates/parses
        them, and sends to the backend.
        """
        nginx_sources = self.config.get("nginx_sources", [])
        if not nginx_sources:
            return

        # Read each unique file path exactly once per cycle.
        access_lines_by_path: Dict[str, List[str]] = {}
        error_lines_by_path: Dict[str, List[str]] = {}

        for source in nginx_sources:
            for store, path in [
                (access_lines_by_path, source["access_log_path"]),
                (error_lines_by_path, source["error_log_path"]),
            ]:
                if path not in store:
                    store[path] = self._read_new_lines(path)

        # Process each source with its collected lines.
        for source in nginx_sources:
            source_id = source["id"]
            prefix = source.get("filter_path_prefix", "")

            access_lines = access_lines_by_path.get(source["access_log_path"], [])
            buckets = self._aggregate_access_lines(access_lines, prefix)
            if buckets:
                self._send_access_metrics(source_id, buckets)

            error_lines = error_lines_by_path.get(source["error_log_path"], [])
            events = self._parse_error_lines(error_lines)
            if events:
                self._send_error_events(source_id, events)

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    def _read_new_lines(self, path: str) -> List[str]:
        """
        Read new lines from a log file since the last recorded offset.
        Handles log rotation by resetting to offset 0 when the file shrinks.
        Returns an empty list if the file does not exist or cannot be read.
        """
        if not os.path.exists(path):
            return []

        try:
            current_size = os.path.getsize(path)
            last_position = self._file_positions.get(path, 0)

            # Log rotation: file is smaller than our last position.
            if current_size < last_position:
                self.logger.info(f"Nginx log rotation detected: {path}")
                last_position = 0

            # No new content.
            if current_size <= last_position:
                return []

            lines: List[str] = []
            with open(path, "r", errors="replace") as f:
                f.seek(last_position)
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        lines.append(stripped)
                self._file_positions[path] = f.tell()

            return lines

        except Exception as e:
            self.logger.error(f"Error reading nginx log file {path}: {e}")
            return []

    # ------------------------------------------------------------------
    # Access log parsing & aggregation
    # ------------------------------------------------------------------

    def _parse_access_line(self, line: str) -> Optional[dict]:
        """
        Parse a single watchdock-format access log line.
        Returns a dict with parsed fields, or None if the line doesn't match.
        """
        match = ACCESS_LOG_RE.match(line)
        if not match:
            return None

        _, time_local, method, raw_path, status_str, bytes_str, rt_str, up_str = (
            match.group(1),
            match.group(2),
            match.group(3),
            match.group(4),
            match.group(5),
            match.group(6),
            match.group(7),
            match.group(8),
        )

        # Parse timestamp. Format: 26/Feb/2026:10:23:01 +0000
        try:
            ts = datetime.strptime(time_local, "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            return None

        # Truncate to 1-minute bucket.
        bucket_time = ts.replace(second=0, microsecond=0)

        # Strip query string from path.
        endpoint = urlparse(raw_path).path

        # Parse numeric fields.
        status = int(status_str)
        bytes_sent = int(bytes_str)
        request_time = float(rt_str) if rt_str != "-" else None
        upstream_time = float(up_str) if up_str != "-" else None

        return {
            "bucket_time": bucket_time,
            "endpoint": endpoint,
            "method": method.upper(),
            "status": status,
            "bytes_sent": bytes_sent,
            "request_time": request_time,   # seconds
            "upstream_time": upstream_time,  # seconds
        }

    def _aggregate_access_lines(
        self, lines: List[str], prefix: str
    ) -> List[dict]:
        """
        Parse lines, filter by prefix, and aggregate into 1-minute buckets.
        Returns a list of bucket dicts ready for the backend payload.
        """
        # buckets keyed by (bucket_time_iso, endpoint, method)
        buckets: Dict[Tuple[str, str, str], dict] = {}

        for line in lines:
            parsed = self._parse_access_line(line)
            if parsed is None:
                continue

            endpoint = parsed["endpoint"]

            # Apply path prefix filter (agent side).
            if prefix and not endpoint.startswith(prefix):
                continue

            bucket_time_iso = parsed["bucket_time"].isoformat()
            key = (bucket_time_iso, endpoint, parsed["method"])

            if key not in buckets:
                buckets[key] = {
                    "bucket_time": bucket_time_iso,
                    "endpoint": endpoint,
                    "method": parsed["method"],
                    "status_2xx": 0,
                    "status_3xx": 0,
                    "status_4xx": 0,
                    "status_5xx": 0,
                    "request_count": 0,
                    "_response_times": [],
                    "_upstream_times": [],
                    "total_bytes_sent": 0,
                }

            b = buckets[key]
            b["request_count"] += 1
            b["total_bytes_sent"] += parsed["bytes_sent"]

            status_group = parsed["status"] // 100
            if status_group == 2:
                b["status_2xx"] += 1
            elif status_group == 3:
                b["status_3xx"] += 1
            elif status_group == 4:
                b["status_4xx"] += 1
            elif status_group == 5:
                b["status_5xx"] += 1

            if parsed["request_time"] is not None:
                b["_response_times"].append(parsed["request_time"])
            if parsed["upstream_time"] is not None:
                b["_upstream_times"].append(parsed["upstream_time"])

        return [self._finalize_bucket(b) for b in buckets.values()]

    def _finalize_bucket(self, b: dict) -> dict:
        """Compute avg/p95/max from collected times, convert s → ms, remove internals."""
        rtimes = b.pop("_response_times")
        uptimes = b.pop("_upstream_times")

        if rtimes:
            b["avg_response_ms"] = round(sum(rtimes) / len(rtimes) * 1000, 2)
            b["max_response_ms"] = round(max(rtimes) * 1000, 2)
            b["p95_response_ms"] = round(self._percentile(rtimes, 95) * 1000, 2)
        else:
            b["avg_response_ms"] = None
            b["max_response_ms"] = None
            b["p95_response_ms"] = None

        b["avg_upstream_ms"] = (
            round(sum(uptimes) / len(uptimes) * 1000, 2) if uptimes else None
        )

        return b

    # ------------------------------------------------------------------
    # Error log parsing
    # ------------------------------------------------------------------

    def _parse_error_lines(self, lines: List[str]) -> List[dict]:
        """
        Parse nginx error log lines into discrete event dicts.
        Skips lines that do not match the expected format.
        """
        events: List[dict] = []
        for line in lines:
            match = ERROR_LOG_RE.match(line)
            if not match:
                continue
            ts_str, level, message = match.group(1), match.group(2), match.group(3)
            try:
                ts = datetime.strptime(ts_str, "%Y/%m/%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
            events.append({
                "timestamp": ts.isoformat(),
                "level": level.lower(),
                "message": message.strip(),
            })
        return events

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def _send_access_metrics(self, source_id: str, buckets: List[dict]) -> None:
        """POST aggregated access metric buckets to the backend."""
        try:
            response = requests.post(
                f"{self.config.get('api_endpoint')}/core/agent/nginx-access-metrics/",
                json={"nginx_log_source_id": source_id, "buckets": buckets},
                headers={
                    "Authorization": f"Bearer {self.config.get('api_token')}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if response.status_code in (200, 201):
                self.logger.debug(
                    f"Nginx access metrics sent: {len(buckets)} buckets for source {source_id}"
                )
            else:
                self.logger.warning(
                    f"Failed to send nginx access metrics: {response.status_code} - {response.text}"
                )
        except Exception as e:
            self.logger.error(f"Error sending nginx access metrics: {e}")

    def _send_error_events(self, source_id: str, events: List[dict]) -> None:
        """POST parsed error events to the backend."""
        try:
            response = requests.post(
                f"{self.config.get('api_endpoint')}/core/agent/nginx-error-events/",
                json={"nginx_log_source_id": source_id, "events": events},
                headers={
                    "Authorization": f"Bearer {self.config.get('api_token')}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if response.status_code in (200, 201):
                self.logger.debug(
                    f"Nginx error events sent: {len(events)} events for source {source_id}"
                )
            else:
                self.logger.warning(
                    f"Failed to send nginx error events: {response.status_code} - {response.text}"
                )
        except Exception as e:
            self.logger.error(f"Error sending nginx error events: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _percentile(data: List[float], pct: int) -> float:
        """Linear interpolation percentile over a list of floats."""
        sorted_data = sorted(data)
        if len(sorted_data) == 1:
            return sorted_data[0]
        idx = (len(sorted_data) - 1) * pct / 100
        lo = int(idx)
        hi = lo + 1
        if hi >= len(sorted_data):
            return sorted_data[lo]
        frac = idx - lo
        return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])
