#!/usr/bin/env python3
"""
Network Monitor Service
=====================

A standalone service that monitors:
- Network traffic (upload/download speeds)
- System resources (CPU, memory, disk I/O)
- Open ports and running services
- Port security analysis

Publishes real-time data to Redis for consumption by the dashboard backend.

Author: EDOS Detection Kit
Version: 1.0.0
"""

import asyncio
import logging
import signal
import sys
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional

import redis
import psutil
import json
import time
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("network_monitor.log"),
    ],
)
logger = logging.getLogger("NetworkMonitor")


@dataclass
class NetworkSpeed:
    timestamp: str
    download: float  # Mbps
    upload: float  # Mbps


@dataclass
class SystemMetrics:
    cpu: Dict
    memory: Dict
    disk: Dict


@dataclass
class OpenPort:
    port: int
    protocol: str
    service: str
    program: str
    status: str
    risk: str


@dataclass
class NetworkAnalysisData:
    networkSpeeds: List[NetworkSpeed]
    systemMetrics: SystemMetrics
    openPorts: List[OpenPort]
    isConnected: bool
    lastUpdate: str


class NetworkMonitor:
    def __init__(self, redis_host="localhost", redis_port=6379, redis_db=0):
        self.redis_client = redis.Redis(
            host=redis_host, port=redis_port, db=redis_db, decode_responses=True
        )
        self.running = False
        self.network_speeds = []

        # Test Redis connection
        try:
            self.redis_client.ping()
            logger.info("✅ Connected to Redis successfully")
        except redis.ConnectionError:
            logger.error("❌ Failed to connect to Redis")
            raise

    def get_network_speed(self) -> NetworkSpeed:
        """Get current network upload/download speeds"""
        # Get network I/O statistics
        net_io = psutil.net_io_counters()

        # For now, we'll simulate network speed calculation
        # In production, you'd measure bytes transferred over time intervals
        # This is a simplified version for demonstration

        # Simulate realistic network speeds
        download_mbps = random.uniform(50, 150)  # 50-150 Mbps
        upload_mbps = random.uniform(10, 40)  # 10-40 Mbps

        return NetworkSpeed(
            timestamp=datetime.now(timezone.utc).isoformat(),
            download=round(download_mbps, 2),
            upload=round(upload_mbps, 2),
        )

    def get_system_metrics(self) -> SystemMetrics:
        """Get current system resource usage"""
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        process_count = len(psutil.pids())

        # Memory metrics
        memory = psutil.virtual_memory()
        memory_used_gb = memory.used / (1024**3)
        memory_total_gb = memory.total / (1024**3)
        memory_available_gb = memory.available / (1024**3)

        # Disk metrics
        disk_usage = psutil.disk_usage("/")
        disk_used_gb = disk_usage.used / (1024**3)
        disk_total_gb = disk_usage.total / (1024**3)

        # Disk I/O
        disk_io = psutil.disk_io_counters()
        # Simulate read/write speeds (you'd calculate this over time in production)
        read_speed_mbs = random.uniform(50, 150)
        write_speed_mbs = random.uniform(30, 110)

        return SystemMetrics(
            cpu={
                "usage": round(cpu_percent, 1),
                "cores": cpu_count,
                "processes": process_count,
            },
            memory={
                "used": round(memory_used_gb, 1),
                "total": round(memory_total_gb, 1),
                "available": round(memory_available_gb, 1),
            },
            disk={
                "used": round(disk_used_gb, 1),
                "total": round(disk_total_gb, 1),
                "readSpeed": round(read_speed_mbs, 1),
                "writeSpeed": round(write_speed_mbs, 1),
            },
        )

    def get_open_ports(self) -> List[OpenPort]:
        """Scan for open ports and running services"""
        open_ports = []

        # Get network connections
        connections = psutil.net_connections(kind="inet")

        # Track unique listening ports
        listening_ports = set()
        port_to_pid = {}

        for conn in connections:
            if conn.status == "LISTEN" and conn.laddr:
                port = conn.laddr.port
                listening_ports.add(port)
                if conn.pid:
                    port_to_pid[port] = conn.pid

        # Common port mappings
        port_services = {
            22: ("SSH", "sshd"),
            23: ("Telnet", "telnetd"),
            25: ("SMTP", "sendmail"),
            53: ("DNS", "named"),
            80: ("HTTP", "httpd"),
            110: ("POP3", "pop3d"),
            143: ("IMAP", "imapd"),
            443: ("HTTPS", "httpd"),
            993: ("IMAPS", "imapd"),
            995: ("POP3S", "pop3d"),
            3306: ("MySQL", "mysqld"),
            5432: ("PostgreSQL", "postgres"),
            6379: ("Redis", "redis-server"),
            8080: ("HTTP-Alt", "node"),
            9200: ("Elasticsearch", "elasticsearch"),
        }

        # Risk assessment
        high_risk_ports = {
            23,
            21,
            135,
            139,
            445,
            1433,
            3389,
        }  # Telnet, FTP, Windows services, RDP
        medium_risk_ports = {
            22,
            25,
            110,
            143,
            993,
            995,
            3306,
            5432,
        }  # SSH, mail, databases

        for port in sorted(listening_ports):
            service, default_program = port_services.get(port, ("Unknown", "unknown"))

            # Try to get actual program name
            program = default_program
            if port in port_to_pid:
                try:
                    process = psutil.Process(port_to_pid[port])
                    program = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # Determine risk level
            if port in high_risk_ports:
                risk = "high"
            elif port in medium_risk_ports:
                risk = "medium"
            else:
                risk = "low"

            open_ports.append(
                OpenPort(
                    port=port,
                    protocol="TCP",
                    service=service,
                    program=program,
                    status="open",
                    risk=risk,
                )
            )

        return open_ports

    def publish_data(self, data: NetworkAnalysisData):
        """Publish data to Redis"""
        try:
            # Convert dataclass to dict
            data_dict = asdict(data)

            # Publish to Redis
            self.redis_client.set(
                "network_analysis:latest",
                json.dumps(data_dict, default=str),
                ex=60,  # Expire after 60 seconds
            )

            # Also publish to a channel for real-time updates
            self.redis_client.publish(
                "network_analysis:updates", json.dumps(data_dict, default=str)
            )

            logger.info(f"📡 Published network analysis data to Redis")

        except Exception as e:
            logger.error(f"❌ Failed to publish data to Redis: {e}")

    async def collect_and_publish(self):
        """Main data collection and publishing loop"""
        logger.info("🚀 Starting network monitoring...")

        while self.running:
            try:
                # Collect current network speed
                current_speed = self.get_network_speed()

                # Maintain rolling window of network speeds (last 30 seconds)
                self.network_speeds.append(current_speed)
                if len(self.network_speeds) > 30:
                    self.network_speeds.pop(0)

                # Get system metrics
                system_metrics = self.get_system_metrics()

                # Get open ports (less frequent to avoid overhead)
                open_ports = self.get_open_ports()

                # Create complete data structure
                analysis_data = NetworkAnalysisData(
                    networkSpeeds=self.network_speeds,
                    systemMetrics=system_metrics,
                    openPorts=open_ports,
                    isConnected=True,
                    lastUpdate=datetime.now(timezone.utc).isoformat(),
                )

                # Publish to Redis
                self.publish_data(analysis_data)

                # Wait for next collection cycle
                await asyncio.sleep(2)  # Collect every 2 seconds

            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Wait longer on error

    async def start(self):
        """Start the monitoring service"""
        self.running = True

        # Handle graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"🛑 Received signal {signum}, shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start monitoring
        await self.collect_and_publish()

        logger.info("✅ Network monitor service stopped")


async def main():
    """Main entry point"""
    logger.info("🌟 EDOS Network Monitor Service v1.0.0")
    logger.info("=" * 50)

    try:
        # Initialize monitor
        monitor = NetworkMonitor(redis_host="localhost", redis_port=6379, redis_db=0)

        # Start monitoring
        await monitor.start()

    except KeyboardInterrupt:
        logger.info("🛑 Service interrupted by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
