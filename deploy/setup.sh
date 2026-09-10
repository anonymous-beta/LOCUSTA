#!/bin/bash

# LOCUSTA Hive — Quick Deployment Script

set -e

echo "╔══════════════════════════════════════════╗"
echo "║   LOCUSTA — Command & Control Interface  ║"
echo "║           'The Hive'                     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check dependencies
if ! command -v docker &> /dev/null; then
    echo "[!] Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "[!] Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

# Generate secrets if not set
if [ -z "$LOCUSTA_SECRET" ]; then
    export LOCUSTA_SECRET=$(openssl rand -hex 32)
    echo "[+] Generated LOCUSTA_SECRET"
fi

if [ -z "$LOCUSTA_JWT_SECRET" ]; then
    export LOCUSTA_JWT_SECRET=$(openssl rand -hex 32)
    echo "[+] Generated LOCUSTA_JWT_SECRET"
fi

if [ -z "$LOCUSTA_ADMIN_PASS" ]; then
    export LOCUSTA_ADMIN_PASS="locusta-$(openssl rand -hex 4)"
    echo "[!] Generated admin password: $LOCUSTA_ADMIN_PASS"
    echo "[!] SAVE THIS PASSWORD!"
fi

if [ -z "$DB_PASSWORD" ]; then
    export DB_PASSWORD=$(openssl rand -hex 16)
    echo "[+] Generated DB_PASSWORD"
fi

# Create SSL directory
mkdir -p ssl

# Generate self-signed cert if none exists
if [ ! -f ssl/cert.pem ]; then
    echo "[+] Generating self-signed SSL certificate..."
    openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem \
        -days 365 -nodes -subj "/CN=locusta.local"
fi

# Build and start
echo "[+] Building containers..."
docker-compose build

echo "[+] Starting LOCUSTA Hive..."
docker-compose up -d

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Hive is online                         ║"
echo "╠══════════════════════════════════════════╣"
echo "║   Dashboard: http://localhost:3000       ║"
echo "║   API:       http://localhost:8443       ║"
echo "║   Workers:   http://localhost:9443       ║"
echo "╠══════════════════════════════════════════╣"
echo "║   Login:     admin                       ║"
echo "║   Password:  $LOCUSTA_ADMIN_PASS"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "[+] To view logs: docker-compose logs -f"
echo "[+] To stop: docker-compose down"
echo ""

# Save credentials to file
cat > .credentials <<EOF
LOCUSTA Admin Credentials
=========================
URL: http://localhost:3000
Username: admin
Password: $LOCUSTA_ADMIN_PASS

Database:
Password: $DB_PASSWORD

Secrets:
LOCUSTA_SECRET: $LOCUSTA_SECRET
LOCUSTA_JWT_SECRET: $LOCUSTA_JWT_SECRET
EOF

chmod 600 .credentials
echo "[+] Credentials saved to .credentials"
