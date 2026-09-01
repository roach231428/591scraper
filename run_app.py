"""Entry point for the 591 scraper GUI application.

This script initializes the GUI module and runs the Flet application.
"""

import sys
import flet as ft
from pathlib import Path

# Add the project root to sys.path so that gui and scraper modules can be imported
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from gui.app import app

if __name__ == "__main__":
    ft.app(app)
