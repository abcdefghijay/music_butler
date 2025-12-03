#!/bin/bash
# Music Butler - Startup Script
# Automatically starts Music Butler on boot

echo "Starting Music Butler..."

# Wait for system to fully boot
sleep 30

# Navigate to project directory
cd /home/pi/music-butler

# Start Music Butler with display
DISPLAY=:0 python3 music_butler.py

# Log output (optional)
# DISPLAY=:0 python3 music_butler.py >> /home/pi/music-butler.log 2>&1