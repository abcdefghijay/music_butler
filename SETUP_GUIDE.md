# Music Butler - Complete Setup Guide

**Build a QR Code-Controlled Spotify Player with Raspberry Pi**

This guide walks you through building Music Butler from scratch, starting with zero knowledge of Raspberry Pi.

---

## Table of Contents

- [Part 1: Shopping List](#part-1-shopping-list)
- [Part 2: Prepare SD Card](#part-2-prepare-the-sd-card)
- [Part 3: Hardware Assembly](#part-3-assemble-the-hardware)
- [Part 4: First Boot](#part-4-first-boot-and-setup)
- [Part 5: System Configuration](#part-5-configure-the-system)
- [Part 6: Spotify API Setup](#part-6-set-up-spotify-api)
- [Part 7: Install Music Butler](#part-7-install-music-butler)
- [Part 8: Testing](#part-8-first-run-and-test)
- [Part 9: Printer Setup (Optional)](#part-9-add-the-printer-optional)
- [Part 10: Creating QR Codes](#part-10-creating-qr-codes)
- [Part 11: Usage](#part-11-usage-guide)

---

## Part 1: Shopping List

### Required Components

| Item | Approx Price | Where to Buy | Notes |
|------|--------------|--------------|-------|
| Raspberry Pi 4 (4GB) | $55 | Amazon, Adafruit, Microcenter | 4GB model recommended |
| Raspberry Pi Camera Module V2 | $25 | Amazon, Adafruit | 8MP, official module |
| Adafruit I2S 3W Stereo Speaker Bonnet | $15 | Adafruit (#3346) | For audio output |
| MicroSD Card (32GB, Class 10) | $10 | Amazon, Best Buy | SanDisk or Samsung |
| USB-C Power Supply (5V 3A) | $8 | Amazon, Adafruit | Official Pi adapter recommended |
| 2x 4Ω 3W Speakers | $12 | Amazon, Parts Express | 2-3 inch diameter |
| Speaker Wire (22-18 AWG) | $7 | Amazon, Home Depot | 10-20 feet |
| Phomemo M02 Printer | $45 | Amazon | Optional, for printing stickers |
| Thermal Sticker Paper (53mm) | $12 | Amazon | Comes with printer, extras available |

**Total Cost:** ~$140 (without printer) or ~$185 (with printer)

### Tools Needed

- Computer (Mac, Windows, or Linux)
- SD card reader
- Small Phillips screwdriver
- Wire strippers or scissors
- Internet connection (WiFi)

---

## Part 2: Prepare the SD Card

**Time: 15 minutes**

### Download Raspberry Pi Imager

1. On your computer, go to: https://www.raspberrypi.com/software/
2. Download **Raspberry Pi Imager** for your OS
3. Install and open it

### Flash the Operating System

1. **Insert microSD card** into your computer

2. **In Raspberry Pi Imager:**
   - Click **"Choose Device"** → Select **Raspberry Pi 4**
   - Click **"Choose OS"** → **Raspberry Pi OS (64-bit)**
   - Click **"Choose Storage"** → Select your SD card

3. **Click the Settings icon** (⚙️ gear) in bottom right

4. **Configure settings:**
   ```
   General tab:
   ✅ Set hostname: musicbutler
   ✅ Set username/password:
      Username: pi
      Password: [choose a secure password]
   ✅ Configure wireless LAN:
      SSID: [your WiFi name]
      Password: [your WiFi password]
      Country: [your country, e.g., US]
   ✅ Set locale settings:
      Timezone: [your timezone]
      Keyboard: [usually US]
   
   Services tab:
   ✅ Enable SSH
   ⦿ Use password authentication

   RaspberryPi Connect
   ⦿ Enable RaspberryPi Connect
    Create ID or Login
    Click “Create Auth Key and Open RaspberryPi Imager”

   ```

5. Click **"Save"** → Click **"Yes"** to apply settings

6. Click **"Write"** → Confirm to erase SD card

7. Wait 5-10 minutes for write and verify

8. When it says "Write Successful", click “Finish”, and **eject the SD card**


---

## Part 3: Assemble the Hardware

**Time: 20 minutes**

⚠️ **Important:** Do not plug in power until instructed!

### Step 1: Insert SD Card

1. Locate the microSD slot on the Pi (bottom, opposite USB ports)
2. Insert card with metal contacts facing up
3. Push until it clicks

### Step 2: Connect Camera

1. **Locate camera connector** (between HDMI and USB ports)
2. **Gently pull up** on the black plastic clip (~2mm)
3. **Insert ribbon cable:**
   - Blue side facing USB ports
   - Metal contacts facing HDMI ports
   - Push in firmly
4. **Push down** the black clip to lock
5. **Gently tug** cable to verify it's secure. Note: You will still see some of the metal connectors above the top of the camera connector.

### Step 3: Mount Speaker Bonnet

1. **Position the bonnet** above the Pi
2. **Align the 40-pin header** with GPIO pins
3. **Press down firmly** until fully seated
4. All 40 pins should be connected

### Step 4: Connect Speakers

**Option A: JST Connectors (If your speakers have them)**

1. Simply plug speaker connectors into the JST sockets on the bonnet
2. Left speaker → LEFT socket
3. Right speaker → RIGHT socket
4. Should click in place

**Option B: Screw Terminals**

1. **Strip wire ends** (~1cm of insulation)
2. **Twist copper strands** to prevent fraying
3. **Connect to green screw terminals:**
   ```
   [L+] [L-] [R-] [R+]
   
   Left speaker red wire → L+
   Left speaker black wire → L-
   Right speaker red wire → R+
   Right speaker black wire → R-
   ```
4. Use small screwdriver to tighten screws firmly

---

## Part 4: First Boot and Setup

**Time: 30 minutes**

### Power On

1. **Plug USB-C power into Pi**
2. **Plug power adapter into wall**
3. **Watch for LEDs:**
   - Red LED: Power (solid)
   - Green LED: Activity (flashing)
4. **Wait 2-3 minutes** for first boot

### Connect via SSH

**Find your Pi:**

```bash
# Try hostname first (Mac/Linux/Windows 10+)
ping musicbutler.local
```

You should see replies showing the IP address.

**SSH into the Pi:**

```bash
ssh pi@musicbutler.local
```

Or use IP address if `.local` doesn't work:

```bash
ssh pi@192.168.1.XXX
```

**First connection:**
- Type `yes` when asked about authenticity
- Enter the password you set during SD card setup

**Success!** You should see:
```
pi@musicbutler:~ $
```

---

## Part 5: Configure the System

**Time: 45 minutes**

### Update System

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

Wait 5-10 minutes for updates.

### Configure Audio and Camera

```bash
sudo nano /boot/firmware/config.txt
```

Scroll to bottom (use arrow keys) and add:

```ini
# Music Butler Configuration
# Disable onboard audio
dtparam=audio=off

# Enable I2S audio (Speaker Bonnet)
dtoverlay=hifiberry-dac
dtoverlay=i2s-mmap

# Enable camera
camera_auto_detect=1
start_x=1
```

**Save:** `Ctrl+X` → `Y` → `Enter`

### Reboot and Test

```bash
sudo reboot
```

Wait 1 minute, reconnect:

```bash
ssh pi@musicbutler.local
```

**Test camera:**

```bash
vcgencmd get_camera
```

Should show: `supported=1 detected=1`

**Test audio:**

```bash
aplay -l
```

Should show: `card 0: sndrpihifiberry`

```bash
speaker-test -c2 -t wav
```

You should hear "front left" and "front right" from each speaker.
Press `Ctrl+C` to stop.

**If no sound:**

```bash
amixer set Master unmute
amixer set Master 80%
speaker-test -c2 -t wav
```

### Install Dependencies

```bash
# System packages
sudo apt-get install -y python3-pip python3-opencv libzbar0 python3-numpy \
  libusb-1.0-0-dev python3-pil git curl

# Python libraries
pip3 install --break-system-packages spotipy opencv-python pyzbar pillow \
  qrcode python-escpos
```

### Install Raspotify

```bash
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
```

**Configure Raspotify:**

```bash
sudo nano /etc/raspotify/conf
```

Find and modify these lines (remove `#`):

```bash
DEVICE_NAME="Music Butler"
BITRATE="320"
OPTIONS="--backend alsa --device hw:0,0 --mixer Master --initial-volume=50"
```

**Save and restart:**

```bash
sudo systemctl restart raspotify
sudo systemctl enable raspotify
```

**Test:** Open Spotify on your phone → Play a song → Tap devices icon → Select "Music Butler"

---

## Part 6: Set Up Spotify API

**Time: 10 minutes**

### Create Developer App

1. Go to: https://developer.spotify.com/dashboard
2. **Log in** with your Spotify account
3. Click **"Create app"**
4. Fill in:
   - App name: `Music Butler`
   - App description: `QR code music player`
   - Redirect URI: `http://localhost:8888/callback` ⚠️ **EXACT**
   - Check "Web API"
   - Accept terms
5. Click **"Save"**

### Get Credentials

1. Click **"Settings"** (top right)
2. Copy your **Client ID**
3. Click **"View client secret"** → Copy **Client Secret**
4. **Save these somewhere** - you'll need them next!

---

## Part 7: Install Music Butler

**Time: 15 minutes**

### Clone or Create Project

**Option A: Clone from Git (if repo exists)**

```bash
cd ~
git clone https://github.com/yourusername/music-butler.git
cd music-butler
```

**Option B: Create manually**

```bash
mkdir ~/music-butler
cd ~/music-butler
```

### Create Main Application

```bash
nano music_butler.py
```

Copy the complete code from the `music_butler.py` artifact (see earlier in our conversation).

**Scroll to top and find these lines:**

```python
SPOTIPY_CLIENT_ID = 'YOUR_CLIENT_ID_HERE'
SPOTIPY_CLIENT_SECRET = 'YOUR_CLIENT_SECRET_HERE'
```

**Replace with your actual Spotify credentials from Part 6.**

**Save:** `Ctrl+X` → `Y` → `Enter`

```bash
chmod +x music_butler.py
```

### Create Startup Script

```bash
nano ~/start-music-butler.sh
```

Paste:

```bash
#!/bin/bash
echo "Starting Music Butler..."
sleep 30
cd /home/pi/music-butler
DISPLAY=:0 python3 music_butler.py
```

**Save and make executable:**

```bash
chmod +x ~/start-music-butler.sh
```

### Set Up Auto-Start

```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/music-butler.desktop
```

Paste:

```ini
[Desktop Entry]
Type=Application
Name=Music Butler
Comment=Spotify QR Code Player
Exec=/home/pi/start-music-butler.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
```

**Save:** `Ctrl+X` → `Y` → `Enter`

---

## Part 8: First Run and Test

**Time: 10 minutes**

### Run Music Butler

```bash
cd ~/music-butler
python3 music_butler.py
```

### First-Time Authentication

You'll see a long URL starting with `https://accounts.spotify.com/authorize?...`

**What to do:**

1. **Copy the entire URL**
2. **Paste in a web browser** (any device)
3. **Log into Spotify** if prompted
4. **Click "Agree"** to authorize
5. You'll see "This site can't be reached" - **THIS IS NORMAL**
6. **Copy the ENTIRE URL from browser address bar**
   - Starts with: `http://localhost:8888/callback?code=`
7. **Paste back into terminal**
8. **Press Enter**

Authentication is saved - you won't need to do this again!

### Music Butler Starts!

You should see:

```
============================================================
  MUSIC BUTLER - At Your Service!
============================================================

📷 CAMERA MODES:
  • PLAY MODE (default): Scan QR code to play music
  • PRINT MODE: Scan QR code to print a sticker
...
```

A window opens showing the camera view!

### Create Test QR Code

**On your phone/computer:**

1. Open Spotify
2. Find any playlist
3. Tap ⋯ (three dots) → Share → **Copy Spotify URI**
4. Go to: https://www.qr-code-generator.com/
5. Select "Text" → Paste the URI
6. Generate QR code
7. Display on phone screen

### Test Scanning

1. Hold QR code in front of camera (6-12 inches away)
2. **Music should start playing!** 🎵

**Try controls:**
- `+` = Increase volume
- `-` = Decrease volume
- `q` = Quit

---

## Part 9: Add the Printer (Optional)

**Time: 15 minutes**

Skip if you don't have the Phomemo M02 printer.

### Connect Printer

1. Plug Phomemo M02 into USB port
2. Turn printer on
3. Load sticker paper

### Find USB IDs

```bash
lsusb
```

Look for "Phomemo", "ICS Advent", or similar.

Example output:
```
Bus 001 Device 004: ID 0fe6:811e ICS Advent
```

Note: `0x0fe6` (vendor) and `0x811e` (product)

### Set Permissions

```bash
sudo nano /etc/udev/rules.d/99-printer.rules
```

Paste (replace with YOUR IDs):

```
SUBSYSTEM=="usb", ATTR{idVendor}=="0fe6", ATTR{idProduct}=="811e", MODE="0666"
```

**Save and reload:**

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and replug printer.

### Configure Music Butler

```bash
nano ~/music-butler/music_butler.py
```

Find:

```python
PRINTER_VENDOR_ID = 0x0000
PRINTER_PRODUCT_ID = 0x0000
```

Change to your IDs:

```python
PRINTER_VENDOR_ID = 0x0fe6
PRINTER_PRODUCT_ID = 0x811e
```

**Save:** `Ctrl+X` → `Y` → `Enter`

### Test Printer

```bash
python3 ~/music-butler/music_butler.py
```

1. Press `p` for Print Mode (text turns orange)
2. Scan a QR code
3. Printer should create a sticker!
4. Press `p` to return to Play Mode

---

## Part 10: Creating QR Codes

### Get Spotify URIs

**Desktop:**
- Right-click playlist/album → Share → Copy Spotify URI

**Mobile:**
- Tap ⋯ → Share → Copy Spotify URI

**Convert from link:**
```
Link: https://open.spotify.com/playlist/37i9dQZF1DX4WYpdgoIcn6
URI:  spotify:playlist:37i9dQZF1DX4WYpdgoIcn6
```

### Generate QR Codes

**Online generators:**
- https://www.qr-code-generator.com/
- https://www.qrcode-monkey.com/

**Steps:**
1. Select "Text" type
2. Paste Spotify URI
3. Generate
4. Download or display on screen

### Bulk Generator Script

```bash
nano ~/music-butler/create_qr_codes.py
```

Paste:

```python
#!/usr/bin/env python3
import qrcode
import os

PLAYLISTS = {
    "Chill Vibes": "spotify:playlist:37i9dQZF1DX4WYpdgoIcn6",
    "Workout": "spotify:playlist:37i9dQZF1DX76Wlfdnj7AP",
    # Add more here
}

os.makedirs("QR_codes", exist_ok=True)

for name, uri in PLAYLISTS.items():
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    filename = f"QR_codes/{name.replace(' ', '_')}.png"
    img.save(filename)
    print(f"✓ Created: {filename}")
```

**Run:**

```bash
chmod +x create_qr_codes.py
python3 create_qr_codes.py
```

---

## Part 11: Usage Guide

### Starting Music Butler

**Manually:**
```bash
python3 ~/music-butler/music_butler.py
```

**Auto-start (already configured):**
```bash
sudo reboot
```

Waits 30 seconds, then starts automatically.

### Keyboard Controls

| Key | Function |
|-----|----------|
| `p` | Toggle Play/Print mode |
| `+` or `=` | Increase volume |
| `-` | Decrease volume |
| `q` | Quit |

### Modes

**Play Mode (Green):**
- Default mode
- Scan QR code → Music plays

**Print Mode (Orange):**
- Press `p` to switch
- Scan QR code → Prints sticker

### Best Practices

**QR Code Size:**
- Minimum 2x2 inches
- 3x3 inches ideal
- Works on screens or paper

**Camera Distance:**
- 6-12 inches from camera
- Ensure good focus

**Lighting:**
- Bright, even lighting
- Avoid direct sunlight on camera

**Scanning:**
- 3-second cooldown between scans
- Hold steady until recognized

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed solutions.

### Quick Fixes

**No sound:**
```bash
amixer set Master unmute
amixer set Master 80%
sudo systemctl restart raspotify
```

**Camera not working:**
```bash
vcgencmd get_camera
# Check cable connection
```

**Spotify device not found:**
```bash
sudo systemctl restart raspotify
# Check in Spotify app for "Music Butler"
```

**QR codes won't scan:**
- Move closer/farther
- Improve lighting
- Print larger codes
- Hold steadier

---

## Advanced Topics

### Building an Enclosure

Consider a case once everything works:
- Cardboard box with holes
- 3D printed case
- Wooden craft box
- Include: camera port, speaker grills, printer slot, ventilation

### Usage Ideas

**Music cards for kids:**
- Print playlist stickers
- Mount on cardboard cards
- Kids choose independently

**Party playlist selector:**
- Display QR codes
- Guests scan to change music

**Physical music library:**
- Print all playlists
- Organize in binder
- Browse like vinyl

---

## System Maintenance

### Check Status

```bash
# Raspotify
sudo systemctl status raspotify

# Camera
vcgencmd get_camera

# Audio
aplay -l

# Disk space
df -h
```

### Update System

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### View Logs

```bash
# Music Butler output
cd ~/music-butler
python3 music_butler.py 2>&1 | tee debug.log

# Raspotify logs
sudo journalctl -u raspotify -f
```

---

## What You've Built

✅ Raspberry Pi music player  
✅ QR code scanning system  
✅ High-quality audio output  
✅ Optional sticker printer  
✅ Auto-start on boot  
✅ No phone needed  

**Enjoy your Music Butler!** 🎵🤖

---

**Questions or issues?** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or open an issue on GitHub.