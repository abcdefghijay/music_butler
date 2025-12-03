# Music Butler

A Raspberry Pi-based music player that scans QR codes to play Spotify playlists, albums, and tracks. Can also print custom QR code stickers!

## Features

- 📷 QR code scanning via Raspberry Pi camera
- 🎵 Plays Spotify content (playlists, albums, tracks)
- 🖨️ Prints custom QR code stickers on thermal printer
- 🔊 High-quality audio via I2S DAC
- ⌨️ Simple keyboard controls
- 🚀 Auto-starts on boot

## Hardware Requirements

- Raspberry Pi 4 (4GB recommended)
- Raspberry Pi Camera Module V2
- Adafruit I2S 3W Stereo Speaker Bonnet
- 2x 4Ω 3W speakers
- Phomemo M02 thermal sticker printer (optional)
- MicroSD card (32GB+)
- USB-C power supply (5V 3A)

## Software Requirements

- Raspberry Pi OS (64-bit)
- Python 3.9+
- Raspotify (Spotify Connect)
- Required Python packages:
  - spotipy
  - opencv-python
  - pyzbar
  - pillow
  - qrcode
  - python-escpos

## Setup

### 1. Configure Audio

Edit `/boot/firmware/config.txt`:
```
dtparam=audio=off
dtoverlay=hifiberry-dac
dtoverlay=i2s-mmap
```

### 2. Install Dependencies
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-opencv libzbar0 python3-numpy libusb-1.0-0-dev python3-pil
pip3 install --break-system-packages spotipy opencv-python pyzbar pillow qrcode python-escpos
```

### 3. Install Raspotify
```bash
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
```

Configure in `/etc/raspotify/conf`:
```
DEVICE_NAME="Music Butler"
OPTIONS="--backend alsa --device hw:0,0 --mixer Master --initial-volume=50"
```

### 4. Configure Spotify API

1. Go to https://developer.spotify.com/dashboard
2. Create an app
2. a) Use redirect URI http://127.0.0.1:8000/callback
2. b) Set scopes Web API (and Web Playback SDK?)
3. Get Client ID and Client Secret
4. Edit `music_butler.py` and add your credentials

### 5. Configure Printer (Optional)

1. Connect Phomemo M02 via USB
2. Run `lsusb` to find vendor and product IDs
3. Edit `music_butler.py` and add printer IDs
4. Set up udev rules for permissions

## Usage

### Running Manually
```bash
cd ~/music-butler
python3 music_butler.py
```

### Keyboard Controls

- `p` - Toggle between Play and Print modes
- `+` - Increase volume
- `-` - Decrease volume
- `q` - Quit

### Creating QR Codes

1. Get Spotify URI:
   - Right-click playlist/album in Spotify
   - Share → Copy Spotify URI
2. Generate QR code at https://www.qr-code-generator.com/
3. Print or display on phone screen

### Play Mode (Default)

Scan QR codes to play music instantly!

### Print Mode

Press `p` to enter Print mode, then scan QR codes to print stickers.

## Troubleshooting

### No Sound
```bash
speaker-test -c2 -t wav
amixer set Master unmute
amixer set Master 80%
sudo systemctl restart raspotify
```

### Camera Not Working
```bash
vcgencmd get_camera
# Should show: supported=1 detected=1
```

Check camera cable and `/boot/firmware/config.txt`.

### Spotify Device Not Found
```bash
sudo systemctl status raspotify
sudo journalctl -u raspotify -f
```

Open Spotify app and look for "Music Butler" in devices list.

### Printer Not Working
```bash
lsusb  # Check if printer is detected
```

Verify USB IDs in `music_butler.py` and udev rules.

## File Structure
```
~/music-butler/
├── music_butler.py          # Main application
├── README.md                # This file
├── .spotify_cache           # Spotify auth cache (auto-generated)
└── QR_codes/                # Store your QR code images (optional)
```

## License

MIT License - Feel free to modify and share!

## Credits

Built with:
- Spotipy (Spotify API)
- OpenCV (Camera processing)
- pyzbar (QR code detection)
- python-escpos (Thermal printing)

## ACKNOWLEDGEMENTS

Special thanks to:
- Elena e Pasuqale (Supervision)
- Mindy (Artwork)
- tbd (Casing)

## Version History

- v1.0 (2025) - Initial release