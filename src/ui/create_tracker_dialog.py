from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QTextEdit,
                            QPushButton, QHBoxLayout, QVBoxLayout, QLabel,
                            QSizePolicy, QFileDialog, QMessageBox, QListWidget,
                            QListWidgetItem)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont
import os

from ..utils.theme_manager import ThemeManager
from ..internal.tracker import Tracker

class CreateTrackerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Tracker")
        self.setModal(True)
        self.setMinimumSize(600, 500)
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Add header
        header_label = QLabel("Create a New Tracker")
        header_label.setObjectName("dialogHeader")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header_label)
        
        # Create form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Name field
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("nameEdit")
        self.name_edit.setPlaceholderText("Enter tracker name")
        self.name_edit.setMinimumHeight(30)
        form_layout.addRow("Name:", self.name_edit)
        
        # Description field
        self.description_edit = QTextEdit()
        self.description_edit.setObjectName("descriptionEdit")
        self.description_edit.setPlaceholderText("Enter tracker description (optional)")
        self.description_edit.setMinimumHeight(100)
        form_layout.addRow("Description:", self.description_edit)
        
        # Log directories section
        dir_label = QLabel("Log Directories:")
        dir_label.setObjectName("sectionHeader")
        main_layout.addWidget(dir_label)
        
        # Directory list
        self.dir_list = QListWidget()
        self.dir_list.setObjectName("dirList")
        self.dir_list.setMinimumHeight(150)
        main_layout.addWidget(self.dir_list)
        
        # Directory buttons
        dir_buttons = QHBoxLayout()
        
        add_dir_btn = QPushButton("Add Directory")
        add_dir_btn.setObjectName("addDirButton")
        add_dir_btn.clicked.connect(self.browse_directory)
        
        remove_dir_btn = QPushButton("Remove Directory")
        remove_dir_btn.setObjectName("removeDirButton")
        remove_dir_btn.clicked.connect(self.remove_directory)
        
        dir_buttons.addWidget(add_dir_btn)
        dir_buttons.addWidget(remove_dir_btn)
        main_layout.addLayout(dir_buttons)
        
        # Add some spacing
        main_layout.addSpacing(10)
        
        # Create button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Create buttons
        create_btn = QPushButton("Create")
        create_btn.setObjectName("createButton")
        create_btn.setMinimumSize(100, 30)
        create_btn.clicked.connect(self.validate_and_accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setMinimumSize(100, 30)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(create_btn)
        
        main_layout.addLayout(button_layout)
        
        # Apply theme
        self.setStyleSheet(ThemeManager.get_dialog_style())
    
    def browse_directory(self):
        """Open a directory selection dialog."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Log Directory",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        if directory and directory not in [self.dir_list.item(i).text() for i in range(self.dir_list.count())]:
            self.dir_list.addItem(directory)
    
    def remove_directory(self):
        """Remove the selected directory from the list."""
        current_item = self.dir_list.currentItem()
        if current_item:
            self.dir_list.takeItem(self.dir_list.row(current_item))
    
    def validate_and_accept(self):
        """Validate the input and accept the dialog if valid."""
        name = self.name_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Error", "Tracker name cannot be empty")
            return
        
        if self.dir_list.count() == 0:
            QMessageBox.warning(self, "Error", "Please add at least one log directory")
            return
        
        # Validate all directories exist
        for i in range(self.dir_list.count()):
            directory = self.dir_list.item(i).text()
            if not os.path.exists(directory):
                QMessageBox.warning(self, "Error", f"Directory does not exist: {directory}")
                return
            if not os.path.isdir(directory):
                QMessageBox.warning(self, "Error", f"Path is not a directory: {directory}")
                return
        
        self.accept()
    
    def get_tracker_data(self):
        """Get the entered tracker data"""
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "log_directories": [self.dir_list.item(i).text() for i in range(self.dir_list.count())]
        }
 