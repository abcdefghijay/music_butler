# Music Butler Configuration File
# 
# This file contains your personal settings and credentials.
# This file is tracked in git with placeholder values.
# Edit this file locally with your actual credentials - your changes won't be committed.
# This file is NOT overwritten when you update music_butler.py
#
# IMPORTANT: Add your actual Spotify credentials below!

# Spotify API Credentials (get from https://developer.spotify.com/dashboard)
SPOTIPY_CLIENT_ID = 'YOUR_CLIENT_ID_HERE'
SPOTIPY_CLIENT_SECRET = 'YOUR_CLIENT_SECRET_HERE'
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8888/callback'

# Printer USB IDs (find with 'lsusb' command after connecting printer)
# Common Phomemo M02 IDs: 0x0fe6:0x811e or 0x0416:0x5011 or 0x28e9:0x0289
PRINTER_VENDOR_ID = 0x0000  # Replace with your printer's vendor ID (e.g., 0x0fe6)
PRINTER_PRODUCT_ID = 0x0000  # Replace with your printer's product ID (e.g., 0x811e)

# Enable/disable printer (set to False if no printer connected)
PRINTER_ENABLED = True
