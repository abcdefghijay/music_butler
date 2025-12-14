#!/usr/bin/env python3
"""
QR Code Generator for Music Butler
Bulk create QR codes for your Spotify playlists
"""

import qrcode
import sys
import argparse
import os
import re

# Try to import printer functionality
try:
    from music_butler import StickerPrinter
    import config
    PRINTER_AVAILABLE = True
except ImportError:
    PRINTER_AVAILABLE = False
    StickerPrinter = None

# Add your playlists here
PLAYLISTS = {
    # "Chill Vibes": "spotify:playlist:37i9dQZF1DX4WYpdgoIcn6",
    # "Workout Mix": "spotify:playlist:37i9dQZF1DX76Wlfdnj7AP",
    # "Dinner Party": "spotify:playlist:37i9dQZF1DX4xuWVBs4FgJ",
    "Vulpeck--The Joy of Music, The Job of Real Estate": "spotify:album:0woDg8EWf32yL9I5bhrGSD",
    "St. Vincent--St. Vincent": "spotify:album:2FtneRtIF1I5HPBsIxSqf0",
}

def convert_spotify_url_to_uri(url):
    """Convert a Spotify URL to a Spotify URI"""
    # Pattern: https://open.spotify.com/{type}/{id}?...
    pattern = r'https://open\.spotify\.com/(playlist|album|track|artist)/([a-zA-Z0-9]+)'
    match = re.search(pattern, url)
    if match:
        content_type = match.group(1)
        content_id = match.group(2)
        return f"spotify:{content_type}:{content_id}"
    return None

def extract_title_from_uri(uri):
    """Extract a readable title from a Spotify URI"""
    # spotify:playlist:37i9dQZF1DX4WYpdgoIcn6 -> "Playlist"
    # spotify:album:4uLU6hMCjMI75M1A2tKUQC -> "Album"
    # spotify:track:4uLU6hMCjMI75M1A2tKUQC -> "Track"
    if uri.startswith("spotify:"):
        parts = uri.split(":")
        if len(parts) >= 2:
            content_type = parts[1].capitalize()
            return content_type
    return "QR Code"

def create_qr_code(name, uri, output_dir="QR_codes", show=False, print_sticker=False, printer=None):
    """Create a QR code image for a Spotify URI
    
    Returns:
        tuple: (filename, print_success) where print_success is True/False/None
               (None if printing was not attempted)
    """
    import os
    
    # Normalize URI - convert URL to URI if needed
    if uri.startswith("http"):
        converted_uri = convert_spotify_url_to_uri(uri)
        if converted_uri:
            uri = converted_uri
            print(f"  → Converted URL to URI: {uri}")
        else:
            print(f"  ⚠ Could not convert URL to Spotify URI: {uri}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save
    filename = f"{output_dir}/{name.replace(' ', '_')}.png"
    img.save(filename)
    print(f"✓ Created: {filename}")
    
    # Print if requested
    print_success = None
    if print_sticker and printer:
        if printer.enabled:
            title = name if name != extract_title_from_uri(uri) else extract_title_from_uri(uri)
            print_success = printer.print_qr_sticker(uri, title, "")
            if print_success:
                print(f"  → Printed sticker for '{name}'")
            else:
                print(f"  ✗ Failed to print sticker")
        else:
            print(f"  ⚠ Printer not available - cannot print")
    
    # Display if requested
    if show:
        try:
            # Check if DISPLAY is set (X11 forwarding)
            if 'DISPLAY' in os.environ:
                img.show()
                print(f"  → Displayed QR code for '{name}'")
            else:
                print(f"  ⚠ Cannot display: DISPLAY not set")
                print(f"  → Reconnect with: ssh -X pi@musicbutler.local")
                print(f"  → Or view with: xdg-open {filename}")
        except Exception as e:
            print(f"  ⚠ Could not display image: {e}")
            print(f"  → View manually: xdg-open {filename}")
    
    return filename, print_success

def main():
    """Generate all QR codes"""
    parser = argparse.ArgumentParser(
        description='Generate QR codes for Spotify playlists or print a single QR code'
    )
    parser.add_argument(
        'uri',
        nargs='?',
        type=str,
        help='Spotify URI or URL to generate QR code for (e.g., spotify:playlist:... or https://open.spotify.com/...)'
    )
    parser.add_argument(
        '--uri', '-u',
        type=str,
        dest='uri_keyword',
        help='Spotify URI or URL to generate QR code for (alternative to positional argument)'
    )
    parser.add_argument(
        '--show', '-s',
        action='store_true',
        help='Display QR codes after creating them (requires X11 forwarding: ssh -X)'
    )
    parser.add_argument(
        '--playlist', '-p',
        type=str,
        help='Generate QR code for a specific playlist name (from PLAYLISTS dict)'
    )
    parser.add_argument(
        '--print',
        action='store_true',
        help='Print QR code sticker (requires printer to be configured)'
    )
    parser.add_argument(
        '--name', '-n',
        type=str,
        help='Name/title for the QR code (default: extracted from URI)'
    )
    args = parser.parse_args()
    
    print("Music Butler - QR Code Generator\n")
    print("="*50)
    
    # Initialize printer if requested
    printer = None
    if args.print:
        if PRINTER_AVAILABLE:
            try:
                printer = StickerPrinter(config.PRINTER_VENDOR_ID, config.PRINTER_PRODUCT_ID)
                if not printer.enabled:
                    print("⚠ Printer not available - --print flag will be ignored")
            except Exception as e:
                print(f"⚠ Could not initialize printer: {e}")
                print("  --print flag will be ignored")
        else:
            print("⚠ Printer functionality not available")
            print("  Make sure music_butler.py and config.py are in the same directory")
            print("  --print flag will be ignored")
    
    # If URI is provided as positional or keyword argument, handle it directly
    uri = args.uri or args.uri_keyword
    if uri:
        name = args.name if args.name else extract_title_from_uri(uri)
        
        print(f"Generating QR code for: {uri}\n")
        filename, print_success = create_qr_code(name, uri, show=args.show, print_sticker=args.print, printer=printer)
        
        print("\n" + "="*50)
        print(f"✓ Done!")
        if args.print:
            if print_success is True:
                print("  → QR code printed successfully!")
            elif print_success is False:
                print("  ✗ QR code generation succeeded, but printing failed")
            elif printer and not printer.enabled:
                print("  ⚠ Printer not available")
        return
    
    # Otherwise, use the playlist-based workflow
    if len(PLAYLISTS) == 0:
        print("No playlists configured!")
        print("Edit this script and add your Spotify URIs to PLAYLISTS")
        print("\nOr provide a URI/URL as an argument:")
        print("  python3 create_qr_codes.py spotify:playlist:37i9dQZF1DX4WYpdgoIcn6")
        print("  python3 create_qr_codes.py https://open.spotify.com/playlist/37i9dQZF1DX4WYpdgoIcn6")
        sys.exit(1)
    
    # Check for display availability if --show is used
    if args.show:
        if 'DISPLAY' not in os.environ:
            print("⚠ WARNING: DISPLAY not set - cannot show images")
            print("  Reconnect with X11 forwarding: ssh -X pi@musicbutler.local")
            print("  Or use: xdg-open QR_codes/<filename>.png\n")
    
    # Filter playlists if specific one requested
    playlists_to_generate = {}
    if args.playlist:
        if args.playlist in PLAYLISTS:
            playlists_to_generate[args.playlist] = PLAYLISTS[args.playlist]
        else:
            print(f"✗ Playlist '{args.playlist}' not found in PLAYLISTS")
            print(f"  Available playlists: {', '.join(PLAYLISTS.keys())}")
            sys.exit(1)
    else:
        playlists_to_generate = PLAYLISTS
    
    print(f"Generating {len(playlists_to_generate)} QR code(s)...\n")
    
    print_results = []
    for name, uri in playlists_to_generate.items():
        filename, print_success = create_qr_code(name, uri, show=args.show, print_sticker=args.print, printer=printer)
        if args.print:
            print_results.append(print_success)
    
    print("\n" + "="*50)
    print(f"✓ Done! Created {len(playlists_to_generate)} QR code(s) in ./QR_codes/")
    
    if args.print and print_results:
        successful_prints = sum(1 for r in print_results if r is True)
        failed_prints = sum(1 for r in print_results if r is False)
        if successful_prints > 0:
            print(f"  → Successfully printed {successful_prints} sticker(s)")
        if failed_prints > 0:
            print(f"  ✗ Failed to print {failed_prints} sticker(s)")
    
    if not args.show:
        print("\nTo display QR codes:")
        print("  • Use --show flag: python3 create_qr_codes.py --show")
        print("  • Or view manually: xdg-open QR_codes/<filename>.png")
        print("  • Note: For SSH, reconnect with: ssh -X pi@musicbutler.local")
    if not args.print:
        print("\nTo print QR codes:")
        print("  • Use --print flag: python3 create_qr_codes.py <uri> --print")
    print("\nYou can now print these images or display them on a screen!")

if __name__ == "__main__":
    main()