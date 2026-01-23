"""
Quick script to enable file logging
Run this once, then restart the app
"""
import logging

# Enable file logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log'),
        logging.StreamHandler()
    ]
)

print("File logging enabled! Logs will go to app_debug.log")
