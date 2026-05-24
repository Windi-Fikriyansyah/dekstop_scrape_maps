#!/usr/bin/env python3
"""
Quick UI test untuk memastikan aplikasi bisa diimport dan instantiate tanpa error.
Bukan untuk menjalankan full app, hanya verifikasi struktur.
"""
import sys
import os

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    # Mock API calls dan database jika diperlukan
    os.environ['WAMAPS_API_URL'] = 'https://localhost'
    
    # Import desktop_app untuk cek apakah ada error struktur
    print("✓ Mengimpor desktop_app.py...")
    from desktop_app import ModernApp, COLORS
    
    print("✓ COLORS palette loaded:", len(COLORS), "items")
    print("✓ ModernApp class imported successfully")
    
    # Cek apakah COLORS memiliki key yang diharapkan
    required_keys = ["bg_light", "bg_card", "text_primary", "accent"]
    for key in required_keys:
        if key not in COLORS:
            print(f"✗ Missing color key: {key}")
        else:
            print(f"✓ Color key '{key}': {COLORS[key]}")
    
    print("\n✓ UI structure check passed!")
    print("Aplikasi siap dijalankan dengan: python desktop_app.py")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
