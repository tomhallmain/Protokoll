import sys
from PyQt6.QtWidgets import QApplication
from .ui.main_window import MainWindow
from .utils.logging_manager import LoggingManager
from .utils.theme_manager import ThemeManager
import logging

def main():
    # Set up logging
    logger = LoggingManager.setup_logging(level=logging.DEBUG)
    logger.info("Starting Protokoll application")
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Protokoll")
    
    # Apply dark theme
    ThemeManager.apply_dark_theme(app)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Start event loop
    logger.info("Entering application event loop")
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 