"""Background load and export so the window stays responsive."""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QObject, Signal

from image_resizer.core.crop_geometry import CropAnchor
from image_resizer.core.errors import ImageResizerError
from image_resizer.core.export_service import export_image
from image_resizer.core.presets import Preset
from image_resizer.models.settings import CollisionPolicy, Color, OutputFormat, ResizeMode
from image_resizer.services.image_loader import LoadedImage, load_image
from image_resizer.ui.images import build_preview


class ExportCancelled(Exception):
    """Raised from the progress callback when the user cancels an export."""


class LoadImageWorker(QObject):
    """Decode one file and build the display copy off the GUI thread."""

    succeeded = Signal(object, object)
    failed = Signal(str)

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            loaded: LoadedImage = load_image(self._path)
            preview = build_preview(loaded.image)
        except ImageResizerError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(f"The image could not be opened: {exc}")
            return
        self.succeeded.emit(loaded, preview)


class ExportWorker(QObject):
    """Write every selected preset, reporting progress after each file."""

    progress = Signal(int, int)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        image: Image.Image,
        source_filename: str,
        presets: tuple[Preset, ...],
        destination: str,
        mode: ResizeMode,
        output_format: OutputFormat,
        quality: int,
        background: Color,
        crop_anchors: dict[str, CropAnchor],
        collision_policy: CollisionPolicy,
    ) -> None:
        super().__init__()
        self._image = image
        self._source_filename = source_filename
        self._presets = presets
        self._destination = destination
        self._mode = mode
        self._output_format = output_format
        self._quality = quality
        self._background = background
        self._crop_anchors = dict(crop_anchors)
        self._collision_policy = collision_policy
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        def report(done: int, total: int) -> None:
            self.progress.emit(done, total)
            if self._cancel:
                raise ExportCancelled()

        try:
            summary = export_image(
                self._image,
                self._source_filename,
                self._presets,
                self._destination,
                mode=self._mode,
                output_format=self._output_format,
                quality=self._quality,
                background=self._background,
                crop_anchors=self._crop_anchors,
                collision_policy=self._collision_policy,
                progress=report,
            )
        except ExportCancelled:
            self.cancelled.emit()
            return
        except ImageResizerError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(f"Export failed: {exc}")
            return
        self.succeeded.emit(summary)
