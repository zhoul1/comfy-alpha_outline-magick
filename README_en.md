# ComfyUI Alpha Outline Magick

A custom **Output Node** for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) that uses **ImageMagick** to remove white backgrounds, clean up transparent edge "white halos/fringing", and optionally downscale using nearest-neighbor (point) filtering. Results are **saved directly to disk as transparent RGBA PNGs** — no output wires needed.

## Features

- **White Background Removal**: Uses ImageMagick's floodfill algorithm to convert white backgrounds to transparent.
- **Edge Fringing Cleanup**: Targets and removes bright "white halo" pixels at the alpha mask boundary, while preserving inner bright details.
- **Direct Save — No Output Ports**: Acts as a terminal node. Processed images are saved automatically; no downstream connections required.
- **Auto-Numbered Filenames**: Files are saved as `{filename_prefix}_orig_{counter}.png`, e.g. `my_sprite_orig_00001.png`.

## Installation

1. Navigate to your ComfyUI `custom_nodes` folder.
2. Clone this repository (or copy the folder):
   ```bash
   git clone https://github.com/your-username/comfy-alpha_outline-magick.git
   ```
3. Restart ComfyUI.

### ImageMagick Dependency

This node **requires** [ImageMagick](https://imagemagick.org/script/download.php).
The search order for finding `magick` / `magick.exe` is:

1. **`magick_exe` parameter**: An explicit absolute path in the node.
2. **Local directory**: `custom_nodes/comfy-alpha_outline-magick/magick/magick.exe` (portable).
3. **Environment variable**: Path in the `IM_CMD` environment variable.
4. **System PATH**: Global ImageMagick installation.

## Node Inputs

| Parameter | Type | Description |
| --- | --- | --- |
| **`images`** | `IMAGE` | Input image(s) — typically with a white/solid background. |
| **`fuzz`** | `STRING` | Floodfill tolerance for background removal. Default: `8%`. |
| **`threshold`** | `STRING` | Alpha mask binarization threshold. Default: `60%`. |
| **`gap`** | `STRING` | Brightness threshold for identifying white halo pixels. Default: `88%`. |
| **`edge`** | `INT` | Morphological dilate thickness (Square kernel) for the cleanup ring. Default: `2`. |
| **`magick_exe`** | `STRING` | (Optional) Explicit path to ImageMagick executable. |
| **`filename_prefix`** | `STRING` | Base name prefix for saved files. Default: `alpha_outline`. |
| **`subfolder`** | `STRING` | Subfolder inside ComfyUI's output directory. |
| **`invert_mask`** | `BOOLEAN` | Invert the alpha channel when saving. |

> **Note**: This is an Output Node — it has **no output ports**. All results are saved as RGBA PNG files named `{prefix}_orig_{counter:05d}.png`.

## How it Works

1. Removes the white background via `-draw alpha floodfill` at 4 corners, controlled by `fuzz`.
2. Extracts and cleans a binary Alpha Mask (AMASK) using diamond morphology (Open/Close).
3. Builds a boundary "Ring" around the mask's transparent edge using the `edge` thickness.
4. Locates excessively bright pixels strictly within that Ring (controlled by `gap`).
5. Masks out *only* those bright edge pixels — eliminating white outlines standard removal misses.
6. Saves the result directly to disk with auto-incremented filenames.

---
