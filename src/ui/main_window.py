from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QLabel, QLineEdit, QTextEdit,
                            QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPalette, QColor, QFontMetrics
import os
import re

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
        
        # Left panel for tracker management
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_panel.setMaximumWidth(250)  # Limit the width of the left panel
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        
        # Tracker list
        self.tracker_list = QListWidget()
        self.tracker_list.setObjectName("trackerList")
        self.tracker_list.currentItemChanged.connect(self.on_tracker_selected)
        self.tracker_list.itemDoubleClicked.connect(self.edit_tracker)
        
        # Buttons for tracker management
        create_btn = QPushButton("Create New Tracker")
        create_btn.setObjectName("createButton")
        create_btn.clicked.connect(self.create_tracker)
        
        left_layout.addWidget(QLabel("Trackers"))
        left_layout.addWidget(self.tracker_list)
        left_layout.addWidget(create_btn)
        
        # Right panel for log viewing
        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(8)
        
        # Log files section
        files_label = QLabel("Log Files:")
        files_label.setObjectName("sectionHeader")
        right_layout.addWidget(files_label)
        
        self.files_list = QListWidget()
        self.files_list.setObjectName("filesList")
        self.files_list.setMaximumHeight(150)
        self.files_list.itemSelectionChanged.connect(self.on_log_file_selected)
        right_layout.addWidget(self.files_list)
        
        # Search bar
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText("Search in logs...")
        self.search_edit.returnPressed.connect(self.search_logs)
        search_btn = QPushButton("Search")
        search_btn.setObjectName("searchButton")
        search_btn.clicked.connect(self.search_logs)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(search_btn)
        
        # Add line numbers checkbox
        self.show_line_numbers = QCheckBox("Show line numbers")
        self.show_line_numbers.setObjectName("showLineNumbers")
        self.show_line_numbers.setChecked(True)  # Default to showing line numbers
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
            return
        
        log_files = self.current_tracker.get_log_files()
        logger.debug(f"Found {len(log_files)} log files")
        
        for log_file in log_files:
            logger.debug(f"Adding log file to list: {log_file['path']}")
            item = QListWidgetItem(os.path.basename(log_file["path"]))
            item.setData(Qt.ItemDataRole.UserRole, log_file["path"])
            self.files_list.addItem(item)
        
        logger.debug(f"File list now contains {self.files_list.count()} items")
    
    def on_log_file_selected(self):
        """Handle log file selection"""
        self.log_viewer.clear()
        selected_items = self.files_list.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.log_viewer.append(f'<span style="color: #569cd6;">=== {os.path.basename(file_path)} ===</span>\n')
                    self.log_viewer.append(content)
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
                    # Strip ANSI color codes and format the line
                    clean_line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line).strip()
                    if self.show_line_numbers.isChecked():
                        matches.append(f"{i}: {clean_line}")
                    else:
                        matches.append(clean_line)
            
            if matches:
                # Show results in the log viewer
                self.log_viewer.clear()
                self.log_viewer.append(f"File: {os.path.basename(log_file_path)} Found {len(matches)} matches\n")
                self.log_viewer.append("\n".join(matches))
            else:
                self.log_viewer.clear()
                self.log_viewer.append(f"No matches found for '{search_text}'")
                
        except Exception as e:
            self.log_viewer.clear()
            self.log_viewer.append(f"Error reading log file: {str(e)}")
    
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