from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QLabel, QLineEdit, QTextEdit,
                            QListWidget, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPalette, QColor
import os

from ..internal.tracker import Tracker
from ..utils.config_manager import ConfigManager
from ..utils.theme_manager import ThemeManager
from .tracker_dialog import TrackerDialog

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
        
        # Search bar
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText("Search in logs...")
        search_btn = QPushButton("Search")
        search_btn.setObjectName("searchButton")
        search_btn.clicked.connect(self.search_logs)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(search_btn)
        
        # Log viewer
        self.log_viewer = QTextEdit()
        self.log_viewer.setObjectName("logViewer")
        self.log_viewer.setReadOnly(True)
        self.setup_log_viewer()
        
        # Add log file button
        add_log_btn = QPushButton("Add Log File")
        add_log_btn.setObjectName("addLogButton")
        add_log_btn.clicked.connect(self.add_log_file)
        
        right_layout.addLayout(search_layout)
        right_layout.addWidget(self.log_viewer)
        right_layout.addWidget(add_log_btn)
        
        # Add panels to main layout
        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)
        
        # Apply custom styles
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            
            QLabel {
                color: #d4d4d4;
                font-size: 12px;
            }
            
            QPushButton {
                background-color: #3c3c3c;
                color: #d4d4d4;
                border: 1px solid #4c4c4c;
                border-radius: 4px;
                padding: 6px 12px;
                min-height: 24px;
            }
            
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            
            QPushButton:pressed {
                background-color: #2c2c2c;
            }
            
            QLineEdit {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 24px;
            }
            
            QListWidget {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px;
            }
            
            QListWidget::item {
                padding: 4px 8px;
                border-radius: 2px;
            }
            
            QListWidget::item:selected {
                background-color: #264f78;
            }
            
            QListWidget::item:hover {
                background-color: #2d2d2d;
            }
            
            #leftPanel, #rightPanel {
                background-color: #1e1e1e;
                border-radius: 6px;
                padding: 8px;
            }
        """)
    
    def setup_log_viewer(self):
        """Set up the log viewer with configured font and settings"""
        font = QFont(
            self.config_manager.get('log_viewer.font_family', 'Consolas'),
            self.config_manager.get('log_viewer.font_size', 12)
        )
        self.log_viewer.setFont(font)
        self.log_viewer.setLineWrapMode(
            QTextEdit.LineWrapMode.WidgetWidth if 
            self.config_manager.get('log_viewer.line_wrap', True)
            else QTextEdit.LineWrapMode.NoWrap
        )
        self.log_viewer.setStyleSheet(ThemeManager.get_log_viewer_style())
    
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
            self.log_viewer.clear()
            return
        
        tracker_name = current.text()
        self.current_tracker = Tracker.load(tracker_name, self.config_manager)
        self.config_manager.set('last_tracker', tracker_name)
        self.update_log_viewer()
    
    def update_log_viewer(self):
        """Update the log viewer with current tracker's logs"""
        self.log_viewer.clear()
        if not self.current_tracker:
            return
        
        for log_file in self.current_tracker.get_log_files():
            try:
                with open(log_file["path"], "r", encoding="utf-8") as f:
                    content = f.read()
                    self.log_viewer.append(f'<span style="color: #569cd6;">=== {os.path.basename(log_file["path"])} ===</span>\n')
                    self.log_viewer.append(content)
                    self.log_viewer.append("\n")
            except Exception as e:
                self.log_viewer.append(f'<span style="color: #f14c4c;">Error reading {log_file["path"]}: {str(e)}</span>\n')
    
    def add_log_file(self):
        """Add a log file to the current tracker"""
        if not self.current_tracker:
            QMessageBox.warning(self, "Error", "Please select a tracker first")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Log File",
            "",
            "Log Files (*.log *.txt);;All Files (*.*)"
        )
        
        if file_path:
            if self.current_tracker.add_log_file(file_path):
                self.update_log_viewer()
            else:
                QMessageBox.warning(self, "Error", "Failed to add log file")
    
    def search_logs(self):
        """Search through the current tracker's logs"""
        if not self.current_tracker:
            QMessageBox.warning(self, "Error", "Please select a tracker first")
            return
        
        query = self.search_edit.text().strip()
        if not query:
            self.update_log_viewer()
            return
        
        results = self.current_tracker.search_logs(query)
        self.log_viewer.clear()
        
        if not results:
            self.log_viewer.append('<span style="color: #cca700;">No matches found</span>')
            return
        
        for result in results:
            self.log_viewer.append(
                f'<span style="color: #569cd6;">File: {os.path.basename(result["file"])}</span>\n'
                f'<span style="color: #6a9955;">Line: {result["line"]}</span>\n'
                f'<span style="color: #d4d4d4;">Content: {result["content"]}</span>\n'
                f'<span style="color: #3c3c3c;">{"-" * 50}</span>\n'
            )
    
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
                
                # Remove directories that are no longer tracked
                for directory in current_dirs - new_dirs:
                    tracker.remove_log_directory(directory)
                
                # Add new directories
                for directory in new_dirs - current_dirs:
                    tracker.add_log_directory(directory)
                
                # Save changes
                tracker.save_metadata()
                
                # Update UI
                self.load_trackers()
                
                # Select the updated tracker
                items = self.tracker_list.findItems(data["name"], Qt.MatchFlag.MatchExactly)
                if items:
                    self.tracker_list.setCurrentItem(items[0])
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update tracker: {str(e)}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.save_window_state()
        super().closeEvent(event) 