"""
QR Code Scanner module for Music Butler
Handles QR code decoding and validation
"""

import cv2
import numpy as np
from pyzbar import pyzbar


class QRScanner:
    """Handles QR code scanning and validation"""
    
    def __init__(self, print_mode=False, debug_mode=False):
        self.print_mode = print_mode
        self.debug_mode = debug_mode
        self.qr_detection_count = 0
    
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
    
    @staticmethod
    def is_valid_spotify_uri(qr_data):
        """
        Check if QR code data is a valid Spotify URI
        
        Args:
            qr_data: QR code data string
            
        Returns:
            bool: True if valid Spotify URI
        """
        return qr_data.startswith(('spotify:playlist:', 'spotify:album:', 'spotify:track:'))
