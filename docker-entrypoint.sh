#!/bin/bash
echo "Starting the application..."
pip3 install -r /repo/requirements.txt || echo "Error, could not install requirements.txt $?"
python3 /repo/src/menu.py || echo "Python script exited with error code $?"
echo "Application has terminated."
