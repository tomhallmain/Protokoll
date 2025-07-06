import re

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


    @staticmethod
    def convert_ansi_to_html(text):
        """Convert ANSI color codes to HTML formatting"""
        # ANSI color code patterns
        # Reset: \x1b[0m
        # Color codes: \x1b[38;2;r;g;bm (24-bit) or \x1b[38;5;nm (8-bit) or \x1b[38;nm (standard)
        # Background codes: \x1b[48;2;r;g;bm (24-bit) or \x1b[48;5;nm (8-bit) or \x1b[48;nm (standard)
        
        # Use centralized color constants from theme manager
        ansi_colors = ThemeManager.ANSI_COLORS
        ansi_bg_colors = ThemeManager.ANSI_BG_COLORS
        
        # Check if we have ANSI codes
        ansi_pattern = r'\x1b\[[0-9;]*[a-zA-Z]'
        if not re.search(ansi_pattern, text):
            return text
        
        # Split text into lines to process each line separately
        lines = text.split('\n')
        processed_lines = []
        
        for line in lines:
            # Split the line into segments based on ANSI codes
            ansi_pattern = r'\x1b\[([0-9;]*)m'
            
            # Find all ANSI codes and their positions
            matches = list(re.finditer(ansi_pattern, line))
            if not matches:
                # No ANSI codes, just return the line as plain text
                processed_lines.append(line)
                continue
            

            
            # Track current styling
            current_fg = None
            current_bg = None
            current_bold = False
            
            # Build the HTML line by processing each segment
            html_parts = []
            last_end = 0
            
            for match in matches:
                # Add text before this ANSI code
                if match.start() > last_end:
                    text_segment = line[last_end:match.start()]
                    if text_segment:
                        # Apply current styling to this text segment
                        style_parts = []
                        if current_fg:
                            style_parts.append(f"color: {current_fg}")
                        if current_bg:
                            style_parts.append(f"background-color: {current_bg}")
                        if current_bold:
                            style_parts.append("font-weight: bold")
                        
                        if style_parts:
                            style = "; ".join(style_parts)
                            html_parts.append(f'<span style="{style}">{text_segment}</span>')
                        else:
                            html_parts.append(text_segment)
                
                # Process the ANSI code
                code_str = match.group(1)
                
                if not code_str:  # Reset code [0m
                    current_fg = None
                    current_bg = None
                    current_bold = False
                else:
                    # Parse the code string
                    code_parts = [int(x) if x else 0 for x in code_str.split(';')]
                    
                    i = 0
                    while i < len(code_parts):
                        code = code_parts[i]
                        
                        if code == 0:  # Reset
                            current_fg = None
                            current_bg = None
                            current_bold = False
                        elif code == 1:  # Bold
                            current_bold = True
                        elif code == 22:  # Normal intensity
                            current_bold = False
                        elif 30 <= code <= 37 or 90 <= code <= 97:  # Foreground colors
                            current_fg = ansi_colors.get(code, "#ffffff")
                            # Check if there's a modifier code (like ;20) following
                            if i + 1 < len(code_parts) and code_parts[i + 1] == 20:
                                # Apply a dimming effect for the ;20 modifier
                                if current_fg:
                                    # Make the color slightly dimmer
                                    current_fg = ThemeManager._dim_color(current_fg)
                                i += 1  # Skip the modifier code
                        elif 40 <= code <= 47 or 100 <= code <= 107:  # Background colors
                            current_bg = ansi_bg_colors.get(code, "#000000")
                        elif code == 38:  # Extended foreground color
                            # Check if next code is 5 (8-bit color) or 2 (24-bit color)
                            if i + 1 < len(code_parts):
                                next_code = code_parts[i + 1]
                                if next_code == 5 and i + 2 < len(code_parts):  # 8-bit color
                                    color_code = code_parts[i + 2]
                                    # Map 8-bit colors to our color palette
                                    if 0 <= color_code <= 15:  # Standard colors
                                        current_fg = ansi_colors.get(30 + (color_code % 8) + (90 if color_code >= 8 else 0), "#ffffff")
                                    i += 2  # Skip the next two codes
                                elif next_code == 2 and i + 4 < len(code_parts):  # 24-bit color
                                    # Extract RGB values
                                    r, g, b = code_parts[i + 2], code_parts[i + 3], code_parts[i + 4]
                                    current_fg = f"#{r:02x}{g:02x}{b:02x}"
                                    i += 4  # Skip the next four codes
                                else:  # Handle non-standard extended color format (like 38;20)
                                    # Treat the next code as a simple color index
                                    color_code = next_code
                                    # Map to a reasonable color based on the code
                                    if color_code == 20:
                                        current_fg = "#d4d4d4"  # Light gray for code 20 (matches the custom formatter's grey)
                                    elif 0 <= color_code <= 15:
                                        # Map to standard ANSI colors
                                        current_fg = ansi_colors.get(30 + (color_code % 8) + (90 if color_code >= 8 else 0), "#ffffff")
                                    else:
                                        # Default to white for unknown codes
                                        current_fg = "#ffffff"
                                    i += 1  # Skip the next code
                            else:
                                i += 1  # Skip the next code
                        elif code == 48:  # Extended background color
                            # Similar handling as foreground
                            if i + 1 < len(code_parts):
                                next_code = code_parts[i + 1]
                                if next_code == 5 and i + 2 < len(code_parts):  # 8-bit color
                                    color_code = code_parts[i + 2]
                                    if 0 <= color_code <= 15:  # Standard colors
                                        current_bg = ansi_bg_colors.get(40 + (color_code % 8) + (100 if color_code >= 8 else 0), "#000000")
                                    i += 2  # Skip the next two codes
                                elif next_code == 2 and i + 4 < len(code_parts):  # 24-bit color
                                    r, g, b = code_parts[i + 2], code_parts[i + 3], code_parts[i + 4]
                                    current_bg = f"#{r:02x}{g:02x}{b:02x}"
                                    i += 4  # Skip the next four codes
                                else:
                                    i += 1
                            else:
                                i += 1
                        elif code == 39:  # Default foreground
                            current_fg = None
                        elif code == 49:  # Default background
                            current_bg = None
                        else:
                            # Unknown code, log it for debugging
                            # logger.debug(f"Unknown ANSI code: {code}")
                            pass
                        
                        i += 1
                
                last_end = match.end()
            
            # Add any remaining text after the last ANSI code
            if last_end < len(line):
                text_segment = line[last_end:]
                if text_segment:
                    # Apply current styling to this text segment
                    style_parts = []
                    if current_fg:
                        style_parts.append(f"color: {current_fg}")
                    if current_bg:
                        style_parts.append(f"background-color: {current_bg}")
                    if current_bold:
                        style_parts.append("font-weight: bold")
                    
                    if style_parts:
                        style = "; ".join(style_parts)
                        html_parts.append(f'<span style="{style}">{text_segment}</span>')
                    else:
                        html_parts.append(text_segment)
            
            # Join all HTML parts (these are on the same line)
            html_line = ''.join(html_parts)
            processed_lines.append(html_line)
        
        return '<br>'.join(processed_lines)

    @staticmethod
    def _dim_color(color):
        """Dim a color by reducing its brightness"""
        if not color or not color.startswith('#'):
            return color
        
        try:
            # Parse the hex color
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            
            # Dim the color by reducing brightness (80%)
            r = int(r * 0.8)
            g = int(g * 0.8)
            b = int(b * 0.8)
            
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, IndexError):
            return color
