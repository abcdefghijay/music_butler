"""
Rotary Encoder Handler module for Music Butler
Handles rotary encoder input in a separate thread
"""

import time
import threading

from config.settings import (
    ROTARY_ENCODER_AVAILABLE,
    ROTARY_ENCODER_ENABLED,
    DOUBLE_PRESS_TIMEOUT
)

# Import rotary encoder libraries if available
if ROTARY_ENCODER_AVAILABLE:
    from adafruit_seesaw.seesaw import Seesaw
    from adafruit_seesaw.rotaryio import IncrementalEncoder
    from adafruit_seesaw.digitalio import DigitalIO
    import board
    import busio


class RotaryEncoderHandler:
    """Handles rotary encoder input in a separate thread"""
    
    def __init__(self, callback_volume, callback_single_press, callback_double_press):
        self.enabled = False
        self.encoder = None
        self.button = None
        self.i2c = None
        self.seesaw = None
        self.running = False
        self.thread = None
        
        self.callback_volume = callback_volume
        self.callback_single_press = callback_single_press
        self.callback_double_press = callback_double_press
        
        self.last_position = None
        self.last_button_state = False
        self.last_press_time = 0
        
        if not ROTARY_ENCODER_AVAILABLE:
            print("⚠ Rotary encoder library not available")
            return
        
        if not ROTARY_ENCODER_ENABLED:
            print("⚠ Rotary encoder disabled in configuration")
            return
        
        try:
            # Initialize I2C
            try:
                self.i2c = busio.I2C(board.SCL, board.SDA)
            except (ValueError, AttributeError) as e:
                raise Exception(f"I2C pins not available: {e}. Make sure I2C is enabled.")
            
            self.seesaw = Seesaw(self.i2c, addr=0x36)
            
            # Initialize encoder
            self.encoder = IncrementalEncoder(self.seesaw)
            self.last_position = self.encoder.position
            
            # Initialize button
            self.button = DigitalIO(self.seesaw, 24)
            self.button.direction = DigitalIO.INPUT
            self.button.pull = DigitalIO.PULL_UP
            
            self.enabled = True
            print("✓ Rotary encoder connected")
        except Exception as e:
            print(f"⚠ Rotary encoder not available: {e}")
            print("  Rotary encoder disabled - keyboard controls will still work")
            print("  To enable: Install adafruit-circuitpython-seesaw and enable I2C")
    
    def start(self):
        """Start the encoder monitoring thread"""
        if not self.enabled:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("✓ Rotary encoder monitoring started")
    
    def stop(self):
        """Stop the encoder monitoring thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
    
    def _monitor_loop(self):
        """Main monitoring loop (runs in thread)"""
        while self.running:
            try:
                # Check encoder position
                current_position = self.encoder.position
                if self.last_position is not None:
                    position_change = current_position - self.last_position
                    if position_change != 0:
                        # Volume control
                        if self.callback_volume:
                            self.callback_volume(position_change)
                        self.last_position = current_position
                else:
                    self.last_position = current_position
                
                # Check button state
                button_pressed = not self.button.value  # Inverted because of pull-up
                current_time = time.time()
                
                if button_pressed and not self.last_button_state:
                    # Button just pressed
                    time_since_last = current_time - self.last_press_time
                    
                    if time_since_last < DOUBLE_PRESS_TIMEOUT:
                        # Double press detected
                        if self.callback_double_press:
                            self.callback_double_press()
                        self.last_press_time = 0  # Reset to prevent triple-press
                    else:
                        # Single press - wait to see if it becomes double
                        self.last_press_time = current_time
                
                elif not button_pressed and self.last_button_state:
                    # Button just released
                    time_since_press = current_time - self.last_press_time
                    
                    if (time_since_press >= DOUBLE_PRESS_TIMEOUT and 
                        self.last_press_time > 0):
                        # Single press confirmed (no second press)
                        if self.callback_single_press:
                            self.callback_single_press()
                        self.last_press_time = 0
                
                self.last_button_state = button_pressed
                
                time.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                print(f"⚠ Rotary encoder error: {e}")
                time.sleep(0.1)
