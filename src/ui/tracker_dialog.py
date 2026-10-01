import os

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QLineEdit, QTextEdit, QListWidget,
                            QListWidgetItem, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt

from ..utils.globals import AppInfo
from ..utils.theme_manager import ThemeManager
from ..utils.logging_setup import get_logger
from ..utils.translations import _
from ..internal.tracker import Tracker
from .find_log_dirs_dialog import FindLogDirsDialog

logger = get_logger('ui.tracker_dialog')

#: exec() result asking the caller to delete the tracker being edited. QDialog
#: itself uses 0 for rejected and 1 for accepted; this is the third outcome
#: editing can end in. The dialog confirms the deletion with the user but does
#: not carry it out - the tracker list and the current selection belong to the
#: window that opened it.
#:
#: A module constant rather than a class attribute so that a caller reads it
#: from here, not through its own reference to TrackerDialog, which tests
#: replace with a stand-in.
DELETE_REQUESTED = 2


class TrackerDialog(QDialog):
    def __init__(self, tracker: Tracker = None, parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.is_edit_mode = tracker is not None
        
        self.setWindowTitle(_("Edit Tracker") if self.is_edit_mode else _("Create New Tracker"))
        self.setModal(True)
        self.setMinimumSize(400, 300)
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Add header
        header_label = QLabel(_("Edit Tracker") if self.is_edit_mode else _("Create New Tracker"))
        header_label.setObjectName("dialogHeader")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header_label)
        
        # Form layout
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)
        
        # Name field
        name_layout = QHBoxLayout()
        name_label = QLabel(_("Name:"))
        name_label.setMinimumWidth(100)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(_("Enter tracker name"))
        if self.is_edit_mode:
            self.name_input.setText(tracker.name)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        form_layout.addLayout(name_layout)
        
        # Description field
        desc_layout = QHBoxLayout()
        desc_label = QLabel(_("Description:"))
        desc_label.setMinimumWidth(100)
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText(_("Enter tracker description"))
        self.desc_input.setMaximumHeight(100)
        if self.is_edit_mode:
            self.desc_input.setText(tracker.description)
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(self.desc_input)
        form_layout.addLayout(desc_layout)
        
        # Log directories section
        dirs_label = QLabel(_("Log Directories:"))
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
        
        find_btn = QPushButton(_("Find Directories"))
        find_btn.setObjectName("findButton")
        find_btn.clicked.connect(self.find_directories)
        
        add_btn = QPushButton(_("Add Directory"))
        add_btn.setObjectName("addButton")
        add_btn.clicked.connect(self.add_directory)
        
        remove_btn = QPushButton(_("Remove Directory"))
        remove_btn.setObjectName("removeButton")
        remove_btn.clicked.connect(self.remove_directory)
        
        dir_buttons_layout.addWidget(find_btn)
        dir_buttons_layout.addWidget(add_btn)
        dir_buttons_layout.addWidget(remove_btn)
        form_layout.addLayout(dir_buttons_layout)

        # Encrypted logs (.enc): optional, since the key is usually found without them.
        encryption_label = QLabel(_("Encrypted logs"))
        encryption_label.setObjectName("sectionHeader")
        form_layout.addWidget(encryption_label)

        encryption_help = QLabel(_(
            "Only needed if this tracker's encrypted logs do not open. Enter the "
            "service name and app ID the app writing them uses for its log key."))
        encryption_help.setWordWrap(True)
        form_layout.addWidget(encryption_help)

        service_layout = QHBoxLayout()
        service_label = QLabel(_("Service name:"))
        service_label.setMinimumWidth(100)
        self.encryption_service_input = QLineEdit()
        self.encryption_service_input.setPlaceholderText(AppInfo.LOG_ENCRYPTION_SERVICE)
        service_layout.addWidget(service_label)
        service_layout.addWidget(self.encryption_service_input)
        form_layout.addLayout(service_layout)

        app_id_layout = QHBoxLayout()
        app_id_label = QLabel(_("App ID:"))
        app_id_label.setMinimumWidth(100)
        self.encryption_app_id_input = QLineEdit()
        self.encryption_app_id_input.setPlaceholderText(_("Detected from the log file name"))
        app_id_layout.addWidget(app_id_label)
        app_id_layout.addWidget(self.encryption_app_id_input)
        form_layout.addLayout(app_id_layout)

        if self.is_edit_mode:
            self.encryption_service_input.setText(tracker.log_encryption_service)
            self.encryption_app_id_input.setText(tracker.log_encryption_app_id)

        main_layout.addLayout(form_layout)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton(_("Save Changes") if self.is_edit_mode else _("Create Tracker"))
        save_btn.setObjectName("saveButton")
        save_btn.setMinimumSize(100, 30)
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setMinimumSize(100, 30)
        cancel_btn.clicked.connect(self.reject)
        
        # Away from Save, and only where there is something to delete.
        if self.is_edit_mode:
            delete_btn = QPushButton(_("Delete Tracker"))
            delete_btn.setObjectName("deleteButton")
            delete_btn.setMinimumSize(100, 30)
            delete_btn.clicked.connect(self.request_delete)
            button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        main_layout.addLayout(button_layout)
        
        # Apply theme
        self.setStyleSheet(ThemeManager.get_dialog_style())
    
    def find_directories(self):
        """Open dialog to find log directories."""
        app_name = self.name_input.text()
        logger.debug(f"Finding directories for app: {app_name}")
        dialog = FindLogDirsDialog(app_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_dirs = dialog.get_selected_directories()
            logger.info(f"Found {len(selected_dirs)} directories for {app_name}")
            for directory in selected_dirs:
                if directory not in [self.dirs_list.item(i).text() for i in range(self.dirs_list.count())]:
                    self.dirs_list.addItem(directory)
                    logger.debug(f"Added directory: {directory}")
        else:
            logger.debug("Directory search cancelled by user")
    
    def add_directory(self):
        """Add a new log directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            _("Select Log Directory"),
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            # Check if directory already exists in list
            for i in range(self.dirs_list.count()):
                if self.dirs_list.item(i).text() == directory:
                    logger.debug(f"Directory already in list: {directory}")
                    return
            
            self.dirs_list.addItem(directory)
            logger.info(f"Added directory: {directory}")
    
    def remove_directory(self):
        """Remove selected log directory."""
        current_item = self.dirs_list.currentItem()
        if current_item:
            directory = current_item.text()
            self.dirs_list.takeItem(self.dirs_list.row(current_item))
            logger.info(f"Removed directory: {directory}")
        else:
            logger.debug("No directory selected for removal")
    
    def request_delete(self):
        """Confirm with the user, then close asking the caller to delete."""
        confirmation = QMessageBox.question(
            self,
            _("Delete Tracker"),
            _('Delete the tracker "{0}"?').format(self.tracker.name) + "\n\n"
            + _("This removes the tracker and the directories it watches from "
                "Protokoll. The log files themselves are left where they are."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirmation == QMessageBox.StandardButton.Yes:
            logger.info(f"Deletion confirmed for tracker: {self.tracker.name}")
            self.done(DELETE_REQUESTED)
        else:
            logger.debug(f"Deletion cancelled for tracker: {self.tracker.name}")

    def get_tracker_data(self) -> dict:
        """Get the tracker data from the dialog."""
        return {
            'name': self.name_input.text(),
            'description': self.desc_input.toPlainText(),
            'log_directories': [self.dirs_list.item(i).text() for i in range(self.dirs_list.count())],
            'log_encryption_service': self.encryption_service_input.text().strip(),
            'log_encryption_app_id': self.encryption_app_id_input.text().strip(),
        }
    
    def accept(self):
        """Validate and accept the dialog."""
        if not self.name_input.text():
            QMessageBox.warning(
                self,
                _("Validation Error"),
                _("Please enter a tracker name.")
            )
            return
        
        # Validate that all directories exist
        for i in range(self.dirs_list.count()):
            directory = self.dirs_list.item(i).text()
            if not os.path.exists(directory):
                QMessageBox.warning(
                    self,
                    _("Validation Error"),
                    _("Directory does not exist: {0}").format(directory)
                )
                return
        
        super().accept() 