# LOCUSTA

<p align="center">
  <img src="logo-1.svg" alt="LOCUSTA" width="180">
</p>

<p align="center">
  <strong>Command & Control for a distributed swarm of worker nodes.</strong><br>
  Real-time. Role-based. AI-assisted.         BUILT BY ANONYMOUS-BETA(Chinedu)
</p>

---

# LOCUSTA

The Hive — Authorized Red-Team / Security-Lab Orchestration Platform

LOCUSTA is a full-stack web interface for managing a distributed collection of worker nodes in controlled, authorized security-testing environments.

## Architecture

                         ┌──────────────────────┐
                         │       Browser        │
                         │   LOCUSTA Hive UI    │
                         └──────────┬───────────┘
                                    │
                              HTTP :3000
                                    │
                         ┌──────────▼───────────┐
                         │       Nginx           │
                         │   React production    │
                         └──────────┬───────────┘
                                    │
                         Docker network / HTTP
                                    │
                         ┌──────────▼───────────┐
                         │      LOCUSTA C2       │
                         │ Flask + Socket.IO     │
                         │ JWT + SQLite          │
                         │       :8443           │
                         └──────────┬───────────┘
                                    │
                         HTTP / Socket.IO
                                    │
                         ┌──────────▼───────────┐
                         │    Worker process     │
                         │      Python           │
                         └───────────────────────┘

«Important: LOCUSTA should only be used against systems, applications, networks, and infrastructure for which you have explicit authorization.»

---

## 1. Repository Structure

LOCUSTA/
│
├── backend/
│   ├── app.py
│   └── requirements.txt
│
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── public/
│   └── src/
│
├── worker/
│   └── locusta_worker.py
│
├── deploy/
│   ├── docker-compose.yml
│   ├── Dockerfile.c2
│   ├── Dockerfile.frontend
│   ├── nginx.conf
│   └── .env.example
│
├── DISCLAIMER.md
├── LICENSE
├── README.md
└── logo-1.svg

---

## 2. Requirements

For the Docker deployment you need:

Docker
Docker Compose v2
Git

Verify:

docker --version
docker compose version
git --version

---

## 3. Clone

git clone https://github.com/anonymous-beta/LOCUSTA.git
cd LOCUSTA

---

## 4. Configure Environment

Create the deployment environment file:

cp deploy/.env.example deploy/.env

Edit it:

nano deploy/.env

At minimum, change:

LOCUSTA_SECRET=replace-with-a-long-random-secret
LOCUSTA_JWT_SECRET=replace-with-a-different-long-random-secret
LOCUSTA_ADMIN_PASS=change-this-password

For a local test, leave:

LOCUSTA_AI_ENABLED=false

until the core application is confirmed working.

---

## 5. Generate Strong Secrets

On Linux/macOS/Termux:

openssl rand -hex 32

Run it twice.

Use the first result for:

LOCUSTA_SECRET=

and the second for:

LOCUSTA_JWT_SECRET=

---

## 6. Start LOCUSTA

The Compose file lives in "deploy/".

Run:

cd deploy
docker compose up --build

The first build may take several minutes.

---

## 7. Verify Containers

Open another terminal:

cd LOCUSTA/deploy
docker compose ps

You should see:

locusta-c2
locusta-frontend

Both should be running.

---

## 8. Check C2 Logs

docker compose logs --tail=100 locusta-c2

You should see a message similar to:

LOCUSTA C2 starting on port 8443

The backend creates the SQLite database on first startup.

---

## 9. Open the Hive

Open:

http://localhost:3000

Do not use HTTPS for the default local deployment.

The frontend is served by Nginx on port 3000.

---

## 10. Login

The default username is:

admin

The password is the value configured in:

LOCUSTA_ADMIN_PASS

If you left that variable unset, the backend generates a random initial password and prints it in the C2 logs.

Check:

docker compose logs locusta-c2

Look for:

Default admin created.

---

## 11. C2 Direct Access

The backend is exposed locally on:

http://localhost:8443

The frontend normally communicates through Nginx.

The API is available under:

http://localhost:3000/api/

and Nginx forwards those requests internally to:

http://locusta-c2:8443

---

## 12. Worker — Local Host

The worker can be run outside Docker.

From the repository root:

export LOCUSTA_C2=http://localhost:8443
export LOCUSTA_ROLE=scout

python3 worker/locusta_worker.py

Available roles currently defined by the application are:

scout
analyzer
storm
graffiti

The worker first registers with:

POST /api/workers/register

and then establishes its Socket.IO connection.

---

## 13. Worker — Inside Docker

If a worker is eventually placed into the same Docker network as the C2, it should not use:

http://localhost:8443

Inside a container, "localhost" refers to that container.

The Docker service name is:

locusta-c2

Therefore the internal address is:

http://locusta-c2:8443

---

## 14. Stop LOCUSTA

From "deploy/":

docker compose down

---

## 15. Stop and Remove Persistent Data

The SQLite database is stored in the Docker volume:

locusta-data

To remove it:

docker compose down -v

Warning: this deletes the persistent LOCUSTA database volume.

---

## 16. Rebuild From Scratch

If Docker appears to be using stale layers:

docker compose down
docker compose build --no-cache
docker compose up

---

## 17. Useful Diagnostics

Show containers

docker compose ps

C2 logs

docker compose logs --tail=200 locusta-c2

Frontend logs

docker compose logs --tail=200 locusta-frontend

Follow C2 logs

docker compose logs -f locusta-c2

Follow frontend logs

docker compose logs -f locusta-frontend

Check the C2 port

curl http://localhost:8443/

Check the frontend

curl -I http://localhost:3000/

---

## 18. Important Current Architecture Notes

LOCUSTA currently uses SQLite for its database.

The Docker deployment therefore uses:

locusta-data

for persistent application data.

PostgreSQL is not required by the current backend implementation.

The C2 currently listens on:

8443

The separate "9443" worker port is not currently started by "app.py".

TLS is not enabled by default.

Therefore the default local URLs are:

Frontend:
http://localhost:3000

C2:
http://localhost:8443

---

## 19. Development Frontend

If you want to run React without Docker:

cd frontend
npm install
npm start

The development server normally runs on:

http://localhost:3000

The frontend defaults to:

http://localhost:8443/api

for API communication and:

http://localhost:8443

for Socket.IO.

---

## 20. Production Deployment

Before exposing LOCUSTA outside a controlled environment, configure:

- TLS termination
- strong secrets
- restricted network access
- authenticated worker enrollment
- operator access controls
- target/scope controls
- audit logging
- firewall rules
- monitoring

Do not expose the C2 directly to the public Internet without implementing and reviewing these controls.

---

## 21. Troubleshooting

Error:

COPY deploy/nginx.conf ... not found

Make sure "docker-compose.yml" uses:

build:
  context: ..
  dockerfile: deploy/Dockerfile.frontend

The build context must be the repository root.

---

Error:

npm run build

Inspect:

docker compose logs locusta-frontend

For a direct frontend build:

cd frontend
npm install
npm run build

---

Error connecting to C2

Check:

docker compose ps

Then:

docker compose logs locusta-c2

Confirm that the C2 reports:

LOCUSTA C2 starting on port 8443

---

Frontend loads but API requests fail

Confirm the browser is using:

http://localhost:3000

and that Nginx is running.

Then inspect:

docker compose logs locusta-frontend
docker compose logs locusta-c2

---

## 22. Current Status

LOCUSTA is composed of:

Frontend
    React
    Tailwind
    Framer Motion
    Socket.IO client

Backend
    Flask
    Flask-SocketIO
    JWT
    SQLite

Worker
    Python
    HTTP registration
    WebSocket/Socket.IO communication

Deployment
    Docker
    Docker Compose
    Nginx

The deployment configuration intentionally keeps the initial stack small:

React/Nginx
      ↓
Flask/Socket.IO
      ↓
SQLite

Additional infrastructure can be introduced after the core system has been verified end-to-end.
*BUILT BY ANONYMOUS-BETA(CHINEDU)*