from datetime import datetime
import os

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QLabel, QLineEdit, QTextEdit,
                            QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QCheckBox, QFrame, QMenu)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPalette, QColor, QFontMetrics

from ..internal.tracker import Tracker
from ..utils.config_manager import ConfigManager
from ..utils.theme_manager import ThemeManager
from ..utils.logging_setup import get_logger
from ..utils.file_handler import FileHandler
from ..utils.utils import Utils
from .tracker_dialog import TrackerDialog

logger = get_logger('ui.main_window')

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        try:
            self.config_manager = ConfigManager()
        except Exception as e:
            logger.error(f"MainWindow.__init__: Failed to create ConfigManager: {str(e)}")
            raise
        
        self.current_tracker = None
        
        try:
            self.file_handler = FileHandler()
        except Exception as e:
            logger.error(f"MainWindow.__init__: Failed to create FileHandler: {str(e)}")
            raise
        
        self.setWindowTitle("Protokoll")
        
        try:
            self.setup_ui()
        except Exception as e:
            logger.error(f"MainWindow.__init__: Failed to setup UI: {str(e)}")
            raise
        
        try:
            self.load_window_state()
        except Exception as e:
            logger.error(f"MainWindow.__init__: Failed to load window state: {str(e)}")
            # Don't raise here, this is not critical
        
        try:
            self.load_trackers()
        except Exception as e:
            logger.error(f"MainWindow.__init__: Failed to load trackers: {str(e)}")
            # Don't raise here, this is not critical
        
    
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
        
        # Add Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("clearButton")
        clear_btn.clicked.connect(self.clear_search_and_reload)
        
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(search_btn)
        search_layout.addWidget(clear_btn)
        search_layout.addWidget(self.show_line_numbers)
        
        # Open in Editor button with context menu
        open_editor_btn = QPushButton("Open in Editor")
        open_editor_btn.setObjectName("openEditorButton")
        open_editor_btn.clicked.connect(self.open_in_editor)
        
        # Create context menu for editor options
        editor_menu = QMenu(open_editor_btn)
        default_action = editor_menu.addAction("Use Default Editor")
        default_action.triggered.connect(self.open_in_default_editor)
        
        custom_action = editor_menu.addAction("Configure Custom Editor...")
        custom_action.triggered.connect(self.configure_custom_editor)
        
        # Show current custom editor if configured
        custom_editor = self.config_manager.get('custom_editor_command')
        if custom_editor:
            editor_menu.addSeparator()
            current_action = editor_menu.addAction(f"Current: {custom_editor}")
            current_action.setEnabled(False)
            clear_action = editor_menu.addAction("Clear Custom Editor")
            clear_action.triggered.connect(self.clear_custom_editor)
        
        open_editor_btn.setMenu(editor_menu)
        search_layout.addWidget(open_editor_btn)
        
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
        
        # Enable rich text (HTML) support
        self.log_viewer.setAcceptRichText(True)
    
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
            # Create display text with file info
            filename = os.path.basename(log_file["path"])
            size_info = log_file.get("size_human", "")
            compressed_indicator = "📦 " if log_file.get("is_compressed", False) else ""
            warning_indicator = "⚠️ " if log_file.get("warnings") else ""
            
            display_text = f"{compressed_indicator}{warning_indicator}{filename}"
            if size_info:
                display_text += f" ({size_info})"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, log_file["path"])
            
            # Add tooltip with detailed information
            tooltip_parts = [f"Path: {log_file['path']}", f"Size: {size_info}"]
            if log_file.get("warnings"):
                tooltip_parts.append("Warnings:")
                tooltip_parts.extend([f"  • {w}" for w in log_file["warnings"]])
            
            item.setToolTip("\n".join(tooltip_parts))
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
            self.append_styled_content("No log files found in the tracked directories.", color=ThemeManager.DARK_THEME["log_viewer"]["warning"])
            self.append_styled_content("Add directories containing log files to this tracker.", color=ThemeManager.DARK_THEME["log_viewer"]["success"])
        
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

    def append_styled_content(self, text, color=None, bold=False, background_color=None):
        """Append content to the log viewer with optional styling"""
        style_parts = []
        if color:
            style_parts.append(f"color: {color}")
        if background_color:
            style_parts.append(f"background-color: {background_color}")
        if bold:
            style_parts.append("font-weight: bold")
        
        if style_parts:
            style = "; ".join(style_parts)
            self.log_viewer.append(f'<span style="{style}">{text}</span>')
        else:
            self.log_viewer.append(text)

    def _load_single_long_line(self, content):
        """Handle a single very long line (e.g., minified JSON) by truncating"""
        max_length = 10000  # Show first 10KB
        
        if len(content) > max_length:
            # Truncate and show warning
            truncated_content = content[:max_length]
            self.append_styled_content("⚠️  File contains a very long line. Showing first 10KB:", color=ThemeManager.DARK_THEME["log_viewer"]["warning"])
            self.log_viewer.append("\n")
            
            # Convert the truncated content
            formatted_content = ThemeManager.convert_ansi_to_html(truncated_content)
            self.log_viewer.append(formatted_content)
            
            # Show truncation indicator
            self.append_styled_content(f"\n... (truncated, original length: {len(content):,} characters)", color=ThemeManager.DARK_THEME["log_viewer"]["warning"])
        else:
            # Convert the full content
            formatted_content = ThemeManager.convert_ansi_to_html(content)
            self.log_viewer.append(formatted_content)

    def _load_large_file_chunked(self, content):
        """Handle a large multi-line file by loading in chunks"""
        lines = content.split('\n')
        chunk_size = 500  # Process 500 lines at a time
        total_chunks = (len(lines) + chunk_size - 1) // chunk_size
        
        # Show progress indicator
        self.append_styled_content(f"Loading large log file (0/{total_chunks} chunks)...", color=ThemeManager.DARK_THEME["log_viewer"]["info"])
        QApplication.processEvents()
        
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i+chunk_size]
            chunk_content = '\n'.join(chunk_lines)
            
            # Convert this chunk
            formatted_chunk = ThemeManager.convert_ansi_to_html(chunk_content)
            self.log_viewer.append(formatted_chunk)
            
            # Update progress indicator every 5 chunks
            current_chunk = (i // chunk_size) + 1
            if current_chunk % 5 == 0 or current_chunk == total_chunks:
                # Remove old progress indicator
                cursor = self.log_viewer.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                cursor.deletePreviousChar()  # Remove the newline
                
                # Add updated progress indicator
                self.append_styled_content(f"Loading large log file ({current_chunk}/{total_chunks} chunks)...", color=ThemeManager.DARK_THEME["log_viewer"]["info"])
            
            # Process events every few chunks to keep UI responsive
            if i % (chunk_size * 2) == 0:
                QApplication.processEvents()
        
        # Remove final progress indicator
        cursor = self.log_viewer.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()  # Remove the newline

    def display_log_file(self, file_path):
        """Display the selected log file"""
        self.log_viewer.clear()
        
        # Validate file before attempting to read
        is_valid, reason, file_info = self.file_handler.validate_file_for_viewing(file_path)
        
        if not is_valid:
            self.append_styled_content(f"⚠️  Cannot display file: {reason}", color=ThemeManager.DARK_THEME["log_viewer"]["error"])
            if "warnings" in file_info and file_info["warnings"]:
                for warning in file_info["warnings"]:
                    self.append_styled_content(f"  • {warning}", color=ThemeManager.DARK_THEME["log_viewer"]["warning"])
            self.log_viewer.append("\n")
            return
        
        # Show file information header
        self.append_styled_content(f"=== {os.path.basename(file_path)} ===", color=ThemeManager.DARK_THEME["log_viewer"]["info"])
        self.append_styled_content(f"Size: {file_info['size_human']} | Lines: {file_info.get('total_lines', 'Unknown')}", color=ThemeManager.DARK_THEME["log_viewer"]["info"])
        
        if file_info.get("is_compressed", False):
            self.append_styled_content("📦 Compressed file detected", color=ThemeManager.DARK_THEME["log_viewer"]["info"])
        
        if file_info.get("warnings"):
            for warning in file_info["warnings"]:
                self.append_styled_content(f"⚠️  {warning}", color=ThemeManager.DARK_THEME["log_viewer"]["warning"])
        
        self.log_viewer.append("\n")
        
        # Read file content safely
        success, content, read_info = self.file_handler.read_file_safe(file_path)
        
        if not success:
            self.append_styled_content(f"❌ Error reading file: {read_info.get('error', 'Unknown error')}", color=ThemeManager.DARK_THEME["log_viewer"]["error"])
            self.log_viewer.append("\n")
            return
        
        # Determine how to handle the content based on its characteristics
        content_length = len(content)
        line_count = content.count('\n') + 1
        
        if content_length > 1000000:  # Very large file (>1MB)
            # Case 1: Multi-lined sections, very long file - use chunks
            if line_count > 100:  # Multiple lines
                self._load_large_file_chunked(content)
            else:
                # Case 2: One very long line (minified JSON, etc.) - truncate
                self._load_single_long_line(content)
        else:
            # Case 3: Single append for reasonable length files
            formatted_content = ThemeManager.convert_ansi_to_html(content)
            self.log_viewer.append(formatted_content)
        
        self.log_viewer.append("\n")
    
    def clear_search_and_reload(self):
        """Clear the search bar and reload the current log file if one is selected."""
        logger.debug("Clearing search bar and reloading current log file")
        self.search_edit.clear()
        selected_items = self.files_list.selectedItems()
        if selected_items:
            log_file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.display_log_file(log_file_path)

    def search_logs(self):
        """Search through the current log file"""
        if not self.current_tracker:
            return
        
        search_text = self.search_edit.text().strip()
        # If search is empty, reload the full log file
        if not search_text:
            selected_items = self.files_list.selectedItems()
            if selected_items:
                log_file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
                self.display_log_file(log_file_path)
            return
        
        # Get the currently selected log file
        selected_items = self.files_list.selectedItems()
        if not selected_items:
            return
        
        log_file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        
        # Validate file before searching
        is_valid, reason, file_info = self.file_handler.validate_file_for_viewing(log_file_path)
        
        if not is_valid:
            self.log_viewer.clear()
            self.append_styled_content(f"⚠️  Cannot search file: {reason}", color=ThemeManager.DARK_THEME["log_viewer"]["error"])
            return
        
        # Read file content safely
        success, content, read_info = self.file_handler.read_file_safe(log_file_path)
        
        if not success:
            self.log_viewer.clear()
            self.append_styled_content(f"❌ Error reading file: {read_info.get('error', 'Unknown error')}", color=ThemeManager.DARK_THEME["log_viewer"]["error"])
            return
        
        # Search through the content
        lines = content.split('\n')
        matches = []
        
        for i, line in enumerate(lines, 1):
            if search_text.lower() in line.lower():
                # Convert ANSI color codes to HTML formatting
                formatted_line = ThemeManager.convert_ansi_to_html(line.rstrip('\n'))
                if self.show_line_numbers.isChecked():
                    line_number = f"{i}: "
                    matches.append(f"{line_number}{formatted_line}")
                else:
                    matches.append(formatted_line)
        
        if matches:
            # Show results in the log viewer
            self.log_viewer.clear()
            self.append_styled_content(f"File: {os.path.basename(log_file_path)} Found {len(matches)} matches", color=ThemeManager.DARK_THEME["log_viewer"]["info"])
            self.log_viewer.append("\n")
            
            # Process matches to add line number styling
            for match in matches:
                if self.show_line_numbers.isChecked() and ": " in match:
                    # Split line number from content
                    parts = match.split(": ", 1)
                    if len(parts) == 2:
                        line_num, content = parts
                        self.append_styled_content(f"{line_num}: ", color=ThemeManager.DARK_THEME["log_viewer"]["info"])
                        self.log_viewer.append(content)
                    else:
                        self.log_viewer.append(match)
                else:
                    self.log_viewer.append(match)
        else:
            self.log_viewer.clear()
            self.append_styled_content(f"No matches found for '{search_text}'", color=ThemeManager.DARK_THEME["log_viewer"]["error"])
    
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
    
    def open_in_editor(self):
        """Open the currently selected log file in the system's default text editor or custom editor"""
        selected_items = self.files_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No File Selected", "Please select a log file to open in the editor.")
            return
        
        log_file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        
        # Get custom editor command from config if available
        custom_editor = self.config_manager.get('custom_editor_command')
        
        Utils.open_file_with_editor(log_file_path, custom_editor, self.handle_error)

    def open_in_default_editor(self):
        """Open the currently selected log file in the system's default text editor"""
        selected_items = self.files_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No File Selected", "Please select a log file to open in the editor.")
            return
        
        log_file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        
        Utils.open_file_with_editor(log_file_path, None, self.handle_error)  # Use default editor

    def configure_custom_editor(self):
        """Show dialog to configure custom editor command"""
        current_command = self.config_manager.get('custom_editor_command', '')
        
        command, ok = QLineEdit.getText(
            self, 
            "Configure Custom Editor", 
            "Enter custom editor command (use {filepath} as placeholder for file path):\n\n"
            "Examples:\n"
            "• notepad.exe {filepath}\n"
            "• code {filepath}\n"
            "• gedit {filepath}\n"
            "• vim {filepath}",
            text=current_command
        )
        
        if ok and command.strip():
            # Validate the command contains the placeholder
            if "{filepath}" not in command:
                QMessageBox.warning(self, "Invalid Command", 
                                  "The command must contain {filepath} as a placeholder for the file path.")
                return
            
            # Test if the executable exists
            cmd_parts = command.split()
            executable = cmd_parts[0]
            if not Utils.executable_available(executable):
                reply = QMessageBox.question(self, "Executable Not Found", 
                                           f"The executable '{executable}' was not found in your system PATH.\n"
                                           f"Do you want to save this command anyway?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return
            
            self.config_manager.set('custom_editor_command', command.strip())
            QMessageBox.information(self, "Success", f"Custom editor command saved: {command.strip()}")
        elif ok and not command.strip():
            # User cleared the command
            self.config_manager.set('custom_editor_command', '')
            QMessageBox.information(self, "Success", "Custom editor command cleared. Will use default editor.")

    def clear_custom_editor(self):
        """Clear the custom editor command"""
        reply = QMessageBox.question(self, "Clear Custom Editor", 
                                   "Are you sure you want to clear the custom editor command?\n"
                                   "This will revert to using the system default editor.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.set('custom_editor_command', '')
            QMessageBox.information(self, "Success", "Custom editor command cleared.")

    def closeEvent(self, event):
        """Handle window close event"""
        self.save_window_state()
        super().closeEvent(event) 

    def handle_error(self, error_message: str):
        QMessageBox.warning(self, "Error", error_message)
