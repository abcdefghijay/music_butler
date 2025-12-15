"""
Spotify Client module for Music Butler
Handles Spotify authentication and API interactions
"""

import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from urllib.parse import urlparse, parse_qs

from config.settings import (
    SPOTIPY_CLIENT_ID,
    SPOTIPY_CLIENT_SECRET,
    SPOTIPY_REDIRECT_URI,
    SCOPE
)


class SpotifyClient:
    """Wrapper for Spotify API client with authentication"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.sp = None
        self._authenticate()
    
    def _authenticate(self):
        """Handle Spotify authentication"""
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
                    if self.verbose:
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
    
    def play_content(self, spotify_uri, device_id):
        """
        Play Spotify content (playlist/album/track)
        
        Args:
            spotify_uri: Spotify URI to play
            device_id: Device ID to play on
            
        Returns:
            bool: True if successful
        """
        try:
            # Play based on type
            if spotify_uri.startswith('spotify:track:'):
                self.sp.start_playback(device_id=device_id, uris=[spotify_uri])
            else:
                self.sp.start_playback(device_id=device_id, context_uri=spotify_uri)
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
    
    def toggle_playback(self, device_id, current_playback_context):
        """
        Toggle play/pause for current playback
        
        Args:
            device_id: Device ID
            current_playback_context: Current playback context URI (for resuming)
        
        Returns:
            tuple: (success, is_playing) where is_playing is the new state
        """
        try:
            playback = self.sp.current_playback()
            
            if playback and playback.get('is_playing'):
                # Pause
                self.sp.pause_playback(device_id=device_id)
                return True, False
            else:
                # Resume or start
                if playback and playback.get('item'):
                    # Resume existing playback
                    self.sp.start_playback(device_id=device_id)
                    return True, True
                else:
                    # Nothing to resume - try to use last context
                    if current_playback_context:
                        if current_playback_context.startswith('spotify:track:'):
                            self.sp.start_playback(device_id=device_id, uris=[current_playback_context])
                        else:
                            self.sp.start_playback(device_id=device_id, context_uri=current_playback_context)
                        return True, True
                    else:
                        print("✗ No content to play")
                        return False, False
            
        except Exception as e:
            print(f"✗ Error toggling playback: {e}")
            return False, False
