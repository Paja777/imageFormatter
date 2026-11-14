"""Recoverable failures raised by the image pipeline."""


class ImageResizerError(Exception):
    """Base class for errors a caller can show to the user."""


class ImageNotFoundError(ImageResizerError):
    """The source path is missing or is not a file."""


class UnsupportedFormatError(ImageResizerError):
    """The file extension or encoded format is not supported."""


class CorruptedImageError(ImageResizerError):
    """The file looks like an image but cannot be decoded."""


class ImageTooLargeError(ImageResizerError):
    """The file exceeds a configured or decoder safety limit."""


class InvalidPresetError(ImageResizerError):
    """A preset name or size is not usable."""


class BuiltinPresetError(ImageResizerError):
    """A built-in preset cannot be edited or deleted."""


class PresetNotFoundError(ImageResizerError):
    """No custom preset exists for the given id."""


class ExportError(ImageResizerError):
    """Export could not start, or a single file could not be written."""
