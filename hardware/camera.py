"""
Camera module for Music Butler
Handles camera initialization for both picamera2 and OpenCV
"""

import cv2
import sys
import glob
import logging

from config.settings import (
    PICAMERA2_AVAILABLE,
    CAMERA_WIDTH,
    CAMERA_HEIGHT
)

# Import picamera2 if available
if PICAMERA2_AVAILABLE:
    from picamera2 import Picamera2


def initialize_camera():
    """
    Initialize camera - tries picamera2 first, then falls back to OpenCV
    
    Returns:
        tuple: (camera_object, camera_type) where camera_type is 'picamera2' or 'opencv'
        Returns (None, None) if camera initialization fails
    """
    camera = None
    camera_type = None
    camera_found = False
    
    # Try picamera2 first (best option for Raspberry Pi with libcamera)
    if PICAMERA2_AVAILABLE:
        try:
            picam2 = Picamera2()
            # Configure camera
            config = picam2.create_preview_configuration(
                main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT)}
            )
            picam2.configure(config)
            picam2.start()
            
            # Test if we can read a frame
            test_frame = picam2.capture_array()
            if test_frame is not None and test_frame.size > 0:
                camera = picam2
                camera_type = 'picamera2'
                camera_found = True
                print("✓ Camera initialized using picamera2 (libcamera)")
        except Exception as e:
            print(f"⚠ picamera2 failed: {e}")
            if camera:
                try:
                    camera.stop()
                    camera.close()
                except:
                    pass
    
    # Fall back to OpenCV VideoCapture if picamera2 didn't work
    if not camera_found:
        # Try multiple device indices (libcamera may use different device numbers)
        video_devices = []
        for dev_path in glob.glob('/dev/video*'):
            try:
                # Extract device number from path (e.g., /dev/video10 -> 10)
                dev_num = int(dev_path.replace('/dev/video', ''))
                video_devices.append(dev_num)
            except ValueError:
                continue
        
        # Try existing devices first, then fall back to range 0-20
        devices_to_try = sorted(set(video_devices + list(range(21))))
        
        # Suppress OpenCV warnings temporarily
        logging.getLogger().setLevel(logging.ERROR)
        
        for device_index in devices_to_try:
            try:
                test_camera = cv2.VideoCapture(device_index)
                if test_camera.isOpened():
                    test_camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                    test_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                    
                    # Test if we can actually read from it
                    ret, _ = test_camera.read()
                    if ret:
                        camera = test_camera
                        camera_type = 'opencv'
                        camera_found = True
                        print(f"✓ Camera initialized on device {device_index} (OpenCV/V4L2)")
                        break
                    else:
                        test_camera.release()
                else:
                    test_camera.release()
            except Exception:
                continue
        
        # Restore logging
        logging.getLogger().setLevel(logging.WARNING)
    
    if not camera_found:
        print("❌ Failed to initialize camera: Could not read from camera")
        if not PICAMERA2_AVAILABLE:
            print("\n⚠ picamera2 is not installed. Install with:")
            print("   pip3 install --break-system-packages picamera2")
        print("\nTroubleshooting:")
        print("- Check camera cable connection")
        print("- Verify camera is enabled in /boot/firmware/config.txt")
        print("- Try: vcgencmd get_camera")
        print("- Try: rpicam-still -o test.jpg (to verify camera works)")
        return None, None
    
    return camera, camera_type


def read_frame(camera, camera_type):
    """
    Read a frame from the camera
    
    Args:
        camera: Camera object (picamera2 or OpenCV VideoCapture)
        camera_type: 'picamera2' or 'opencv'
    
    Returns:
        tuple: (success, frame) where success is bool and frame is numpy array or None
    """
    if camera_type == 'picamera2':
        try:
            frame = camera.capture_array()
            ret = frame is not None and frame.size > 0
            return ret, frame
        except Exception as e:
            print(f"✗ Failed to read from camera: {e}")
            return False, None
    else:  # OpenCV
        ret, frame = camera.read()
        return ret, frame


def cleanup_camera(camera, camera_type):
    """
    Clean up camera resources
    
    Args:
        camera: Camera object
        camera_type: 'picamera2' or 'opencv'
    """
    if camera:
        if camera_type == 'picamera2':
            try:
                camera.stop()
                camera.close()
            except:
                pass
        else:  # OpenCV
            camera.release()
