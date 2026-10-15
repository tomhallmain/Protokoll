import logging
import os
import sys

from PyQt6.QtWidgets import QApplication
from .ui.main_window import MainWindow
from .ui.qt_message_log import install_qt_message_handler
from .utils.build_maintenance import start_build_maintenance
from .utils.crash_log import enable_fault_log
from .utils.logging_setup import get_logger
from .utils.theme_manager import ThemeManager
from .utils.version import describe

def main():
    # Set up logging
    logger = get_logger('main')
    logger.info("Starting Protokoll application")
    logger.info(describe())
    try:
        logger.info(f"Fault log: {enable_fault_log()}")
    except OSError as e:
        logger.error(f"Could not open the fault log: {e}")
    install_qt_message_handler()

    if "--smoke-test" in sys.argv[1:]:
        sys.exit(_smoke_test())

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Protokoll")
    
    # Apply dark theme
    ThemeManager.apply_dark_theme(app)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    # Not in the smoke test: it exits within seconds, which would cut a folder
    # removal short.
    start_build_maintenance(on_drift=window.source_drift.emit)
    
    # Start event loop
    sys.exit(app.exec())

def _smoke_test() -> int:
    """Run the smoke test in the environment run.py isolated for it."""
    from .utils.globals import AppInfo
    from .utils.smoke_test import SCRATCH_DIR_ENV, SMOKE_SERVICE_NAME, run_smoke_test

    if AppInfo.SERVICE_NAME != SMOKE_SERVICE_NAME:
        # Without run.py's isolation the checks would write to the user's
        # config dir and key store.
        get_logger('main').error("--smoke-test needs the environment run.py sets up; start it through run.py")
        return 1
    return run_smoke_test(os.environ[SCRATCH_DIR_ENV], expect_oqs="--expect-oqs" in sys.argv[1:])

if __name__ == "__main__":
    main() 