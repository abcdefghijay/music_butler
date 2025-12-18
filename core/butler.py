"""
Core Music Butler application class
Orchestrates all components: Spotify, camera, printer, encoder, QR scanner
"""

import sys
import os
import time
import subprocess
import cv2
import numpy as np

from config.settings import (
    PRINTER_ENABLED,
    PRINTER_VENDOR_ID,
    PRINTER_PRODUCT_ID,
    SCAN_COOLDOWN,
    DEFAULT_VOLUME,
    VOLUME_STEP
)

from hardware.printer import StickerPrinter
from hardware.encoder import RotaryEncoderHandler
from hardware.camera import initialize_camera, read_frame, cleanup_camera
from spotify.client import SpotifyClient
from qr.scanner import QRScanner


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
        
        # Initialize Spotify client
        self.spotify = SpotifyClient(verbose=verbose)
        
        # Initialize printer
        if PRINTER_ENABLED:
            self.printer = StickerPrinter(PRINTER_VENDOR_ID, PRINTER_PRODUCT_ID)
        else:
            self.printer = StickerPrinter(0, 0)
        
        # Initialize camera
        self.camera, self.camera_type = initialize_camera()
        if not self.camera:
            sys.exit(1)
        
        # Scanner state
        self.last_qr_code = None
        self.last_scan_time = 0
        self.scan_cooldown = SCAN_COOLDOWN
        self.print_mode = False
        self.verbose = verbose
        self.debug_mode = debug_mode
        self.last_qr_attempt_time = 0
        
        # Initialize QR scanner
        self.qr_scanner = QRScanner(print_mode=self.print_mode, debug_mode=debug_mode)
        
        # Check if display is available (for showing camera preview)
        self.display_available = False
        self.force_display = force_display
        no_display = no_display
        
        # Skip display test if --no-display flag is set
        if no_display:
            self.display_available = False
        else:
            try:
                # Check if DISPLAY environment variable is set (X11)
                if 'DISPLAY' in os.environ:
                    display_val = os.environ.get('DISPLAY', '')
                    # Try to create a test window to see if display works
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
    
    def play_content(self, spotify_uri):
        """
        Play Spotify content (playlist/album/track)
        
        Args:
            spotify_uri: Spotify URI to play
            
        Returns:
            bool: True if successful
        """
        try:
            device_id = self.spotify.get_active_device()
            
            if not device_id:
                print("✗ No active Spotify device found!")
                print("  Make sure Raspotify is running:")
                print("  sudo systemctl status raspotify")
                return False
            
            info = self.spotify.get_content_info(spotify_uri)
            
            # Play content
            success = self.spotify.play_content(spotify_uri, device_id)
            
            if success:
                # Track current playback context
                self.current_playback_context = spotify_uri
                self.is_playing = True
                print(f"♪ Now playing: {info['display']}")
            
            return success
            
        except Exception as e:
            print(f"✗ Error playing content: {e}")
            return False
    
    def toggle_playback(self):
        """Toggle play/pause for current playback"""
        try:
            device_id = self.spotify.get_active_device()
            if not device_id:
                print("✗ No active Spotify device found!")
                return False
            
            success, is_playing = self.spotify.toggle_playback(device_id, self.current_playback_context)
            
            if success:
                self.is_playing = is_playing
                if is_playing:
                    print("▶️ Resumed")
                else:
                    print("⏸ Paused")
            
            return success
            
        except Exception as e:
            print(f"✗ Error toggling playback: {e}")
            return False
    
    def print_current_content(self):
        """Print a sticker for the currently playing content (playlist/album/track's album)"""
        try:
            # First try to get from current playback
            playback_info = self.spotify.get_current_playback()
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
        info = self.spotify.get_content_info(spotify_uri)
        
        title = info.get('name', 'Unknown')
        
        # For playlists, show "(Playlist)" as subtitle
        if spotify_uri.startswith('spotify:playlist:') or info.get('type') == 'playlist':
            # If name lookup failed but we know it's a playlist, use "Playlist" instead of "Unknown"
            if title == 'Unknown' and info.get('type') == 'unknown':
                title = 'Playlist'
                subtitle = ""  # Don't show redundant "(Playlist)" subtitle if title is just "Playlist"
            else:
                subtitle = "(Playlist)"
        else:
            # For albums and tracks, use artist
            subtitle = info.get('artist', info.get('owner', ''))
        
        return self.printer.print_qr_sticker(spotify_uri, title, subtitle)
    
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
                # Read camera frame
                ret, frame = read_frame(self.camera, self.camera_type)
                
                if not ret or frame is None:
                    print("✗ Failed to read from camera")
                    time.sleep(0.1)
                    continue
                
                # Update QR scanner mode
                self.qr_scanner.print_mode = self.print_mode
                
                # Decode QR code
                qr_data = self.qr_scanner.decode_qr(frame)
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
                        if self.qr_scanner.is_valid_spotify_uri(qr_data):
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
                if self.qr_scanner.qr_detection_count > 0:
                    detection_text = f"QR scans: {self.qr_scanner.qr_detection_count}"
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
            # Clean up camera
            cleanup_camera(self.camera, self.camera_type)
            if self.display_available:
                cv2.destroyAllWindows()
            print("✓ Thank you for using Music Butler!\n")
