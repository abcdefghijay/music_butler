#!/usr/bin/env python3
"""
Music Butler - Spotify QR Code Player with Sticker Printer
A Raspberry Pi-based music player that scans QR codes to play Spotify content
and prints custom QR code stickers.

Version: 1.1
License: MIT
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cv2
from pyzbar import pyzbar
import time
import numpy as np
import subprocess
import sys
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
import threading
import argparse

# Try to import picamera2 (for direct libcamera access on Raspberry Pi)
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False

# Try to import printer library (optional)
try:
    from escpos.printer import Usb
    ESCPOS_AVAILABLE = True
except ImportError:
    ESCPOS_AVAILABLE = False
    print("⚠ python-escpos not installed. Printing will be disabled.")

# Try to import rotary encoder library (optional)
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

# =============================================================================
# CONFIGURATION - Load from config.py
# =============================================================================

# Import configuration from config.py (user-specific settings)
try:
    from config import (
        SPOTIPY_CLIENT_ID,
        SPOTIPY_CLIENT_SECRET,
        SPOTIPY_REDIRECT_URI,
        PRINTER_VENDOR_ID,
        PRINTER_PRODUCT_ID,
        PRINTER_ENABLED
    )
except ImportError:
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

# =============================================================================
# STICKER PRINTER CLASS
# =============================================================================

class StickerPrinter:
    """Handles QR code sticker printing on thermal printers"""
    
    @staticmethod
    def _set_media_width(printer, width_pixels):
        """
        Set the media width in pixels for the printer profile.
        This enables the center flag to work properly.
        
        Args:
            printer: The escpos Usb printer object
            width_pixels: Width in pixels (384 for 53mm thermal printer)
        """
        try:
            if not hasattr(printer, 'profile') or not printer.profile:
                return False
            
            if not hasattr(printer.profile, 'media'):
                return False
            
            media = printer.profile.media
            
            # Try dictionary-style access first
            if hasattr(media, '__setitem__') or isinstance(media, dict):
                if 'width' not in media:
                    media['width'] = {}
                media['width']['pixel'] = width_pixels
                return True
            
            # Try object-style access
            if hasattr(media, 'width'):
                if not hasattr(media.width, 'pixel'):
                    # Create a simple object with pixel attribute
                    class WidthObj:
                        def __init__(self, pixel):
                            self.pixel = pixel
                    media.width = WidthObj(width_pixels)
                else:
                    media.width.pixel = width_pixels
                return True
            
            # Try to create width attribute
            class WidthObj:
                def __init__(self, pixel):
                    self.pixel = pixel
            media.width = WidthObj(width_pixels)
            return True
            
        except (AttributeError, TypeError, KeyError, Exception):
            return False
    
    @staticmethod
    def _convert_id_to_int(id_value):
        """Convert printer ID to integer, handling both string and int formats"""
        if isinstance(id_value, int):
            return id_value
        elif isinstance(id_value, str):
            # Handle string formats: '0x4c4a', '0x4c4a', '4c4a', etc.
            id_value = id_value.strip()
            if id_value.startswith('0x') or id_value.startswith('0X'):
                return int(id_value, 16)
            else:
                # Try as hex first, then decimal
                try:
                    return int(id_value, 16)
                except ValueError:
                    return int(id_value)
        else:
            raise ValueError(f"Invalid printer ID format: {id_value} (type: {type(id_value)})")
    
    def __init__(self, vendor_id, product_id):
        self.enabled = False
        self.printer = None
        
        if not ESCPOS_AVAILABLE:
            print("⚠ Printer library not available")
            return
        
        # Convert IDs to integers if they're strings
        try:
            self.vendor_id = self._convert_id_to_int(vendor_id)
            self.product_id = self._convert_id_to_int(product_id)
        except (ValueError, TypeError) as e:
            print(f"⚠ Invalid printer ID format: {e}")
            print("  Printer IDs should be integers (e.g., 0x4c4a) or hex strings (e.g., '0x4c4a')")
            return
            
        if self.vendor_id == 0x0000 or self.product_id == 0x0000:
            print("⚠ Printer IDs not configured (printing disabled)")
            return
        
        try:
            # Jieli Technology printers (vendor 0x4c4a) often need manual endpoint configuration
            # Try manual endpoints first for these printers
            is_jieli_printer = (self.vendor_id == 0x4c4a)
            
            if not is_jieli_printer:
                # Try multiple profile options for better compatibility
                for profile in ['simple', 'default', 'POS-5890']:
                    try:
                        self.printer = Usb(self.vendor_id, self.product_id, profile=profile)
                        # Set media width for centering (384 pixels for 53mm thermal printer)
                        self._set_media_width(self.printer, 384)
                        self.enabled = True
                        self.profile = profile
                        print(f"✓ Sticker printer connected (profile: {profile})")
                        break
                    except Exception as profile_error:
                        # Only show error if it's the last profile we're trying
                        if profile == 'POS-5890':
                            continue
                        continue
            
            # If profiles failed (or Jieli printer), try manual endpoint configuration
            if not self.enabled:
                if is_jieli_printer:
                    print("  → Using manual endpoint configuration for Jieli Technology printer...")
                else:
                    print("  → Profiles failed, trying manual endpoint configuration...")
                # Common endpoint combinations for thermal printers
                # Most printers use: out_ep=0x01 or 0x02, in_ep=0x81 or 0x82
                # Jieli Technology printers typically use (0x02, 0x82)
                endpoint_combos = [
                    (0x02, 0x82),  # Jieli Technology / Phomemo (most common for this vendor)
                    (0x01, 0x81),  # Other common printers
                    (0x01, 0x82),
                    (0x02, 0x81),
                    (0x03, 0x83),
                ]
                
                for out_ep, in_ep in endpoint_combos:
                    try:
                        self.printer = Usb(
                            self.vendor_id, 
                            self.product_id, 
                            interface=0,
                            in_ep=in_ep,
                            out_ep=out_ep
                        )
                        # Set media width for centering (384 pixels for 53mm thermal printer)
                        self._set_media_width(self.printer, 384)
                        self.enabled = True
                        self.profile = None
                        self.endpoints = (out_ep, in_ep)
                        print(f"✓ Sticker printer connected (manual endpoints: out=0x{out_ep:02x}, in=0x{in_ep:02x})")
                        break
                    except Exception as ep_error:
                        continue
                
                if not self.enabled:
                    raise Exception("Could not connect with any profile or endpoint combination")
                
        except Exception as e:
            print(f"⚠ Printer not available: {e}")
            print("  Printing disabled - scanner will still work")
            print("\n  To find correct endpoints, run:")
            print(f"    lsusb -vvv -d {hex(self.vendor_id)}:{hex(self.product_id)} | grep bEndpointAddress")
            print("  Look for lines with 'OUT' and 'IN' to find out_ep and in_ep values")
    
    def print_qr_sticker(self, spotify_uri, title, artist_or_owner=""):
        """
        Print a QR code sticker with title and artist/owner
        
        Args:
            spotify_uri: Spotify URI (playlist/album/track)
            title: Main title to print
            artist_or_owner: Subtitle (artist or playlist owner)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            print("✗ Printer not available")
            return False
        
        try:
            print(f"🖨 Printing: {title}")
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=4,
                border=2,
            )
            qr.add_data(spotify_uri)
            qr.make(fit=True)
            
            # Create QR code image
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Create sticker layout
            # Standard 53mm thermal printer = ~384 pixels width
            sticker_width = 384
            qr_size = 280
            
            # Resize QR code
            qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
            
            # Calculate height
            header_height = 30  # Space for "MUSIC BUTLER" at top
            text_height = 100   # Space for title/artist below QR code
            sticker_height = header_height + qr_size + text_height
            
            # Create white background
            sticker = Image.new('1', (sticker_width, sticker_height), 1)
            
            # Add text
            draw = ImageDraw.Draw(sticker)
            
            # Try to load fonts
            try:
                font_header = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
                font_title = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
                font_artist = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except:
                font_header = ImageFont.load_default()
                font_title = ImageFont.load_default()
                font_artist = ImageFont.load_default()
            
            # Draw "MUSIC BUTLER" header at top
            header_text = "MUSIC BUTLER"
            bbox = draw.textbbox((0, 0), header_text, font=font_header)
            text_width = bbox[2] - bbox[0]
            x_pos = (sticker_width - text_width) // 2
            y_pos = 5
            draw.text((x_pos, y_pos), header_text, fill=0, font=font_header)
            
            # Paste QR code centered (below header)
            x_offset = (sticker_width - qr_size) // 2
            sticker.paste(qr_img, (x_offset, header_height))
            
            # Truncate text if too long
            if len(title) > 30:
                title = title[:27] + "..."
            if len(artist_or_owner) > 35:
                artist_or_owner = artist_or_owner[:32] + "..."
            
            # Draw title (below QR code)
            y_pos = header_height + qr_size + 10
            bbox = draw.textbbox((0, 0), title, font=font_title)
            text_width = bbox[2] - bbox[0]
            x_pos = (sticker_width - text_width) // 2
            draw.text((x_pos, y_pos), title, fill=0, font=font_title)
            
            # Draw artist/owner
            if artist_or_owner:
                y_pos += 25
                bbox = draw.textbbox((0, 0), artist_or_owner, font=font_artist)
                text_width = bbox[2] - bbox[0]
                x_pos = (sticker_width - text_width) // 2
                draw.text((x_pos, y_pos), artist_or_owner, fill=0, font=font_artist)
            
            # Print the sticker
            # Set media width if not already set (for centering to work)
            self._set_media_width(self.printer, sticker_width)
            self.printer.image(sticker, center=True)
            self.printer.text("\n\n")
            self.printer.cut()
            
            print(f"✓ Sticker printed successfully")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"✗ Error printing sticker: {error_msg}")
            
            # Provide helpful error messages for common issues
            if "device not found" in error_msg.lower() or "not found or cable not plugged" in error_msg.lower():
                print("  → USB device not found error")
                print("  → Troubleshooting steps:")
                print(f"     1. Check if printer is connected: lsusb | grep -i '{hex(self.vendor_id)[2:]}'")
                print(f"     2. Verify printer IDs in config.py:")
                print(f"        Current: vendor_id={hex(self.vendor_id)}, product_id={hex(self.product_id)}")
                print("     3. Unplug and replug the printer USB cable")
                print("     4. Try a different USB port")
                print("     5. Check USB device list: lsusb")
                print("     6. Verify the printer is powered on")
            elif "endpoint" in error_msg.lower() or "0x1" in error_msg or "invalid endpoint" in error_msg.lower():
                print("  → USB endpoint error detected")
                print("  → Attempting to reconnect with manual endpoint configuration...")
                # When endpoint errors occur, skip profiles and use manual endpoints directly
                # Profiles are causing the endpoint issue, so we need explicit endpoint addresses
                try:
                    # Common endpoint combinations for thermal printers
                    # Jieli Technology printers typically use (0x02, 0x82)
                    endpoint_combos = [
                        (0x02, 0x82),  # Jieli Technology / Phomemo (most common for this vendor)
                        (0x01, 0x81),  # Other common printers
                        (0x01, 0x82),
                        (0x02, 0x81),
                        (0x03, 0x83),
                    ]
                    
                    reconnected = False
                    # Skip profiles - go straight to manual endpoints when endpoint error occurs
                    for out_ep, in_ep in endpoint_combos:
                        try:
                            self.printer = Usb(
                                self.vendor_id, 
                                self.product_id, 
                                interface=0,
                                in_ep=in_ep,
                                out_ep=out_ep
                            )
                            # Set media width for centering (384 pixels for 53mm thermal printer)
                            self._set_media_width(self.printer, 384)
                            self.profile = None
                            self.endpoints = (out_ep, in_ep)
                            print(f"  → Reconnected with manual endpoints: out=0x{out_ep:02x}, in=0x{in_ep:02x}")
                            reconnected = True
                            break
                        except Exception as ep_error:
                            continue
                    
                    if not reconnected:
                        raise Exception("Could not reconnect with any endpoint combination")
                    
                    # Retry printing after reconnection
                    print("  → Retrying print operation...")
                    # Set media width if not already set (for centering to work)
                    self._set_media_width(self.printer, sticker_width)
                    self.printer.image(sticker, center=True)
                    self.printer.text("\n\n")
                    self.printer.cut()
                    print(f"✓ Sticker printed successfully")
                    return True
                    
                except Exception as reconnect_error:
                    print(f"  → Reconnection failed: {reconnect_error}")
                    print("  → Troubleshooting steps:")
                    print("     1. Find correct endpoints:")
                    print(f"        lsusb -vvv -d {hex(self.vendor_id)}:{hex(self.product_id)} | grep bEndpointAddress")
                    print("        Look for lines with 'OUT' (out_ep) and 'IN' (in_ep)")
                    print("     2. Unplug and replug the printer USB cable")
                    print("     3. Try a different USB port")
                    print("     4. Check if printer needs drivers: dmesg | tail -20")
            elif "permission" in error_msg.lower() or "access" in error_msg.lower():
                print("  → Permission error - try:")
                print("     1. Add user to printer group: sudo usermod -a -G lp pi")
                print("     2. Check udev rules for USB device permissions")
                print("     3. Verify USB device permissions: ls -l /dev/bus/usb/")
            
            return False

# =============================================================================
# ROTARY ENCODER HANDLER CLASS
# =============================================================================

class RotaryEncoderHandler:
    """Handles rotary encoder input in a separate thread"""
    
    def __init__(self, callback_volume, callback_single_press, callback_double_press):
        self.enabled = False
        self.encoder = None
        self.button = None
        self.i2c = None
        self.seesaw = None
        self.running = False
        self.thread = None
        
        self.callback_volume = callback_volume
        self.callback_single_press = callback_single_press
        self.callback_double_press = callback_double_press
        
        self.last_position = None
        self.last_button_state = False
        self.last_press_time = 0
        
        if not ROTARY_ENCODER_AVAILABLE:
            print("⚠ Rotary encoder library not available")
            return
        
        if not ROTARY_ENCODER_ENABLED:
            print("⚠ Rotary encoder disabled in configuration")
            return
        
        try:
            # Initialize I2C
            try:
                self.i2c = busio.I2C(board.SCL, board.SDA)
            except (ValueError, AttributeError) as e:
                raise Exception(f"I2C pins not available: {e}. Make sure I2C is enabled.")
            
            self.seesaw = Seesaw(self.i2c, addr=0x36)
            
            # Initialize encoder
            self.encoder = IncrementalEncoder(self.seesaw)
            self.last_position = self.encoder.position
            
            # Initialize button
            self.button = DigitalIO(self.seesaw, 24)
            self.button.direction = DigitalIO.INPUT
            self.button.pull = DigitalIO.PULL_UP
            
            self.enabled = True
            print("✓ Rotary encoder connected")
        except Exception as e:
            print(f"⚠ Rotary encoder not available: {e}")
            print("  Rotary encoder disabled - keyboard controls will still work")
            print("  To enable: Install adafruit-circuitpython-seesaw and enable I2C")
    
    def start(self):
        """Start the encoder monitoring thread"""
        if not self.enabled:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("✓ Rotary encoder monitoring started")
    
    def stop(self):
        """Stop the encoder monitoring thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
    
    def _monitor_loop(self):
        """Main monitoring loop (runs in thread)"""
        while self.running:
            try:
                # Check encoder position
                current_position = self.encoder.position
                if self.last_position is not None:
                    position_change = current_position - self.last_position
                    if position_change != 0:
                        # Volume control
                        if self.callback_volume:
                            self.callback_volume(position_change)
                        self.last_position = current_position
                else:
                    self.last_position = current_position
                
                # Check button state
                button_pressed = not self.button.value  # Inverted because of pull-up
                current_time = time.time()
                
                if button_pressed and not self.last_button_state:
                    # Button just pressed
                    time_since_last = current_time - self.last_press_time
                    
                    if time_since_last < DOUBLE_PRESS_TIMEOUT:
                        # Double press detected
                        if self.callback_double_press:
                            self.callback_double_press()
                        self.last_press_time = 0  # Reset to prevent triple-press
                    else:
                        # Single press - wait to see if it becomes double
                        self.last_press_time = current_time
                
                elif not button_pressed and self.last_button_state:
                    # Button just released
                    time_since_press = current_time - self.last_press_time
                    
                    if (time_since_press >= DOUBLE_PRESS_TIMEOUT and 
                        self.last_press_time > 0):
                        # Single press confirmed (no second press)
                        if self.callback_single_press:
                            self.callback_single_press()
                        self.last_press_time = 0
                
                self.last_button_state = button_pressed
                
                time.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                print(f"⚠ Rotary encoder error: {e}")
                time.sleep(0.1)

# =============================================================================
# MUSIC BUTLER CLASS
# =============================================================================

class MusicButler:
    """Main application class for QR code scanning and playback"""
    
    def __init__(self, force_display=False, verbose=False, debug_mode=False, no_display=False):
        self._force_display = force_display
        self._verbose = verbose
        self._debug_mode = debug_mode
        self._no_display = no_display
        print("\n" + "="*60)
        print("  MUSIC BUTLER - Initialization")
        print("="*60)
        
        # Check credentials
        if SPOTIPY_CLIENT_ID == 'YOUR_CLIENT_ID_HERE':
            print("\n❌ ERROR: Spotify API credentials not configured!")
            print("\nPlease edit config.py and add your credentials:")
            print("1. Go to: https://developer.spotify.com/dashboard")
            print("2. Create an app and get your Client ID and Secret")
            print("3. Edit config.py and replace YOUR_CLIENT_ID_HERE")
            print("   and YOUR_CLIENT_SECRET_HERE with your actual values\n")
            sys.exit(1)
        
        # Initialize Spotify client
        # Disable browser opening for headless operation
        # Use cached token if available, otherwise prompt for manual auth
        try:
            auth_manager = SpotifyOAuth(
                client_id=SPOTIPY_CLIENT_ID,
                client_secret=SPOTIPY_CLIENT_SECRET,
                redirect_uri=SPOTIPY_REDIRECT_URI,
                scope=SCOPE,
                cache_path='.spotify_cache',
                open_browser=False  # Disable browser opening for headless operation
            )
            
            # Check if we have a cached token
            token_info = auth_manager.get_cached_token()
            
            if not token_info:
                # No cached token - need to authenticate
                print("\n" + "="*60)
                print("  SPOTIFY AUTHENTICATION REQUIRED")
                print("="*60)
                print("\nNo cached authentication token found.")
                print("You need to authenticate with Spotify first.\n")
                print("OPTION 1: Run the authentication script (recommended):")
                print("  python3 authenticate_spotify.py\n")
                print("OPTION 2: Authenticate manually:")
                print("  1. The auth URL will be printed below")
                print("  2. Copy the URL and open it in a browser (on any device)")
                print("  3. Log in and authorize the app")
                print("  4. Copy the ENTIRE callback URL from the browser")
                print("  5. Paste it here when prompted\n")
                print("="*60 + "\n")
                
                # Get authorization URL
                auth_url = auth_manager.get_authorize_url()
                print(f"\n🔗 Authorization URL:\n{auth_url}\n")
                print("="*60)
                print("\n📋 INSTRUCTIONS:")
                print("1. Copy the URL above")
                print("2. Open it in a web browser (on your computer or phone)")
                print("3. Log in to Spotify if prompted")
                print("4. Click 'Agree' to authorize Music Butler")
                print("5. You'll see an error page (this is normal)")
                print("6. Copy the ENTIRE URL from the browser address bar")
                print(f"   (It should start with: {SPOTIPY_REDIRECT_URI}?code=...)")
                print("7. Paste it below and press Enter\n")
                
                # Get callback URL from user
                callback_url = input("Paste the callback URL here: ").strip()
                
                if not callback_url:
                    print("\n❌ No callback URL provided. Authentication cancelled.")
                    sys.exit(1)
                
                # Parse the callback URL to get the code
                try:
                    # Extract code from callback URL
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(callback_url)
                    params = parse_qs(parsed.query)
                    
                    if 'code' not in params:
                        print("\n❌ Invalid callback URL. No authorization code found.")
                        print("   Make sure you copied the ENTIRE URL from the browser.")
                        sys.exit(1)
                    
                    code = params['code'][0]
                    
                    # Exchange code for token
                    print("\n⏳ Exchanging authorization code for token...")
                    token_info = auth_manager.get_access_token(code, as_dict=False)
                    
                    if token_info:
                        print("✓ Authentication successful! Token cached.")
                    else:
                        print("❌ Failed to get access token.")
                        sys.exit(1)
                        
                except Exception as parse_error:
                    print(f"\n❌ Error parsing callback URL: {parse_error}")
                    print("   Make sure you copied the ENTIRE URL from the browser.")
                    sys.exit(1)
            else:
                # Check if token is expired
                if auth_manager.is_token_expired(token_info):
                    print("⚠ Cached token expired. Refreshing...")
                    token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
                    if token_info:
                        print("✓ Token refreshed successfully")
                    else:
                        print("❌ Failed to refresh token. Please re-authenticate:")
                        print("   python3 authenticate_spotify.py")
                        sys.exit(1)
            
            # Create Spotify client with auth manager
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            
            # Test the connection
            try:
                test_user = self.sp.current_user()
                if test_user:
                    print("✓ Spotify API connected")
                    if self._verbose:
                        print(f"   Logged in as: {test_user.get('display_name', 'Unknown')}")
                else:
                    print("⚠ Spotify API connected but user info unavailable")
            except Exception as test_error:
                print(f"⚠ Spotify API connected but test failed: {test_error}")
                print("   This may be normal if token needs refresh on first use")
                
        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ Failed to connect to Spotify API: {error_msg}")
            
            # Provide helpful error messages
            if "Invalid client" in error_msg or "Invalid redirect" in error_msg:
                print("\n💡 TROUBLESHOOTING:")
                print("   1. Verify your Client ID and Secret in config.py")
                print("   2. Check that the redirect URI in config.py matches")
                print("      the one in your Spotify app settings:")
                print(f"      Current: {SPOTIPY_REDIRECT_URI}")
                print("   3. Go to: https://developer.spotify.com/dashboard")
                print("   4. Edit your app → Settings → Redirect URIs")
                print("   5. Make sure the redirect URI is added and matches exactly")
            elif "No cached token" in error_msg or "token" in error_msg.lower():
                print("\n💡 TROUBLESHOOTING:")
                print("   Run the authentication script:")
                print("   python3 authenticate_spotify.py")
            else:
                print("\n💡 TROUBLESHOOTING:")
                print("   1. Check your internet connection")
                print("   2. Verify Spotify API credentials in config.py")
                print("   3. Try running: python3 authenticate_spotify.py")
            
            sys.exit(1)
        
        # Initialize printer
        if PRINTER_ENABLED:
            self.printer = StickerPrinter(PRINTER_VENDOR_ID, PRINTER_PRODUCT_ID)
        else:
            self.printer = StickerPrinter(0, 0)
        
        # Initialize camera
        # Prefer picamera2 (direct libcamera access) over OpenCV VideoCapture
        self.camera = None
        self.camera_type = None  # 'picamera2' or 'opencv'
        camera_found = False
        
        # Try picamera2 first (best option for Raspberry Pi with libcamera)
        if PICAMERA2_AVAILABLE:
            try:
                picam2 = Picamera2()
                # Configure camera
                config = picam2.create_preview_configuration(
                    main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT)}
                )
                picam2.configure(config)
                picam2.start()
                
                # Test if we can read a frame
                test_frame = picam2.capture_array()
                if test_frame is not None and test_frame.size > 0:
                    self.camera = picam2
                    self.camera_type = 'picamera2'
                    camera_found = True
                    print("✓ Camera initialized using picamera2 (libcamera)")
            except Exception as e:
                print(f"⚠ picamera2 failed: {e}")
                if PICAMERA2_AVAILABLE:
                    try:
                        if self.camera:
                            self.camera.stop()
                            self.camera.close()
                    except:
                        pass
        
        # Fall back to OpenCV VideoCapture if picamera2 didn't work
        if not camera_found:
            # Try multiple device indices (libcamera may use different device numbers)
            import glob
            video_devices = []
            for dev_path in glob.glob('/dev/video*'):
                try:
                    # Extract device number from path (e.g., /dev/video10 -> 10)
                    dev_num = int(dev_path.replace('/dev/video', ''))
                    video_devices.append(dev_num)
                except ValueError:
                    continue
            
            # Try existing devices first, then fall back to range 0-20
            devices_to_try = sorted(set(video_devices + list(range(21))))
            
            # Suppress OpenCV warnings temporarily
            import warnings
            import logging
            logging.getLogger().setLevel(logging.ERROR)
            
            for device_index in devices_to_try:
                try:
                    test_camera = cv2.VideoCapture(device_index)
                    if test_camera.isOpened():
                        test_camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                        test_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                        
                        # Test if we can actually read from it
                        ret, _ = test_camera.read()
                        if ret:
                            self.camera = test_camera
                            self.camera_type = 'opencv'
                            camera_found = True
                            print(f"✓ Camera initialized on device {device_index} (OpenCV/V4L2)")
                            break
                        else:
                            test_camera.release()
                    else:
                        test_camera.release()
                except Exception:
                    continue
            
            # Restore logging
            logging.getLogger().setLevel(logging.WARNING)
        
        if not camera_found:
            print("❌ Failed to initialize camera: Could not read from camera")
            if not PICAMERA2_AVAILABLE:
                print("\n⚠ picamera2 is not installed. Install with:")
                print("   pip3 install --break-system-packages picamera2")
            print("\nTroubleshooting:")
            print("- Check camera cable connection")
            print("- Verify camera is enabled in /boot/firmware/config.txt")
            print("- Try: vcgencmd get_camera")
            print("- Try: rpicam-still -o test.jpg (to verify camera works)")
            sys.exit(1)
        
        # Scanner state
        self.last_qr_code = None
        self.last_scan_time = 0
        self.scan_cooldown = SCAN_COOLDOWN
        self.print_mode = False
        self.verbose = getattr(self, '_verbose', False)
        self.debug_mode = getattr(self, '_debug_mode', False)
        self.last_qr_attempt_time = 0
        self.qr_detection_count = 0
        
        # Check if display is available (for showing camera preview)
        self.display_available = False
        self.force_display = getattr(self, '_force_display', False)
        no_display = getattr(self, '_no_display', False)
        
        # Skip display test if --no-display flag is set
        if no_display:
            self.display_available = False
        else:
            try:
                # Check if DISPLAY environment variable is set (X11)
                if 'DISPLAY' in os.environ:
                    display_val = os.environ.get('DISPLAY', '')
                    # Try to create a test window to see if display works
                    # This works for both local displays (e.g., :0) and SSH X11 forwarding (e.g., localhost:10.0)
                    try:
                        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
                        cv2.namedWindow('__test__', cv2.WINDOW_NORMAL)
                        cv2.imshow('__test__', test_img)
                        cv2.waitKey(1)
                        cv2.destroyWindow('__test__')
                        self.display_available = True
                        if self._verbose:
                            print(f"✓ Display test passed (DISPLAY={display_val})")
                    except (cv2.error, SystemError, OSError, Exception) as e:
                        # OpenCV GUI failed - likely no valid display
                        self.display_available = False
                        if self._verbose:
                            print(f"⚠ Display test failed (DISPLAY={display_val}): {e}")
                # Check if framebuffer exists (for direct framebuffer access)
                elif os.path.exists('/dev/fb0'):
                    # Framebuffer available, but OpenCV might not work without X11
                    # We'll try anyway, but it may fail
                    self.display_available = False  # Conservative: assume no display
            except Exception as e:
                self.display_available = False
                if self.force_display:
                    print(f"⚠ Display test failed: {e}")
        
        if not self.display_available:
            print("⚠ Display not available - running in headless mode")
            print("  Camera will work, but no preview window will be shown")
            if 'DISPLAY' not in os.environ:
                print("\n  To enable camera preview:")
                print("  • If running on Pi directly: DISPLAY=:0 python3 music_butler.py")
                print("  • If running via SSH: ssh -X pi@musicbutler.local")
            print("  Use keyboard controls: 'q' to quit, '+'/'-' for volume")
        else:
            print("✓ Display available - camera preview will be shown")
        
        # Playback state tracking
        self.current_volume = DEFAULT_VOLUME
        self.current_playback_context = None  # URI of currently playing content
        self.is_playing = False
        
        # Set initial volume
        self.set_volume(DEFAULT_VOLUME)
        
        # Initialize rotary encoder
        self.rotary_encoder = RotaryEncoderHandler(
            callback_volume=self._on_encoder_rotate,
            callback_single_press=self._on_button_single_press,
            callback_double_press=self._on_button_double_press
        )
        
        if self.rotary_encoder.enabled:
            self.rotary_encoder.start()
        
        print("\n✓ Music Butler is ready to serve!")
    
    def set_volume(self, volume_percent):
        """Set system volume (0-100)"""
        try:
            volume_percent = max(0, min(100, volume_percent))
            self.current_volume = volume_percent
            subprocess.run(
                ['amixer', 'set', 'Master', f'{volume_percent}%'],
                capture_output=True,
                check=False
            )
        except Exception as e:
            pass  # Ignore volume errors
    
    def _on_encoder_rotate(self, position_change):
        """Callback for rotary encoder rotation"""
        volume_change = position_change * VOLUME_STEP
        new_volume = max(0, min(100, self.current_volume - volume_change))
        if new_volume != self.current_volume:
            self.set_volume(new_volume)
            print(f"🔊 Volume: {self.current_volume}%")
    
    def _on_button_single_press(self):
        """Callback for single button press - play/pause"""
        self.toggle_playback()
    
    def _on_button_double_press(self):
        """Callback for double button press - print current content"""
        self.print_current_content()
    
    def get_active_device(self):
        """Get the active Spotify device ID"""
        try:
            devices = self.sp.devices()
            if devices['devices']:
                # Prefer active device
                for device in devices['devices']:
                    if device['is_active']:
                        return device['id']
                # Fall back to first device
                return devices['devices'][0]['id']
            return None
        except Exception as e:
            print(f"⚠ Error getting devices: {e}")
            return None
    
    def get_content_info(self, uri):
        """
        Get detailed info about Spotify content
        
        Args:
            uri: Spotify URI
            
        Returns:
            dict: Content information
        """
        try:
            if uri.startswith('spotify:playlist:'):
                playlist_id = uri.split(':')[-1]
                playlist = self.sp.playlist(playlist_id)
                return {
                    'type': 'playlist',
                    'name': playlist['name'],
                    'owner': playlist['owner']['display_name'],
                    'display': f"Playlist: {playlist['name']}"
                }
            elif uri.startswith('spotify:album:'):
                album_id = uri.split(':')[-1]
                album = self.sp.album(album_id)
                return {
                    'type': 'album',
                    'name': album['name'],
                    'artist': album['artists'][0]['name'],
                    'display': f"Album: {album['name']} by {album['artists'][0]['name']}"
                }
            elif uri.startswith('spotify:track:'):
                track_id = uri.split(':')[-1]
                track = self.sp.track(track_id)
                return {
                    'type': 'track',
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'display': f"Track: {track['name']} by {track['artists'][0]['name']}"
                }
        except Exception as e:
            print(f"⚠ Error getting content info: {e}")
        
        return {
            'type': 'unknown',
            'name': 'Unknown',
            'display': 'Unknown content'
        }
    
    def play_content(self, spotify_uri):
        """
        Play Spotify content (playlist/album/track)
        
        Args:
            spotify_uri: Spotify URI to play
            
        Returns:
            bool: True if successful
        """
        try:
            device_id = self.get_active_device()
            
            if not device_id:
                print("✗ No active Spotify device found!")
                print("  Make sure Raspotify is running:")
                print("  sudo systemctl status raspotify")
                return False
            
            info = self.get_content_info(spotify_uri)
            
            # Play based on type
            if spotify_uri.startswith('spotify:track:'):
                self.sp.start_playback(device_id=device_id, uris=[spotify_uri])
            else:
                self.sp.start_playback(device_id=device_id, context_uri=spotify_uri)
            
            # Track current playback context
            self.current_playback_context = spotify_uri
            self.is_playing = True
            
            print(f"♪ Now playing: {info['display']}")
            return True
            
        except Exception as e:
            print(f"✗ Error playing content: {e}")
            return False
    
    def get_current_playback(self):
        """
        Get information about currently playing content
        
        Returns:
            dict: Playback information with context and track info, or None if not playing
        """
        try:
            playback = self.sp.current_playback()
            if playback and playback.get('is_playing'):
                context = playback.get('context')
                item = playback.get('item')  # Current track
                
                result = {
                    'is_playing': True,
                    'context_uri': context.get('uri') if context else None,
                    'context_type': context.get('type') if context else None,
                    'track': item
                }
                
                return result
            return None
        except Exception as e:
            print(f"⚠ Error getting current playback: {e}")
            return None
    
    def toggle_playback(self):
        """Toggle play/pause for current playback"""
        try:
            device_id = self.get_active_device()
            if not device_id:
                print("✗ No active Spotify device found!")
                return False
            
            playback = self.sp.current_playback()
            
            if playback and playback.get('is_playing'):
                # Pause
                self.sp.pause_playback(device_id=device_id)
                self.is_playing = False
                print("⏸ Paused")
            else:
                # Resume or start
                if playback and playback.get('item'):
                    # Resume existing playback
                    self.sp.start_playback(device_id=device_id)
                    self.is_playing = True
                    print("▶️ Resumed")
                else:
                    # Nothing to resume - try to use last context
                    if self.current_playback_context:
                        self.play_content(self.current_playback_context)
                    else:
                        print("✗ No content to play")
                        return False
            
            return True
            
        except Exception as e:
            print(f"✗ Error toggling playback: {e}")
            return False
    
    def print_current_content(self):
        """Print a sticker for the currently playing content (playlist/album/track's album)"""
        try:
            # First try to get from current playback
            playback_info = self.get_current_playback()
            context_source = None
            uri_to_print = None
            
            if playback_info:
                context_uri = playback_info.get('context_uri')
                context_type = playback_info.get('context_type')
                track = playback_info.get('track')
                
                # Case 1: Playing from a playlist or album context
                if context_uri and context_uri.startswith(('spotify:playlist:', 'spotify:album:')):
                    uri_to_print = context_uri
                    context_source = f"current {context_type}"
                    print(f"🖨 Printing sticker for {context_source}: {context_uri}")
                
                # Case 2: Playing a track directly (no context) - print the track's album
                elif track and not context_uri:
                    album_uri = track.get('album', {}).get('uri')
                    if album_uri:
                        uri_to_print = album_uri
                        context_source = "track's album (no context)"
                        track_name = track.get('name', 'Unknown Track')
                        album_name = track.get('album', {}).get('name', 'Unknown Album')
                        print(f"🖨 Printing sticker for {context_source}")
                        print(f"   Track: {track_name} → Album: {album_name}")
                    else:
                        print("✗ No album information available for current track")
                        return False
                
                # Case 3: Playing from an unsupported context (e.g., artist)
                elif context_uri:
                    print(f"✗ Unsupported context type: {context_type}")
                    print("  Only playlists and albums can be printed")
                    return False
            
            # Fall back to last played context if nothing currently playing
            if not uri_to_print and self.current_playback_context:
                if self.current_playback_context.startswith(('spotify:playlist:', 'spotify:album:')):
                    uri_to_print = self.current_playback_context
                    context_source = "last played context"
                    print(f"🖨 Printing sticker for {context_source}: {uri_to_print}")
            
            if uri_to_print:
                success = self.print_sticker(uri_to_print)
                if success and context_source:
                    print(f"✓ Printed using {context_source}")
                return success
            
            print("✗ No printable content available")
            print("  Play a playlist, album, or track first, then press 'r' or double-press the knob")
            return False
            
        except Exception as e:
            print(f"✗ Error printing current content: {e}")
            return False
    
    def print_sticker(self, spotify_uri):
        """
        Print a sticker for Spotify content
        
        Args:
            spotify_uri: Spotify URI
            
        Returns:
            bool: True if successful
        """
        info = self.get_content_info(spotify_uri)
        
        title = info.get('name', 'Unknown')
        subtitle = info.get('artist', info.get('owner', ''))
        
        return self.printer.print_qr_sticker(spotify_uri, title, subtitle)
    
    def decode_qr(self, frame):
        """
        Decode QR codes from camera frame
        
        Args:
            frame: OpenCV frame
            
        Returns:
            str or None: QR code data if found
        """
        decoded_objects = pyzbar.decode(frame)
        
        if decoded_objects:
            self.qr_detection_count += 1
        
        for obj in decoded_objects:
            try:
                qr_data = obj.data.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    qr_data = obj.data.decode('latin-1')
                except:
                    qr_data = str(obj.data)
            
            # Draw rectangle around QR code
            points = obj.polygon
            if len(points) == 4:
                pts = [(point.x, point.y) for point in points]
                pts = np.array(pts, np.int32)
                
                # Color based on mode and validity
                is_spotify = qr_data.startswith(('spotify:playlist:', 'spotify:album:', 'spotify:track:'))
                if is_spotify:
                    color = (255, 165, 0) if self.print_mode else (0, 255, 0)  # Orange for print, green for play
                else:
                    color = (0, 165, 255)  # Blue for non-Spotify QR codes
                
                cv2.polylines(frame, [pts], True, color, 3)
                
                # Add mode text and QR data preview
                mode_text = "PRINT MODE" if self.print_mode else "PLAY MODE"
                if is_spotify:
                    status_text = "✓ VALID SPOTIFY"
                else:
                    status_text = "⚠ NOT SPOTIFY"
                    if self.debug_mode:
                        # Show first 30 chars of QR data for debugging
                        preview = qr_data[:30] + "..." if len(qr_data) > 30 else qr_data
                        status_text = f"⚠ {preview}"
                
                cv2.putText(
                    frame, mode_text,
                    (pts[0][0], pts[0][1] - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
                )
                cv2.putText(
                    frame, status_text,
                    (pts[0][0], pts[0][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1
                )
            
            return qr_data
        
        return None
    
    def run(self):
        """Main application loop"""
        print("\n" + "="*60)
        print("  MUSIC BUTLER - At Your Service!")
        print("="*60)
        print("\n📷 CAMERA MODES:")
        print("  • PLAY MODE (default): Scan QR code to play music")
        print("  • PRINT MODE: Scan QR code to print a sticker")
        print("\n🎛️  ROTARY ENCODER CONTROLS:")
        if self.rotary_encoder.enabled:
            print("  • Rotate knob - Adjust volume")
            print("  • Single press - Play/Pause")
            print("  • Double press - Print sticker for current content")
        else:
            print("  (Rotary encoder not connected)")
        print("\n⌨️  KEYBOARD CONTROLS:")
        print("  • 'm' - Toggle between Play/Print mode")
        print("  • 'p' - Print QR code sticker for currently playing content")
        print("  • '+' - Increase volume")
        print("  • '-' - Decrease volume")
        print("  • 'q' - Quit application")
        print("\n" + "="*60)
        
        if not self.printer.enabled:
            print("\n⚠ NOTE: Printer not available - only Play mode will work")
        
        print("\nStarting camera...\n")
        
        try:
            while True:
                # Read camera frame (different API for picamera2 vs OpenCV)
                if self.camera_type == 'picamera2':
                    try:
                        frame = self.camera.capture_array()
                        ret = frame is not None and frame.size > 0
                    except Exception as e:
                        print(f"✗ Failed to read from camera: {e}")
                        ret = False
                        frame = None
                else:  # OpenCV
                    ret, frame = self.camera.read()
                
                if not ret or frame is None:
                    print("✗ Failed to read from camera")
                    time.sleep(0.1)
                    continue
                
                # Decode QR code
                qr_data = self.decode_qr(frame)
                current_time = time.time()
                
                # Show debug info about QR detection attempts
                if self.debug_mode and (current_time - self.last_qr_attempt_time) > 1.0:
                    if qr_data:
                        print(f"[DEBUG] QR detected: {qr_data[:50]}...")
                    self.last_qr_attempt_time = current_time
                
                # Process QR code if found and cooldown passed
                if qr_data and (current_time - self.last_scan_time) > self.scan_cooldown:
                    if qr_data != self.last_qr_code:
                        print(f"\n{'='*60}")
                        print(f"→ QR Code detected: {qr_data}")
                        print(f"{'='*60}")
                        
                        # Validate Spotify URI
                        if qr_data.startswith(('spotify:playlist:', 
                                              'spotify:album:', 
                                              'spotify:track:')):
                            
                            print("✓ Valid Spotify URI detected!")
                            
                            # Execute action based on mode
                            if self.print_mode:
                                print("🖨 Print mode active...")
                                self.print_sticker(qr_data)
                            else:
                                print("▶️  Play mode active...")
                                self.play_content(qr_data)
                            
                            self.last_qr_code = qr_data
                            self.last_scan_time = current_time
                        else:
                            print("✗ Not a supported Spotify URI")
                            print(f"\n  Detected QR code content: {qr_data}")
                            print(f"  Length: {len(qr_data)} characters")
                            print("\n  Expected format:")
                            print("    • spotify:playlist:XXXXX")
                            print("    • spotify:album:XXXXX")
                            print("    • spotify:track:XXXXX")
                            print("\n  Common issues:")
                            print("    • QR code might be for a Spotify URL (https://open.spotify.com/...)")
                            print("    • QR code might be for a different service")
                            print("    • QR code might be corrupted or incomplete")
                            
                            # Show first/last few chars for debugging
                            if len(qr_data) > 60:
                                print(f"\n  First 30 chars: {qr_data[:30]}")
                                print(f"  Last 30 chars: ...{qr_data[-30:]}")
                            
                            # Still update last_qr_code to prevent spam
                            self.last_qr_code = qr_data
                            self.last_scan_time = current_time
                elif qr_data and self.verbose:
                    # QR code detected but in cooldown
                    time_remaining = self.scan_cooldown - (current_time - self.last_scan_time)
                    if time_remaining > 0:
                        print(f"[Cooldown: {time_remaining:.1f}s] Same QR code detected")
                
                # Draw UI overlay
                mode_text = "MODE: PRINT STICKER" if self.print_mode else "MODE: PLAY MUSIC"
                mode_color = (255, 165, 0) if self.print_mode else (0, 255, 0)
                
                y_offset = 30
                cv2.putText(frame, mode_text, (10, y_offset),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)
                y_offset += 30
                
                cv2.putText(frame, f"Volume: {self.current_volume}%", (10, y_offset),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                y_offset += 25
                
                # Show playback status (use ASCII instead of emojis for OpenCV compatibility)
                playback_status = "[>] Playing" if self.is_playing else "[||] Paused"
                cv2.putText(frame, playback_status, (10, y_offset),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                y_offset += 25
                
                # Show QR detection status
                if self.qr_detection_count > 0:
                    detection_text = f"QR scans: {self.qr_detection_count}"
                    cv2.putText(frame, detection_text, (10, y_offset),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 255), 1)
                    y_offset += 20
                
                # Show cooldown status
                if self.last_scan_time > 0:
                    time_since_scan = current_time - self.last_scan_time
                    if time_since_scan < self.scan_cooldown:
                        cooldown_remaining = self.scan_cooldown - time_since_scan
                        cooldown_text = f"Cooldown: {cooldown_remaining:.1f}s"
                        cv2.putText(frame, cooldown_text, (10, y_offset),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 200, 0), 1)
                        y_offset += 20
                
                # Show controls
                if self.rotary_encoder.enabled:
                    control_text = "Knob: Vol | 1x=Play/Pause | 2x=Print | 'p'=Print | 'q'=Quit"
                else:
                    control_text = "Press 'm' to switch | 'p' to print | 'q' to quit"
                cv2.putText(frame, control_text, (10, frame.shape[0] - 20),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
                
                # Show debug mode indicator
                if self.debug_mode:
                    cv2.putText(frame, "DEBUG MODE", (frame.shape[1] - 150, 30),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
                
                # Display frame (if display is available)
                if self.display_available:
                    cv2.imshow('Music Butler', frame)
                    # Handle keyboard input from window
                    key = cv2.waitKey(1) & 0xFF
                else:
                    # Headless mode - no display, just process frames
                    # Note: Keyboard input won't work in headless mode
                    # User would need to use Ctrl+C to quit
                    key = 0
                    time.sleep(0.033)  # ~30 fps
                
                if key == ord('q'):
                    print("\n👋 Music Butler signing off...")
                    break
                    
                elif key == ord('m'):
                    # Toggle between Play/Print mode
                    if not self.printer.enabled and not self.print_mode:
                        print("\n⚠ Printer not available - cannot switch to print mode")
                    else:
                        self.print_mode = not self.print_mode
                        mode = "PRINT" if self.print_mode else "PLAY"
                        print(f"\n→ Switched to {mode} mode")
                
                elif key == ord('p'):
                    # Print QR code for currently playing content
                    if not self.printer.enabled:
                        print("\n⚠ Printer not available - cannot print")
                    else:
                        self.print_current_content()
                        
                elif key == ord('+') or key == ord('='):
                    self.current_volume = min(100, self.current_volume + 5)
                    self.set_volume(self.current_volume)
                    print(f"🔊 Volume: {self.current_volume}%")
                    
                elif key == ord('-') or key == ord('_'):
                    self.current_volume = max(0, self.current_volume - 5)
                    self.set_volume(self.current_volume)
                    print(f"🔉 Volume: {self.current_volume}%")
                
                elif key == ord(' '):  # Spacebar for play/pause
                    self.toggle_playback()
                    
        except KeyboardInterrupt:
            print("\n\n⚠ Interrupted by user")
            
        finally:
            # Cleanup
            print("Cleaning up...")
            if self.rotary_encoder.enabled:
                self.rotary_encoder.stop()
            # Clean up camera (different methods for picamera2 vs OpenCV)
            if self.camera:
                if self.camera_type == 'picamera2':
                    try:
                        self.camera.stop()
                        self.camera.close()
                    except:
                        pass
                else:  # OpenCV
                    self.camera.release()
            if self.display_available:
                cv2.destroyAllWindows()
            print("✓ Thank you for using Music Butler!\n")

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Music Butler - Spotify QR Code Player',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with display (on Pi with monitor):
  DISPLAY=:0 python3 music_butler.py

  # Run with display (via SSH with X11 forwarding):
  ssh -X pi@musicbutler.local
  python3 music_butler.py

  # Force display mode (will show error if display unavailable):
  python3 music_butler.py --display

  # Run in headless mode (no camera preview):
  python3 music_butler.py --no-display

  # Run with verbose debugging:
  python3 music_butler.py --verbose --debug
        """
    )
    parser.add_argument(
        '--display', '-d',
        action='store_true',
        help='Force display mode (show error if display unavailable)'
    )
    parser.add_argument(
        '--no-display',
        action='store_true',
        help='Run in headless mode (no camera preview window)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output (show all QR code detection attempts)'
    )
    parser.add_argument(
        '--debug', '--debug-mode',
        action='store_true',
        dest='debug_mode',
        help='Debug mode (show detailed QR code information and detection stats)'
    )
    args = parser.parse_args()
    
    # Set DISPLAY if requested
    if args.display and 'DISPLAY' not in os.environ:
        # Try common display values
        if os.path.exists('/dev/tty7') or os.path.exists('/dev/tty1'):
            os.environ['DISPLAY'] = ':0'
            print("→ Set DISPLAY=:0 for local display")
        else:
            print("⚠ Warning: DISPLAY not set. Set it manually:")
            print("  export DISPLAY=:0  # For local display")
            print("  Or use: ssh -X pi@musicbutler.local  # For SSH with X11")
    
    # Override display availability if --no-display is set
    force_display = args.display
    no_display = args.no_display
    
    try:
        butler = MusicButler(
            force_display=force_display,
            verbose=args.verbose,
            debug_mode=args.debug_mode,
            no_display=no_display
        )
        if no_display:
            print("→ Running in headless mode (--no-display flag)")
        if args.verbose:
            print("→ Verbose mode enabled - showing all QR detection attempts")
        if args.debug_mode:
            print("→ Debug mode enabled - showing detailed QR code information")
        butler.run()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)