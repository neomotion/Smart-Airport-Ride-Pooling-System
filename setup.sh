#!/usr/bin/env bash
set -e

echo "========================================"
echo "  Smart Airport Ride Pooling - Setup"
echo "========================================"
echo

# ── 0. Environment file ──────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "       Created .env from .env.example"
fi

# ── 1. Docker check ──────────────────────────────────────────────────
echo "[1/5] Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running."
    echo "       Please start Docker Desktop and try again."
    exit 1
fi
echo "       Docker is running."

# ── 2. Start infrastructure ──────────────────────────────────────────
echo "[2/5] Starting PostgreSQL + Redis..."
docker compose up -d
echo "       Waiting for services to be healthy..."
sleep 3
# poll until postgres is ready (max 30s)
for i in $(seq 1 10); do
    if docker compose exec -T postgres pg_isready -U ridepooling > /dev/null 2>&1; then
        break
    fi
    sleep 3
done
echo "       Services are up."

# ── 3. Python virtual environment ────────────────────────────────────
echo "[3/5] Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "       Created virtual environment."
else
    echo "       Virtual environment already exists."
fi
source venv/bin/activate
pip install -q -r requirements.txt
echo "       Dependencies installed."

# ── 4. Database migrations ───────────────────────────────────────────
echo "[4/5] Running database migrations..."
alembic upgrade head
echo "       Migrations complete."

# ── 5. Seed sample data ─────────────────────────────────────────────
echo "[5/5] Seeding sample data..."
python seed.py
echo

echo "========================================"
echo "  Setup complete!"
echo "  Run ./start.sh to start the server."
echo "========================================"
