"""
Real-time data generator for the EDoS Security Dashboard
Generates realistic cybersecurity data for demonstration
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from faker import Faker

from app.models.schemas import *
from app.utils.pydantic_compat import model_to_dict

fake = Faker()


class DataGenerator:
    """Generates realistic cybersecurity data"""

    def __init__(self):
        # Global threat locations (major cities with cyber activity)
        self.threat_locations = [
            {
                "lat": 40.7128,
                "lng": -74.0060,
                "name": "New York",
                "country": "US",
                "city": "New York",
            },
            {
                "lat": 55.7558,
                "lng": 37.6176,
                "name": "Moscow",
                "country": "RU",
                "city": "Moscow",
            },
            {
                "lat": 39.9042,
                "lng": 116.4074,
                "name": "Beijing",
                "country": "CN",
                "city": "Beijing",
            },
            {
                "lat": 51.5074,
                "lng": -0.1278,
                "name": "London",
                "country": "GB",
                "city": "London",
            },
            {
                "lat": 35.6762,
                "lng": 139.6503,
                "name": "Tokyo",
                "country": "JP",
                "city": "Tokyo",
            },
            {
                "lat": 37.7749,
                "lng": -122.4194,
                "name": "San Francisco",
                "country": "US",
                "city": "San Francisco",
            },
            {
                "lat": 52.5200,
                "lng": 13.4050,
                "name": "Berlin",
                "country": "DE",
                "city": "Berlin",
            },
            {
                "lat": -33.8688,
                "lng": 151.2093,
                "name": "Sydney",
                "country": "AU",
                "city": "Sydney",
            },
            {
                "lat": 48.8566,
                "lng": 2.3522,
                "name": "Paris",
                "country": "FR",
                "city": "Paris",
            },
            {
                "lat": 43.6532,
                "lng": -79.3832,
                "name": "Toronto",
                "country": "CA",
                "city": "Toronto",
            },
            {
                "lat": 25.2048,
                "lng": 55.2708,
                "name": "Dubai",
                "country": "AE",
                "city": "Dubai",
            },
            {
                "lat": 1.3521,
                "lng": 103.8198,
                "name": "Singapore",
                "country": "SG",
                "city": "Singapore",
            },
            {
                "lat": 19.0760,
                "lng": 72.8777,
                "name": "Mumbai",
                "country": "IN",
                "city": "Mumbai",
            },
            {
                "lat": -23.5505,
                "lng": -46.6333,
                "name": "São Paulo",
                "country": "BR",
                "city": "São Paulo",
            },
            {
                "lat": 37.5665,
                "lng": 126.9780,
                "name": "Seoul",
                "country": "KR",
                "city": "Seoul",
            },
        ]

        # Attack types and patterns
        self.attack_types = [
            {"type": "ddos", "severity": "HIGH", "color": "#ef4444"},
            {"type": "malware", "severity": "CRITICAL", "color": "#dc2626"},
            {"type": "brute_force", "severity": "MEDIUM", "color": "#f59e0b"},
            {"type": "sql_injection", "severity": "HIGH", "color": "#ef4444"},
            {"type": "phishing", "severity": "MEDIUM", "color": "#f59e0b"},
            {"type": "ransomware", "severity": "CRITICAL", "color": "#dc2626"},
            {"type": "port_scan", "severity": "LOW", "color": "#6b7280"},
        ]

        # Resource names and types
        self.resource_names = [
            "web-server-01",
            "web-server-02",
            "db-primary",
            "db-replica",
            "api-gateway",
            "cache-cluster",
            "load-balancer",
            "auth-server",
            "monitoring-01",
            "backup-server",
            "vpn-gateway",
            "firewall-01",
        ]

        self.resource_types = ["EC2", "RDS", "Lambda", "ElastiCache", "ELB", "VPN"]
        self.operating_systems = [
            "ubuntu",
            "centos",
            "windows",
            "mysql",
            "redis",
            "nodejs",
        ]

        # Log message templates
        self.log_templates = {
            "info": [
                "System scan initiated on {resource}",
                "Firewall rules updated successfully",
                "User authentication successful for {user}",
                "Database backup completed for {resource}",
                "SSL certificate renewed for {domain}",
                "Security patch applied to {resource}",
                "Real-time monitoring active on {resource}",
                "Service health check passed on {resource}",
                "Configuration updated on {resource}",
                "Network optimization completed",
            ],
            "warn": [
                "High memory usage detected on {resource}: {percentage}%",
                "Disk usage above 80% on {resource}",
                "Unusual network activity from {ip}",
                "Service response time degraded on {resource}",
                "Connection pool nearly exhausted on {resource}",
                "Rate limiting threshold approached from {ip}",
                "Certificate expires in 30 days for {domain}",
                "Low disk space warning on {resource}",
            ],
            "error": [
                "Intrusion attempt blocked from IP {ip}",
                "Authentication failed for user {user} from {ip}",
                "Service unavailable: {resource}",
                "Database connection timeout on {resource}",
                "Failed to load security rules on {resource}",
                "Backup process failed for {resource}",
                "Configuration validation error on {resource}",
                "Network connectivity lost to {resource}",
            ],
            "debug": [
                "API response time: {time}ms for {endpoint}",
                "Cache hit ratio: {percentage}% on {resource}",
                "Memory allocation: {size}MB on {resource}",
                "Thread pool size: {count} on {resource}",
                "Database query executed in {time}ms",
                "File system access: {path} on {resource}",
            ],
        }

        # Current metrics state
        self.current_metrics = {
            "threats_detected": 1247,
            "blocked_attacks": 1198,
            "data_processed": 2.4,  # TB
            "system_uptime": 99.97,
            "cpu_usage": 65.0,
            "memory_usage": 78.0,
            "network_io": 156.7,
            "active_connections": 15678,
        }

    def generate_alert(self, user_id: str = None, resource_name: str = None) -> Alert:
        """Generate a realistic security alert for a specific user/resource"""
        attack = random.choice(self.attack_types)
        source_loc = random.choice(self.threat_locations)
        dest_loc = random.choice(
            [loc for loc in self.threat_locations if loc != source_loc]
        )

        # Determine if this is an attack (70% chance for demo purposes)
        is_attack = random.random() < 0.7

        # Use provided resource name or pick random one
        target_resource = resource_name or random.choice(self.resource_names)

        if is_attack:
            messages = [
                f"{attack['type'].replace('_', ' ').title()} attack detected from {source_loc['name']}",
                f"Suspicious {attack['type']} activity from {source_loc['country']}",
                f"Multiple {attack['type']} attempts from {source_loc['name']} region",
                f"High-severity {attack['type']} detected targeting {target_resource}",
            ]
            level = attack["severity"]
        else:
            messages = [
                f"Normal traffic pattern from {source_loc['name']} to {target_resource}",
                f"Legitimate connection from {source_loc['country']}",
                f"Regular monitoring data from {source_loc['name']}",
                f"Secure connection established with {target_resource}",
            ]
            level = "LOW"

        alert_id = str(uuid.uuid4())

        return Alert(
            alert_id=alert_id,
            level=AlertLevel(level),
            event=EventInfo(
                category="network",
                action=f"{attack['type']}_detected" if is_attack else "normal_traffic",
            ),
            source=NetworkEndpoint(
                ip=fake.ipv4(),
                port=random.choice([80, 443, 22, 21, 3389, 8080]),
                geo=GeoLocation(
                    country_iso=source_loc["country"],
                    region=source_loc["name"],
                    city=source_loc["city"],
                    lat=source_loc["lat"],
                    lng=source_loc["lng"],
                ),
            ),
            destination=NetworkEndpoint(
                ip=fake.ipv4_private(),
                port=random.choice([80, 443, 22, 3306, 5432]),
                geo=GeoLocation(
                    country_iso=dest_loc["country"],
                    region=dest_loc["name"],
                    city=dest_loc["city"],
                    lat=dest_loc["lat"],
                    lng=dest_loc["lng"],
                ),
            ),
            model=ModelInfo(
                name="I-MPaFS-RF",
                version=f"v{random.randint(3,4)}.{random.randint(1,9)}.{random.randint(0,9)}",
                probability=(
                    random.uniform(0.85, 0.99)
                    if is_attack
                    else random.uniform(0.1, 0.4)
                ),
                threshold=0.85,
            ),
            message=random.choice(messages),
            recommendation=(
                "Block source IP immediately" if is_attack else "Continue monitoring"
            ),
            severity_score=(
                random.randint(80, 100) if is_attack else random.randint(10, 40)
            ),
            time=f"{random.randint(1, 30)} mins ago",
        )

    def generate_network_traffic(self) -> Dict[str, Any]:
        """Generate network traffic data for the 3D globe"""
        # Generate arcs (connections)
        arcs = []
        for _ in range(random.randint(1, 3)):
            source = random.choice(self.threat_locations)
            dest = random.choice(
                [loc for loc in self.threat_locations if loc != source]
            )
            is_attack = random.random() < 0.3  # 30% attack traffic

            arc = NetworkArc(
                id=str(uuid.uuid4()),
                startLat=source["lat"],
                startLng=source["lng"],
                endLat=dest["lat"],
                endLng=dest["lng"],
                isAttack=is_attack,
                label=f"{'Attack' if is_attack else 'Safe'} traffic: {source['name']} → {dest['name']}",
                color="#ef4444" if is_attack else "#22c55e",
                attack_type=(
                    random.choice(self.attack_types)["type"] if is_attack else None
                ),
                data_size=f"{random.randint(1, 100)}MB",
                duration=random.randint(15, 300),
            )
            arcs.append(model_to_dict(arc))

        # Generate points (monitoring stations)
        points = []
        for _ in range(random.randint(0, 2)):
            location = random.choice(self.threat_locations)
            is_threat = random.random() < 0.2  # 20% threat sources

            point = ThreatPoint(
                lat=location["lat"],
                lng=location["lng"],
                label=f"{location['name']} - {'Threat Source' if is_threat else 'Monitoring Station'}",
                isAttack=is_threat,
                color="#ef4444" if is_threat else "#22c55e",
                size=random.uniform(0.5, 1.2),
                city=location["city"],
                country=location["country"],
                connections=random.randint(50, 500),
                status="threat" if is_threat else "monitoring",
            )
            points.append(model_to_dict(point))

        return {"arcs": arcs, "points": points}

    def generate_metrics(self) -> Dict[str, Any]:
        """Generate system metrics with realistic fluctuations"""
        # Update metrics with small random changes
        self.current_metrics["threats_detected"] += random.randint(0, 5)
        self.current_metrics["blocked_attacks"] += random.randint(0, 3)
        self.current_metrics["cpu_usage"] = max(
            20, min(95, self.current_metrics["cpu_usage"] + random.uniform(-5, 5))
        )
        self.current_metrics["memory_usage"] = max(
            30, min(90, self.current_metrics["memory_usage"] + random.uniform(-3, 3))
        )
        self.current_metrics["network_io"] = max(
            50, min(300, self.current_metrics["network_io"] + random.uniform(-20, 20))
        )
        self.current_metrics["active_connections"] += random.randint(-100, 200)

        resp = MetricsResponse(
            system=SystemMetrics(
                cpu_usage=round(self.current_metrics["cpu_usage"], 1),
                memory_usage=round(self.current_metrics["memory_usage"], 1),
                disk_usage=random.uniform(40, 85),
                network_io=round(self.current_metrics["network_io"], 1),
                uptime=round(self.current_metrics["system_uptime"], 2),
            ),
            threats=ThreatMetrics(
                total_detected=self.current_metrics["threats_detected"],
                blocked_attacks=self.current_metrics["blocked_attacks"],
                active_threats=random.randint(15, 45),
                threat_level=random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
            ),
            network=NetworkMetrics(
                total_connections=max(
                    10000, self.current_metrics["active_connections"]
                ),
                data_processed=f"{self.current_metrics['data_processed']:.1f} TB",
                bandwidth_usage=random.uniform(60, 90),
                regions_monitored=15,
            ),
        )
        return model_to_dict(resp)

    def generate_log(self) -> LogEntry:
        """Generate a realistic log entry"""
        level = random.choice(["info", "warn", "error", "debug"])
        template = random.choice(self.log_templates[level])

        # Fill template variables
        message = template.format(
            resource=random.choice(self.resource_names),
            user=fake.user_name(),
            ip=fake.ipv4(),
            percentage=random.randint(70, 95),
            domain=fake.domain_name(),
            time=random.randint(50, 500),
            endpoint=f"/api/v1/{fake.word()}",
            size=random.randint(100, 2000),
            count=random.randint(5, 50),
            path=f"/var/log/{fake.file_name()}",
        )

        return LogEntry(
            level=LogLevel(level),
            message=message,
            source=random.choice(self.resource_names),
        )

    def generate_cloud_resources(self, count: int = 12) -> List[CloudResource]:
        """Generate initial cloud resources"""
        resources = []

        for i in range(count):
            resource = CloudResource(
                id=i + 1,
                name=self.resource_names[i % len(self.resource_names)],
                type=random.choice(self.resource_types),
                os=random.choice(self.operating_systems),
                status=ResourceStatus(
                    random.choice(["running", "running", "running", "stopped"])
                ),  # Mostly running
                health=ResourceHealth(
                    random.choice(["healthy", "healthy", "warning", "critical"])
                ),  # Mostly healthy
                cpu=random.uniform(10, 85),
                memory=random.uniform(20, 90),
                disk=random.uniform(30, 80),
                region=random.choice(
                    [
                        "us-east-1",
                        "us-west-2",
                        "eu-central-1",
                        "ap-south-1",
                        "eu-west-1",
                    ]
                ),
                uptime=f"{random.randint(1, 200)}d {random.randint(1, 23)}h",
            )
            resources.append(resource)

        return resources

    def generate_user_alert(self, user_id: str, resource_name: str = None) -> Alert:
        """Generate an alert specific to a user and their resources"""
        return self.generate_alert(user_id=user_id, resource_name=resource_name)

    def generate_user_log(self, user_id: str, resource_name: str = None) -> LogEntry:
        """Generate a log entry specific to a user and their resources"""
        level = random.choice(["info", "warn", "error", "debug"])
        template = random.choice(self.log_templates[level])

        # Use provided resource or pick random one
        target_resource = resource_name or random.choice(self.resource_names)

        # Fill template variables
        message = template.format(
            resource=target_resource,
            user=fake.user_name(),
            ip=fake.ipv4(),
            percentage=random.randint(70, 95),
            domain=fake.domain_name(),
            time=random.randint(50, 500),
            endpoint=f"/api/v1/{fake.word()}",
            size=random.randint(100, 2000),
            count=random.randint(5, 50),
            path=f"/var/log/{fake.file_name()}",
        )

        return LogEntry(level=LogLevel(level), message=message, source=target_resource)

    def generate_user_metrics(self, user_id: str) -> Dict[str, Any]:
        """Generate metrics specific to a user's resources"""
        return self.generate_metrics()  # For now, return general metrics

    def generate_user_network_traffic(
        self, user_id: str, resource_name: str = None
    ) -> Dict[str, Any]:
        """Generate network traffic specific to a user's resources"""
        return self.generate_network_traffic()  # For now, return general traffic
