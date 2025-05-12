#!/bin/bash
echo "Starting the application..."
pip3 install -r config/requirements.txt || echo "Error, could not install requirements.txt $?"
exec python3 src/menu.py || echo "Python script exited with error code $?"
echo "Application has terminated."
