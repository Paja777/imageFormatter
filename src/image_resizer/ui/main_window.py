"""Main window: one source image, many output sizes, one export."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from image_resizer.core.crop_geometry import CropAnchor, Size
from image_resizer.core.errors import ImageResizerError
from image_resizer.core.export_service import ExportSummary, filesystem_stem
from image_resizer.core.presets import Preset, PresetStore
from image_resizer.models.settings import WHITE, CollisionPolicy, OutputFormat
from image_resizer.services.image_loader import LoadedImage
from image_resizer.services.preferences import (
    Preferences,
    PreferencesStore,
    default_export_directory,
)
from image_resizer.ui.dialogs import ExportSummaryDialog, PresetEditorDialog
from image_resizer.ui.drop_zone import first_supported_image, local_paths_from_mime
from image_resizer.ui.image_preview import PreviewPanel
from image_resizer.ui.images import pil_to_qimage
from image_resizer.ui.output_panel import OutputPanel
from image_resizer.ui.source_panel import SourcePanel
from image_resizer.ui.styles import apply_theme
from image_resizer.ui.workers import ExportWorker, LoadImageWorker


class Banner(QFrame):
    """A single dismissible status line under the header."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("banner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._label = QLabel("")
        self._label.setObjectName("bannerLabel")
        self._label.setWordWrap(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._label)
        self.setVisible(False)

    def set_message(self, text: str, kind: str = "warning") -> None:
        self._label.setText(text)
        self.setProperty("kind", kind)
        self._label.setProperty("kind", kind)
        self.setVisible(bool(text))
        for widget in (self, self._label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def clear(self) -> None:
        self.set_message("", "info")


class MainWindow(QMainWindow):
    """Desktop shell around the image pipeline."""

    image_loaded = Signal()
    image_failed = Signal(str)
    export_completed = Signal(object)
    export_failed = Signal(str)

    def __init__(self, presets: PresetStore, preferences: PreferencesStore) -> None:
        super().__init__()
        self._presets = presets
        self._preference_store = preferences
        self._saved = preferences.get()
        self._theme = self._saved.theme if self._saved.theme in {"light", "dark"} else "light"
        self._loaded: LoadedImage | None = None
        self._qimage: QImage | None = None
        self._checked: set[str] = set()
        self._preview_id: str | None = None
        self._anchors: dict[str, CropAnchor] = {}
        self._loading = False
        self._exporting = False
        self._queued_path: str | None = None
        self._load_thread: QThread | None = None
        self._load_worker: LoadImageWorker | None = None
        self._export_thread: QThread | None = None
        self._export_worker: ExportWorker | None = None
        self._summary_dialog: ExportSummaryDialog | None = None
        self._planned_folder: Path | None = None

        self.setWindowTitle("Image Resizer")
        self.setMinimumSize(1040, 640)
        self.resize(1280, 720)
        self.setAcceptDrops(True)
        self._build()
        directory = self._saved.export_directory or default_export_directory()
        self._output.apply_preferences(self._saved, directory)
        self._reload_presets()
        self._connect()
        notes = self._presets.warnings + self._preference_store.warnings
        if notes:
            self._banner.set_message(" ".join(notes), "warning")
        self._update_actions()

    def open_image(self, path: str) -> None:
        """Load ``path`` on a worker thread. A newer request waits until it finishes."""
        if self._exporting:
            self._banner.set_message(
                "Wait for the export to finish before replacing the image.",
                "warning",
            )
            return
        if self._loading:
            self._queued_path = path
            return
        self._begin_load(path)

    def import_local_paths(self, paths: list[str]) -> None:
        """Import the first supported image in ``paths``."""
        if self._exporting:
            self._banner.set_message(
                "Wait for the export to finish before replacing the image.",
                "warning",
            )
            return
        if not paths:
            self._banner.set_message("Only local image files can be opened.", "warning")
            return
        image = first_supported_image(paths)
        if image is None:
            if any(Path(path).is_dir() for path in paths):
                self._banner.set_message(
                    "Folders are not imported. Choose a single image file.",
                    "warning",
                )
            else:
                self._banner.set_message(
                    "Unsupported image format. Use JPG, PNG, WEBP, BMP, or TIFF.",
                    "warning",
                )
            return
        self.open_image(image)

    def crop_anchor_for(self, preset_id: str) -> CropAnchor:
        return self._anchors.get(preset_id, CropAnchor())

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        self.import_local_paths(local_paths_from_mime(event.mimeData()))
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._persist()
        if self._export_worker is not None:
            self._export_worker.cancel()
        for thread in (self._load_thread, self._export_thread):
            if thread is not None and thread.isRunning():
                thread.wait(8000)
        still_running = [
            thread
            for thread in (self._load_thread, self._export_thread)
            if thread is not None and thread.isRunning()
        ]
        if still_running:
            event.ignore()
            self._banner.set_message("Still finishing the current task.", "warning")
            return
        super().closeEvent(event)

    def _build(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        title = QLabel("Image Resizer")
        title.setObjectName("title")
        subtitle = QLabel("Resize and export for web, social, and banners")
        subtitle.setObjectName("muted")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        self._dark = QCheckBox("Dark theme")
        self._dark.setObjectName("darkTheme")
        self._dark.setChecked(self._theme == "dark")

        header = QHBoxLayout()
        header.addLayout(titles, stretch=1)
        header.addWidget(self._dark, alignment=Qt.AlignmentFlag.AlignTop)

        self._banner = Banner()
        self._source = SourcePanel()
        self._preview = PreviewPanel()
        self._output = OutputPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._source)
        splitter.addWidget(self._preview)
        splitter.addWidget(self._output)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 4)
        splitter.setSizes([320, 560, 380])

        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)
        root.addLayout(header)
        root.addWidget(self._banner)
        root.addWidget(splitter, stretch=1)

        open_shortcut = QShortcut(QKeySequence.StandardKey.Open, self)
        open_shortcut.activated.connect(self._browse)
        export_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        export_shortcut.activated.connect(self._start_export)

    def _connect(self) -> None:
        self._dark.toggled.connect(self._on_theme)
        self._source.browse_requested.connect(self._browse)
        self._source.paths_dropped.connect(self.import_local_paths)
        self._output.values_changed.connect(self._refresh_preview)
        self._output.values_changed.connect(self._update_actions)
        self._output.commit_changed.connect(self._persist)
        self._output.export_requested.connect(self._start_export)
        self._output.cancel_requested.connect(self._cancel_export)
        self._output.add_preset_requested.connect(self._add_preset)
        self._output.edit_preset_requested.connect(self._edit_preset)
        self._output.delete_preset_requested.connect(self._delete_preset)
        self._output.check_changed.connect(self._on_checked)
        self._output.preview_requested.connect(self._on_preview_requested)
        self._preview.preview_requested.connect(self._on_preview_requested)
        self._preview.anchor_changed.connect(self._on_anchor)

    def _browse(self) -> None:
        if self._exporting:
            self._banner.set_message(
                "Wait for the export to finish before replacing the image.",
                "warning",
            )
            return
        if self._loaded is not None:
            start = str(self._loaded.metadata.path.parent)
        else:
            start = self._output.directory() or str(Path.home())
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Choose an image",
            start,
            "Images (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)",
        )
        if path:
            self.open_image(path)

    def _begin_load(self, path: str) -> None:
        self._loading = True
        self._banner.set_message("Loading image…", "info")
        self._update_actions()
        worker = LoadImageWorker(path)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._on_loaded)
        worker.failed.connect(self._on_load_failed)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_load_thread_finished)
        self._load_thread = thread
        self._load_worker = worker
        thread.start()

    def _on_loaded(self, loaded: LoadedImage, preview: Image.Image) -> None:
        self._loading = False
        self._loaded = loaded
        self._qimage = pil_to_qimage(preview)
        self._anchors.clear()
        self._source.set_image(loaded.metadata, self._qimage)
        self._banner.clear()
        self._refresh_preview()
        self._update_actions()
        self.image_loaded.emit()

    def _on_load_failed(self, message: str) -> None:
        self._loading = False
        self._banner.set_message(message, "warning")
        self._update_actions()
        self.image_failed.emit(message)

    def _on_load_thread_finished(self) -> None:
        thread = self.sender()
        if thread is self._load_thread:
            self._load_thread = None
            self._load_worker = None
            queued = self._queued_path
            self._queued_path = None
            if isinstance(thread, QThread):
                thread.deleteLater()
            if queued:
                self._begin_load(queued)
        elif isinstance(thread, QThread):
            thread.deleteLater()

    def _on_theme(self, dark: bool) -> None:
        self._theme = "dark" if dark else "light"
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, self._theme)
        self._refresh_preview()
        self._persist()

    def _on_checked(self, preset_id: str, checked: bool) -> None:
        if checked:
            self._checked.add(preset_id)
        else:
            self._checked.discard(preset_id)
            if self._preview_id == preset_id:
                remaining = self._selected_presets()
                self._preview_id = remaining[0].id if remaining else None
        self._output.set_marks(self._checked, self._preview_id)
        self._refresh_preview()
        self._update_actions()

    def _on_preview_requested(self, preset_id: str) -> None:
        if self._presets.get(preset_id) is None:
            return
        self._preview_id = preset_id
        self._output.set_marks(self._checked, self._preview_id)
        self._refresh_preview()

    def _on_anchor(self, anchor: CropAnchor) -> None:
        if self._preview_id is None:
            return
        self._anchors[self._preview_id] = anchor

    def _refresh_preview(self) -> None:
        preset = self._preview_preset()
        settings = self._output.settings()
        source = None
        if self._loaded is not None:
            source = Size(self._loaded.metadata.width, self._loaded.metadata.height)
        anchor = self._anchors.get(preset.id, CropAnchor()) if preset is not None else CropAnchor()
        self._preview.set_scene(
            image=self._qimage,
            source=source,
            preset=preset,
            choices=self._selected_presets(),
            mode=settings.mode,
            anchor=anchor,
            background=settings.background,
            flatten_alpha=settings.output_format is OutputFormat.JPEG,
            source_has_alpha=self._loaded is not None and self._loaded.image.mode == "RGBA",
            dark=self._theme == "dark",
        )
        self._output.set_source_has_alpha(
            self._loaded is not None and self._loaded.image.mode == "RGBA"
        )
        self._output.set_custom_actions(self._custom_preview_available())

    def _selected_presets(self) -> list[Preset]:
        return [preset for preset in self._presets.presets() if preset.id in self._checked]

    def _preview_preset(self) -> Preset | None:
        if self._preview_id is None:
            return None
        return self._presets.get(self._preview_id)

    def _custom_preview_available(self) -> bool:
        preset = self._preview_preset()
        return preset is not None and not preset.builtin and not self._exporting

    def _update_actions(self) -> None:
        reason = self._export_block_reason()
        self._output.set_export_state(
            enabled=reason is None,
            reason="" if reason is None else reason,
            count=len(self._selected_presets()),
        )
        self._source.set_busy(self._exporting)
        self._preview.set_interaction_enabled(not self._exporting)
        self._output.set_custom_actions(self._custom_preview_available())

    def _export_block_reason(self) -> str | None:
        if self._exporting:
            return "Export is running."
        if self._loading:
            return "Wait for the image to finish loading."
        if self._loaded is None:
            return "Add an image first."
        if not self._selected_presets():
            return "Check at least one output size."
        if not self._output.directory():
            return "Choose an export folder."
        return None

    def _start_export(self) -> None:
        reason = self._export_block_reason()
        if reason is not None or self._loaded is None:
            if reason:
                self._output.set_status(reason, "warning")
            return
        settings = self._output.settings()
        if settings.collision_policy is CollisionPolicy.OVERWRITE:
            answer = QMessageBox.question(
                self,
                "Overwrite files",
                "Existing files in the output folder will be replaced. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        presets = tuple(self._selected_presets())
        anchors = {
            preset.id: self._anchors.get(preset.id, CropAnchor())
            for preset in presets
        }
        self._planned_folder = Path(settings.directory) / filesystem_stem(self._loaded.metadata.filename)
        self._exporting = True
        self._output.set_busy(True)
        self._output.set_status("Exporting…", "muted")
        self._output.set_progress(0, len(presets))
        self._update_actions()
        worker = ExportWorker(
            self._loaded.image,
            self._loaded.metadata.filename,
            presets,
            settings.directory,
            settings.mode,
            settings.output_format,
            settings.quality,
            settings.background,
            anchors,
            settings.collision_policy,
        )
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._output.set_progress)
        worker.succeeded.connect(self._on_export_finished)
        worker.failed.connect(self._on_export_failed)
        worker.cancelled.connect(self._on_export_cancelled)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_export_thread_finished)
        self._export_thread = thread
        self._export_worker = worker
        thread.start()

    def _cancel_export(self) -> None:
        if self._export_worker is not None:
            self._export_worker.cancel()

    def _on_export_finished(self, summary: ExportSummary) -> None:
        self._finish_export_ui()
        self._output.set_output_folder(str(summary.output_directory))
        saved = len(summary.succeeded)
        if summary.failed and not saved:
            self._output.set_status("Export failed. See the summary for details.", "warning")
        elif summary.failed:
            self._output.set_status(
                f"Saved {saved}. {len(summary.failed)} could not be written.",
                "warning",
            )
        else:
            noun = "image" if saved == 1 else "images"
            self._output.set_status(f"Saved {saved} {noun}.", "success")
        self._show_summary(summary)
        self._persist()
        self.export_completed.emit(summary)

    def _on_export_failed(self, message: str) -> None:
        self._finish_export_ui()
        self._output.set_status(message, "warning")
        self._banner.set_message(message, "warning")
        self.export_failed.emit(message)

    def _on_export_cancelled(self) -> None:
        self._finish_export_ui()
        folder = self._planned_folder
        if folder is not None:
            self._output.set_output_folder(str(folder))
            message = f"Export cancelled. Images already written were kept in {folder}."
        else:
            message = "Export cancelled. Images already written were kept."
        self._output.set_status(message, "warning")

    def _finish_export_ui(self) -> None:
        self._exporting = False
        self._output.set_busy(False)
        self._update_actions()

    def _on_export_thread_finished(self) -> None:
        thread = self.sender()
        if thread is self._export_thread:
            self._export_thread = None
            self._export_worker = None
        if isinstance(thread, QThread):
            thread.deleteLater()

    def _show_summary(self, summary: ExportSummary) -> None:
        dialog = ExportSummaryDialog(summary, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        previous = self._summary_dialog
        self._summary_dialog = dialog
        dialog.destroyed.connect(lambda *_args, dialog=dialog: self._forget_summary(dialog))
        if previous is not None:
            previous.close()
        dialog.show()

    def _forget_summary(self, dialog: ExportSummaryDialog) -> None:
        if self._summary_dialog is dialog:
            self._summary_dialog = None

    def _add_preset(self) -> None:
        created: dict[str, Preset] = {}

        def validate(name: str, width: int, height: int) -> None:
            created["preset"] = self._presets.add_custom(name, width, height)

        dialog = PresetEditorDialog(self, title="New preset", validate=validate)
        if not _dialog_accepted(dialog.exec()):
            return
        preset = created.get("preset")
        if preset is None:
            return
        self._checked.add(preset.id)
        self._preview_id = preset.id
        self._reload_presets()

    def _edit_preset(self) -> None:
        current = self._preview_preset()
        if current is None or current.builtin:
            return
        created: dict[str, Preset] = {}

        def validate(name: str, width: int, height: int) -> None:
            created["preset"] = self._presets.update_custom(
                current.id,
                name=name,
                width=width,
                height=height,
            )

        dialog = PresetEditorDialog(
            self,
            title="Edit preset",
            name=current.name,
            width=current.width,
            height=current.height,
            validate=validate,
        )
        if not _dialog_accepted(dialog.exec()):
            return
        self._reload_presets()

    def _delete_preset(self) -> None:
        current = self._preview_preset()
        if current is None or current.builtin:
            return
        answer = QMessageBox.question(
            self,
            "Delete preset",
            f"Delete the custom preset '{current.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._presets.delete_custom(current.id)
        except ImageResizerError as exc:
            self._banner.set_message(str(exc), "warning")
            return
        self._checked.discard(current.id)
        self._anchors.pop(current.id, None)
        if self._preview_id == current.id:
            self._preview_id = None
        self._reload_presets()

    def _reload_presets(self) -> None:
        known = {preset.id for preset in self._presets.presets()}
        self._checked &= known
        self._anchors = {key: value for key, value in self._anchors.items() if key in known}
        if self._preview_id not in known:
            selected = self._selected_presets()
            self._preview_id = selected[0].id if selected else None
        self._output.set_presets(self._presets.presets(), self._checked, self._preview_id)
        self._refresh_preview()
        self._update_actions()

    def _collect_preferences(self) -> Preferences:
        settings = self._output.settings()
        background = settings.background if settings.background is not None else WHITE
        return Preferences(
            export_directory=settings.directory,
            output_format=settings.output_format,
            quality=settings.quality,
            theme=self._theme,
            resize_mode=settings.mode,
            background=background,
            collision_policy=settings.collision_policy,
        )

    def _persist(self) -> None:
        try:
            self._preference_store.update(self._collect_preferences())
        except OSError as exc:
            self._banner.set_message(f"Could not save settings: {exc}", "warning")


def _dialog_accepted(result: object) -> bool:
    return int(result) == int(QDialog.DialogCode.Accepted)
