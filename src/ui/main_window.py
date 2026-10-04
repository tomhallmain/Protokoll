from datetime import datetime
import os
import re

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QLabel, QLineEdit, QTextEdit,
                            QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QFrame, QMenu,
                            QToolButton, QStyle, QSpinBox)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor, QFontMetrics, QTextCursor

from ..internal import log_content, log_entries, log_search
from ..internal.tracker import Tracker
from ..utils.config_manager import ConfigManager
from ..utils.theme_manager import ThemeManager
from ..utils.logging_setup import get_logger
from ..utils.translations import _
from ..utils.utils import Utils
from .log_workers import LogLoadThread, LogSearchThread
from .toast import show_toast
from .tracker_dialog import DELETE_REQUESTED, TrackerDialog

logger = get_logger('ui.main_window')

class MainWindow(QMainWindow):
    #: A log file's content (or the reason it can't be shown) is on screen.
    log_displayed = pyqtSignal(str)
    #: A search request has finished and its outcome is on screen.
    search_finished = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Every request that writes to the log viewer takes a new generation;
        # a worker's result is shown only if no request has been made since.
        self._generation = 0
        self._workers = []

        try:
            self.config_manager = ConfigManager()
        except Exception as e:
            logger.error(f"MainWindow.__init__: Failed to create ConfigManager: {str(e)}")
            raise
        
        self.current_tracker = None

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
        
        # An unreadable cache leaves the tracker list empty and stops anything
        # being saved over it, neither of which is visible on its own.
        cache_error = self.config_manager.app_info_cache.load_error
        if cache_error:
            logger.error(f"MainWindow.__init__: Encrypted cache could not be read: {cache_error}")
            self.handle_error(
                _("Your trackers could not be read, and no changes will be saved until "
                  "that is resolved.") + f"\n\n{cache_error}"
            )
        
    
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
        create_btn = QPushButton(_("Create New Tracker"))
        create_btn.setObjectName("createButton")
        create_btn.clicked.connect(self.create_tracker)
        left_layout.addWidget(create_btn)
        
        # Tracker section
        tracker_label = QLabel(_("Trackers"))
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
        files_label = QLabel(_("Log Files"))
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
        self.search_edit.setPlaceholderText(_("Search in logs..."))
        self.search_edit.returnPressed.connect(self.search_logs)
        search_btn = QPushButton(_("Search"))
        search_btn.setObjectName("searchButton")
        search_btn.clicked.connect(self.search_logs)
        
        # Icon toggles (tooltips explain each); state persisted in config
        style = self.style()
        self.show_line_numbers = QToolButton()
        self.show_line_numbers.setObjectName("showLineNumbers")
        self.show_line_numbers.setCheckable(True)
        self.show_line_numbers.setChecked(self.config_manager.get(ConfigManager.SEARCH_SHOW_LINE_NUMBERS))
        self.show_line_numbers.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogListView))
        self.show_line_numbers.setToolTip(_("Show line numbers"))
        self.show_line_numbers.toggled.connect(self._save_search_settings)
        
        self.use_regex = QToolButton()
        self.use_regex.setObjectName("useRegex")
        self.use_regex.setCheckable(True)
        self.use_regex.setChecked(self.config_manager.get(ConfigManager.SEARCH_USE_REGEX))
        self.use_regex.setText(".*")
        self.use_regex.setToolTip(_("Use regular expression"))
        self.use_regex.toggled.connect(self._save_search_settings)
        
        self.limit_to_line_start = QToolButton()
        self.limit_to_line_start.setObjectName("limitToLineStart")
        self.limit_to_line_start.setCheckable(True)
        self.limit_to_line_start.setChecked(self.config_manager.get(ConfigManager.SEARCH_LIMIT_TO_LINE_START))
        self.limit_to_line_start.setText("^")
        self.limit_to_line_start.setToolTip(_("Match only at start of log line (after level: INFO, ERROR, WARNING, DEBUG, TRACE)"))
        self.limit_to_line_start.toggled.connect(self._save_search_settings)
        
        self.search_all_files = QToolButton()
        self.search_all_files.setObjectName("searchAllFiles")
        self.search_all_files.setCheckable(True)
        self.search_all_files.setChecked(self.config_manager.get(ConfigManager.SEARCH_ALL_FILES))
        self.search_all_files.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.search_all_files.setToolTip(_("Search all log files in the tracker (not just the selected file)"))
        self.search_all_files.toggled.connect(self._save_search_settings)

        self.multiline_entries = QToolButton()
        self.multiline_entries.setObjectName("multilineEntries")
        self.multiline_entries.setCheckable(True)
        self.multiline_entries.setChecked(self.config_manager.get(ConfigManager.SEARCH_MULTILINE_ENTRIES))
        self.multiline_entries.setText("¶")
        self.multiline_entries.setToolTip(
            _("Group multi-line logger calls (tracebacks, formatted messages) into single entries"))
        self.multiline_entries.toggled.connect(self._save_search_settings)

        self.context_before = QSpinBox()
        self.context_before.setObjectName("contextBefore")
        self.context_before.setRange(0, 50)
        self.context_before.setValue(self.config_manager.get(ConfigManager.SEARCH_CONTEXT_BEFORE))
        self.context_before.setPrefix(_("B:"))
        self.context_before.setToolTip(_("Entries of context to show before each match"))
        self.context_before.valueChanged.connect(self._save_search_settings)

        self.context_after = QSpinBox()
        self.context_after.setObjectName("contextAfter")
        self.context_after.setRange(0, 50)
        self.context_after.setValue(self.config_manager.get(ConfigManager.SEARCH_CONTEXT_AFTER))
        self.context_after.setPrefix(_("A:"))
        self.context_after.setToolTip(_("Entries of context to show after each match"))
        self.context_after.valueChanged.connect(self._save_search_settings)

        # Add Clear button
        clear_btn = QPushButton(_("Clear"))
        clear_btn.setObjectName("clearButton")
        clear_btn.clicked.connect(self.clear_search_and_reload)
        
        # Add Refresh button
        refresh_btn = QPushButton(_("Refresh"))
        refresh_btn.setObjectName("refreshButton")
        refresh_btn.clicked.connect(self.refresh_current_log)
        
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(search_btn)
        search_layout.addWidget(clear_btn)
        search_layout.addWidget(refresh_btn)
        search_layout.addWidget(self.show_line_numbers)
        search_layout.addWidget(self.use_regex)
        search_layout.addWidget(self.limit_to_line_start)
        search_layout.addWidget(self.search_all_files)
        search_layout.addWidget(self.multiline_entries)
        search_layout.addWidget(self.context_before)
        search_layout.addWidget(self.context_after)
        
        # Open in Editor button with context menu
        open_editor_btn = QPushButton(_("Open in Editor"))
        open_editor_btn.setObjectName("openEditorButton")
        open_editor_btn.clicked.connect(self.open_in_editor)
        
        # Create context menu for editor options
        editor_menu = QMenu(open_editor_btn)
        default_action = editor_menu.addAction(_("Use Default Editor"))
        default_action.triggered.connect(self.open_in_default_editor)
        
        copy_path_action = editor_menu.addAction(_("Copy path to clipboard"))
        copy_path_action.triggered.connect(self.copy_log_path_to_clipboard)
        
        custom_action = editor_menu.addAction(_("Configure Custom Editor..."))
        custom_action.triggered.connect(self.configure_custom_editor)
        
        # Show current custom editor if configured
        custom_editor = self.config_manager.get(ConfigManager.CUSTOM_EDITOR_COMMAND)
        if custom_editor:
            editor_menu.addSeparator()
            current_action = editor_menu.addAction(_("Current: {0}").format(custom_editor))
            current_action.setEnabled(False)
            clear_action = editor_menu.addAction(_("Clear Custom Editor"))
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
        
        # No line wrapping: long lines scroll horizontally
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
        width = self.config_manager.get(ConfigManager.WINDOW_WIDTH)
        height = self.config_manager.get(ConfigManager.WINDOW_HEIGHT)
        x = self.config_manager.get(ConfigManager.WINDOW_X)
        y = self.config_manager.get(ConfigManager.WINDOW_Y)
        
        self.resize(width, height)
        if x is not None and y is not None:
            self.move(x, y)
    
    def save_window_state(self):
        """Save window state to configuration"""
        self.config_manager.set(ConfigManager.WINDOW_WIDTH, self.width())
        self.config_manager.set(ConfigManager.WINDOW_HEIGHT, self.height())
        self.config_manager.set(ConfigManager.WINDOW_X, self.x())
        self.config_manager.set(ConfigManager.WINDOW_Y, self.y())

    def _save_search_settings(self, _checked=None):
        """Persist search toggle states to config (called when any search toggle changes)."""
        self.config_manager.set(ConfigManager.SEARCH_SHOW_LINE_NUMBERS, self.show_line_numbers.isChecked())
        self.config_manager.set(ConfigManager.SEARCH_USE_REGEX, self.use_regex.isChecked())
        self.config_manager.set(ConfigManager.SEARCH_LIMIT_TO_LINE_START, self.limit_to_line_start.isChecked())
        self.config_manager.set(ConfigManager.SEARCH_ALL_FILES, self.search_all_files.isChecked())
        self.config_manager.set(ConfigManager.SEARCH_MULTILINE_ENTRIES, self.multiline_entries.isChecked())
        self.config_manager.set(ConfigManager.SEARCH_CONTEXT_BEFORE, self.context_before.value())
        self.config_manager.set(ConfigManager.SEARCH_CONTEXT_AFTER, self.context_after.value())
    
    def load_trackers(self):
        """Load and display all available trackers"""
        self.tracker_list.clear()
        for tracker in Tracker.list_trackers(self.config_manager):
            self.tracker_list.addItem(tracker.name)
        
        # Select last used tracker if available
        last_tracker = self.config_manager.get(ConfigManager.LAST_TRACKER)
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
                tracker.set_log_encryption(data["log_encryption_service"], data["log_encryption_app_id"])

                tracker.set_log_directories(data["log_directories"])
                
                self.config_manager.add_recent_tracker(data["name"])
                self.load_trackers()
                
                # Select the newly created tracker
                items = self.tracker_list.findItems(data["name"], Qt.MatchFlag.MatchExactly)
                if items:
                    self.tracker_list.setCurrentItem(items[0])
                    
            except Exception as e:
                QMessageBox.critical(self, _("Error"), _("Failed to create tracker: {0}").format(str(e)))
    
    def on_tracker_selected(self, current, previous):
        """Handle tracker selection"""
        if current is None:
            self.current_tracker = None
            self.files_list.clear()
            self._begin_viewer_update()
            self.log_viewer.clear()
            return
        
        tracker_name = current.text()
        logger.debug(f"Loading tracker: {tracker_name}")
        self.current_tracker = Tracker.load(tracker_name, self.config_manager)
        if self.current_tracker:
            logger.debug(f"Tracker loaded with directories: {self.current_tracker.get_log_directories()}")
        self.config_manager.set(ConfigManager.LAST_TRACKER, tracker_name)
        self.update_log_files_list()
    
    def update_log_files_list(self):
        """Update the list of log files for the current tracker"""
        self._begin_viewer_update()
        self.files_list.clear()
        if not self.current_tracker:
            logger.debug("No current tracker, clearing file list")
            self.update_window_title()
            return
        
        log_files = self.current_tracker.get_log_files()
        logger.debug(f"Found {len(log_files)} log files")
        
        # Sort log files by last modified time, most recent first
        log_files.sort(key=lambda x: x["last_modified"], reverse=True)
        
        last_selected = self.config_manager.get(
            ConfigManager.last_log_file_key(self.current_tracker.name))
        selected_row = None
        for idx, log_file in enumerate(log_files):
            # Create display text with file info
            filename = os.path.basename(log_file["path"])
            size_info = log_file.get("size_human", "")
            compressed_indicator = "📦 " if log_file.get("is_compressed", False) else ""
            encrypted_indicator = "🔒 " if log_file.get("is_encrypted", False) else ""
            warning_indicator = "⚠️ " if log_file.get("warnings") else ""

            display_text = f"{compressed_indicator}{encrypted_indicator}{warning_indicator}{filename}"
            if size_info:
                display_text += f" ({size_info})"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, log_file["path"])
            
            # Add tooltip with detailed information
            tooltip_parts = [
                _("Path: {0}").format(log_file["path"]),
                _("Size: {0}").format(size_info),
            ]
            if log_file.get("warnings"):
                tooltip_parts.append(_("Warnings:"))
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
            self.config_manager.set(
                ConfigManager.last_log_file_key(self.current_tracker.name), log_files[0]["path"])
        
        # Pre-select the appropriate log file
        if selected_row is not None:
            self.files_list.setCurrentRow(selected_row)
        else:
            # No log files found, show message in log viewer
            self.log_viewer.clear()
            self.append_styled_content(_("No log files found in the tracked directories."), color=ThemeManager.DARK_THEME["log_viewer"]["warning"])
            self.append_styled_content(_("Add directories containing log files to this tracker."), color=ThemeManager.DARK_THEME["log_viewer"]["success"])
        
        self.update_window_title()
    
    def update_window_title(self):
        """Update the window title to show current context"""
        title = "Protokoll"
        if self.current_tracker:
            title += f" - {self.current_tracker.name}"
            log_file_path = self.get_current_log_file_path()
            if log_file_path:
                log_file = os.path.basename(log_file_path)
                try:
                    last_modified = os.path.getmtime(log_file_path)
                    last_modified_str = datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M:%S')
                    title += " - {0} ({1}: {2})".format(
                        log_file, _("Last modified"), last_modified_str)
                except Exception:
                    title += f" - {log_file}"
        self.setWindowTitle(title)
    
    def on_log_file_selected(self):
        """Handle log file selection"""
        log_file_path = self.get_current_log_file_path()
        if not log_file_path:
            return
        # Save last selected log file for this tracker
        if self.current_tracker:
            tracker_key = ConfigManager.last_log_file_key(self.current_tracker.name)
            self.config_manager.set(tracker_key, log_file_path)
        self.display_log_file(log_file_path)
        self.update_window_title()

    def _log_key_candidates(self, file_path):
        """Keys to try for an encrypted log: the current tracker's, or none without one."""
        return self.current_tracker.log_key_candidates(file_path) if self.current_tracker else []

    def append_styled_content(self, text, color=None, bold=False, background_color=None):
        """Append content to the log viewer with optional styling"""
        self.log_viewer.append(ThemeManager.styled_span(
            text, color=color, bold=bold, background_color=background_color))

    def _load_single_long_line(self, content):
        """Handle a single very long line (e.g., minified JSON) by truncating"""
        text, original_length = log_content.truncate_long_line(content)

        if original_length is not None:
            # "10KB" is an approximation of log_content.MAX_LONG_LINE_CHARS, which counts
            # characters rather than bytes; change both together.
            self.append_styled_content(
                _("⚠️  File contains a very long line. Showing first 10KB:"),
                color=ThemeManager.DARK_THEME["log_viewer"]["warning"])
            self.log_viewer.append("\n")

        self.log_viewer.append(ThemeManager.convert_ansi_to_html(text))

        if original_length is not None:
            self.append_styled_content(
                "\n" + _("... (truncated, original length: {0} characters)").format(f"{original_length:,}"),
                color=ThemeManager.DARK_THEME["log_viewer"]["warning"])

    def _load_large_file_chunked(self, content, generation):
        """Handle a large multi-line file by loading in chunks.

        Returns False if a newer request took over the viewer part way through:
        processEvents() can run its slot, which clears the viewer, so this stops
        rather than appending the rest of the old file after it.
        """
        # No in-document progress indicator here (deliberately): an earlier version tried
        # to insert one and then update/remove it in place via cursor manipulation, which
        # got corrupted by or never found again past the file-info header this method is
        # always called after. Getting that right needs a live PyQt6 environment to verify
        # against, which isn't available where this was last touched - periodic
        # processEvents() calls below still keep the UI responsive during the load.
        for i, chunk in enumerate(log_content.iter_chunks(content)):
            self.log_viewer.append(ThemeManager.convert_ansi_to_html(chunk))

            # Process events every few chunks to keep UI responsive
            if i % 2 == 0:
                QApplication.processEvents()
                if not self._is_current(generation):
                    return False
        return True

    # ------------------------------------------------------------------
    # Background work for the log viewer
    # ------------------------------------------------------------------

    def _begin_viewer_update(self):
        """Start a new request for the log viewer, making every earlier one stale."""
        self._generation += 1
        for worker in self._workers:
            worker.cancel()
        return self._generation

    def _is_current(self, generation):
        return generation == self._generation

    def _start_worker(self, worker):
        # A worker is released only once it has stopped and its result has been
        # delivered; releasing it earlier would destroy a running QThread.
        self._workers = [w for w in self._workers
                         if not (w.isFinished() and w.delivered)]
        self._workers.append(worker)
        worker.start()

    def _take_result(self, generation):
        """Mark the worker for *generation* as delivered, and return it."""
        for worker in self._workers:
            if worker.generation == generation:
                worker.delivered = True
                return worker
        return None

    def display_log_file(self, file_path):
        """Display the selected log file; the reading happens on a worker thread."""
        generation = self._begin_viewer_update()
        self.log_viewer.clear()
        self.append_styled_content(_("Loading {0}...").format(os.path.basename(file_path)),
                                   color=ThemeManager.DARK_THEME["log_viewer"]["info"])

        worker = LogLoadThread(
            generation, file_path,
            self.config_manager.get(ConfigManager.MAX_LOAD_BYTES),
            self._log_key_candidates(file_path))
        worker.loaded.connect(self._on_log_loaded)
        self._start_worker(worker)

    def _on_log_loaded(self, generation, result):
        self._take_result(generation)
        if not self._is_current(generation):
            return
        if self._render_log_file(generation, result):
            self.log_displayed.emit(result.file_path)

    def _render_log_file(self, generation, result):
        """Show a LoadResult. Returns False if a newer request took over mid-render."""
        file_path = result.file_path
        file_info = result.file_info
        self.log_viewer.clear()

        if not result.is_valid:
            self.append_styled_content(_("⚠️  Cannot display file: {0}").format(result.reason), color=ThemeManager.DARK_THEME["log_viewer"]["error"])
            if "warnings" in file_info and file_info["warnings"]:
                for warning in file_info["warnings"]:
                    self.append_styled_content(f"  • {warning}", color=ThemeManager.DARK_THEME["log_viewer"]["warning"])
            self.log_viewer.append("\n")
            return True

        content, read_info = result.content, result.read_info
        if not result.success:
            self.append_styled_content(_("❌ Error reading file: {0}").format(read_info.get("error", _("Unknown error"))), color=ThemeManager.DARK_THEME["log_viewer"]["error"])
            self.log_viewer.append("\n")
            return True

        is_tail = read_info.get("is_tail", False)
        lines_label = _("Lines shown") if is_tail else _("Lines")

        # Show file information header
        last_modified = file_info.get("last_modified")
        updated_today_note = ""
        if last_modified is not None:
            try:
                if datetime.fromtimestamp(last_modified).date() == datetime.now().date():
                    updated_today_note = " | " + _("Updated today")
            except (OSError, ValueError):
                pass
        self.append_styled_content(f"=== {os.path.basename(file_path)} ===", color=ThemeManager.DARK_THEME["log_viewer"]["info"])
        self.append_styled_content(
            "{0} | {1}: {2}{3}".format(
                _("Size: {0}").format(file_info["size_human"]),
                lines_label,
                file_info.get("total_lines", _("Unknown")),
                updated_today_note),
            color=ThemeManager.DARK_THEME["log_viewer"]["info"])

        if is_tail:
            # A compressed or encrypted file's size on disk is not the size of
            # its text, so only a plain file can say what fraction is shown.
            if file_info.get("is_compressed", False):
                of_what = _("the decompressed contents")
            elif file_info.get("is_encrypted", False):
                of_what = _("the decrypted contents")
            else:
                of_what = file_info["size_human"]
            self.append_styled_content(
                _("⏱️  Showing the last {0} of {1}. Earlier lines are not loaded - "
                  "open the file in an editor to see them.").format(
                      read_info["shown_size_human"], of_what),
                color=ThemeManager.DARK_THEME["log_viewer"]["warning"])

        if file_info.get("is_compressed", False):
            self.append_styled_content(_("📦 Compressed file detected"), color=ThemeManager.DARK_THEME["log_viewer"]["info"])

        if file_info.get("is_encrypted", False):
            self.append_styled_content(_("🔒 Encrypted log, decrypted for viewing"), color=ThemeManager.DARK_THEME["log_viewer"]["info"])
            if read_info.get("skipped_records"):
                self.append_styled_content(
                    _("⚠️  {0} record(s) could not be decrypted and are not shown").format(
                        read_info["skipped_records"]),
                    color=ThemeManager.DARK_THEME["log_viewer"]["warning"])

        if file_info.get("warnings"):
            for warning in file_info["warnings"]:
                self.append_styled_content(f"⚠️  {warning}", color=ThemeManager.DARK_THEME["log_viewer"]["warning"])

        self.log_viewer.append("\n")

        line_count = log_content.count_lines(content)
        header_had_unknown_lines = file_info.get("total_lines") is None

        strategy = log_content.choose_render_strategy(content)
        if strategy == log_content.RENDER_CHUNKED:
            if not self._load_large_file_chunked(content, generation):
                return False
        elif strategy == log_content.RENDER_LONG_LINE:
            self._load_single_long_line(content)
        else:
            self.log_viewer.append(ThemeManager.convert_ansi_to_html(content))

        self.log_viewer.append("\n")

        if header_had_unknown_lines:
            self._update_header_line_count(
                line_count, file_path, file_info["size_human"], updated_today_note, lines_label)
        return True

    def _update_header_line_count(self, line_count: int, file_path: str = None, size_human: str = None, updated_today_note: str = "", lines_label: str = None) -> None:
        """Replace 'Lines: Unknown' in the header with the actual line count, then append the same header at the end."""
        lines_label = lines_label or _("Lines")
        vbar = self.log_viewer.verticalScrollBar()
        scroll_value = vbar.value()
        at_bottom = scroll_value >= vbar.maximum() - 1

        cursor = self.log_viewer.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.log_viewer.setTextCursor(cursor)
        if self.log_viewer.find("{0}: {1}".format(lines_label, _("Unknown"))):
            cursor = self.log_viewer.textCursor()
            cursor.insertText(f"{lines_label}: {line_count:,}")

        if file_path is not None and size_human is not None:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_viewer.setTextCursor(cursor)
            self.log_viewer.append("\n")
            self.append_styled_content(f"=== {os.path.basename(file_path)} ===", color=ThemeManager.DARK_THEME["log_viewer"]["info"])
            self.append_styled_content(
                "{0} | {1}: {2}{3}".format(
                    _("Size: {0}").format(size_human), lines_label, f"{line_count:,}", updated_today_note),
                color=ThemeManager.DARK_THEME["log_viewer"]["info"])

        if at_bottom:
            vbar.setValue(vbar.maximum())
        else:
            vbar.setValue(scroll_value)
    
    def clear_search_and_reload(self):
        """Clear the search bar and reload the current log file if one is selected."""
        logger.debug("Clearing search bar and reloading current log file")
        self.search_edit.clear()
        log_file_path = self.get_current_log_file_path()
        if log_file_path:
            self.display_log_file(log_file_path)

    def refresh_current_log(self):
        """Refresh the currently viewed log file and update the log files list."""
        logger.debug("Refreshing current log file and log files list")

        # Save the currently selected file path before refreshing
        selected_file_path = self.get_current_log_file_path()

        if not self.current_tracker:
            if selected_file_path:
                self.display_log_file(selected_file_path)
            return

        # Rebuilding the list reselects the last viewed file, and selecting a
        # file loads it, so the file is not loaded again here.
        self.update_log_files_list()
        if selected_file_path and self.get_current_log_file_path() != selected_file_path:
            for i in range(self.files_list.count()):
                if self.files_list.item(i).data(Qt.ItemDataRole.UserRole) == selected_file_path:
                    self.files_list.setCurrentRow(i)
                    return

    def _prepare_search_pattern(self, search_text):
        """Return (search_re, search_text_lower, error_message)."""
        if self.use_regex.isChecked():
            try:
                return re.compile(search_text, re.IGNORECASE), None, None
            except re.error:
                return None, None, _("Invalid regular expression: {0}").format(search_text)
        return None, search_text.lower(), None

    def _matcher(self, search_re, search_text_lower):
        """content -> match blocks, with the search toggles as they are now.

        The toggles are read here, on the GUI thread, because the returned
        function runs on a worker.
        """
        options = dict(
            use_regex=self.use_regex.isChecked(),
            limit_to_line_start=self.limit_to_line_start.isChecked(),
            multiline=self.multiline_entries.isChecked(),
            context_before=self.context_before.value(),
            context_after=self.context_after.value(),
            max_entry_lines=self.config_manager.get(ConfigManager.SEARCH_MAX_ENTRY_LINES),
        )

        def find_matches(content):
            return log_entries.find_matches(content, search_re, search_text_lower, **options)
        return find_matches

    def _display_search_blocks(self, blocks):
        """Render match blocks, with a separator between non-adjacent blocks."""
        for i, block in enumerate(blocks):
            if i > 0:
                self.append_styled_content("--", color=ThemeManager.DARK_THEME["log_viewer"]["text"])
            for entry in block:
                for line_num, line_content, is_match in entry:
                    self._append_search_match(line_num, line_content, is_match)

    def _append_search_match(self, line_num, line_content, is_match=True):
        formatted_line = ThemeManager.convert_ansi_to_html(line_content)
        if self.show_line_numbers.isChecked() and line_num is not None:
            number_color = (ThemeManager.DARK_THEME["log_viewer"]["info"] if is_match
                             else ThemeManager.DARK_THEME["log_viewer"]["text"])
            number_span = ThemeManager.styled_span(f"{line_num}: ", color=number_color)
            # Combined into one append() call so the number sits to the left of the
            # line on the same row, instead of on its own paragraph above it.
            self.log_viewer.append(number_span + formatted_line)
        else:
            self.log_viewer.append(formatted_line)

    def _search_scope_description(self):
        mode = _("regex") if self.use_regex.isChecked() else _("plain text")
        scope = _("limit to line start") if self.limit_to_line_start.isChecked() else _("full line")
        return mode, scope

    def _display_single_file_search_results(self, log_file_path, blocks, search_text):
        self.log_viewer.clear()
        self.append_styled_content(
            _("File: {0} Found {1} matches").format(
                os.path.basename(log_file_path), log_entries.count_matches(blocks)),
            color=ThemeManager.DARK_THEME["log_viewer"]["info"],
        )
        self.log_viewer.append("\n")
        self._display_search_blocks(blocks)

    def _display_skipped_files(self, skipped_files):
        if not skipped_files:
            return
        self.append_styled_content(
            _("Skipped {0} file(s):").format(len(skipped_files)),
            color=ThemeManager.DARK_THEME["log_viewer"]["warning"],
        )
        for file_path, _kind, reason in skipped_files:
            self.append_styled_content(
                "  • {0}: {1}".format(os.path.basename(file_path), reason),
                color=ThemeManager.DARK_THEME["log_viewer"]["warning"],
            )

    def _display_all_files_search_results(self, file_results, skipped_files, search_text, files_searched):
        total_matches = sum(log_entries.count_matches(blocks) for _, blocks in file_results)
        files_with_matches = len(file_results)
        self.log_viewer.clear()
        self.append_styled_content(
            _("Found {0} matches in {1} file(s) (searched {2} file(s))").format(
                total_matches, files_with_matches, files_searched),
            color=ThemeManager.DARK_THEME["log_viewer"]["info"],
        )
        self._display_skipped_files(skipped_files)
        self.log_viewer.append("\n")
        for file_path, blocks in file_results:
            self.append_styled_content(
                "=== {0} ===".format(
                    _("{0} ({1} match(es))").format(
                        os.path.basename(file_path), log_entries.count_matches(blocks))),
                color=ThemeManager.DARK_THEME["log_viewer"]["info"],
            )
            self._display_search_blocks(blocks)
            self.log_viewer.append("")

    def search_logs(self):
        """Search the current log file or all tracker log files, on a worker thread."""
        generation = self._begin_viewer_update()
        if not self.current_tracker:
            self.search_finished.emit()
            return

        search_text = self.search_edit.text().strip()
        # If search is empty, reload the full log file
        if not search_text:
            log_file_path = self.get_current_log_file_path()
            if log_file_path:
                self.display_log_file(log_file_path)
            self.search_finished.emit()
            return

        search_re, search_text_lower, error_message = self._prepare_search_pattern(search_text)
        if error_message:
            self.log_viewer.clear()
            self.append_styled_content(error_message, color=ThemeManager.DARK_THEME["log_viewer"]["error"])
            self.search_finished.emit()
            return

        tracker = self.current_tracker
        all_files = self.search_all_files.isChecked()
        if all_files:
            def list_file_paths():
                return [log_file["path"] for log_file in tracker.get_log_files()]
        else:
            log_file_path = self.get_current_log_file_path()
            if not log_file_path:
                self.search_finished.emit()
                return

            def list_file_paths():
                return [log_file_path]

        self.log_viewer.clear()
        self.append_styled_content(_("Searching..."), color=ThemeManager.DARK_THEME["log_viewer"]["info"])

        worker = LogSearchThread(
            generation, list_file_paths, self._matcher(search_re, search_text_lower),
            tracker.log_key_candidates, search_text, all_files)
        worker.searched.connect(self._on_search_done)
        worker.failed.connect(self._on_search_failed)
        self._start_worker(worker)

    def _on_search_done(self, generation, outcome):
        worker = self._take_result(generation)
        if not self._is_current(generation) or worker is None:
            return
        if worker.all_files:
            self._show_all_files_outcome(outcome, worker.search_text)
        else:
            self._show_single_file_outcome(outcome, worker.search_text)
        self.search_finished.emit()

    def _on_search_failed(self, generation, message):
        self._take_result(generation)
        if not self._is_current(generation):
            return
        self.log_viewer.clear()
        self.append_styled_content(_("❌ Search failed: {0}").format(message),
                                   color=ThemeManager.DARK_THEME["log_viewer"]["error"])
        self.search_finished.emit()

    def _show_all_files_outcome(self, outcome, search_text):
        if outcome.files_searched == 0:
            self.log_viewer.clear()
            self.append_styled_content(
                _("No log files found in the tracked directories."),
                color=ThemeManager.DARK_THEME["log_viewer"]["warning"],
            )
            return

        if outcome.file_results:
            self._display_all_files_search_results(
                outcome.file_results, outcome.skipped_files, search_text, outcome.files_searched
            )
            return

        self.log_viewer.clear()
        mode, scope = self._search_scope_description()
        self.append_styled_content(
            _("No matches found for '{0}' across {1} file(s) ({2}, {3})").format(
                search_text, outcome.files_searched, mode, scope),
            color=ThemeManager.DARK_THEME["log_viewer"]["error"],
        )
        self._display_skipped_files(outcome.skipped_files)

    def _show_single_file_outcome(self, outcome, search_text):
        if outcome.skipped_files:
            self.log_viewer.clear()
            _file_path, kind, message = outcome.skipped_files[0]
            if kind == log_search.SKIP_VALIDATION:
                self.append_styled_content(
                    _("⚠️  Cannot search file: {0}").format(message),
                    color=ThemeManager.DARK_THEME["log_viewer"]["error"],
                )
            else:
                self.append_styled_content(
                    _("❌ Error reading file: {0}").format(message),
                    color=ThemeManager.DARK_THEME["log_viewer"]["error"],
                )
            return

        if outcome.file_results:
            log_file_path, blocks = outcome.file_results[0]
            self._display_single_file_search_results(log_file_path, blocks, search_text)
            return

        self.log_viewer.clear()
        mode, scope = self._search_scope_description()
        self.append_styled_content(
            _("No matches found for '{0}' ({1}, {2})").format(search_text, mode, scope),
            color=ThemeManager.DARK_THEME["log_viewer"]["error"],
        )

    def edit_tracker(self, item):
        """Edit the selected tracker"""
        if not item:
            return
        
        tracker_name = item.text()
        tracker = Tracker.load(tracker_name, self.config_manager)
        if not tracker:
            QMessageBox.critical(self, _("Error"), _("Failed to load tracker: {0}").format(tracker_name))
            return
        
        dialog = TrackerDialog(tracker, self)
        result = dialog.exec()

        if result == DELETE_REQUESTED:
            # The dialog has already confirmed this with the user.
            self.delete_tracker(tracker)
            return

        if result:
            data = dialog.get_tracker_data()
            try:
                # Update tracker properties
                tracker.name = data["name"]
                tracker.description = data["description"]
                tracker.set_log_encryption(data["log_encryption_service"], data["log_encryption_app_id"])

                tracker.set_log_directories(data["log_directories"])
                logger.debug(f"Final directories after update: {tracker.get_log_directories()}")

                # Update UI
                self.load_trackers()
                
                # Select the updated tracker
                items = self.tracker_list.findItems(data["name"], Qt.MatchFlag.MatchExactly)
                if items:
                    self.tracker_list.setCurrentItem(items[0])
                    
            except Exception as e:
                logger.error(f"Error updating tracker: {str(e)}")
                QMessageBox.critical(self, _("Error"), _("Failed to update tracker: {0}").format(str(e)))

    def delete_tracker(self, tracker):
        """Remove a tracker, along with the app's record of where it was last read."""
        try:
            self.config_manager.remove_tracker(tracker.name)
        except Exception as e:
            logger.error(f"Error deleting tracker {tracker.name}: {str(e)}")
            QMessageBox.critical(self, _("Error"), _("Failed to delete tracker: {0}").format(str(e)))
            return

        logger.info(f"Deleted tracker: {tracker.name}")
        if self.current_tracker and self.current_tracker.name == tracker.name:
            self.current_tracker = None
            self.files_list.clear()
            self._begin_viewer_update()
            self.log_viewer.clear()

        self.load_trackers()
        self.update_window_title()
        show_toast(self, _('Deleted tracker "{0}"').format(tracker.name))

    def get_current_log_file_path(self):
        """Return the path of the currently selected log file, or None if none is selected."""
        selected_items = self.files_list.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].data(Qt.ItemDataRole.UserRole)

    def open_in_editor(self):
        """Open the currently selected log file in the system's default text editor or custom editor"""
        log_file_path = self.get_current_log_file_path()
        if not log_file_path:
            QMessageBox.information(self, _("No File Selected"), _("Please select a log file to open in the editor."))
            return

        # Get custom editor command from config if available
        custom_editor = self.config_manager.get(ConfigManager.CUSTOM_EDITOR_COMMAND)

        Utils.open_file_with_editor(log_file_path, custom_editor, self.handle_error)
        show_toast(self, _("Opening in editor"))

    def open_in_default_editor(self):
        """Open the currently selected log file in the system's default text editor"""
        log_file_path = self.get_current_log_file_path()
        if not log_file_path:
            QMessageBox.information(self, _("No File Selected"), _("Please select a log file to open in the editor."))
            return

        Utils.open_file_with_editor(log_file_path, None, self.handle_error)  # Use default editor
        show_toast(self, _("Opening in editor"))

    def copy_log_path_to_clipboard(self):
        """Copy the absolute path of the currently selected log file to the clipboard."""
        log_file_path = self.get_current_log_file_path()
        if not log_file_path:
            QMessageBox.information(self, _("No File Selected"), _("Please select a log file to copy its path."))
            return

        absolute_path = os.path.abspath(log_file_path)
        QApplication.clipboard().setText(absolute_path)
        show_toast(self, _("Path copied to clipboard"))

    def configure_custom_editor(self):
        """Show dialog to configure custom editor command"""
        current_command = self.config_manager.get(ConfigManager.CUSTOM_EDITOR_COMMAND, '')
        
        command, ok = QLineEdit.getText(
            self, 
            _("Configure Custom Editor"),
            _("Enter custom editor command (use {filepath} as placeholder for file path):") + "\n\n"
            + _("Examples:") + "\n"
            "• notepad.exe {filepath}\n"
            "• code {filepath}\n"
            "• gedit {filepath}\n"
            "• vim {filepath}",
            text=current_command
        )
        
        if ok and command.strip():
            if not Utils.editor_command_has_placeholder(command):
                QMessageBox.warning(self, _("Invalid Command"),
                                  _("The command must contain {filepath} as a placeholder for the file path."))
                return

            executable, _arguments = Utils.editor_command_parts(command)
            if not Utils.executable_available(executable):
                reply = QMessageBox.question(self, _("Executable Not Found"),
                                           _("The executable '{0}' was not found in your system PATH.").format(executable)
                                           + "\n" + _("Do you want to save this command anyway?"),
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return
            
            self.config_manager.set(ConfigManager.CUSTOM_EDITOR_COMMAND, command.strip())
            show_toast(self, _("Custom editor saved"))
        elif ok and not command.strip():
            # User cleared the command
            self.config_manager.set(ConfigManager.CUSTOM_EDITOR_COMMAND, '')
            show_toast(self, _("Custom editor cleared"))

    def clear_custom_editor(self):
        """Clear the custom editor command"""
        reply = QMessageBox.question(self, _("Clear Custom Editor"),
                                   _("Are you sure you want to clear the custom editor command?") + "\n"
                                   + _("This will revert to using the system default editor."),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.set(ConfigManager.CUSTOM_EDITOR_COMMAND, '')
            show_toast(self, _("Custom editor cleared"))

    def closeEvent(self, event):
        """Handle window close event"""
        # Destroying a QThread that is still running aborts the process, so
        # outstanding workers are stopped where they can be and waited for.
        self._begin_viewer_update()
        for worker in self._workers:
            worker.wait()
        self.save_window_state()
        self.config_manager.flush_cache()
        super().closeEvent(event) 

    def handle_error(self, error_message: str):
        QMessageBox.warning(self, _("Error"), error_message)
