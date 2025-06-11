import sys
from PyQt6.QtWidgets import QApplication
from .ui.main_window import MainWindow
from .utils.theme_manager import ThemeManager

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Protokoll")
    
    # Apply dark theme
    ThemeManager.apply_dark_theme(app)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 