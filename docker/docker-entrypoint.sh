#!/bin/bash
set -e  # Exit immediately if any command fails

echo "Starting the application..."

echo ">>> Installing dependencies..."
pip3 install -r config/requirements.txt || echo "Error, could not install requirements.txt $?"

echo ">>> Running database migrations..."
python3 src/migrations/001_add_discarded_applied.py || echo "Warning: migration script exited with error"

echo ">>> Launching application..."
exec python3 src/menu.py || echo "Python script exited with error code $?"

echo "Application has terminated."
