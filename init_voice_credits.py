"""Initialize Voice Credits with Deepgram $200 free credits"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voice_credits import get_credits_manager

# Initialize with 13 million characters (~$200 worth)
manager = get_credits_manager('deepgram')
manager.set_credits(13000000)  # 13 million characters

# Set alert threshold to 500
manager.set_alert_threshold(500)

status = manager.get_status()
print("=" * 50)
print("VOICE CREDITS INITIALIZED")
print("=" * 50)
print(f"Provider: {status['provider'].upper()}")
print(f"Total Credits: {status['total_credits']:,} characters")
print(f"Remaining: {status['remaining_credits']:,} characters")
print(f"Alert Threshold: {status['alert_threshold']} characters")
print(f"Is Low: {status['is_low']}")
print("=" * 50)
print("SUCCESS!")
