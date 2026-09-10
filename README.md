# LOCUSTA

<p align="center">
  <img src="logo-1.svg" alt="LOCUSTA" width="180">
</p>

<p align="center">
  <strong>Command & Control for a distributed swarm of worker nodes.</strong><br>
  Real-time. Role-based. AI-assisted.         BUILT BY ANONYMOUS-BETA(Chinedu)
</p>

---

LOCUSTA (Latin for locust) is a full-stack C2 web interface that lets you manage a living swarm of workers.
The Hive (C2) issues tasks. The Swarm (workers) executes them. Everything is live over WebSockets.

# Core Ideas

· Roles instead of one-size-fits-all agents — scout · analyzer · storm · graffiti
· Real-time telemetry — workers report in, tasks flow out, dashboards update instantly
· AI-assisted decisions (optional) — OpenAI / Anthropic / local models can help plan and approve actions
· Clean separation — backend, frontend, worker, and deploy are independent

---

# Architecture

```text
[ WebSockets / HTTP ]
        │
┌───────┴───────────────────────┐
│       Frontend (The Hive)     │
│      React + Tailwind         │
└───────┬───────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│         Backend (C2)          │
│    Flask + SocketIO           │
│    JWT + SQLite               │
└───────┬───────────────────────┘
        │ Task assign / heartbeat
        ▼
┌───────────────────────────────┐
│        Worker Swarm           │
│      (Python agents)          │
└───────────────────────────────┘
```

# Components

Component Tech Stack Purpose
Backend Flask, Flask-SocketIO, JWT, SQLite C2 core, task routing, auth
Frontend React, Tailwind, Framer Motion The Hive UI, real-time dashboard
Worker Pure Python Task execution, heartbeats
Deploy Docker Compose One-command orchestration

---

Quick Start

1. Clone & Configure

```bash
git clone https://github.com/anonymous-beta/LOCUSTA.git
cd LOCUSTA
cp deploy/.env.example deploy/.env  # edit secrets!
```

Note: Be sure to edit deploy/.env to set your LOCUSTA_SECRET, LOCUSTA_JWT_SECRET, and LOCUSTA_ADMIN_PASS before proceeding.

2. Run with Docker (Recommended)

```bash
cd deploy
docker compose up --build
```
Once running, access the services at:

· Frontend: http://localhost:3000
· C2 API / WebSocket: https://localhost:8443 (or the ports you mapped)

Default Admin: The default admin account is created on the first run. Check the backend logs for the generated password, or set LOCUSTA_ADMIN_PASS in your .env file.

3. Launch a Worker

Workers auto-generate a stable ID from the host and start heartbeating.

```bash
export LOCUSTA_C2=https://your-c2:8443
export LOCUSTA_ROLE=scout  # scout | analyzer | storm | graffiti
python worker/locusta_worker.py
```

---

# Worker Roles

Tasks are prioritized and can be targeted to a specific worker, a role, or the first available agent.

Role Focus
scout Recon — connectivity, subdomains, ports, tech fingerprinting
analyzer Deeper analysis of findings
storm High-volume / parallel task execution
graffiti Content / payload deployment (with optional auto-revert)

---

# Environment Variables

## Variable Description
```
LOCUSTA_SECRET Flask secret
LOCUSTA_JWT_SECRET JWT signing key
LOCUSTA_ADMIN_PASS Initial admin password
LOCUSTA_AI_ENABLED Enable AI assistance
LOCUSTA_AI_PROVIDER openai / anthropic
LOCUSTA_AI_KEY API key for the chosen provider
LOCUSTA_AI_MODEL Model name
LOCUSTA_C2 Worker -> C2 URL
LOCUSTA_ROLE Worker role
```
---
## Ọ bụ Anonymous-beta rụrụ ya
