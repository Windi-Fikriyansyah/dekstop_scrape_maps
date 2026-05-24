#!/usr/bin/env python3
"""
Diagnostic test untuk staffspy import issues
"""
import sys
import os

print("=" * 60)
print("StaffSpy Dependency Diagnostic")
print("=" * 60)

# Check if staffspy directory exists
staffspy_dir = os.path.join(os.path.dirname(__file__), "staffspy")
print(f"\n1. Checking staffspy directory: {staffspy_dir}")
print(f"   Exists: {os.path.exists(staffspy_dir)}")

if os.path.exists(staffspy_dir):
    files = os.listdir(staffspy_dir)
    print(f"   Files: {files}")

# Try importing basic dependencies
print("\n2. Checking core dependencies...")
deps_to_check = [
    "customtkinter",
    "playwright",
    "sqlalchemy",
    "pandas",
    "requests",
    "selenium",
    "beautifulsoup4",
]

for dep in deps_to_check:
    try:
        __import__(dep)
        print(f"   ✓ {dep}")
    except ImportError as e:
        print(f"   ✗ {dep}: {e}")

# Try importing staffspy
print("\n3. Attempting to import staffspy...")
sys.path.insert(0, os.path.dirname(__file__))

try:
    from staffspy import LinkedInAccount
    print("   ✓ Successfully imported LinkedInAccount from staffspy")
except ImportError as e:
    print(f"   ✗ Failed to import: {e}")
    
    # Try importing staffspy module directly
    try:
        import staffspy
        print(f"   ℹ staffspy module found at: {staffspy.__file__}")
        print(f"   ℹ staffspy attributes: {dir(staffspy)}")
    except ImportError as e2:
        print(f"   ✗ Cannot import staffspy module: {e2}")

# Solution
print("\n" + "=" * 60)
print("SOLUTION:")
print("=" * 60)
print("If staffspy import fails, try one of these:")
print("")
print("1. Install missing dependencies:")
print("   pip install -r requirements.txt")
print("")
print("2. If staffspy is a local module, ensure __init__.py exists:")
print("   - Check if staffspy/__init__.py exists")
print("   - If not, you may need to create it")
print("")
print("3. For LinkedIn scraping to work without staffspy:")
print("   - You can disable LinkedIn tab or use a simpler API")
print("")
