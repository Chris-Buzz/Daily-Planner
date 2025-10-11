#!/usr/bin/env python3
"""
Generate VAPID keys for Web Push Notifications

This script generates a public/private key pair for VAPID (Voluntary Application Server Identification)
which is required for sending push notifications to browsers.

Usage:
    python generate_vapid_keys.py

The script will output the keys which you should add to your .env file:
    VAPID_PUBLIC_KEY=<generated_public_key>
    VAPID_PRIVATE_KEY=<generated_private_key>
    VAPID_EMAIL=mailto:your-email@example.com
"""

try:
    from py_vapid import Vapid
except ImportError:
    print("❌ Error: py_vapid package not installed")
    print("📦 Please install it with: pip install py-vapid")
    print("   Or install from requirements.txt: pip install -r requirements.txt")
    exit(1)

def generate_vapid_keys():
    """Generate VAPID key pair for push notifications"""
    print("🔐 Generating VAPID keys for Web Push Notifications...")
    print()

    # Generate new VAPID key pair
    vapid = Vapid()
    vapid.generate_keys()

    # Get the keys
    public_key = vapid.public_key.encode('utf-8').decode('utf-8')
    private_key = vapid.private_key.encode('utf-8').decode('utf-8')

    print("✅ VAPID keys generated successfully!")
    print()
    print("=" * 70)
    print("Add these lines to your .env file:")
    print("=" * 70)
    print()
    print(f"VAPID_PUBLIC_KEY={public_key}")
    print(f"VAPID_PRIVATE_KEY={private_key}")
    print("VAPID_EMAIL=mailto:your-email@example.com")
    print()
    print("=" * 70)
    print()
    print("📝 Instructions:")
    print("1. Copy the three lines above")
    print("2. Add them to your .env file")
    print("3. Replace 'your-email@example.com' with your actual email")
    print("4. Restart your application")
    print()
    print("🔒 Security Notes:")
    print("- Keep your VAPID_PRIVATE_KEY secret!")
    print("- Never commit your .env file to version control")
    print("- The VAPID_PUBLIC_KEY is safe to expose to clients")
    print()

if __name__ == "__main__":
    generate_vapid_keys()
