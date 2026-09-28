from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .ffmpeg import FFmpegNotFoundError, find_binary
from .worker import ConversionWorker


QUALITY_MODES = {
    "High Quality MP3 · VBR V0 (recommended)": "mp3_v0",
    "Maximum Bitrate MP3 · 320 kbps": "mp3_320",
    "Original Audio · no re-encoding": "original",
}

VIDEO_FILTER = (
    "Media files (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.mpeg *.mpg *.ts *.mts "
    "*.m2ts *.wmv *.flv *.3gp *.ogv *.vob);;All files (*.*)"
)

TERMINAL_STATUSES = {"Done", "Failed", "Cancelled"}


class DropArea(QFrame):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setMinimumHeight(112)

        layout = QVBoxLayout(self)
        title = QLabel("Drop video files here")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Mix formats freely — files are processed one by one.")
        subtitle.setObjectName("dropSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Ratanak Media Converter")
        self.resize(980, 700)

        self.settings = QSettings()
        self.files: list[Path] = []
        self.worker: ConversionWorker | None = None
        self.custom_output: Path | None = None
        self.last_output_directory: Path | None = None

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        )
        self.tray.setToolTip("Ratanak Media Converter")
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self._build_ui()
        self._load_settings()
        self.quality.currentTextChanged.connect(self._save_preferences)
        self._apply_style()
        self._refresh_controls()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        heading = QLabel("Ratanak Media Converter")
        heading.setObjectName("heading")
        description = QLabel(
            "Batch-convert video audio with FFmpeg while preserving source sample rate and channels."
        )
        description.setObjectName("description")
        layout.addWidget(heading)
        layout.addWidget(description)

        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self.add_paths)
        layout.addWidget(self.drop_area)

        toolbar = QHBoxLayout()
        self.add_button = QPushButton("Add files")
        self.remove_button = QPushButton("Remove selected")
        self.clear_completed_button = QPushButton("Clear completed")
        self.clear_button = QPushButton("Clear all")
        self.add_button.clicked.connect(self.choose_files)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_completed_button.clicked.connect(self.clear_completed)
        self.clear_button.clicked.connect(self.clear_queue)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.remove_button)
        toolbar.addWidget(self.clear_completed_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["File", "Source audio", "Status", "Output"]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        settings = QHBoxLayout()
        settings.addWidget(QLabel("Audio:"))

        self.quality = QComboBox()
        self.quality.addItems(QUALITY_MODES.keys())
        settings.addWidget(self.quality, 1)

        settings.addWidget(QLabel("Output:"))
        self.output_mode = QComboBox()
        self.output_mode.addItems(
            ["Same folder as source", "Custom folder"]
        )
        self.output_mode.currentIndexChanged.connect(
            self.output_mode_changed
        )
        settings.addWidget(self.output_mode)

        self.folder_button = QPushButton("Choose folder")
        self.folder_button.clicked.connect(self.choose_output_folder)
        self.folder_button.setEnabled(False)
        settings.addWidget(self.folder_button)
        layout.addLayout(settings)

        self.output_label = QLabel(
            "Output: same folder as each source file"
        )
        self.output_label.setObjectName("description")
        layout.addWidget(self.output_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Ready")
        layout.addWidget(self.progress)

        actions = QHBoxLayout()
        self.open_folder_button = QPushButton("Open output folder")
        self.open_folder_button.clicked.connect(self.open_output_folder)

        self.start_button = QPushButton("Start conversion")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self.start_conversion)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.cancel_button.setEnabled(False)

        actions.addWidget(self.open_folder_button)
        actions.addStretch()
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.start_button)
        layout.addLayout(actions)

    def _load_settings(self) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        saved_quality = str(
            self.settings.value("conversion/quality", "")
        )
        quality_index = self.quality.findText(saved_quality)
        if quality_index >= 0:
            self.quality.setCurrentIndex(quality_index)

        saved_folder = str(
            self.settings.value("conversion/custom_output", "")
        )
        if saved_folder:
            self.custom_output = Path(saved_folder)

        try:
            output_index = int(
                self.settings.value("conversion/output_mode", 0)
            )
        except (TypeError, ValueError):
            output_index = 0

        output_index = 1 if output_index == 1 else 0
        self.output_mode.blockSignals(True)
        self.output_mode.setCurrentIndex(output_index)
        self.output_mode.blockSignals(False)
        self.output_mode_changed(output_index)

    def _save_preferences(self, *_args) -> None:
        self.settings.setValue(
            "conversion/quality", self.quality.currentText()
        )
        self.settings.setValue(
            "conversion/output_mode", self.output_mode.currentIndex()
        )
        self.settings.setValue(
            "conversion/custom_output",
            str(self.custom_output) if self.custom_output else "",
        )

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QMainWindow, QWidget {
                background: #f6f7f9;
                color: #202124;
            }
            QLabel#heading {
                font-size: 22pt;
                font-weight: 700;
            }
            QLabel#description, QLabel#dropSubtitle {
                color: #62666d;
            }
            QFrame#dropArea {
                background: #ffffff;
                border: 2px dashed #aeb4bd;
                border-radius: 12px;
            }
            QLabel#dropTitle {
                font-size: 14pt;
                font-weight: 600;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #dfe2e6;
                border-radius: 8px;
                gridline-color: #eceef1;
            }
            QHeaderView::section {
                background: #eef0f3;
                padding: 7px;
                border: none;
                border-bottom: 1px solid #dfe2e6;
                font-weight: 600;
            }
            QPushButton, QComboBox {
                min-height: 32px;
                padding: 0 10px;
            }
            QPushButton#primaryButton {
                font-weight: 700;
                min-width: 145px;
            }
            QProgressBar {
                min-height: 22px;
                text-align: center;
            }
            """
        )

    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add media files", "", VIDEO_FILTER
        )
        if paths:
            self.add_paths(paths)

    def add_paths(self, paths: list[str]) -> None:
        known = {str(path).lower() for path in self.files}
        added = 0

        for raw in paths:
            path = Path(raw)
            key = str(path).lower()
            if not path.is_file() or key in known:
                continue

            self.files.append(path)
            known.add(key)

            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.setItem(row, 1, QTableWidgetItem("—"))
            self.table.setItem(row, 2, QTableWidgetItem("Queued"))
            self.table.setItem(row, 3, QTableWidgetItem("—"))
            self.table.item(row, 0).setToolTip(str(path))
            added += 1

        if added:
            self.progress.setValue(0)
            self.progress.setFormat(f"{len(self.files)} file(s) queued")
        self._refresh_controls()

    def _remove_rows(self, rows: list[int]) -> None:
        for row in sorted(set(rows), reverse=True):
            if 0 <= row < len(self.files):
                self.table.removeRow(row)
                del self.files[row]

    def remove_selected(self) -> None:
        rows = [index.row() for index in self.table.selectedIndexes()]
        self._remove_rows(rows)
        self._refresh_controls()

    def clear_completed(self) -> None:
        rows = []
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 2)
            if status_item and status_item.text() == "Done":
                rows.append(row)

        self._remove_rows(rows)
        if not self.files:
            self.progress.setValue(0)
            self.progress.setFormat("Ready")
        else:
            self.progress.setFormat(
                f"{len(self.files)} file(s) remaining in the list"
            )
        self._refresh_controls()

    def clear_queue(self) -> None:
        self.files.clear()
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.progress.setFormat("Ready")
        self.last_output_directory = None
        self._refresh_controls()

    def output_mode_changed(self, index: int) -> None:
        custom = index == 1
        self.folder_button.setEnabled(custom and self.worker is None)

        if custom:
            if self.custom_output:
                self.output_label.setText(
                    f"Output: {self.custom_output}"
                )
            else:
                self.output_label.setText(
                    "Output: choose a custom folder"
                )
        else:
            self.output_label.setText(
                "Output: same folder as each source file"
            )

        self._save_preferences()

    def choose_output_folder(self) -> None:
        start = (
            str(self.custom_output)
            if self.custom_output and self.custom_output.exists()
            else ""
        )
        folder = QFileDialog.getExistingDirectory(
            self, "Choose output folder", start
        )
        if folder:
            self.custom_output = Path(folder)
            self.output_label.setText(
                f"Output: {self.custom_output}"
            )
            self._save_preferences()

    def _validate_dependencies(self) -> bool:
        try:
            find_binary("ffmpeg")
            find_binary("ffprobe")
            return True
        except FFmpegNotFoundError as exc:
            QMessageBox.critical(
                self,
                "FFmpeg not found",
                f"{exc}\n\nSee the README for the Windows setup options.",
            )
            return False

    def start_conversion(self) -> None:
        if not self.files or self.worker is not None:
            return

        if not self._validate_dependencies():
            return

        if (
            self.output_mode.currentIndex() == 1
            and self.custom_output is None
        ):
            self.choose_output_folder()
            if self.custom_output is None:
                return

        for row in range(self.table.rowCount()):
            self.table.item(row, 1).setText("—")
            self.table.item(row, 2).setText("Queued")
            self.table.item(row, 3).setText("—")

        mode = QUALITY_MODES[self.quality.currentText()]
        output_dir = (
            self.custom_output
            if self.output_mode.currentIndex() == 1
            else None
        )

        self.worker = ConversionWorker(
            list(self.files), mode, output_dir, self
        )
        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_info.connect(self.on_file_info)
        self.worker.file_progress.connect(self.on_file_progress)
        self.worker.file_finished.connect(self.on_file_finished)
        self.worker.batch_finished.connect(self.on_batch_finished)
        self.worker.finished.connect(self.worker.deleteLater)

        self.progress.setValue(0)
        self.progress.setFormat(
            f"Starting · 0 / {len(self.files)}"
        )
        self._refresh_controls()
        self.worker.start()

    def cancel_conversion(self) -> None:
        if self.worker:
            self.cancel_button.setEnabled(False)
            self.progress.setFormat("Cancelling…")
            self.worker.cancel()

    def on_file_started(self, index: int, name: str) -> None:
        self.table.item(index, 2).setText("Preparing…")
        self.progress.setFormat(
            f"{name} · file {index + 1} of {len(self.files)}"
        )

    def on_file_info(self, index: int, summary: str) -> None:
        self.table.item(index, 1).setText(summary)

    def on_file_progress(self, index: int, percent: int) -> None:
        self.table.item(index, 2).setText(
            f"Converting · {percent}%"
        )
        total = max(1, len(self.files))
        overall = int(
            ((index + percent / 100) / total) * 100
        )
        self.progress.setValue(overall)
        self.progress.setFormat(
            f"Converting · file {index + 1} of {total} · {percent}%"
        )

    def on_file_finished(
        self,
        index: int,
        success: bool,
        output: str,
        error: str,
    ) -> None:
        if success:
            self.table.item(index, 2).setText("Done")
            self.table.item(index, 3).setText(output)
            self.table.item(index, 3).setToolTip(output)
            self.last_output_directory = Path(output).parent
        else:
            self.table.item(index, 2).setText("Failed")
            self.table.item(index, 3).setText(error)
            self.table.item(index, 3).setToolTip(error)

    def on_batch_finished(
        self,
        completed: int,
        failed: int,
        cancelled: bool,
    ) -> None:
        self.worker = None

        if cancelled:
            for row in range(self.table.rowCount()):
                status_item = self.table.item(row, 2)
                if (
                    status_item
                    and status_item.text() not in TERMINAL_STATUSES
                ):
                    status_item.setText("Cancelled")

            self.progress.setFormat(
                f"Cancelled · {completed} completed, {failed} failed"
            )
        else:
            self.progress.setValue(100)
            message = f"Finished · {completed} completed"
            if failed:
                message += f", {failed} failed"
            self.progress.setFormat(message)

            notification = (
                f"Conversion finished. {completed} completed, "
                f"{failed} failed."
            )
            if self.tray.isVisible():
                self.tray.showMessage(
                    "Ratanak Media Converter",
                    notification,
                    QSystemTrayIcon.MessageIcon.Information,
                    5000,
                )
            else:
                QMessageBox.information(
                    self,
                    "Conversion finished",
                    notification,
                )

        self._refresh_controls()

    def open_output_folder(self) -> None:
        directory = self.last_output_directory

        if (
            directory is None
            and self.output_mode.currentIndex() == 1
        ):
            directory = self.custom_output

        if directory is None and self.files:
            directory = self.files[0].parent

        if directory and directory.exists():
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(directory))
            )

    def _refresh_controls(self) -> None:
        running = self.worker is not None
        has_completed = any(
            self.table.item(row, 2)
            and self.table.item(row, 2).text() == "Done"
            for row in range(self.table.rowCount())
        )

        self.add_button.setEnabled(not running)
        self.remove_button.setEnabled(
            bool(self.files) and not running
        )
        self.clear_completed_button.setEnabled(
            has_completed and not running
        )
        self.clear_button.setEnabled(
            bool(self.files) and not running
        )
        self.start_button.setEnabled(
            bool(self.files) and not running
        )
        self.cancel_button.setEnabled(running)
        self.quality.setEnabled(not running)
        self.output_mode.setEnabled(not running)
        self.folder_button.setEnabled(
            not running and self.output_mode.currentIndex() == 1
        )
        self.drop_area.setEnabled(not running)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None:
            answer = QMessageBox.question(
                self,
                "Conversion in progress",
                "A conversion is still running. Cancel it and close the app?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

            self.worker.cancel()
            self.worker.wait(3000)

        self.settings.setValue(
            "window/geometry", self.saveGeometry()
        )
        self._save_preferences()
        event.accept()
