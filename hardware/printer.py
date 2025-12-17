"""
Sticker Printer module for Music Butler
Handles QR code sticker printing on thermal printers
"""

import time
import qrcode
from PIL import Image, ImageDraw, ImageFont
import subprocess

from config.settings import ESCPOS_AVAILABLE, USB_CORE_AVAILABLE

# Import escpos if available
if ESCPOS_AVAILABLE:
    from escpos.printer import Usb

# Import USB core if available
if USB_CORE_AVAILABLE:
    import usb.core
    import usb.util


class StickerPrinter:
    """Handles QR code sticker printing on thermal printers"""
    
    @staticmethod
    def _set_media_width(printer, width_pixels):
        """
        Set the media width in pixels for the printer profile.
        This enables the center flag to work properly.
        
        Args:
            printer: The escpos Usb printer object
            width_pixels: Width in pixels (384 for 53mm thermal printer)
        
        Returns:
            bool: True if successfully set, False otherwise
        """
        try:
            # First, try to set via profile if it exists
            if hasattr(printer, 'profile') and printer.profile:
                if hasattr(printer.profile, 'media'):
                    media = printer.profile.media
                    
                    # Try dictionary-style access first
                    if hasattr(media, '__setitem__') or isinstance(media, dict):
                        if 'width' not in media:
                            media['width'] = {}
                        media['width']['pixel'] = width_pixels
                        return True
                    
                    # Try object-style access
                    if hasattr(media, 'width'):
                        if not hasattr(media.width, 'pixel'):
                            # Create a simple object with pixel attribute
                            class WidthObj:
                                def __init__(self, pixel):
                                    self.pixel = pixel
                            media.width = WidthObj(width_pixels)
                        else:
                            media.width.pixel = width_pixels
                        return True
                    
                    # Try to create width attribute
                    class WidthObj:
                        def __init__(self, pixel):
                            self.pixel = pixel
                    media.width = WidthObj(width_pixels)
                    return True
            
            # If no profile, try to create a minimal profile structure
            # This is needed for printers using manual endpoints
            if not hasattr(printer, 'profile') or not printer.profile:
                # Create a simple profile-like structure
                class SimpleMedia:
                    class WidthObj:
                        def __init__(self, pixel):
                            self.pixel = pixel
                    def __init__(self, width_pixels):
                        self.width = self.WidthObj(width_pixels)
                
                class SimpleProfile:
                    def __init__(self, width_pixels):
                        self.media = SimpleMedia(width_pixels)
                
                printer.profile = SimpleProfile(width_pixels)
                return True
            
            return False
            
        except (AttributeError, TypeError, KeyError, Exception) as e:
            # Silently fail - the warning will come from escpos library
            return False
    
    @staticmethod
    def _convert_id_to_int(id_value):
        """Convert printer ID to integer, handling both string and int formats"""
        if isinstance(id_value, int):
            return id_value
        elif isinstance(id_value, str):
            # Handle string formats: '0x4c4a', '0x4c4a', '4c4a', etc.
            id_value = id_value.strip()
            if id_value.startswith('0x') or id_value.startswith('0X'):
                return int(id_value, 16)
            else:
                # Try as hex first, then decimal
                try:
                    return int(id_value, 16)
                except ValueError:
                    return int(id_value)
        else:
            raise ValueError(f"Invalid printer ID format: {id_value} (type: {type(id_value)})")
    
    def __init__(self, vendor_id, product_id):
        self.enabled = False
        self.printer = None
        
        if not ESCPOS_AVAILABLE:
            print("⚠ Printer library not available")
            return
        
        # Convert IDs to integers if they're strings
        try:
            self.vendor_id = self._convert_id_to_int(vendor_id)
            self.product_id = self._convert_id_to_int(product_id)
        except (ValueError, TypeError) as e:
            print(f"⚠ Invalid printer ID format: {e}")
            print("  Printer IDs should be integers (e.g., 0x4c4a) or hex strings (e.g., '0x4c4a')")
            return
            
        if self.vendor_id == 0x0000 or self.product_id == 0x0000:
            print("⚠ Printer IDs not configured (printing disabled)")
            return
        
        try:
            # Jieli Technology printers (vendor 0x4c4a) often need manual endpoint configuration
            # Try manual endpoints first for these printers
            is_jieli_printer = (self.vendor_id == 0x4c4a)
            
            if not is_jieli_printer:
                # Try multiple profile options for better compatibility
                for profile in ['simple', 'default', 'POS-5890']:
                    try:
                        self.printer = Usb(self.vendor_id, self.product_id, profile=profile)
                        # Set media width for centering (384 pixels for 53mm thermal printer)
                        self._set_media_width(self.printer, 384)
                        self.enabled = True
                        self.profile = profile
                        print(f"✓ Sticker printer connected (profile: {profile})")
                        break
                    except Exception as profile_error:
                        # Only show error if it's the last profile we're trying
                        if profile == 'POS-5890':
                            continue
                        continue
            
            # If profiles failed (or Jieli printer), try manual endpoint configuration
            if not self.enabled:
                if is_jieli_printer:
                    print("  → Using manual endpoint configuration for Jieli Technology printer...")
                else:
                    print("  → Profiles failed, trying manual endpoint configuration...")
                # Common endpoint combinations for thermal printers
                # Most printers use: out_ep=0x01 or 0x02, in_ep=0x81 or 0x82
                # Jieli Technology printers typically use (0x02, 0x82)
                endpoint_combos = [
                    (0x02, 0x82),  # Jieli Technology / Phomemo (most common for this vendor)
                    (0x01, 0x81),  # Other common printers
                    (0x01, 0x82),
                    (0x02, 0x81),
                    (0x03, 0x83),
                ]
                
                # For CDC devices (like Jieli Technology), try interface 1 first (data interface)
                # Interface 0 is usually the communication interface, interface 1 is the data interface
                interface_numbers = [1, 0] if is_jieli_printer else [0, 1]
                
                for interface_num in interface_numbers:
                    for out_ep, in_ep in endpoint_combos:
                        try:
                            self.printer = Usb(
                                self.vendor_id, 
                                self.product_id, 
                                interface=interface_num,
                                in_ep=in_ep,
                                out_ep=out_ep
                            )
                            
                            # CRITICAL: For USB Composite Devices, we may need to explicitly
                            # claim the interface and detach kernel driver
                            try:
                                if hasattr(self.printer, 'device') and hasattr(self.printer.device, 'is_kernel_driver_active'):
                                    # Check if kernel driver is active
                                    for cfg in self.printer.device:
                                        for intf in cfg:
                                            if intf.bInterfaceNumber == interface_num:
                                                if self.printer.device.is_kernel_driver_active(intf.bInterfaceNumber):
                                                    try:
                                                        self.printer.device.detach_kernel_driver(intf.bInterfaceNumber)
                                                        print(f"  → Detached kernel driver from interface {intf.bInterfaceNumber}")
                                                    except:
                                                        pass
                                                try:
                                                    self.printer.device.set_configuration(cfg)
                                                    self.printer.device.claim_interface(intf.bInterfaceNumber)
                                                    print(f"  → Claimed interface {intf.bInterfaceNumber}")
                                                    self.claimed_interface = intf.bInterfaceNumber
                                                except:
                                                    pass
                            except Exception as intf_error:
                                # Interface claiming is optional - continue if it fails
                                pass
                            
                            # Set media width for centering (384 pixels for 53mm thermal printer)
                            self._set_media_width(self.printer, 384)
                            self.enabled = True
                            self.profile = None
                            self.endpoints = (out_ep, in_ep)
                            self.interface_num = interface_num
                            print(f"✓ Sticker printer connected (interface={interface_num}, out=0x{out_ep:02x}, in=0x{in_ep:02x})")
                            break
                        except Exception as ep_error:
                            continue
                    else:
                        continue  # Continue to next interface if this one didn't work
                    break  # Break out of interface loop if we succeeded
                
                if not self.enabled:
                    raise Exception("Could not connect with any profile or endpoint combination")
                
        except Exception as e:
            print(f"⚠ Printer not available: {e}")
            print("  Printing disabled - scanner will still work")
            print("\n  To find correct endpoints, run:")
            print(f"    lsusb -vvv -d {hex(self.vendor_id)}:{hex(self.product_id)} | grep bEndpointAddress")
            print("  Look for lines with 'OUT' and 'IN' to find out_ep and in_ep values")
    
    def _reconnect_printer(self):
        """
        Reconnect the printer by closing and reopening the connection.
        This ensures any buffered commands are flushed.
        
        Returns:
            bool: True if reconnection successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # CRITICAL: Release interface before closing to avoid "Resource busy" errors
            try:
                if self.printer and hasattr(self.printer, 'device'):
                    if hasattr(self, 'claimed_interface') and self.claimed_interface is not None:
                        try:
                            usb.util.release_interface(self.printer.device, self.claimed_interface)
                        except:
                            pass
            except:
                pass
            
            # Close existing connection
            try:
                if self.printer:
                    if hasattr(self.printer, 'close'):
                        self.printer.close()
                    elif hasattr(self.printer, '_raw') and hasattr(self.printer._raw, 'close'):
                        self.printer._raw.close()
            except:
                pass
            
            # Small delay to let USB settle
            time.sleep(0.2)
            
            # Reconnect using the same method as initialization
            is_jieli_printer = (self.vendor_id == 0x4c4a)
            
            if hasattr(self, 'profile') and self.profile:
                # Reconnect with profile
                self.printer = Usb(self.vendor_id, self.product_id, profile=self.profile)
                self._set_media_width(self.printer, 384)
            elif hasattr(self, 'endpoints') and self.endpoints:
                # Reconnect with manual endpoints
                out_ep, in_ep = self.endpoints
                interface_num = getattr(self, 'interface_num', 1 if is_jieli_printer else 0)
                try:
                    self.printer = Usb(
                        self.vendor_id, 
                        self.product_id, 
                        interface=interface_num,
                        in_ep=in_ep,
                        out_ep=out_ep
                    )
                except Exception as usb_error:
                    # If "Resource busy", try to reset the device first
                    if "busy" in str(usb_error).lower() or "16" in str(usb_error):
                        try:
                            # Try to find and reset the device
                            if USB_CORE_AVAILABLE:
                                dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
                                if dev:
                                    # Release all interfaces
                                    try:
                                        cfg = dev.get_active_configuration()
                                        for intf in cfg:
                                            try:
                                                usb.util.release_interface(dev, intf.bInterfaceNumber)
                                            except:
                                                pass
                                    except:
                                        pass
                            time.sleep(0.5)  # Wait for USB to settle
                            # Try again
                            self.printer = Usb(
                                self.vendor_id, 
                                self.product_id, 
                                interface=interface_num,
                                in_ep=in_ep,
                                out_ep=out_ep
                            )
                        except:
                            raise usb_error
                    else:
                        raise
                self._set_media_width(self.printer, 384)
                # Re-claim interface if needed
                try:
                    if hasattr(self.printer, 'device') and hasattr(self.printer.device, 'is_kernel_driver_active'):
                        cfg = self.printer.device.get_active_configuration()
                        for intf in cfg:
                            if intf.bInterfaceNumber == interface_num:
                                if self.printer.device.is_kernel_driver_active(intf.bInterfaceNumber):
                                    try:
                                        self.printer.device.detach_kernel_driver(intf.bInterfaceNumber)
                                    except:
                                        pass
                                try:
                                    # Only set configuration if not already set
                                    try:
                                        self.printer.device.set_configuration(cfg)
                                    except usb.core.USBError as cfg_error:
                                        if "busy" not in str(cfg_error).lower() and "16" not in str(cfg_error):
                                            raise
                                    self.printer.device.claim_interface(intf.bInterfaceNumber)
                                    self.claimed_interface = intf.bInterfaceNumber
                                except:
                                    pass
                except:
                    pass
            else:
                # Fallback: try manual endpoints (Jieli default)
                interface_num = 1 if is_jieli_printer else 0
                self.printer = Usb(
                    self.vendor_id, 
                    self.product_id, 
                    interface=interface_num,
                    in_ep=0x82,
                    out_ep=0x02
                )
                self._set_media_width(self.printer, 384)
                self.endpoints = (0x02, 0x82)
                self.interface_num = interface_num
            
            return True
            
        except Exception as e:
            print(f"  ⚠ Warning: Could not reconnect printer: {e}")
            return False
    
    def _initialize_printer(self):
        """
        Initialize/wake up the printer with ESC/POS commands.
        Some printers need initialization before they'll print.
        """
        try:
            # ESC @ - Initialize printer (resets printer to default state)
            # This is a standard ESC/POS command that wakes up the printer
            init_sent = False
            
            if hasattr(self.printer, '_raw'):
                try:
                    self.printer._raw(b'\x1b\x40')  # ESC @
                    init_sent = True
                except:
                    pass
            elif hasattr(self.printer, 'device') and hasattr(self.printer.device, 'write'):
                try:
                    self.printer.device.write(b'\x1b\x40')
                    init_sent = True
                except:
                    pass
            elif hasattr(self.printer, 'hw') and hasattr(self.printer.hw, 'write'):
                try:
                    self.printer.hw.write(b'\x1b\x40')
                    init_sent = True
                except:
                    pass
            
            # Small delay to let printer process
            if init_sent:
                time.sleep(0.15)
            
            # Some printers need a line feed or text command to wake up
            # Try multiple wake-up methods
            wake_methods = [
                # Method 1: Use control() if available
                lambda: self.printer.control("LF") if hasattr(self.printer, 'control') else None,
                # Method 2: Use _raw with line feed
                lambda: self.printer._raw(b'\n') if hasattr(self.printer, '_raw') else None,
                # Method 3: Use text() method
                lambda: self.printer.text('\n') if hasattr(self.printer, 'text') else None,
                # Method 4: Direct device write
                lambda: self.printer.device.write(b'\n') if hasattr(self.printer, 'device') and hasattr(self.printer.device, 'write') else None,
            ]
            
            for method in wake_methods:
                try:
                    result = method()
                    if result is not None:
                        time.sleep(0.1)
                        break
                except:
                    continue
                    
        except Exception as e:
            # Non-critical - continue even if init fails
            # Some printers don't need initialization
            pass
    
    def _send_raw_command(self, command_bytes):
        """Send raw bytes directly to printer, trying multiple methods"""
        # Try to get the actual endpoint for direct writing
        try:
            if hasattr(self.printer, 'device'):
                # Find the bulk OUT endpoint
                cfg = self.printer.device.get_active_configuration()
                intf = cfg[(0, 0)]  # Interface 0, alternate setting 0
                
                # Find bulk OUT endpoint
                ep_out = None
                for ep in intf:
                    if (ep.bmAttributes & 0x02) == 0x02 and (ep.bEndpointAddress & 0x80) == 0:
                        ep_out = ep
                        break
                
                if ep_out:
                    # Write directly to endpoint
                    bytes_written = self.printer.device.write(ep_out.bEndpointAddress, command_bytes, timeout=1000)
                    if bytes_written == len(command_bytes):
                        return True
        except Exception as e:
            pass
        
        # Fallback to python-escpos methods
        methods = [
            lambda: self.printer._raw(command_bytes) if hasattr(self.printer, '_raw') else None,
            lambda: self.printer.device.write(command_bytes) if hasattr(self.printer, 'device') and hasattr(self.printer.device, 'write') else None,
            lambda: self.printer.hw.write(command_bytes) if hasattr(self.printer, 'hw') and hasattr(self.printer.hw, 'write') else None,
        ]
        
        for method in methods:
            try:
                result = method()
                if result is not None:
                    return True
            except Exception as e:
                continue
        return False
    
    def _check_printer_access(self):
        """Check if we can access the printer device"""
        print("  → Checking printer access...")
        try:
            # Try to access the device
            if hasattr(self.printer, 'device'):
                print(f"    ✓ Device object exists: {type(self.printer.device)}")
                if hasattr(self.printer.device, 'write'):
                    print("    ✓ Device has write() method")
                else:
                    print("    ✗ Device does not have write() method")
            elif hasattr(self.printer, '_raw'):
                print(f"    ✓ _raw object exists: {type(self.printer._raw)}")
            else:
                print("    ⚠ Cannot find device or _raw object")
            
            # Check USB permissions
            result = subprocess.run(['lsusb', '-d', f'{self.vendor_id:04x}:{self.product_id:04x}'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"    ✓ Printer found in USB device list")
                print(f"    → {result.stdout.strip()}")
            else:
                print(f"    ✗ Printer not found in USB device list")
                print(f"    → Run: lsusb | grep -i '{self.vendor_id:04x}'")
            
            return True
        except Exception as e:
            print(f"    ✗ Error checking access: {e}")
            return False
    
    def test_print(self):
        """
        Test print - prints a simple test pattern to verify printer is working
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            print("✗ Printer not available")
            return False
        
        try:
            print("🖨 Testing printer with simple text...")
            print(f"  → Printer: vendor=0x{self.vendor_id:04x}, product=0x{self.product_id:04x}")
            
            # Check printer access first
            self._check_printer_access()
            print()
            
            # Method 1: Try raw ESC/POS commands directly
            print("\n  → Method 1: Sending raw ESC/POS commands...")
            try:
                if not USB_CORE_AVAILABLE:
                    print("    ⚠ usb.core not available, skipping direct USB method")
                else:
                    # Try to write directly to USB endpoint
                    # Get the device directly
                    dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
                    if dev is None:
                        print("    ✗ Could not find USB device")
                    else:
                        print(f"    ✓ Found USB device: {dev}")
                        
                        # Set configuration
                        try:
                            dev.set_configuration()
                            print("    ✓ Set USB configuration")
                        except Exception as e:
                            print(f"    ⚠ Configuration error (may be OK): {e}")
                        
                        # Find and claim interface
                        # For CDC devices (like Jieli Technology), the data interface is usually interface 1
                        # Interface 0 is the communication interface, interface 1 is the data interface
                        cfg = dev.get_active_configuration()
                        
                        # Try interface 1 first for CDC devices, then fall back to 0
                        is_jieli = (self.vendor_id == 0x4c4a)
                        interface_numbers = [1, 0] if is_jieli else [0, 1]
                        
                        intf = None
                        ep_out = None
                        
                        for intf_num in interface_numbers:
                            try:
                                intf = cfg[(intf_num, 0)]
                                
                                # Detach kernel driver if needed
                                try:
                                    if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                                        dev.detach_kernel_driver(intf.bInterfaceNumber)
                                        print(f"    ✓ Detached kernel driver from interface {intf.bInterfaceNumber}")
                                except:
                                    pass
                                
                                # Claim interface
                                try:
                                    usb.util.claim_interface(dev, intf.bInterfaceNumber)
                                    print(f"    ✓ Claimed interface {intf.bInterfaceNumber}")
                                except Exception as e:
                                    print(f"    ⚠ Interface claim error (may be OK): {e}")
                                
                                # Find bulk OUT endpoint (0x02)
                                for ep in intf:
                                    if (ep.bmAttributes & 0x02) == 0x02:  # Bulk transfer
                                        addr = ep.bEndpointAddress
                                        if (addr & 0x80) == 0:  # OUT endpoint
                                            ep_out = ep
                                            print(f"    ✓ Found OUT endpoint: 0x{addr:02x} on interface {intf.bInterfaceNumber}")
                                            break
                                
                                if ep_out:
                                    break
                            except (KeyError, IndexError):
                                continue
                        
                        if ep_out:
                            # Send commands directly
                            print("    → Sending ESC @ (initialize)...")
                            bytes_written = dev.write(ep_out.bEndpointAddress, b'\x1b\x40', timeout=1000)
                            print(f"    ✓ Wrote {bytes_written} bytes (ESC @)")
                            time.sleep(0.2)
                            
                            # Send test text
                            test_text = b"DIRECT USB TEST\nIf you see this, direct USB works!\n\n"
                            print("    → Sending test text...")
                            bytes_written = dev.write(ep_out.bEndpointAddress, test_text, timeout=1000)
                            print(f"    ✓ Wrote {bytes_written} bytes (text)")
                            time.sleep(0.2)
                            
                            # Send cut command
                            cut_cmd = b'\x1d\x56\x00'  # GS V 0 (partial cut)
                            print("    → Sending cut command...")
                            bytes_written = dev.write(ep_out.bEndpointAddress, cut_cmd, timeout=1000)
                            print(f"    ✓ Wrote {bytes_written} bytes (cut)")
                            time.sleep(0.5)
                            
                            # Release interface
                            if intf:
                                try:
                                    usb.util.release_interface(dev, intf.bInterfaceNumber)
                                    print("    ✓ Released interface")
                                except:
                                    pass
                            
                            print("    → Check if anything printed from direct USB commands")
                            time.sleep(2.0)  # Give printer time
                        else:
                            print("    ✗ Could not find OUT endpoint")
                            # Release interface if we claimed one but didn't find endpoint
                            if intf:
                                try:
                                    usb.util.release_interface(dev, intf.bInterfaceNumber)
                                except:
                                    pass
                
            except Exception as e:
                print(f"    ✗ Direct USB method failed: {e}")
                import traceback
                traceback.print_exc()
            
            # Reconnect for method 2
            # First, make sure any interfaces from Method 1 are fully released
            time.sleep(0.5)  # Give USB time to settle after Method 1
            self._reconnect_printer()
            time.sleep(0.5)
            
            # Method 2: Try python-escpos high-level methods
            print("\n  → Method 2: Using python-escpos methods...")
            
            # Initialize/wake up printer
            print("    → Initializing printer...")
            try:
                self._initialize_printer()
            except Exception as init_error:
                # If initialization fails due to resource busy, try reconnecting again
                if "busy" in str(init_error).lower() or "16" in str(init_error):
                    print(f"    ⚠ Resource busy, reconnecting...")
                    time.sleep(1.0)  # Longer delay
                    self._reconnect_printer()
                    time.sleep(0.5)
                    self._initialize_printer()
                else:
                    raise
            time.sleep(0.2)
            
            # Try a simple text print first
            print("    → Sending text commands...")
            self.printer.text("ESC/POS TEST PRINT\n")
            self.printer.text("If you see this, escpos methods work!\n")
            self.printer.text("\n")
            time.sleep(0.1)
            
            # Send form feed to ensure printing starts
            try:
                self.printer.control("LF")  # Line feed
                self.printer.control("FF")  # Form feed
                print("    ✓ Sent form feed")
            except Exception as e:
                print(f"    ⚠ Form feed failed: {e}")
                # If control() doesn't work, try raw commands
                try:
                    if hasattr(self.printer, '_raw'):
                        self.printer._raw(b'\n\n\n')  # Multiple line feeds
                        print("    ✓ Sent raw line feeds")
                except:
                    pass
            
            print("    → Sending cut command...")
            self.printer.cut()
            
            # CRITICAL: Close the connection to flush buffer
            # python-escpos buffers commands until connection is closed
            print("    → Closing connection to flush buffer...")
            connection_closed = False
            try:
                if hasattr(self.printer, 'close'):
                    self.printer.close()
                    connection_closed = True
                    print("    ✓ Connection closed via close() method")
                elif hasattr(self.printer, '_raw') and hasattr(self.printer._raw, 'close'):
                    self.printer._raw.close()
                    connection_closed = True
                    print("    ✓ Connection closed via _raw.close() method")
                elif hasattr(self.printer, 'device') and hasattr(self.printer.device, 'close'):
                    self.printer.device.close()
                    connection_closed = True
                    print("    ✓ Connection closed via device.close() method")
            except Exception as close_error:
                print(f"    ⚠ Could not close connection: {close_error}")
            
            # Give printer time to process after closing
            print("    → Waiting for printer to process commands...")
            time.sleep(2.0)  # Longer delay to give printer time
            
            print("\n✓ Test print commands sent (both methods)")
            print("  → Check if anything printed from the printer")
            print("  → If nothing printed, the printer may need:")
            print("     1. Different USB cable or port")
            print("     2. Driver installation")
            print("     3. Different command format")
            print("     4. Check printer manual for ESC/POS compatibility")
            return True
            
        except Exception as e:
            print(f"✗ Test print failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def print_qr_sticker(self, spotify_uri, title, artist_or_owner=""):
        """
        Print a QR code sticker with title and artist/owner
        
        Args:
            spotify_uri: Spotify URI (playlist/album/track)
            title: Main title to print
            artist_or_owner: Subtitle (artist or playlist owner)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            print("✗ Printer not available")
            return False
        
        try:
            print(f"🖨 Printing: {title}")
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=4,
                border=2,
            )
            qr.add_data(spotify_uri)
            qr.make(fit=True)
            
            # Create QR code image
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Create sticker layout
            # Standard 53mm thermal printer = ~384 pixels width
            sticker_width = 384
            qr_size = 280
            
            # Resize QR code
            qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
            
            # Calculate height
            header_height = 30  # Space for "MUSIC BUTLER" at top
            text_height = 100   # Space for title/artist below QR code
            sticker_height = header_height + qr_size + text_height
            
            # Create white background (mode '1' = 1-bit pixels, black and white)
            # Thermal printers work best with 1-bit images
            sticker = Image.new('1', (sticker_width, sticker_height), 1)
            
            # Ensure QR code is in the right format (1-bit)
            if qr_img.mode != '1':
                qr_img = qr_img.convert('1')
            
            # Add text
            draw = ImageDraw.Draw(sticker)
            
            # Try to load fonts
            try:
                font_header = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
                font_title = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
                font_artist = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except:
                font_header = ImageFont.load_default()
                font_title = ImageFont.load_default()
                font_artist = ImageFont.load_default()
            
            # Draw "MUSIC BUTLER" header at top
            header_text = "MUSIC BUTLER"
            bbox = draw.textbbox((0, 0), header_text, font=font_header)
            text_width = bbox[2] - bbox[0]
            x_pos = (sticker_width - text_width) // 2
            y_pos = 5
            draw.text((x_pos, y_pos), header_text, fill=0, font=font_header)
            
            # Paste QR code centered (below header)
            x_offset = (sticker_width - qr_size) // 2
            sticker.paste(qr_img, (x_offset, header_height))
            
            # Truncate text if too long
            if len(title) > 30:
                title = title[:27] + "..."
            if len(artist_or_owner) > 35:
                artist_or_owner = artist_or_owner[:32] + "..."
            
            # Draw title (below QR code)
            y_pos = header_height + qr_size + 10
            bbox = draw.textbbox((0, 0), title, font=font_title)
            text_width = bbox[2] - bbox[0]
            x_pos = (sticker_width - text_width) // 2
            draw.text((x_pos, y_pos), title, fill=0, font=font_title)
            
            # Draw artist/owner
            if artist_or_owner:
                y_pos += 25
                bbox = draw.textbbox((0, 0), artist_or_owner, font=font_artist)
                text_width = bbox[2] - bbox[0]
                x_pos = (sticker_width - text_width) // 2
                draw.text((x_pos, y_pos), artist_or_owner, fill=0, font=font_artist)
            
            # Initialize/wake up printer before printing
            print("  → Initializing printer...")
            self._initialize_printer()
            time.sleep(0.2)  # Give printer time to wake up
            
            # Send a test line first to wake up the printer and verify it's responding
            # Some printers need text before they'll print images
            try:
                print("  → Sending wake-up text...")
                self.printer.text("")  # Empty text to wake printer
                time.sleep(0.1)
            except Exception as wake_error:
                print(f"  ⚠ Warning: Wake-up text failed: {wake_error}")
            
            # Always use manual centering (skip center flag to avoid media width warning)
            # The sticker is already 384 pixels wide, so it should fit perfectly
            # But ensure it's exactly the right width
            if sticker.width != sticker_width:
                # Resize or pad to exact width
                if sticker.width < sticker_width:
                    # Add padding to center
                    padding_left = (sticker_width - sticker.width) // 2
                    centered_sticker = Image.new('1', (sticker_width, sticker.height), 1)
                    centered_sticker.paste(sticker, (padding_left, 0))
                    sticker = centered_sticker
                else:
                    # Resize to fit
                    sticker = sticker.resize((sticker_width, int(sticker.height * sticker_width / sticker.width)), Image.Resampling.LANCZOS)
            
            # Try multiple methods to send image to printer
            image_sent = False
            img_error = None
            
            print(f"  → Sending image to printer (size: {sticker.width}x{sticker.height}, mode: {sticker.mode})...")
            
            # Ensure image is in 1-bit mode (required for thermal printers)
            if sticker.mode != '1':
                sticker = sticker.convert('1')
                print("  → Converted image to 1-bit mode")
            
            # Try printing with 1-bit image (preferred for thermal printers)
            # Skip center flag to avoid media width warning
            image_sent = False
            img_error = None
            
            try:
                # Use image() method without center flag
                self.printer.image(sticker, center=False)
                image_sent = True
                print("  → Image sent successfully")
            except Exception as e:
                img_error = e
                print(f"  ✗ Error sending image: {e}")
                print(f"  → Error type: {type(e).__name__}")
                # Try to get more details
                import traceback
                print(f"  → Traceback:")
                for line in traceback.format_exc().split('\n')[:5]:
                    if line.strip():
                        print(f"    {line}")
            
            if not image_sent:
                raise Exception(f"Could not send image to printer: {img_error}")
            
            # Feed some blank lines before cutting
            print("  → Sending line feeds...")
            try:
                self.printer.text("\n\n")
            except Exception as text_error:
                print(f"  ⚠ Warning: Error sending text: {text_error}")
            
            # Cut the paper
            print("  → Sending cut command...")
            try:
                self.printer.cut()
            except Exception as cut_error:
                print(f"  ⚠ Warning: Error sending cut command: {cut_error}")
            
            # Some printers need a form feed to actually print
            print("  → Sending form feed...")
            try:
                if hasattr(self.printer, 'control'):
                    self.printer.control("FF")  # Form feed
                elif hasattr(self.printer, '_raw'):
                    self.printer._raw(b'\x0c')  # Form feed byte
            except:
                pass  # Form feed is optional
            
            # CRITICAL: Flush and close the connection to ensure commands are sent
            # python-escpos buffers commands and they are NOT sent until connection is closed
            # This is the most reliable way to ensure commands are actually sent to the printer
            
            # First, try to flush any buffered data
            try:
                if hasattr(self.printer, 'flush'):
                    self.printer.flush()
                elif hasattr(self.printer, '_raw') and hasattr(self.printer._raw, 'flush'):
                    self.printer._raw.flush()
                elif hasattr(self.printer, 'device') and hasattr(self.printer.device, 'flush'):
                    self.printer.device.flush()
            except:
                pass  # Flush is optional, continue with close
            
            # Small delay to let flush complete
            time.sleep(0.1)
            
            # Now close the connection to force sending
            connection_closed = False
            try:
                if hasattr(self.printer, 'close'):
                    self.printer.close()
                    connection_closed = True
                elif hasattr(self.printer, '_raw') and hasattr(self.printer._raw, 'close'):
                    self.printer._raw.close()
                    connection_closed = True
                elif hasattr(self.printer, 'device') and hasattr(self.printer.device, 'close'):
                    self.printer.device.close()
                    connection_closed = True
            except Exception as close_error:
                print(f"  ⚠ Warning: Could not close printer connection: {close_error}")
            
            # Give printer time to process the commands after closing
            # Longer delay to ensure printer has time to print
            print("  → Waiting for printer to process commands...")
            time.sleep(1.0)  # Increased delay - some printers need more time
            
            # Reconnect for next print operation
            if connection_closed:
                print("  → Reconnecting printer for next operation...")
                reconnect_success = self._reconnect_printer()
                if not reconnect_success:
                    print("  ⚠ Warning: Could not reconnect printer")
            else:
                # If we couldn't close, try to flush instead
                print("  → Connection not closed, trying to flush...")
                try:
                    if hasattr(self.printer, 'flush'):
                        self.printer.flush()
                    elif hasattr(self.printer, '_raw') and hasattr(self.printer._raw, 'flush'):
                        self.printer._raw.flush()
                except:
                    pass
            
            print(f"✓ Sticker print commands sent successfully")
            print(f"  → If nothing printed, try:")
            print(f"     1. Check printer power and paper")
            print(f"     2. Run test print: python3 -c \"from hardware.printer import StickerPrinter; import config; p=StickerPrinter(config.PRINTER_VENDOR_ID, config.PRINTER_PRODUCT_ID); p.test_print()\"")
            print(f"     3. Unplug and replug USB cable")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"✗ Error printing sticker: {error_msg}")
            
            # Provide helpful error messages for common issues
            if "device not found" in error_msg.lower() or "not found or cable not plugged" in error_msg.lower():
                print("  → USB device not found error")
                print("  → Troubleshooting steps:")
                print(f"     1. Check if printer is connected: lsusb | grep -i '{hex(self.vendor_id)[2:]}'")
                print(f"     2. Verify printer IDs in config.py:")
                print(f"        Current: vendor_id={hex(self.vendor_id)}, product_id={hex(self.product_id)}")
                print("     3. Unplug and replug the printer USB cable")
                print("     4. Try a different USB port")
                print("     5. Check USB device list: lsusb")
                print("     6. Verify the printer is powered on")
            elif "endpoint" in error_msg.lower() or "0x1" in error_msg or "invalid endpoint" in error_msg.lower():
                print("  → USB endpoint error detected")
                print("  → Attempting to reconnect with manual endpoint configuration...")
                # When endpoint errors occur, skip profiles and use manual endpoints directly
                # Profiles are causing the endpoint issue, so we need explicit endpoint addresses
                try:
                    # Common endpoint combinations for thermal printers
                    # Jieli Technology printers typically use (0x02, 0x82)
                    endpoint_combos = [
                        (0x02, 0x82),  # Jieli Technology / Phomemo (most common for this vendor)
                        (0x01, 0x81),  # Other common printers
                        (0x01, 0x82),
                        (0x02, 0x81),
                        (0x03, 0x83),
                    ]
                    
                    reconnected = False
                    # Skip profiles - go straight to manual endpoints when endpoint error occurs
                    for out_ep, in_ep in endpoint_combos:
                        try:
                            self.printer = Usb(
                                self.vendor_id, 
                                self.product_id, 
                                interface=0,
                                in_ep=in_ep,
                                out_ep=out_ep
                            )
                            # Set media width for centering (384 pixels for 53mm thermal printer)
                            self._set_media_width(self.printer, 384)
                            self.profile = None
                            self.endpoints = (out_ep, in_ep)
                            print(f"  → Reconnected with manual endpoints: out=0x{out_ep:02x}, in=0x{in_ep:02x}")
                            reconnected = True
                            break
                        except Exception as ep_error:
                            continue
                    
                    if not reconnected:
                        raise Exception("Could not reconnect with any endpoint combination")
                    
                    # Retry printing after reconnection
                    print("  → Retrying print operation...")
                    
                    # Initialize printer
                    self._initialize_printer()
                    
                    # Set media width if not already set (for centering to work)
                    self._set_media_width(self.printer, sticker_width)
                    self.printer.image(sticker, center=True)
                    self.printer.text("\n\n")
                    self.printer.cut()
                    
                    # CRITICAL: Close the connection to flush the buffer
                    connection_closed = False
                    try:
                        if hasattr(self.printer, 'close'):
                            self.printer.close()
                            connection_closed = True
                        elif hasattr(self.printer, '_raw') and hasattr(self.printer._raw, 'close'):
                            self.printer._raw.close()
                            connection_closed = True
                    except Exception as close_error:
                        print(f"  ⚠ Warning: Could not close printer connection: {close_error}")
                    
                    # Give printer time to process after closing
                    time.sleep(0.2)
                    
                    # Reconnect for next use
                    if connection_closed:
                        self._reconnect_printer()
                    
                    print(f"✓ Sticker printed successfully")
                    return True
                    
                except Exception as reconnect_error:
                    print(f"  → Reconnection failed: {reconnect_error}")
                    print("  → Troubleshooting steps:")
                    print("     1. Find correct endpoints:")
                    print(f"        lsusb -vvv -d {hex(self.vendor_id)}:{hex(self.product_id)} | grep bEndpointAddress")
                    print("        Look for lines with 'OUT' (out_ep) and 'IN' (in_ep)")
                    print("     2. Unplug and replug the printer USB cable")
                    print("     3. Try a different USB port")
                    print("     4. Check if printer needs drivers: dmesg | tail -20")
            elif "permission" in error_msg.lower() or "access" in error_msg.lower():
                print("  → Permission error - try:")
                print("     1. Add user to dialout group: sudo usermod -a -G dialout $USER")
                print("     2. Add user to printer group: sudo usermod -a -G lp $USER")
                print("     3. Check udev rules for USB device permissions")
                print("     4. Verify USB device permissions: ls -l /dev/bus/usb/")
                print("     5. Log out and back in, or reboot after adding groups")
            else:
                # Generic error - provide general troubleshooting
                print("  → General troubleshooting:")
                print("     1. Verify printer is connected and powered on")
                print("     2. Check USB connection: lsusb")
                print("     3. Try unplugging and replugging the printer")
                print("     4. Check printer paper/ink levels")
                print("     5. Try a test print to verify basic functionality")
                print("\n  → If commands are sent but nothing prints:")
                print("     • The printer may be buffering - try unplugging/replugging")
                print("     • Test with: python3 -c \"from hardware.printer import StickerPrinter; import config; p=StickerPrinter(config.PRINTER_VENDOR_ID, config.PRINTER_PRODUCT_ID); p.test_print()\"")
                print("     • Check USB permissions: ls -l /dev/bus/usb/")
                print("     • Verify printer is powered on and has paper")
            
            return False
