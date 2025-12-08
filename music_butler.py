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
import qrcode
from PIL import Image, ImageDraw, ImageFont
import threading

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
# CONFIGURATION - EDIT THESE VALUES
# =============================================================================

# Spotify API Credentials (get from https://developer.spotify.com/dashboard)
SPOTIPY_CLIENT_ID = 'YOUR_CLIENT_ID_HERE'
SPOTIPY_CLIENT_SECRET = 'YOUR_CLIENT_SECRET_HERE'
SPOTIPY_REDIRECT_URI = 'http://localhost:8888/callback'

# Printer USB IDs (find with 'lsusb' command after connecting printer)
# Common Phomemo M02 IDs: 0x0fe6:0x811e or 0x0416:0x5011 or 0x28e9:0x0289
PRINTER_VENDOR_ID = 0x0000  # Replace with your printer's vendor ID (e.g., 0x0fe6)
PRINTER_PRODUCT_ID = 0x0000  # Replace with your printer's product ID (e.g., 0x811e)

# Enable/disable printer (set to False if no printer connected)
PRINTER_ENABLED = True

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
    
    def __init__(self, vendor_id, product_id):
        self.enabled = False
        self.printer = None
        
        if not ESCPOS_AVAILABLE:
            print("⚠ Printer library not available")
            return
            
        if vendor_id == 0x0000 or product_id == 0x0000:
            print("⚠ Printer IDs not configured (printing disabled)")
            return
        
        try:
            # Try multiple profile options for better compatibility
            for profile in ['simple', 'default', 'POS-5890']:
                try:
                    self.printer = Usb(vendor_id, product_id, profile=profile)
                    self.enabled = True
                    print(f"✓ Sticker printer connected (profile: {profile})")
                    break
                except:
                    continue
                    
            if not self.enabled:
                raise Exception("Could not connect with any profile")
                
        except Exception as e:
            print(f"⚠ Printer not available: {e}")
            print("  Printing disabled - scanner will still work")
    
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
            text_height = 100
            sticker_height = qr_size + text_height
            
            # Create white background
            sticker = Image.new('1', (sticker_width, sticker_height), 1)
            
            # Paste QR code centered
            x_offset = (sticker_width - qr_size) // 2
            sticker.paste(qr_img, (x_offset, 0))
            
            # Add text
            draw = ImageDraw.Draw(sticker)
            
            # Try to load fonts
            try:
                font_title = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
                font_artist = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except:
                font_title = ImageFont.load_default()
                font_artist = ImageFont.load_default()
            
            # Truncate text if too long
            if len(title) > 30:
                title = title[:27] + "..."
            if len(artist_or_owner) > 35:
                artist_or_owner = artist_or_owner[:32] + "..."
            
            # Draw title
            y_pos = qr_size + 10
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
            self.printer.image(sticker, center=True)
            self.printer.text("\n\n")
            self.printer.cut()
            
            print(f"✓ Sticker printed successfully")
            return True
            
        except Exception as e:
            print(f"✗ Error printing sticker: {e}")
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
    
    def __init__(self):
        print("\n" + "="*60)
        print("  MUSIC BUTLER - Initialization")
        print("="*60)
        
        # Check credentials
        if SPOTIPY_CLIENT_ID == 'YOUR_CLIENT_ID_HERE':
            print("\n❌ ERROR: Spotify API credentials not configured!")
            print("\nPlease edit music_butler.py and add your credentials:")
            print("1. Go to: https://developer.spotify.com/dashboard")
            print("2. Create an app and get your Client ID and Secret")
            print("3. Edit music_butler.py and replace YOUR_CLIENT_ID_HERE")
            print("   and YOUR_CLIENT_SECRET_HERE with your actual values\n")
            sys.exit(1)
        
        # Initialize Spotify client
        try:
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=SPOTIPY_CLIENT_ID,
                client_secret=SPOTIPY_CLIENT_SECRET,
                redirect_uri=SPOTIPY_REDIRECT_URI,
                scope=SCOPE,
                cache_path='.spotify_cache'
            ))
            print("✓ Spotify API connected")
        except Exception as e:
            print(f"❌ Failed to connect to Spotify API: {e}")
            sys.exit(1)
        
        # Initialize printer
        if PRINTER_ENABLED:
            self.printer = StickerPrinter(PRINTER_VENDOR_ID, PRINTER_PRODUCT_ID)
        else:
            self.printer = StickerPrinter(0, 0)
        
        # Initialize camera
        # Try multiple device indices (libcamera may use different device numbers)
        self.camera = None
        camera_found = False
        
        for device_index in range(10):  # Try devices 0-9
            try:
                test_camera = cv2.VideoCapture(device_index)
                if test_camera.isOpened():
                    test_camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                    test_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                    
                    # Test if we can actually read from it
                    ret, _ = test_camera.read()
                    if ret:
                        self.camera = test_camera
                        camera_found = True
                        print(f"✓ Camera initialized on device {device_index}")
                        break
                    else:
                        test_camera.release()
            except Exception:
                continue
        
        if not camera_found:
            print("❌ Failed to initialize camera: Could not read from camera")
            print("\nTroubleshooting:")
            print("- Check camera cable connection")
            print("- Verify camera is enabled in /boot/firmware/config.txt")
            print("- Try: vcgencmd get_camera")
            print("- Try: ls -l /dev/video*")
            print("- Note: If rpicam-still works, camera hardware is fine.")
            print("  The issue is OpenCV accessing the camera. Try rebooting.")
            sys.exit(1)
        
        # Scanner state
        self.last_qr_code = None
        self.last_scan_time = 0
        self.scan_cooldown = SCAN_COOLDOWN
        self.print_mode = False
        
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
        """Callback for double button press - print current playlist"""
        self.print_current_playlist()
    
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
            dict: Playback information or None if not playing
        """
        try:
            playback = self.sp.current_playback()
            if playback and playback.get('is_playing'):
                context = playback.get('context')
                if context:
                    return {
                        'uri': context.get('uri'),
                        'type': context.get('type'),
                        'is_playing': True
                    }
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
    
    def print_current_playlist(self):
        """Print a sticker for the currently playing playlist/album"""
        try:
            # First try to get from current playback
            playback_info = self.get_current_playback()
            
            if playback_info and playback_info.get('uri'):
                uri = playback_info['uri']
                # Only print if it's a playlist or album (not a track)
                if uri.startswith(('spotify:playlist:', 'spotify:album:')):
                    print("🖨 Printing sticker for current playlist/album...")
                    return self.print_sticker(uri)
            
            # Fall back to last played context
            if self.current_playback_context:
                if self.current_playback_context.startswith(('spotify:playlist:', 'spotify:album:')):
                    print("🖨 Printing sticker for last played playlist/album...")
                    return self.print_sticker(self.current_playback_context)
            
            print("✗ No playlist or album currently playing")
            print("  Play a playlist or album first, then double-press the knob")
            return False
            
        except Exception as e:
            print(f"✗ Error printing current playlist: {e}")
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
        
        for obj in decoded_objects:
            qr_data = obj.data.decode('utf-8')
            
            # Draw rectangle around QR code
            points = obj.polygon
            if len(points) == 4:
                pts = [(point.x, point.y) for point in points]
                pts = np.array(pts, np.int32)
                
                # Color based on mode
                color = (255, 165, 0) if self.print_mode else (0, 255, 0)
                cv2.polylines(frame, [pts], True, color, 3)
                
                # Add mode text
                mode_text = "PRINT MODE" if self.print_mode else "PLAY MODE"
                cv2.putText(
                    frame, mode_text,
                    (pts[0][0], pts[0][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
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
            print("  • Double press - Print sticker for current playlist")
        else:
            print("  (Rotary encoder not connected)")
        print("\n⌨️  KEYBOARD CONTROLS:")
        print("  • 'p' - Toggle between Play/Print mode")
        print("  • '+' - Increase volume")
        print("  • '-' - Decrease volume")
        print("  • 'q' - Quit application")
        print("\n" + "="*60)
        
        if not self.printer.enabled:
            print("\n⚠ NOTE: Printer not available - only Play mode will work")
        
        print("\nStarting camera...\n")
        
        try:
            while True:
                # Read camera frame
                ret, frame = self.camera.read()
                if not ret:
                    print("✗ Failed to read from camera")
                    time.sleep(0.1)
                    continue
                
                # Decode QR code
                qr_data = self.decode_qr(frame)
                
                # Process QR code if found and cooldown passed
                current_time = time.time()
                if qr_data and (current_time - self.last_scan_time) > self.scan_cooldown:
                    if qr_data != self.last_qr_code:
                        print(f"\n→ QR Code detected: {qr_data}")
                        
                        # Validate Spotify URI
                        if qr_data.startswith(('spotify:playlist:', 
                                              'spotify:album:', 
                                              'spotify:track:')):
                            
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
                            print("  Expected: spotify:playlist:XXXXX")
                            print("           spotify:album:XXXXX")
                            print("           spotify:track:XXXXX")
                
                # Draw UI overlay
                mode_text = "MODE: PRINT STICKER" if self.print_mode else "MODE: PLAY MUSIC"
                mode_color = (255, 165, 0) if self.print_mode else (0, 255, 0)
                
                cv2.putText(frame, mode_text, (10, 30),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)
                cv2.putText(frame, f"Volume: {self.current_volume}%", (10, 60),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Show playback status
                playback_status = "▶️ Playing" if self.is_playing else "⏸ Paused"
                cv2.putText(frame, playback_status, (10, 90),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                
                # Show controls
                if self.rotary_encoder.enabled:
                    control_text = "Knob: Vol | 1x=Play/Pause | 2x=Print | 'q'=Quit"
                else:
                    control_text = "Press 'p' to switch | 'q' to quit"
                cv2.putText(frame, control_text, (10, 115),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
                
                # Display frame
                cv2.imshow('Music Butler', frame)
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    print("\n👋 Music Butler signing off...")
                    break
                    
                elif key == ord('p'):
                    if not self.printer.enabled and not self.print_mode:
                        print("\n⚠ Printer not available - cannot switch to print mode")
                    else:
                        self.print_mode = not self.print_mode
                        mode = "PRINT" if self.print_mode else "PLAY"
                        print(f"\n→ Switched to {mode} mode")
                        
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
            self.camera.release()
            cv2.destroyAllWindows()
            print("✓ Thank you for using Music Butler!\n")

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        butler = MusicButler()
        butler.run()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)