#!/usr/bin/env bash
set -e

source venv/bin/activate

echo "========================================"
echo "  Starting Ride Pooling API Server"
echo "========================================"
echo
echo "  Swagger UI : http://localhost:8000/docs"
echo "  ReDoc      : http://localhost:8000/redoc"
echo "  Health     : http://localhost:8000/api/v1/admin/health"
echo
echo "  Press Ctrl+C to stop."
echo "========================================"
echo

# Wait for server to start, then open browser
#sleep 2
#xdg-open http://localhost:8000/docs &

python main.py
