from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QLineEdit, QTextEdit, QListWidget,
                            QListWidgetItem, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt
import os

from ..utils.theme_manager import ThemeManager
from ..internal.tracker import Tracker
from .find_log_dirs_dialog import FindLogDirsDialog

class TrackerDialog(QDialog):
    def __init__(self, tracker: Tracker = None, parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.is_edit_mode = tracker is not None
        
        self.setWindowTitle("Edit Tracker" if self.is_edit_mode else "Create New Tracker")
        self.setModal(True)
        self.setMinimumSize(400, 300)
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Add header
        header_label = QLabel("Edit Tracker" if self.is_edit_mode else "Create New Tracker")
        header_label.setObjectName("dialogHeader")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header_label)
        
        # Form layout
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)
        
        # Name field
        name_layout = QHBoxLayout()
        name_label = QLabel("Name:")
        name_label.setMinimumWidth(100)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter tracker name")
        if self.is_edit_mode:
            self.name_input.setText(tracker.name)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        form_layout.addLayout(name_layout)
        
        # Description field
        desc_layout = QHBoxLayout()
        desc_label = QLabel("Description:")
        desc_label.setMinimumWidth(100)
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Enter tracker description")
        self.desc_input.setMaximumHeight(100)
        if self.is_edit_mode:
            self.desc_input.setText(tracker.description)
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(self.desc_input)
        form_layout.addLayout(desc_layout)
        
        # Log directories section
        dirs_label = QLabel("Log Directories:")
        dirs_label.setObjectName("sectionHeader")
        form_layout.addWidget(dirs_label)
        
        self.dirs_list = QListWidget()
        self.dirs_list.setMinimumHeight(100)
        if self.is_edit_mode:
            for directory in tracker.log_directories:
                self.dirs_list.addItem(directory)
        form_layout.addWidget(self.dirs_list)
        
        # Directory buttons
        dir_buttons_layout = QHBoxLayout()
        
        find_btn = QPushButton("Find Directories")
        find_btn.setObjectName("findButton")
        find_btn.clicked.connect(self.find_directories)
        
        add_btn = QPushButton("Add Directory")
        add_btn.setObjectName("addButton")
        add_btn.clicked.connect(self.add_directory)
        
        remove_btn = QPushButton("Remove Directory")
        remove_btn.setObjectName("removeButton")
        remove_btn.clicked.connect(self.remove_directory)
        
        dir_buttons_layout.addWidget(find_btn)
        dir_buttons_layout.addWidget(add_btn)
        dir_buttons_layout.addWidget(remove_btn)
        form_layout.addLayout(dir_buttons_layout)
        
        main_layout.addLayout(form_layout)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save Changes" if self.is_edit_mode else "Create Tracker")
        save_btn.setObjectName("saveButton")
        save_btn.setMinimumSize(100, 30)
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setMinimumSize(100, 30)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        main_layout.addLayout(button_layout)
        
        # Apply theme
        self.setStyleSheet(ThemeManager.get_dialog_style())
    
    def find_directories(self):
        """Open dialog to find log directories."""
        dialog = FindLogDirsDialog(self.name_input.text(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_dirs = dialog.get_selected_directories()
            for directory in selected_dirs:
                if directory not in [self.dirs_list.item(i).text() for i in range(self.dirs_list.count())]:
                    self.dirs_list.addItem(directory)
    
    def add_directory(self):
        """Add a new log directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Log Directory",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            # Check if directory already exists in list
            for i in range(self.dirs_list.count()):
                if self.dirs_list.item(i).text() == directory:
                    return
            
            self.dirs_list.addItem(directory)
    
    def remove_directory(self):
        """Remove selected log directory."""
        current_item = self.dirs_list.currentItem()
        if current_item:
            self.dirs_list.takeItem(self.dirs_list.row(current_item))
    
    def get_tracker_data(self) -> dict:
        """Get the tracker data from the dialog."""
        return {
            'name': self.name_input.text(),
            'description': self.desc_input.toPlainText(),
            'log_directories': [self.dirs_list.item(i).text() for i in range(self.dirs_list.count())]
        }
    
    def accept(self):
        """Validate and accept the dialog."""
        if not self.name_input.text():
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please enter a tracker name."
            )
            return
        
        # Validate that all directories exist
        for i in range(self.dirs_list.count()):
            directory = self.dirs_list.item(i).text()
            if not os.path.exists(directory):
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Directory does not exist: {directory}"
                )
                return
        
        super().accept() 