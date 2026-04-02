# ComfyUI Alpha Outline

A custom **Output Node** for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) that removes external background pixels using a pure-Python connected-component flood-fill (BFS) algorithm starting from the four image corners. Results are **saved directly to disk as transparent RGBA PNGs** — no output wires needed.

## Features

- **External Background Removal**: Flood-fills from all four corners, removing only pixels that are color-similar to the corner and connected to it. Interior subject pixels are never touched.
- **1-Pixel Gap Closure**: Automatically detects and seals single-pixel gaps in outlines, preventing flood-fill from leaking into the subject interior.
- **Transparent Trim**: Optionally crops excess transparent pixels while preserving a 1-pixel transparent border.
- **Direct Save — No Output Ports**: Acts as a terminal node. Processed images are saved automatically; no downstream connections required.
- **Auto-Numbered Filenames**: Files are saved as `{filename_prefix}_orig_{counter}.png`, e.g. `my_sprite_orig_00001.png`.

## Dependencies

- Python standard library (`collections`, `pathlib`)
- NumPy
- Pillow (PIL)
- PyTorch (bundled with ComfyUI)

> **No external dependencies**: Does not require ImageMagick or any external executables.

## Installation

1. Navigate to your ComfyUI `custom_nodes` folder.
2. Clone this repository:
   ```bash
   git clone https://github.com/zhoul1/comfy-alpha_outline-magick.git
   ```
3. Restart ComfyUI.

## Node Inputs

| Parameter | Type | Description |
| --- | --- | --- |
| **`images`** | `IMAGE` | Input image(s) — typically with a solid-color background. |
| **`fuzz`** | `STRING` | Background color tolerance. Supports percentage (e.g. `8%`) or absolute value (e.g. `20`). Default: `8%`. |
| **`filename_prefix`** | `STRING` | Base name prefix for saved files. Default: `alpha_outline`. |
| **`subfolder`** | `STRING` | Subfolder inside ComfyUI's output directory. |
| **`trim_transparent`** | `BOOLEAN` | Trim transparent pixels and keep a 1px border. Default: `False`. |

> **Note**: This is an Output Node — it has **no output ports**. All results are saved as RGBA PNG files named `{prefix}_orig_{counter:05d}.png`.

## How it Works

1. Samples a seed pixel from each of the four image corners, using its own color as the reference.
2. Computes the maximum per-channel difference between every pixel and the seed color, determining whether it falls within the `fuzz` tolerance.
3. When gap closure is enabled, detects horizontal/vertical single-pixel gaps in outlines and marks them as impassable barriers.
4. Runs a 4-connected BFS flood-fill, marking only external background pixels connected to a corner.
5. Sets the alpha channel of all marked pixels to 0 (transparent).
6. Optionally trims the transparent region (keeping a 1px border).
7. Saves the result as an RGBA PNG with auto-incremented filenames.
