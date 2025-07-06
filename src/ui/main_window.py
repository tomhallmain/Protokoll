from datetime import datetime
import os
import re

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QLabel, QLineEdit, QTextEdit,
                            QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QCheckBox, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPalette, QColor, QFontMetrics

from ..internal.tracker import Tracker
from ..utils.config_manager import ConfigManager
from ..utils.theme_manager import ThemeManager
from ..utils.logging_manager import LoggingManager
from .tracker_dialog import TrackerDialog

logger = LoggingManager.get_logger('ui.main_window')

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.current_tracker = None
        
        self.setWindowTitle("Protokoll")
        self.setup_ui()
        self.load_window_state()
        self.load_trackers()
    
    def setup_ui(self):
        """Set up the user interface"""
        self.setMinimumSize(800, 600)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Left panel for tracker management and file list
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_panel.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        
        # Create New Tracker button at the top
        create_btn = QPushButton("Create New Tracker")
        create_btn.setObjectName("createButton")
        create_btn.clicked.connect(self.create_tracker)
        left_layout.addWidget(create_btn)
        
        # Tracker section
        tracker_label = QLabel("Trackers")
        tracker_label.setObjectName("sectionHeader")
        left_layout.addWidget(tracker_label)
        
        self.tracker_list = QListWidget()
        self.tracker_list.setObjectName("trackerList")
        self.tracker_list.currentItemChanged.connect(self.on_tracker_selected)
        self.tracker_list.itemDoubleClicked.connect(self.edit_tracker)
        left_layout.addWidget(self.tracker_list)
        
        # Add a separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        left_layout.addWidget(separator)
        
        # Log files section
        files_label = QLabel("Log Files")
        files_label.setObjectName("sectionHeader")
        left_layout.addWidget(files_label)
        
        self.files_list = QListWidget()
        self.files_list.setObjectName("filesList")
        self.files_list.itemSelectionChanged.connect(self.on_log_file_selected)
        left_layout.addWidget(self.files_list)
        
        # Right panel for log viewing
        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(8)
        
        # Search bar
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText("Search in logs...")
        self.search_edit.returnPressed.connect(self.search_logs)
        search_btn = QPushButton("Search")
        search_btn.setObjectName("searchButton")
        search_btn.clicked.connect(self.search_logs)
        self.show_line_numbers = QCheckBox("Show line numbers")
        self.show_line_numbers.setObjectName("showLineNumbers")
        self.show_line_numbers.setChecked(True)
        
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(search_btn)
        search_layout.addWidget(self.show_line_numbers)
        
        # Log viewer
        self.log_viewer = QTextEdit()
        self.log_viewer.setObjectName("logViewer")
        self.log_viewer.setReadOnly(True)
        self.setup_log_viewer()
        
        right_layout.addLayout(search_layout)
        right_layout.addWidget(self.log_viewer)
        
        # Add panels to main layout with adjusted proportions
        layout.addWidget(left_panel, 1)  # Left panel gets 1 part
        layout.addWidget(right_panel, 3)  # Right panel gets 3 parts
        
        # Apply custom styles
        self.setStyleSheet(ThemeManager.get_dialog_style())
    
    def setup_log_viewer(self):
        """Set up the log viewer with monospace font and line numbers"""
        # Use a smaller monospace font
        font = QFont("Consolas", 9)  # Reduced from 10 to 9
        self.log_viewer.setFont(font)
        
        # Set tab width to 4 spaces
        metrics = QFontMetrics(font)
        tab_width = metrics.horizontalAdvance("    ")  # 4 spaces
        self.log_viewer.setTabStopDistance(tab_width)
        
        # Enable line wrapping
        self.log_viewer.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        # Set background and text colors
        palette = self.log_viewer.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))  # Dark background
        palette.setColor(QPalette.ColorRole.Text, QColor("#d4d4d4"))  # Light text
        self.log_viewer.setPalette(palette)
    
    def load_window_state(self):
        """Load window state from configuration"""
        width = self.config_manager.get('window.width', 1024)
        height = self.config_manager.get('window.height', 768)
        x = self.config_manager.get('window.x')
        y = self.config_manager.get('window.y')
        
        self.resize(width, height)
        if x is not None and y is not None:
            self.move(x, y)
    
    def save_window_state(self):
        """Save window state to configuration"""
        self.config_manager.set('window.width', self.width())
        self.config_manager.set('window.height', self.height())
        self.config_manager.set('window.x', self.x())
        self.config_manager.set('window.y', self.y())
    
    def load_trackers(self):
        """Load and display all available trackers"""
        self.tracker_list.clear()
        for tracker in Tracker.list_trackers(self.config_manager):
            self.tracker_list.addItem(tracker.name)
        
        # Select last used tracker if available
        last_tracker = self.config_manager.get('last_tracker')
        if last_tracker:
            items = self.tracker_list.findItems(last_tracker, Qt.MatchFlag.MatchExactly)
            if items:
                self.tracker_list.setCurrentItem(items[0])
    
    def create_tracker(self):
        """Create a new tracker."""
        dialog = TrackerDialog(parent=self)
        if dialog.exec():
            data = dialog.get_tracker_data()
            try:
                # Create the tracker
                tracker = Tracker(
                    name=data["name"],
                    description=data["description"],
                    config_manager=self.config_manager
                )
                
                # Add all log directories
                for directory in data["log_directories"]:
                    tracker.add_log_directory(directory)
                
                # Save initial state
                tracker.save_metadata()
                
                self.config_manager.add_recent_tracker(data["name"])
                self.load_trackers()
                
                # Select the newly created tracker
                items = self.tracker_list.findItems(data["name"], Qt.MatchFlag.MatchExactly)
                if items:
                    self.tracker_list.setCurrentItem(items[0])
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create tracker: {str(e)}")
    
    def on_tracker_selected(self, current, previous):
        """Handle tracker selection"""
        if current is None:
            self.current_tracker = None
            self.files_list.clear()
            self.log_viewer.clear()
            return
        
        tracker_name = current.text()
        logger.debug(f"Loading tracker: {tracker_name}")
        self.current_tracker = Tracker.load(tracker_name, self.config_manager)
        if self.current_tracker:
            logger.debug(f"Tracker loaded with directories: {self.current_tracker.get_log_directories()}")
        self.config_manager.set('last_tracker', tracker_name)
        self.update_log_files_list()
    
    def update_log_files_list(self):
        """Update the list of log files for the current tracker"""
        self.files_list.clear()
        if not self.current_tracker:
            logger.debug("No current tracker, clearing file list")
            self.update_window_title()
            return
        
        log_files = self.current_tracker.get_log_files()
        logger.debug(f"Found {len(log_files)} log files")
        
        # Sort log files by last modified time, most recent first
        log_files.sort(key=lambda x: x["last_modified"], reverse=True)
        
        last_selected = self.config_manager.get(f"last_log_file_{self.current_tracker.name}")
        selected_row = None
        for idx, log_file in enumerate(log_files):
            logger.debug(f"Adding log file to list: {log_file['path']}")
            item = QListWidgetItem(os.path.basename(log_file["path"]))
            item.setData(Qt.ItemDataRole.UserRole, log_file["path"])
            self.files_list.addItem(item)
            if last_selected and log_file["path"] == last_selected:
                selected_row = idx
        
        logger.debug(f"File list now contains {self.files_list.count()} items")
        
        # If we have log files but no previously selected file, select the most recent one
        if selected_row is None and log_files:
            selected_row = 0
            # Save this as the last selected file
            self.config_manager.set(f"last_log_file_{self.current_tracker.name}", log_files[0]["path"])
        
        # Pre-select the appropriate log file
        if selected_row is not None:
            self.files_list.setCurrentRow(selected_row)
        else:
            # No log files found, show message in log viewer
            self.log_viewer.clear()
            self.log_viewer.append('<span style="color: #cca700;">No log files found in the tracked directories.</span>')
            self.log_viewer.append('<span style="color: #6a9955;">Add directories containing log files to this tracker.</span>')
        
        self.update_window_title()
    
    def update_window_title(self):
        """Update the window title to show current context"""
        title = "Protokoll"
        if self.current_tracker:
            title += f" - {self.current_tracker.name}"
            selected_items = self.files_list.selectedItems()
            if selected_items:
                log_file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
                log_file = os.path.basename(log_file_path)
                try:
                    last_modified = os.path.getmtime(log_file_path)
                    last_modified_str = datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M:%S')
                    title += f" - {log_file} (Last modified: {last_modified_str})"
                except Exception:
                    title += f" - {log_file}"
        self.setWindowTitle(title)
    
    def on_log_file_selected(self):
        """Handle log file selection"""
        selected_items = self.files_list.selectedItems()
        if not selected_items:
            return
        log_file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        # Save last selected log file for this tracker
        if self.current_tracker:
            tracker_key = f"last_log_file_{self.current_tracker.name}"
            self.config_manager.set(tracker_key, log_file_path)
        self.display_log_file(log_file_path)
        self.update_window_title()
    
    def convert_ansi_to_html(self, text):
        """Convert ANSI color codes to HTML formatting"""
        # ANSI color code patterns
        # Reset: \x1b[0m
        # Color codes: \x1b[38;2;r;g;bm (24-bit) or \x1b[38;5;nm (8-bit) or \x1b[38;nm (standard)
        # Background codes: \x1b[48;2;r;g;bm (24-bit) or \x1b[48;5;nm (8-bit) or \x1b[48;nm (standard)
        
        # Standard ANSI color codes mapping
        ansi_colors = {
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
        ansi_bg_colors = {
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
        
        # Split text into lines to process each line separately
        lines = text.split('\n')
        processed_lines = []
        
        for line in lines:
            # Track current styling
            current_fg = None
            current_bg = None
            current_bold = False
            
            # Process ANSI codes in the line
            # Pattern to match ANSI escape sequences
            ansi_pattern = r'\x1b\[([0-9;]*)m'
            
            # Find all ANSI codes in the line
            codes = re.findall(ansi_pattern, line)
            if not codes:
                # No ANSI codes, just return the line as plain text
                processed_lines.append(line)
                continue
            
            # Remove ANSI codes from the line to get clean text
            clean_line = re.sub(ansi_pattern, '', line)
            
            # Process the codes to determine styling
            html_line = ""
            for code_str in codes:
                if not code_str:  # Reset code [0m
                    current_fg = None
                    current_bg = None
                    current_bold = False
                    continue
                
                # Parse the code string
                code_parts = [int(x) if x else 0 for x in code_str.split(';')]
                
                for code in code_parts:
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
                    elif 40 <= code <= 47 or 100 <= code <= 107:  # Background colors
                        current_bg = ansi_bg_colors.get(code, "#000000")
                    elif code == 39:  # Default foreground
                        current_fg = None
                    elif code == 49:  # Default background
                        current_bg = None
            
            # Apply styling to the clean line
            style_parts = []
            if current_fg:
                style_parts.append(f"color: {current_fg}")
            if current_bg:
                style_parts.append(f"background-color: {current_bg}")
            if current_bold:
                style_parts.append("font-weight: bold")
            
            if style_parts:
                style = "; ".join(style_parts)
                html_line = f'<span style="{style}">{clean_line}</span>'
            else:
                html_line = clean_line
            
            processed_lines.append(html_line)
        
        return '\n'.join(processed_lines)

    def display_log_file(self, file_path):
        """Display the selected log file"""
        self.log_viewer.clear()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.log_viewer.append(f'<span style="color: #569cd6;">=== {os.path.basename(file_path)} ===</span>\n')
                
                # Convert ANSI color codes to HTML formatting
                formatted_content = self.convert_ansi_to_html(content)
                self.log_viewer.append(formatted_content)
                self.log_viewer.append("\n")
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            self.log_viewer.append(f'<span style="color: #f14c4c;">Error reading {file_path}: {str(e)}</span>\n')
    
    def search_logs(self):
        """Search through the current log file"""
        if not self.current_tracker:
            return
        
        search_text = self.search_edit.text().strip()
        if not search_text:
            return
        
        # Get the currently selected log file
        selected_items = self.files_list.selectedItems()
        if not selected_items:
            return
        
        log_file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if not os.path.exists(log_file_path):
            return
        
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            matches = []
            for i, line in enumerate(lines, 1):
                if search_text.lower() in line.lower():
                    # Convert ANSI color codes to HTML formatting
                    formatted_line = self.convert_ansi_to_html(line.rstrip('\n'))
                    if self.show_line_numbers.isChecked():
                        matches.append(f"<span style='color: #569cd6;'>{i}:</span> {formatted_line}")
                    else:
                        matches.append(formatted_line)
            
            if matches:
                # Show results in the log viewer
                self.log_viewer.clear()
                self.log_viewer.append(f"<span style='color: #569cd6;'>File: {os.path.basename(log_file_path)} Found {len(matches)} matches</span>\n")
                self.log_viewer.append("\n".join(matches))
            else:
                self.log_viewer.clear()
                self.log_viewer.append(f"<span style='color: #f14c4c;'>No matches found for '{search_text}'</span>")
                
        except Exception as e:
            self.log_viewer.clear()
            self.log_viewer.append(f"<span style='color: #f14c4c;'>Error reading log file: {str(e)}</span>")
    
    def edit_tracker(self, item):
        """Edit the selected tracker"""
        if not item:
            return
        
        tracker_name = item.text()
        tracker = Tracker.load(tracker_name, self.config_manager)
        if not tracker:
            QMessageBox.critical(self, "Error", f"Failed to load tracker: {tracker_name}")
            return
        
        dialog = TrackerDialog(tracker, self)
        if dialog.exec():
            data = dialog.get_tracker_data()
            try:
                # Update tracker properties
                tracker.name = data["name"]
                tracker.description = data["description"]
                
                # Update log directories
                current_dirs = set(tracker.get_log_directories())
                new_dirs = set(data["log_directories"])
                
                logger.debug(f"Directories to remove: {current_dirs - new_dirs}")
                logger.debug(f"Directories to add: {new_dirs - current_dirs}")
                
                # Remove directories that are no longer present
                for directory in current_dirs - new_dirs:
                    tracker.remove_log_directory(directory)
                
                # Add new directories
                for directory in new_dirs - current_dirs:
                    tracker.add_log_directory(directory)
                
                logger.debug(f"Final directories after update: {tracker.get_log_directories()}")
                
                # Save changes
                tracker.save_metadata()
                
                # Update UI
                self.load_trackers()
                
                # Select the updated tracker
                items = self.tracker_list.findItems(data["name"], Qt.MatchFlag.MatchExactly)
                if items:
                    self.tracker_list.setCurrentItem(items[0])
                    
            except Exception as e:
                logger.error(f"Error updating tracker: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to update tracker: {str(e)}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.save_window_state()
        super().closeEvent(event) 