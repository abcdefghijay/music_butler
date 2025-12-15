"""
Configuration settings for Music Butler
Loads user-specific settings from config.py
"""

import sys

# Try to import optional libraries and set availability flags
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False

try:
    from escpos.printer import Usb
    ESCPOS_AVAILABLE = True
except ImportError:
    ESCPOS_AVAILABLE = False
    print("⚠ python-escpos not installed. Printing will be disabled.")

try:
    import usb.core
    import usb.util
    USB_CORE_AVAILABLE = True
except ImportError:
    USB_CORE_AVAILABLE = False

try:
    from adafruit_seesaw.seesaw import Seesaw
    from adafruit_seesaw.rotaryio import IncrementalEncoder
    from adafruit_seesaw.digitalio import DigitalIO
    import board
    import busio
    ROTARY_ENCODER_AVAILABLE = True
except ImportError:
    ROTARY_ENCODER_AVAILABLE = False
    print("⚠ Adafruit seesaw library not installed. Rotary encoder will be disabled.")
    print("  Install with: pip3 install --break-system-packages adafruit-circuitpython-seesaw")

# Import configuration from config.py (user-specific settings)
# Note: This imports from the root-level config.py, not this config module
import importlib.util
import pathlib

# Get the parent directory (music-butler root)
root_dir = pathlib.Path(__file__).parent.parent
config_file = root_dir / 'config.py'

if config_file.exists():
    spec = importlib.util.spec_from_file_location("user_config", config_file)
    user_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(user_config)
    
    SPOTIPY_CLIENT_ID = user_config.SPOTIPY_CLIENT_ID
    SPOTIPY_CLIENT_SECRET = user_config.SPOTIPY_CLIENT_SECRET
    SPOTIPY_REDIRECT_URI = user_config.SPOTIPY_REDIRECT_URI
    PRINTER_VENDOR_ID = user_config.PRINTER_VENDOR_ID
    PRINTER_PRODUCT_ID = user_config.PRINTER_PRODUCT_ID
    PRINTER_ENABLED = user_config.PRINTER_ENABLED
else:
    print("❌ ERROR: config.py not found!")
    print("Please create config.py with your Spotify credentials.")
    print("See config.py.example for a template.")
    sys.exit(1)

# Spotify API scopes
SCOPE = 'user-read-playback-state,user-modify-playback-state,playlist-read-private'

# Scanner settings
SCAN_COOLDOWN = 3  # Seconds between scans of same QR code
DEFAULT_VOLUME = 70  # Initial volume (0-100)

# Camera settings
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Rotary encoder settings
ROTARY_ENCODER_ENABLED = True  # Set to False to disable rotary encoder
DOUBLE_PRESS_TIMEOUT = 0.5  # Seconds to detect double press
VOLUME_STEP = 2  # Volume change per encoder step (1-5 recommended)
