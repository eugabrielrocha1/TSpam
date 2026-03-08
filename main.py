"""
CyberTG Mass Scraper & Adder 2026
─────────────────────────────────
Professional Telegram automation desktop tool.
Entry point — initializes database and launches the GUI.
"""
import os
import sys

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.db import init_db
from core.logger import logger
from gui.app import CyberTGApp


def main():
    # Create sessions directory
    os.makedirs(os.path.join(PROJECT_ROOT, "sessions"), exist_ok=True)

    # Initialize database
    init_db()
    logger.info("CyberTG Mass Scraper & Adder 2026 starting...")
    logger.info("Database initialized")

    # Launch application
    app = CyberTGApp()
    app.mainloop()


if __name__ == "__main__":
    main()
