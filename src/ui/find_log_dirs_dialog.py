from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QListWidget, QListWidgetItem,
                            QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ..internal.log_directory_finder import LogDirectoryFinder
from ..utils.theme_manager import ThemeManager
from ..utils.logging_manager import LoggingManager

logger = LoggingManager.get_logger('ui.find_log_dirs_dialog')

class DirectorySearchThread(QThread):
    """Thread for searching directories to keep UI responsive."""
    search_complete = pyqtSignal(dict)
    search_error = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    
    def __init__(self, app_name: str):
        super().__init__()
        self.app_name = app_name
        self.logger = LoggingManager.get_logger('ui.find_log_dirs_dialog.search_thread')
    
    def run(self):
        """Run the directory search."""
        try:
            self.logger.info(f"Starting directory search for: {self.app_name}")
            
            # Validate search query
            is_valid, reason = LogDirectoryFinder.validate_search_query(self.app_name)
            if not is_valid:
                self.logger.warning(f"Invalid search query: {reason}")
                self.search_error.emit(reason)
                return
            
            results = LogDirectoryFinder.find_log_directories(self.app_name)
            self.logger.info("Directory search completed")
            self.search_complete.emit(results)
        except Exception as e:
            self.logger.error(f"Error in directory search: {str(e)}", exc_info=True)
            self.search_error.emit(str(e))

class FindLogDirsDialog(QDialog):
    def __init__(self, app_name: str, parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self.selected_directories = []
        self.search_thread = None
        
        logger.info(f"Initializing FindLogDirsDialog for app: {app_name}")
        
        self.setWindowTitle(f"Find Log Directories for {app_name}")
        self.setModal(True)
        self.setMinimumSize(600, 400)
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Add header
        header_label = QLabel(f"Searching for log directories...")
        header_label.setObjectName("dialogHeader")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        main_layout.addWidget(self.progress_bar)
        
        # Results sections
        # Exact matches
        exact_label = QLabel("Exact Matches:")
        exact_label.setObjectName("sectionHeader")
        main_layout.addWidget(exact_label)
        
        self.exact_list = QListWidget()
        self.exact_list.setObjectName("exactList")
        self.exact_list.setMinimumHeight(100)
        main_layout.addWidget(self.exact_list)
        
        # Potential matches
        potential_label = QLabel("Potential Matches:")
        potential_label.setObjectName("sectionHeader")
        main_layout.addWidget(potential_label)
        
        self.potential_list = QListWidget()
        self.potential_list.setObjectName("potentialList")
        self.potential_list.setMinimumHeight(100)
        main_layout.addWidget(self.potential_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        select_btn = QPushButton("Add Selected")
        select_btn.setObjectName("selectButton")
        select_btn.setMinimumSize(100, 30)
        select_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setMinimumSize(100, 30)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(select_btn)
        
        main_layout.addLayout(button_layout)
        
        # Apply theme
        self.setStyleSheet(ThemeManager.get_dialog_style())
        
        # Start search
        logger.debug("Starting directory search thread")
        self.search_thread = DirectorySearchThread(app_name)
        self.search_thread.search_complete.connect(self.on_search_complete)
        self.search_thread.search_error.connect(self.on_search_error)
        self.search_thread.start()
    
    def on_search_error(self, error_message: str):
        """Handle search errors."""
        logger.error(f"Search error: {error_message}")
        self.progress_bar.hide()
        
        # Update header
        header = self.findChild(QLabel, "dialogHeader")
        if header:
            header.setText("Search Error")
        
        # Show error message
        QMessageBox.warning(
            self,
            "Search Error",
            error_message
        )
        
        # Close dialog
        self.reject()
    
    def on_search_complete(self, results: dict):
        """Handle search completion."""
        logger.info("Search completed, updating UI")
        self.progress_bar.hide()
        
        # Update header
        header = self.findChild(QLabel, "dialogHeader")
        if header:
            header.setText(f"Found {len(results['exact_matches'])} exact matches and {len(results['potential_matches'])} potential matches")
        
        # Populate lists
        for path in results['exact_matches']:
            item = QListWidgetItem(path)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.exact_list.addItem(item)
            logger.debug(f"Added exact match: {path}")
        
        for path in results['potential_matches']:
            item = QListWidgetItem(path)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.potential_list.addItem(item)
            logger.debug(f"Added potential match: {path}")
    
    def get_selected_directories(self) -> list:
        """Get the selected directories."""
        selected = []
        
        # Get checked items from both lists
        for i in range(self.exact_list.count()):
            item = self.exact_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
                logger.debug(f"Selected exact match: {item.text()}")
        
        for i in range(self.potential_list.count()):
            item = self.potential_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
                logger.debug(f"Selected potential match: {item.text()}")
        
        logger.info(f"Total selected directories: {len(selected)}")
        return selected

    def closeEvent(self, event):
        """Handle dialog close event."""
        logger.debug("Dialog closing, cleaning up search thread")
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
        super().closeEvent(event)
    
    def reject(self):
        """Handle dialog rejection (Cancel button)."""
        logger.debug("Dialog rejected, cleaning up search thread")
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
        super().reject()
    
    def accept(self):
        """Handle dialog acceptance (Add Selected button)."""
        logger.debug("Dialog accepted, cleaning up search thread")
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
        super().accept() 