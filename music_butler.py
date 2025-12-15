#!/usr/bin/env python3
"""
Music Butler - Spotify QR Code Player with Sticker Printer
A Raspberry Pi-based music player that scans QR codes to play Spotify content
and prints custom QR code stickers.

Version: 1.1
License: MIT
"""

import os
import sys
import argparse

from core.butler import MusicButler


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
