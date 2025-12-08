#!/usr/bin/env python3
"""
QR Code Generator for Music Butler
Bulk create QR codes for your Spotify playlists
"""

import qrcode
import sys
import argparse
import os

# Add your playlists here
PLAYLISTS = {
    "Chill Vibes": "spotify:playlist:37i9dQZF1DX4WYpdgoIcn6",
    "Workout Mix": "spotify:playlist:37i9dQZF1DX76Wlfdnj7AP",
    "Dinner Party": "spotify:playlist:37i9dQZF1DX4xuWVBs4FgJ",
    # Add more playlists here
}

def create_qr_code(name, uri, output_dir="QR_codes", show=False):
    """Create a QR code image for a Spotify URI"""
    import os
    
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

def main():
    """Generate all QR codes"""
    parser = argparse.ArgumentParser(
        description='Generate QR codes for Spotify playlists'
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
    args = parser.parse_args()
    
    print("Music Butler - QR Code Generator\n")
    print("="*50)
    
    if len(PLAYLISTS) == 0:
        print("No playlists configured!")
        print("Edit this script and add your Spotify URIs to PLAYLISTS")
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
    
    for name, uri in playlists_to_generate.items():
        create_qr_code(name, uri, show=args.show)
    
    print("\n" + "="*50)
    print(f"✓ Done! Created {len(playlists_to_generate)} QR code(s) in ./QR_codes/")
    
    if not args.show:
        print("\nTo display QR codes:")
        print("  • Use --show flag: python3 create_qr_codes.py --show")
        print("  • Or view manually: xdg-open QR_codes/<filename>.png")
        print("  • Note: For SSH, reconnect with: ssh -X pi@musicbutler.local")
    print("\nYou can now print these images or display them on a screen!")

if __name__ == "__main__":
    main()