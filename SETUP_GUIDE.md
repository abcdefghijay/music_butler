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
- [Part 9: Rotary Encoder Setup (Optional)](#part-9-add-the-rotary-encoder-optional)
- [Part 10: Printer Setup (Optional)](#part-10-add-the-printer-optional)
- [Part 11: Creating QR Codes](#part-11-creating-qr-codes)
- [Part 12: Usage](#part-12-usage-guide)

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
| Adafruit I2C QT Rotary Encoder Breakout | $10 | Adafruit (#4991) | Optional, recommended for volume/playback control |
| STEMMA QT Cable (50-200mm) | $1-2 | Adafruit (#4210-4212) | For rotary encoder connection |
| Rotary Encoder Knob | $3 | Adafruit (#5527) | Optional, for better grip |
| Phomemo M02 Printer | $45 | Amazon | Optional, for printing stickers |
| Thermal Sticker Paper (53mm) | $12 | Amazon | Comes with printer, extras available |

**Total Cost:** ~$140 (basic) or ~$155 (with rotary encoder) or ~$200 (with encoder + printer)

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
  qrcode python-escpos adafruit-circuitpython-seesaw
```

### Enable I2C (for Rotary Encoder)

If you plan to use the rotary encoder:

```bash
sudo raspi-config
```

1. Navigate to **Interface Options**
2. Select **I2C**
3. Select **Yes** to enable
4. Select **Finish** and reboot if prompted

**Verify I2C is enabled:**

```bash
lsmod | grep i2c
```

You should see `i2c_dev` and `i2c_bcm2835` listed.

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
   - Redirect URI: `http://127.0.0.1:8000/callback` ⚠️ **EXACT**
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

### Preserve Your Config When Updating

**Important:** After you've edited `config.py` with your personal credentials, you'll want to preserve those settings when pulling updates from GitHub.

**Best Solution: Use `git update-index --skip-worktree`**

This tells Git to ignore local changes to `config.py`:

```bash
# Navigate to your music-butler directory
cd ~/music-butler

# Tell git to skip tracking changes to config.py
git update-index --skip-worktree config.py

# Now you can safely pull updates
git pull origin main  # or master, depending on your branch name
```

Your local `config.py` will be preserved during updates.

**Note: Restoring config.py to Git tracking**

If you later want to add `config.py` back to the worktree (for example, if you want Git to track changes to it again, or if you're switching to a different configuration method), you can restore it:

```bash
# Remove the skip-worktree flag
git update-index --no-skip-worktree config.py

# After this, Git will track changes to config.py again
# You may need to resolve any conflicts if the file has diverged from the repository
```

**Alternative: Stash and Reapply**

If you prefer a temporary approach:

```bash
# Stash your local changes
git stash push config.py -m "Preserve local config"

# Pull the updates
git pull origin main

# Reapply your local config
git stash pop
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
   - Starts with: `http://127.0.0.1:8000/callback?code=`
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
- Rotate knob (if encoder connected) = Adjust volume
- Single press knob = Play/Pause
- `+` = Increase volume (keyboard)
- `-` = Decrease volume (keyboard)
- `q` = Quit

---

## Part 9: Add the Rotary Encoder (Optional)

**Time: 10 minutes**

Skip if you don't have the Adafruit I2C QT Rotary Encoder Breakout.

### What the Rotary Encoder Does

The rotary encoder adds physical controls:
- **Rotate knob** → Adjust volume
- **Single press** → Play/Pause music
- **Double press** → Print sticker for currently playing playlist

### Connect the Rotary Encoder

1. **Locate I2C pins on Raspberry Pi:**
   - **SDA** (GPIO 2) - Data line
   - **SCL** (GPIO 3) - Clock line
   - **3.3V** - Power
   - **GND** - Ground

2. **Connect STEMMA QT cable:**
   - One end plugs into the rotary encoder breakout board
   - The other end connects to the Pi's I2C pins:
     ```
     Red wire (VIN) → 3.3V (Pin 1)
     Black wire (GND) → GND (Pin 6)
     White wire (SDA) → GPIO 2 / SDA (Pin 3)
     Green wire (SCL) → GPIO 3 / SCL (Pin 5)
     ```

   **Alternative:** If you don't have a STEMMA QT cable, you can use jumper wires:
   ```
   VIN → 3.3V (Pin 1)
   GND → GND (Pin 6)
   SDA → GPIO 2 / SDA (Pin 3)
   SCL → GPIO 3 / SCL (Pin 5)
   ```

3. **Attach knob** (optional but recommended):
   - Screw the knob onto the encoder shaft
   - Use the set screw to secure it

### Verify Connection

```bash
# Check if I2C device is detected
sudo i2cdetect -y 1
```

You should see `36` in the output (the rotary encoder's I2C address).

**If you see `UU` instead of `36`:**
- The device is detected but may be in use
- This is okay - Music Butler will handle it

**If you see nothing:**
- Check cable connections
- Verify I2C is enabled (`sudo raspi-config`)
- Try a different STEMMA QT cable

### Test the Rotary Encoder

```bash
cd ~/music-butler
python3 music_butler.py
```

When Music Butler starts, you should see:
```
✓ Rotary encoder connected
✓ Rotary encoder monitoring started
```

**Try the controls:**
- Rotate the knob → Volume should change
- Single press → Music should play/pause
- Double press (quickly) → Should print sticker for current playlist

**If the encoder doesn't work:**
- Check that I2C is enabled
- Verify cable connections
- Make sure `adafruit-circuitpython-seesaw` is installed
- Check the I2C address (should be 0x36)

---

## Part 10: Add the Printer (Optional)

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

## Part 11: Creating QR Codes

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

## Part 12: Usage Guide

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

### Rotary Encoder Controls (if connected)

| Action | Function |
|--------|----------|
| **Rotate knob** | Adjust volume up/down |
| **Single press** | Play/Pause current playback |
| **Double press** | Print sticker for currently playing playlist/album |

### Keyboard Controls

| Key | Function |
|-----|----------|
| `p` | Toggle Play/Print mode |
| `+` or `=` | Increase volume |
| `-` or `_` | Decrease volume |
| `Space` | Play/Pause (alternative to rotary encoder) |
| `q` | Quit |

### Modes

**Play Mode (Green):**
- Default mode
- Scan QR code → Music plays

**Print Mode (Orange):**
- Press `p` to switch
- Scan QR code → Prints sticker

**Printing Current Playlist:**
- Play a playlist or album (via QR code)
- Double-press the rotary encoder knob
- A sticker will be printed for the currently playing content

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