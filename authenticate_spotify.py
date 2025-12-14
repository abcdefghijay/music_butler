#!/usr/bin/env python3
"""
Spotify Authentication Script for Music Butler
Run this script once to authenticate with Spotify and cache your token.
After authentication, music_butler.py will use the cached token automatically.
"""

import sys
import os
from urllib.parse import urlparse, parse_qs

# Try to import spotipy
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    print("❌ ERROR: spotipy not installed!")
    print("   Install with: pip3 install --break-system-packages spotipy")
    sys.exit(1)

# Import configuration
try:
    from config import (
        SPOTIPY_CLIENT_ID,
        SPOTIPY_CLIENT_SECRET,
        SPOTIPY_REDIRECT_URI,
    )
except ImportError:
    print("❌ ERROR: config.py not found!")
    print("   Please create config.py with your Spotify credentials.")
    print("   See config.py.example for a template.")
    sys.exit(1)

# Check credentials
if SPOTIPY_CLIENT_ID == 'YOUR_CLIENT_ID_HERE' or SPOTIPY_CLIENT_SECRET == 'YOUR_CLIENT_SECRET_HERE':
    print("❌ ERROR: Spotify API credentials not configured!")
    print("\nPlease edit config.py and add your credentials:")
    print("1. Go to: https://developer.spotify.com/dashboard")
    print("2. Create an app and get your Client ID and Secret")
    print("3. Edit config.py and replace YOUR_CLIENT_ID_HERE")
    print("   and YOUR_CLIENT_SECRET_HERE with your actual values\n")
    sys.exit(1)

# Spotify API scopes
SCOPE = 'user-read-playback-state,user-modify-playback-state,playlist-read-private'

def main():
    print("\n" + "="*60)
    print("  MUSIC BUTLER - Spotify Authentication")
    print("="*60)
    print()
    
    # Check if token already exists
    cache_path = '.spotify_cache'
    if os.path.exists(cache_path):
        print("⚠ Found existing authentication token.")
        response = input("   Do you want to re-authenticate? (y/N): ").strip().lower()
        if response != 'y':
            print("\n✓ Using existing token. No re-authentication needed.")
            print("   If you're having issues, delete .spotify_cache and run this script again.")
            return
    
    # Create auth manager
    auth_manager = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=cache_path,
        open_browser=False  # Disable browser opening for headless operation
    )
    
    # Get authorization URL
    auth_url = auth_manager.get_authorize_url()
    
    print("📋 AUTHENTICATION STEPS:")
    print("="*60)
    print()
    print("1. Copy the authorization URL below")
    print("2. Open it in a web browser (on your computer or phone)")
    print("3. Log in to Spotify if prompted")
    print("4. Click 'Agree' to authorize Music Butler")
    print("5. You'll see an error page (this is normal - the redirect URI")
    print("   is localhost, so it won't work in the browser)")
        print("6. Copy the ENTIRE URL from the browser address bar")
        print(f"   (It should start with: {SPOTIPY_REDIRECT_URI}?code=...)")
        print("7. Paste it below and press Enter")
    print()
    print("="*60)
    print()
    print(f"🔗 Authorization URL:\n")
    print(auth_url)
    print()
    print("="*60)
    print()
    
    # Get callback URL from user
    callback_url = input("Paste the callback URL here: ").strip()
    
    if not callback_url:
        print("\n❌ No callback URL provided. Authentication cancelled.")
        sys.exit(1)
    
    # Parse the callback URL to get the code
    try:
        # Extract code from callback URL
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)
        
        if 'code' not in params:
            print("\n❌ Invalid callback URL. No authorization code found.")
            print("   Make sure you copied the ENTIRE URL from the browser.")
            print(f"   Expected format: {SPOTIPY_REDIRECT_URI}?code=...")
            print(f"   You provided: {callback_url[:100]}...")
            sys.exit(1)
        
        code = params['code'][0]
        
        # Exchange code for token
        print("\n⏳ Exchanging authorization code for token...")
        token_info = auth_manager.get_access_token(code, as_dict=False)
        
        if token_info:
            print("✓ Authentication successful!")
            print(f"✓ Token saved to: {cache_path}")
            print()
            print("🎉 You're all set! You can now run music_butler.py")
            print("   The token will be automatically used on future runs.")
            print()
            
            # Test the connection
            try:
                sp = spotipy.Spotify(auth_manager=auth_manager)
                user = sp.current_user()
                if user:
                    print(f"✓ Verified: Logged in as {user.get('display_name', 'Unknown')}")
            except Exception as test_error:
                print(f"⚠ Connection test failed: {test_error}")
                print("   But token was saved - try running music_butler.py")
        else:
            print("❌ Failed to get access token.")
            print("   Please try again or check your credentials.")
            sys.exit(1)
            
    except Exception as parse_error:
        print(f"\n❌ Error processing callback URL: {parse_error}")
        print("   Make sure you copied the ENTIRE URL from the browser.")
        print(f"   Expected format: {SPOTIPY_REDIRECT_URI}?code=...")
        print(f"   You provided: {callback_url[:100]}...")
        print()
        print("💡 TROUBLESHOOTING:")
        print("   1. Make sure you copied the COMPLETE URL from the browser")
        print(f"   2. The URL should start with: {SPOTIPY_REDIRECT_URI}?code=")
        print("   3. Check that your redirect URI in config.py matches your")
        print("      Spotify app settings at https://developer.spotify.com/dashboard")
        print(f"      Current redirect URI: {SPOTIPY_REDIRECT_URI}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Authentication cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
