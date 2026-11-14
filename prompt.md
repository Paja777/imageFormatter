# PROJECT: Professional Image Resizer & Format Converter — Windows Desktop Application

## YOUR ROLE

You are a senior Python desktop software engineer, UI/UX designer, and software architect specializing in production-ready Windows applications.

Your task is to **design, implement, test, and package a complete, professional desktop image-processing application**.

Work autonomously in the current Cursor workspace. Make reasonable engineering decisions without asking unnecessary questions.

**IMPORTANT: Build a fully functional application, not a prototype, mockup, proof of concept, or partial implementation.**

The final deliverable must be a polished Windows desktop application that can be distributed to nontechnical clients through a standalone Windows installer.

---

## 1. PROJECT OVERVIEW

Create a modern, user-friendly desktop application that allows users to:

1. Drag and drop an image into the application.
2. Preview the uploaded image.
3. Select one or multiple predefined output image dimensions.
4. Choose how the image should be resized or cropped.
5. Preview the resulting image for each selected dimension.
6. Export all selected formats in one operation.
7. Save the processed images to a local folder.

The application must work **100% offline**, without requiring an internet connection, backend server, external API, user account, or subscription.

The target users are nontechnical Windows users who need to quickly prepare images for websites, social media, banners, and other digital content.

## 2. REQUIRED TECHNOLOGY STACK

Use the following technologies:

- **Python 3.12+** — application language.
- **PySide6 (Qt)** — desktop GUI framework.
- **Pillow** — image manipulation.
- **PyInstaller** — executable packaging.
- **Inno Setup** — Windows installer generation.
- **pytest** — automated testing.

Do not use Electron, a web-based frontend, Flask, FastAPI, or any browser-dependent interface.

Use native desktop GUI components with modern styling.

Avoid unnecessary dependencies and overengineering.

## 3. USER INTERFACE & EXPERIENCE

The application should look like a modern, premium desktop product rather than a traditional Python utility.

### Design principles

- Modern, minimal, professional interface.
- Clean typography and consistent spacing.
- Light and dark themes.
- Rounded cards and buttons.
- Subtle hover and selection effects.
- Clear visual hierarchy.
- Responsive layouts that adapt when the window is resized.
- Intuitive interaction for nontechnical users.
- No unnecessary screens or complicated navigation.

### Main window layout

**LEFT PANEL — Image Input**

- Large drag-and-drop area.
- "Browse Image" button.
- Original image preview.
- Original filename.
- Original dimensions.
- File format and file size.
- Button to replace the image.

**RIGHT PANEL — Output Settings**

- Predefined dimension presets.
- Multi-selection of presets using checkboxes or selectable cards.
- Resize mode selection.
- Output image format selection.
- JPEG/WebP quality setting when applicable.
- Export directory selection.
- Export button.

**PREVIEW AREA**

- Show a preview of the processed image.
- Allow switching between selected presets.
- Clearly show resulting output dimensions.
- Visually indicate cropping boundaries when applicable.
- Support manual crop positioning.

The interface should remain usable at common desktop resolutions, including 1366×768.

Make long preset lists scrollable if necessary.

### User feedback

Provide:

- Progress indicator during export.
- Success notification.
- Useful error messages.
- Export summary.
- "Open Output Folder" action after successful export.

Do not block the UI during image processing or export.

## 4. DRAG & DROP IMAGE INPUT

Implement drag-and-drop functionality.

Supported source formats:

- JPG / JPEG
- PNG
- WEBP
- BMP
- TIFF

Also provide a file-selection dialog.

Requirements:

- Reject unsupported files gracefully.
- Detect corrupt or unreadable images.
- Handle very large source images safely.
- Preserve correct image orientation using EXIF metadata.
- Display useful metadata.
- Allow users to replace the source image without restarting the application.

The initial version only needs to process one source image at a time.

Do not implement batch processing of multiple source images unless the core application is already complete.

## 5. PREDEFINED IMAGE DIMENSIONS

Implement a preset system with predefined output dimensions.

Initial presets:

| Preset | Width | Height |
|---|---:|---:|
| Full HD | 1920 | 1080 |
| HD | 1280 | 720 |
| Square | 1080 | 1080 |
| Portrait | 1080 | 1350 |
| Story / Reel | 1080 | 1920 |
| Web Banner | 1200 | 628 |
| Website Hero | 1920 | 600 |
| Thumbnail | 400 | 400 |
| Small Thumbnail | 150 | 150 |

Requirements:

- Users can select multiple presets simultaneously.
- Each selected preset produces a separate output image.
- Users can deselect presets.
- Show dimensions and aspect ratios clearly.
- Prevent duplicate output naming collisions.
- Presets must be loaded from a configurable local JSON file rather than hardcoded throughout the GUI.

### Custom presets

Allow users to:

- Create a custom preset.
- Enter width and height.
- Assign a name.
- Save it for future sessions.
- Edit or delete their own custom presets.

Store user presets in the appropriate Windows user application-data directory, not in the installed application directory.

Validate dimensions and prevent invalid presets.

## 6. IMAGE RESIZING MODES

Implement three resizing modes:

### A. CROP — Fill target dimensions

Resize the image proportionally until the entire target area is filled.

Crop the excess image area.

- Preserve aspect ratio.
- Never distort the image.
- Default crop position: center.
- Allow manual adjustment of crop position.
- Produce the exact requested output dimensions.

Use high-quality Pillow resampling.

### B. FIT — Preserve the full image

Resize the image proportionally to fit inside the target dimensions.

- Preserve the entire original image.
- Do not crop.
- Add padding when aspect ratios differ.
- Allow background color selection.
- Support transparency where the output format allows it.
- Produce the exact requested output dimensions.

### C. STRETCH — Force exact dimensions

Resize the image directly to the requested dimensions.

- Output exact width and height.
- Ignore original aspect ratio.
- Clearly inform the user that stretching may distort the image.

### Critical requirements

The exported dimensions must always match the selected preset exactly.

Never accidentally change the intended aspect ratio in CROP or FIT modes.

Use `Image.Resampling.LANCZOS` when appropriate.

Correctly handle alpha channels and color mode conversion.

## 7. IMAGE PREVIEW & MANUAL CROP CONTROL

Implement a useful and accurate preview system.

Requirements:

- Preview must reflect the selected preset and resizing mode.
- Maintain correct aspect ratio.
- Show resulting dimensions.
- Support zoom-to-fit.
- Support manual crop repositioning with mouse dragging.
- Do not confuse preview resolution with export resolution.

For CROP mode:

- Allow the user to reposition the visible crop area.
- Keep the crop region constrained within the source image.
- Store crop position independently for each selected preset.
- Ensure exported results match the preview crop.

For FIT mode:

- Preview the padding and chosen background color.

For STRETCH mode:

- Preview the potentially distorted result.

Create a shared image transformation pipeline so preview and export use the same underlying geometry and rendering logic.

Do not implement separate inconsistent algorithms for preview and export.

## 8. EXPORT FUNCTIONALITY

Allow users to choose the output file format:

- JPEG
- PNG
- WEBP

Export all selected dimension presets in one operation.

Example input:

`product-photo.jpg`

Selected presets:

- Full HD
- Square
- Story / Reel

Expected output:

```text
product-photo/
├── product-photo_1920x1080.jpg
├── product-photo_1080x1080.jpg
└── product-photo_1080x1920.jpg
```

Requirements:

- Let the user select an export destination.
- Use meaningful, filesystem-safe filenames.
- Avoid overwriting files without an explicit user decision.
- Support image-quality selection for JPEG and WEBP.
- Preserve transparency for supported output formats.
- Handle transparent images exported as JPEG using a configurable background color.
- Ensure image orientation is correct.
- Correctly convert non-RGB images when required.
- Strip obsolete orientation metadata after applying orientation.
- Export asynchronously using Qt worker threads.
- Keep the application responsive.
- Report progress and individual file failures.
- Show a final export summary.

Use a sensible default quality setting of 90 for lossy formats.

Do not silently upscale without making it clear to the user when the output dimensions exceed the source resolution.

## 9. APPLICATION ARCHITECTURE

Use a clean, maintainable architecture.

Suggested project structure:

```text
image-resizer/
├── src/
│   └── image_resizer/
│       ├── __init__.py
│       ├── main.py
│       ├── app.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── drop_zone.py
│       │   ├── image_preview.py
│       │   ├── preset_selector.py
│       │   └── styles/
│       ├── core/
│       │   ├── image_processor.py
│       │   ├── crop_geometry.py
│       │   ├── export_service.py
│       │   └── presets.py
│       ├── models/
│       │   └── settings.py
│       ├── services/
│       │   ├── config_service.py
│       │   └── image_loader.py
│       └── resources/
│           └── default_presets.json
├── tests/
├── packaging/
│   ├── pyinstaller.spec
│   ├── installer.iss
│   └── build_windows.ps1
├── requirements.txt
├── pyproject.toml
└── README.md
```

This is a suggested structure, not a requirement to create unnecessary files.

Keep the design pragmatic.

Architectural requirements:

- Separate GUI components from image-processing logic.
- Keep transformations independent of Qt widgets where possible.
- Centralize preset configuration.
- Use Python type hints.
- Use dataclasses or typed models where appropriate.
- Avoid global mutable application state.
- Use clear naming and maintainable functions.
- Make the application easy to extend.

## 10. SETTINGS & PERSISTENCE

Persist the following user preferences locally:

- Last export directory.
- Selected output format.
- Image quality.
- Theme.
- Custom presets.
- Preferred resize mode.
- Padding/background color.

Use JSON or QSettings where appropriate.

Store persistent settings in a user-writable location, such as the Windows AppData directory.

The application must not require administrator privileges for normal use.

## 11. ERROR HANDLING & SECURITY

Implement robust error handling.

Consider:

- Unsupported image format.
- Corrupted source image.
- Missing source image.
- Invalid preset dimensions.
- Export directory unavailable.
- Permission denied.
- Insufficient disk space.
- Failed image conversion.
- Extremely large image.
- Interrupted export.
- Invalid saved configuration.
- Filename collisions.

Do not freeze or crash the application on recoverable errors.

Use safe, deterministic handling of untrusted image files.

Do not silently disable Pillow decompression-bomb protections.

Do not embed credentials, analytics, telemetry, or network services.

## 12. WINDOWS PACKAGING

This application must be distributable to Windows clients.

Implement a complete Windows packaging workflow.

### PyInstaller

Generate a Windows executable that:

- Bundles Python.
- Bundles PySide6 and Pillow dependencies.
- Does not require Python on the client's PC.
- Includes icons and required resources.
- Starts without displaying a console window.
- Uses reliable packaged-resource paths.

Prefer PyInstaller one-directory mode for the installer because it is generally easier to maintain and troubleshoot.

### Inno Setup

Create an installer script that:

- Installs the packaged application.
- Creates Start Menu shortcuts.
- Optionally creates a desktop shortcut.
- Provides a standard uninstall mechanism.
- Includes application name and version.
- Installs without requiring Python or development tools.
- Uses per-user installation by default where practical.
- Supports an upgrade path for future versions.

Provide a PowerShell build script to automate packaging.

Expected Windows output:

```text
dist/
└── ImageResizer/
    └── ImageResizer.exe

installer/
└── ImageResizer-Setup-1.0.0.exe
```

The final installer should be generated on Windows using the documented build environment.

If running in a non-Windows environment, create and validate all build scripts and configuration, but do not claim that an actual Windows `.exe` installer was successfully built.

### Additional requirements

- Include a professional application icon if available or create a suitable original vector/icon asset using supported local tooling.
- Handle resource paths correctly in both development and packaged environments.
- Document the complete Windows build process.
- Explain that unsigned executables may trigger Windows SmartScreen warnings and that code signing is recommended for client distribution.

## 13. AUTOMATED TESTS

Write meaningful pytest tests for the core image-processing functions.

At minimum, verify:

1. Correct output dimensions for every resize mode.
2. CROP preserves aspect ratio without stretching.
3. FIT preserves the complete source image.
4. STRETCH generates exact target dimensions.
5. Correct centered cropping.
6. Correct custom crop-position behavior.
7. Correct EXIF orientation processing.
8. Proper alpha-channel handling.
9. JPEG export from transparent PNG.
10. Multiple preset exports.
11. Invalid dimension rejection.
12. Filename collision handling.
13. Custom preset persistence.
14. Corrupted image handling.

Include tests using generated sample images that make geometry mistakes easy to detect.

Use a small number of focused UI tests if practical, without introducing substantial testing complexity.

## 14. PERFORMANCE REQUIREMENTS

The application should:

- Start quickly.
- Use thumbnails for UI previews rather than unnecessarily displaying full-resolution images.
- Avoid repeated expensive image decoding where possible.
- Keep processing off the GUI thread.
- Avoid unnecessary image copies.
- Release temporary resources appropriately.
- Handle images significantly larger than the output target.

Do not prematurely optimize at the expense of correctness.

For unusually large source images, display a clear warning or enforce a configurable, reasonable processing limit.

## 15. DESIGN DETAILS

Use a restrained, modern visual style.

Suggested palette:

- Primary blue: `#1362F8`
- Background: `#F8FAFC`
- Surface: `#FFFFFF`
- Text: `#0F172A`
- Secondary text: `#64748B`
- Border: `#E2E8F0`
- Success: `#16A34A`
- Dark background: `#0C1723`
- Dark surface: `#112031`

Design should emphasize usability rather than decoration.

Use icons consistently and avoid visual clutter.

The export action should be immediately discoverable.

Disabled actions should clearly indicate why they are unavailable.

## 16. IMPLEMENTATION WORKFLOW

Follow this development sequence:

**Phase 1 — Workspace analysis**

- Inspect the existing workspace.
- Identify whether a project already exists.
- Preserve existing useful work.
- Establish dependencies and project structure.

**Phase 2 — Core processing**

- Implement image loading.
- Implement resize modes.
- Implement crop geometry.
- Implement preset management.
- Implement export functionality.

**Phase 3 — Desktop UI**

- Build the main window.
- Implement drag and drop.
- Implement preset selection.
- Implement previews and crop controls.
- Implement export interactions.

**Phase 4 — Quality and robustness**

- Implement error handling.
- Implement local settings persistence.
- Implement tests.
- Fix issues discovered during testing.

**Phase 5 — Windows distribution**

- Configure PyInstaller.
- Create Inno Setup installer script.
- Create automated Windows build script.
- Validate packaging where the environment permits.

**Phase 6 — Documentation**

Write a clear README containing:

- Application overview.
- Main features.
- Development setup.
- How to run the application.
- How to run tests.
- How to create the Windows installer.
- Supported image formats.
- Known limitations.

## 17. ACCEPTANCE CRITERIA

Consider the task complete only when:

- The application launches successfully in the available development environment.
- An image can be loaded by drag and drop or file selection.
- The original image is previewed correctly.
- Multiple output presets can be selected.
- Every resize mode works correctly.
- Crop positioning is functional.
- Output previews agree with exported transformations.
- Selected presets can be exported in one operation.
- Generated images have exactly the requested dimensions.
- Custom presets and preferences persist after restart.
- The UI stays responsive during export.
- Errors are handled gracefully.
- Automated core tests pass.
- Windows packaging scripts exist and are valid.
- A working Windows installer has been built and smoke-tested if the environment supports it.

Do not mark a criterion as complete unless it has been implemented and verified.

## 18. IMPORTANT DEVELOPMENT RULES

1. Do not stop after creating the project structure.
2. Do not implement placeholder buttons or nonfunctional UI elements.
3. Do not use simulated image processing.
4. Do not add unnecessary backend or networking components.
5. Do not replace native desktop functionality with a web interface.
6. Do not overengineer the architecture with unnecessary patterns.
7. Do not repeatedly request approval for routine engineering decisions.
8. Prefer implementation over lengthy theoretical explanations.
9. Run tests and fix failures whenever your environment allows.
10. Preserve existing workspace changes that are unrelated to this task.
11. Be transparent about functionality that could not be tested or built.
12. Prioritize reliability, usability, and correct image transformation over optional visual effects.

## 19. FINAL RESPONSE REQUIRED

After implementation, provide a concise technical report containing:

- What was implemented.
- How to start the app in development.
- How to build the Windows installer.
- Which tests were executed and their results.
- Where the executable and installer are located, if successfully built.
- Any remaining limitations.

**BEGIN IMPLEMENTATION NOW.**

Inspect the project workspace first, then proceed directly through implementation, testing, and packaging.

The goal is a complete, maintainable, professional Windows desktop application that a real client can install and use independently.