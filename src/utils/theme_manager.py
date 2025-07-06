from PyQt6.QtGui import QPalette, QColor

class ThemeManager:
    # Dark theme colors
    DARK_THEME = {
        "window": "#1e1e1e",
        "window_text": "#d4d4d4",
        "base": "#252526",
        "alternate_base": "#2d2d2d",
        "text": "#d4d4d4",
        "button": "#3c3c3c",
        "button_text": "#d4d4d4",
        "bright_text": "#ffffff",
        "highlight": "#264f78",
        "highlight_text": "#ffffff",
        "link": "#569cd6",
        "mid": "#3c3c3c",
        "dark": "#252526",
        "shadow": "#000000",
        "log_viewer": {
            "background": "#1e1e1e",
            "text": "#d4d4d4",
            "error": "#f14c4c",
            "warning": "#cca700",
            "info": "#569cd6",
            "success": "#6a9955"
        },
        "dialog": {
            "background": "#1e1e1e",
            "header": {
                "color": "#d4d4d4",
                "font_size": "16px"
            },
            "input": {
                "background": "#252526",
                "color": "#d4d4d4",
                "border": "#3c3c3c",
                "focus_border": "#569cd6"
            },
            "button": {
                "background": "#3c3c3c",
                "color": "#d4d4d4",
                "border": "#4c4c4c",
                "hover": "#4c4c4c",
                "pressed": "#2c2c2c"
            },
            "primary_button": {
                "background": "#264f78",
                "hover": "#2d5a8c",
                "pressed": "#1e3c5c"
            }
        }
    }
    
    # ANSI color codes mapping for log formatting
    ANSI_COLORS = {
        30: "#000000",  # Black
        31: "#cd3131",  # Red
        32: "#0dbc79",  # Green
        33: "#e5e510",  # Yellow
        34: "#2472c8",  # Blue
        35: "#bc3fbc",  # Magenta
        36: "#11a8cd",  # Cyan
        37: "#e5e5e5",  # White
        90: "#666666",  # Bright Black
        91: "#f14c4c",  # Bright Red
        92: "#23d18b",  # Bright Green
        93: "#f5f543",  # Bright Yellow
        94: "#3b8eea",  # Bright Blue
        95: "#d670d6",  # Bright Magenta
        96: "#29b8db",  # Bright Cyan
        97: "#ffffff",  # Bright White
    }
    
    # Background colors (same as foreground but with different prefix)
    ANSI_BG_COLORS = {
        40: "#000000",  # Black
        41: "#cd3131",  # Red
        42: "#0dbc79",  # Green
        43: "#e5e510",  # Yellow
        44: "#2472c8",  # Blue
        45: "#bc3fbc",  # Magenta
        46: "#11a8cd",  # Cyan
        47: "#e5e5e5",  # White
        100: "#666666", # Bright Black
        101: "#f14c4c", # Bright Red
        102: "#23d18b", # Bright Green
        103: "#f5f543", # Bright Yellow
        104: "#3b8eea", # Bright Blue
        105: "#d670d6", # Bright Magenta
        106: "#29b8db", # Bright Cyan
        107: "#ffffff", # Bright White
    }
    
    @classmethod
    def apply_dark_theme(cls, app):
        """Apply dark theme to the application"""
        palette = QPalette()
        
        # Set colors
        palette.setColor(QPalette.ColorRole.Window, QColor(cls.DARK_THEME["window"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(cls.DARK_THEME["window_text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(cls.DARK_THEME["base"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(cls.DARK_THEME["alternate_base"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(cls.DARK_THEME["text"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(cls.DARK_THEME["button"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(cls.DARK_THEME["button_text"]))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(cls.DARK_THEME["bright_text"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(cls.DARK_THEME["highlight"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(cls.DARK_THEME["highlight_text"]))
        palette.setColor(QPalette.ColorRole.Link, QColor(cls.DARK_THEME["link"]))
        palette.setColor(QPalette.ColorRole.Mid, QColor(cls.DARK_THEME["mid"]))
        palette.setColor(QPalette.ColorRole.Dark, QColor(cls.DARK_THEME["dark"]))
        palette.setColor(QPalette.ColorRole.Shadow, QColor(cls.DARK_THEME["shadow"]))
        
        # Apply palette
        app.setPalette(palette)
        
        # Set stylesheet for additional styling
        app.setStyleSheet(cls.get_global_style())
    
    @classmethod
    def get_global_style(cls) -> str:
        """Get the global stylesheet for the application"""
        return """
            QToolTip {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
            
            QMenu {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
            
            QMenu::item:selected {
                background-color: #264f78;
            }
            
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 14px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #3c3c3c;
                min-height: 20px;
                border-radius: 7px;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 14px;
                margin: 0px;
            }
            
            QScrollBar::handle:horizontal {
                background-color: #3c3c3c;
                min-width: 20px;
                border-radius: 7px;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """
    
    @classmethod
    def get_log_viewer_style(cls) -> str:
        """Get the stylesheet for the log viewer"""
        return f"""
            QTextEdit {{
                background-color: {cls.DARK_THEME["log_viewer"]["background"]};
                color: {cls.DARK_THEME["log_viewer"]["text"]};
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px;
            }}
        """
    
    @classmethod
    def get_dialog_style(cls) -> str:
        """Get the stylesheet for dialogs"""
        dialog = cls.DARK_THEME["dialog"]
        return f"""
            QDialog {{
                background-color: {dialog["background"]};
            }}
            
            #dialogHeader {{
                color: {dialog["header"]["color"]};
                font-size: {dialog["header"]["font_size"]};
                font-weight: bold;
                margin-bottom: 10px;
            }}
            
            QLabel {{
                color: {dialog["input"]["color"]};
                font-size: 12px;
            }}
            
            QLineEdit, QTextEdit {{
                background-color: {dialog["input"]["background"]};
                color: {dialog["input"]["color"]};
                border: 1px solid {dialog["input"]["border"]};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {dialog["input"]["focus_border"]};
            }}
            
            QLineEdit::placeholder, QTextEdit::placeholder {{
                color: #808080;
            }}
            
            #createButton, #cancelButton {{
                background-color: {dialog["button"]["background"]};
                color: {dialog["button"]["color"]};
                border: 1px solid {dialog["button"]["border"]};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            
            #createButton:hover, #cancelButton:hover {{
                background-color: {dialog["button"]["hover"]};
            }}
            
            #createButton:pressed, #cancelButton:pressed {{
                background-color: {dialog["button"]["pressed"]};
            }}
            
            #createButton {{
                background-color: {dialog["primary_button"]["background"]};
            }}
            
            #createButton:hover {{
                background-color: {dialog["primary_button"]["hover"]};
            }}
            
            #createButton:pressed {{
                background-color: {dialog["primary_button"]["pressed"]};
            }}
        """ 