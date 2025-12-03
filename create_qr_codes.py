#!/usr/bin/env python3
"""
QR Code Generator for Music Butler
Bulk create QR codes for your Spotify playlists
"""

import qrcode
import sys

# Add your playlists here
PLAYLISTS = {
    "Chill Vibes": "spotify:playlist:37i9dQZF1DX4WYpdgoIcn6",
    "Workout Mix": "spotify:playlist:37i9dQZF1DX76Wlfdnj7AP",
    "Dinner Party": "spotify:playlist:37i9dQZF1DX4xuWVBs4FgJ",
    # Add more playlists here
}

def create_qr_code(name, uri, output_dir="QR_codes"):
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

def main():
    """Generate all QR codes"""
    print("Music Butler - QR Code Generator\n")
    print("="*50)
    
    if len(PLAYLISTS) == 0:
        print("No playlists configured!")
        print("Edit this script and add your Spotify URIs to PLAYLISTS")
        sys.exit(1)
    
    print(f"Generating {len(PLAYLISTS)} QR codes...\n")
    
    for name, uri in PLAYLISTS.items():
        create_qr_code(name, uri)
    
    print("\n" + "="*50)
    print(f"✓ Done! Created {len(PLAYLISTS)} QR codes in ./QR_codes/")
    print("\nYou can now print these images or display them on a screen!")

if __name__ == "__main__":
    main()