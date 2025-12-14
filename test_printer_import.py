#!/usr/bin/env python3
"""Test script to diagnose StickerPrinter import issues"""

print("Testing StickerPrinter import...")

try:
    print("1. Importing music_butler module...")
    import music_butler
    print("   ✓ Module imported")
except Exception as e:
    print(f"   ✗ Failed to import module: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

try:
    print("2. Checking if StickerPrinter class exists...")
    if hasattr(music_butler, 'StickerPrinter'):
        print("   ✓ StickerPrinter class found")
        print(f"   → Class: {music_butler.StickerPrinter}")
    else:
        print("   ✗ StickerPrinter class not found")
        print(f"   → Available attributes: {[x for x in dir(music_butler) if not x.startswith('_')]}")
        exit(1)
except Exception as e:
    print(f"   ✗ Error checking class: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

try:
    print("3. Importing config...")
    import config
    print("   ✓ Config imported")
    print(f"   → PRINTER_VENDOR_ID: {config.PRINTER_VENDOR_ID}")
    print(f"   → PRINTER_PRODUCT_ID: {config.PRINTER_PRODUCT_ID}")
except Exception as e:
    print(f"   ✗ Failed to import config: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

try:
    print("4. Creating StickerPrinter instance...")
    printer = music_butler.StickerPrinter(config.PRINTER_VENDOR_ID, config.PRINTER_PRODUCT_ID)
    print("   ✓ StickerPrinter instance created")
    print(f"   → Enabled: {printer.enabled}")
except Exception as e:
    print(f"   ✗ Failed to create instance: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n✓ All tests passed! StickerPrinter is working.")
print("\nYou can now run:")
print("  python3 -c \"from music_butler import StickerPrinter; import config; p=StickerPrinter(config.PRINTER_VENDOR_ID, config.PRINTER_PRODUCT_ID); p.test_print()\"")
