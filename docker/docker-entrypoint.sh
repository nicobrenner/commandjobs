#!/bin/bash
set -e  # Exit immediately if any command fails

echo "Starting the application..."

echo ">>> Installing dependencies..."
pip3 install -r config/requirements.txt || echo "Error, could not install requirements.txt $?"

echo ">>> Running database migrations..."
# Loop through every .py in src/migrations, sorted by filename
for migration in src/migrations/*.py; do
  echo "----> Applying $(basename "$migration")"
  python3 "$migration" || echo "Warning: migration $migration exited with error"
done

echo ">>> Launching application..."
exec python3 src/menu.py || echo "Python script exited with error code $?"

echo "Application has terminated."
