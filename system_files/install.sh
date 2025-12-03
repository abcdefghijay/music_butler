#!/bin/bash
# Music Butler - Quick Installation Script

echo "=================================="
echo "  Music Butler - Installation"
echo "=================================="
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo "⚠ Warning: This script is designed for Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Step 1: Updating system..."
sudo apt-get update
sudo apt-get upgrade -y

echo ""
echo "Step 2: Installing system packages..."
sudo apt-get install -y python3-pip python3-opencv libzbar0 python3-numpy \
    libusb-1.0-0-dev python3-pil git curl

echo ""
echo "Step 3: Installing Python packages..."
pip3 install --break-system-packages spotipy opencv-python pyzbar pillow \
    qrcode python-escpos

echo ""
echo "Step 4: Installing Raspotify..."
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh

echo ""
echo "Step 5: Configuring Raspotify..."
sudo bash -c 'cat >> /etc/raspotify/conf << EOF

# Music Butler Configuration
DEVICE_NAME="Music Butler"
BITRATE="320"
OPTIONS="--backend alsa --device hw:0,0 --mixer Master --initial-volume=50"
EOF'

sudo systemctl restart raspotify
sudo systemctl enable raspotify

echo ""
echo "Step 6: Checking camera..."
if vcgencmd get_camera | grep -q "detected=1"; then
    echo "✓ Camera detected"
else
    echo "⚠ Camera not detected - check connection and config.txt"
fi

echo ""
echo "Step 7: Testing audio..."
if aplay -l | grep -q "hifiberry"; then
    echo "✓ Audio device detected"
else
    echo "⚠ Audio device not detected - check speaker bonnet and config.txt"
fi

echo ""
echo "=================================="
echo "  Installation Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit music_butler.py and add your Spotify API credentials"
echo "2. If using a printer, connect it and configure USB IDs"
echo "3. Run: python3 ~/music-butler/music_butler.py"
echo ""
echo "For full instructions, see README.md"