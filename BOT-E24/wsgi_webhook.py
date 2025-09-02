#!/usr/bin/python3
"""
WSGI entry point for PythonAnywhere webhook-only bot
"""

import sys
import os

# Add your project directory to sys.path
path = '/home/yourusername/mysite'  # Замените на ваш путь
if path not in sys.path:
    sys.path.append(path)

from webhook_only_bot import app as application

if __name__ == "__main__":
    application.run()
