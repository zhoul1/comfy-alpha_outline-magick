import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image

import folder_paths


# -----------------------------
# Utilities
# -----------------------------

def _to_im_path(p: Path) -> str:
    """Windows 下 ImageMagick 对 / 路径更稳。"""
    abs_p = p.resolve()
    if os.name == "nt":
        return abs_p.as_posix()
    return str(abs_p)


def _default_magick_in_node_dir() -> Optional[str]:
    """
    约定：magick.exe 固定放在本节点目录下的 magick/ 子目录中
    """
    here = Path(__file__).resolve().parent
    magick_dir = (here / "magick").resolve()

    if os.name == "nt":
        exe = magick_dir / "magick.exe"
        return str(exe) if exe.exists() else None
    else:
        exe = magick_dir / "magick"
        return str(exe) if exe.exists() else None


def _resolve_magick_cmd(magick_exe: str = "") -> str:
    """
    优先级：
      1) 节点参数 magick_exe（可选）
      2) 本节点目录 ./magick/magick(.exe)
      3) 环境变量 IM_CMD
      4) PATH 中的 magick
    """
    here = Path(__file__).resolve().parent

    def norm(p: str) -> str:
        pp = Path(p.strip())
        if pp.is_absolute():
            return str(pp)
        return str((here / pp).resolve())

    # 1) 节点参数
    if magick_exe and magick_exe.strip():
        cmd = norm(magick_exe)
        if Path(cmd).exists():
            return cmd

    # 2) 节点目录固定位置 ./magick/
    node_cmd = _default_magick_in_node_dir()
    if node_cmd:
        return node_cmd

    # 3) 环境变量 IM_CMD
    env_cmd = os.environ.get("IM_CMD", "").strip()
    if env_cmd:
        cmd = norm(env_cmd)
        if Path(cmd).exists():
            return cmd

    # 4) PATH
    which = shutil.which("magick")
    if which:
        return which

    raise FileNotFoundError(
        'Cannot find ImageMagick "magick" executable. '
        "Expected in ./magick/magick(.exe), or set IM_CMD, or pass magick_exe."
    )


def _run_magick(cmd: str, args: list) -> None:
    env = os.environ.copy()

    # portable 版：把 magick.exe 所在目录插入 PATH，方便加载同目录 DLL
    cmd_path = Path(cmd)
    if cmd_path.exists():
        magick_dir = str(cmd_path.parent)
        env["PATH"] = f"{magick_dir}{os.pathsep}{env.get('PATH', '')}"
        env["MAGICK_HOME"] = magick_dir

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    p = subprocess.Popen(
        [cmd, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        shell=False,
        creationflags=creationflags,
    )
    _, stderr = p.communicate()
    if p.returncode != 0:
        raise RuntimeError(
            f"magick exited with code {p.returncode}\n{stderr.decode('utf-8', errors='replace')}"
        )


def _tensor_to_pil_rgb(img: torch.Tensor) -> Image.Image:
    """
    img: (H,W,3) float32 0..1
    """
    x = img.detach().cpu().numpy()
    x = np.clip(x * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(x, mode="RGB")


def _pil_rgba_to_numpy(im: Image.Image) -> np.ndarray:
    """Returns (H,W,4) uint8 RGBA array."""
    return np.array(im.convert("RGBA"))


# -----------------------------
# ImageMagick pipeline
# -----------------------------

def _process_one(
    input_png: Path,
    out_orig_png: Path,
    fuzz: str,
    threshold: str,
    gap: str,
    edge: int,
    magick_exe: str,
) -> None:
    cmd = _resolve_magick_cmd(magick_exe)

    inP = _to_im_path(input_png)
    outO = _to_im_path(out_orig_png)

    # Square 邻域（更适合"贴黑线凹角/相交处"的白点）
    dilateKernel = f"Square:{max(1, int(edge))}"

    args: list = [
        inP,

        # ===== 1) 白底抠透明（主体含白，背景轻微灰噪点）=====
        "-alpha", "set",
        "-channel", "RGBA",
        "-fuzz", fuzz,

        "-fill", "none", "-draw", "alpha 0,0 floodfill",
        "-fill", "none", "-draw", "alpha %[fx:w-1],0 floodfill",
        "-fill", "none", "-draw", "alpha 0,%[fx:h-1] floodfill",
        "-fill", "none", "-draw", "alpha %[fx:w-1],%[fx:h-1] floodfill",

        # 保存当前基底图（用于亮度判断）
        "-write", "mpr:BASE",

        # ===== 2) AMASK：二值 alpha mask（清理灰点/补小孔）=====
        "(",
        "+clone",
        "-alpha", "extract",
        "-threshold", threshold,
        "-morphology", "Open", "Diamond:1",
        "-morphology", "Close", "Diamond:1",
        "-threshold", "50%",
        ")",
        "-write", "mpr:AMASK",
        "+delete",

        # ===== 3) 去贴黑线白点：只在边界环带内剔除"高亮像素"=====
        # 3.1 BRIGHT：取"很亮/近白"的像素（基于颜色，不看 alpha）
        "mpr:BASE",
        "-alpha", "off",
        "-colorspace", "Gray",
        "-threshold", gap,
        "-threshold", "50%",
        "-write", "mpr:BRIGHT",
        "+delete",

        # 3.2 RING：AMASK 内侧靠近透明边界的环带
        # RING = AMASK * Dilate(NOT AMASK)
        "mpr:AMASK",
        "(",
        "+clone",
        "-negate",
        "-morphology", "Dilate", dilateKernel,
        ")",
        "-compose", "Multiply",
        "-composite",
        "-threshold", "50%",
        "-write", "mpr:RING",
        "+delete",

        # 3.3 WHITESP = RING * BRIGHT
        "mpr:RING",
        "mpr:BRIGHT",
        "-compose", "Multiply",
        "-composite",
        "-threshold", "50%",
        "-write", "mpr:WHITESP",
        "+delete",

        # 3.4 AMASK = AMASK * (NOT WHITESP)
        "mpr:WHITESP",
        "-negate",
        "-threshold", "50%",
        "-write", "mpr:KEEP",
        "+delete",

        "mpr:AMASK",
        "mpr:KEEP",
        "-compose", "Multiply",
        "-composite",
        "-threshold", "50%",
        "-write", "mpr:AMASK",
        "+delete",

        # ===== 4) 强制用 AMASK 作为 alpha，得到最终结果 =====
        "mpr:BASE",
        "-alpha", "set",
        "-compose", "CopyOpacity",
        "mpr:AMASK",
        "-composite",
        outO,
    ]

    _run_magick(cmd, args)


def _next_counter(out_dir: Path, prefix: str, flag: str) -> int:
    """
    扫描 out_dir 里已存在的文件，找到当前 prefix_flag_XXXXX 最大序号，返回 +1。
    如果没有则返回 1。
    """
    pattern = f"{prefix}_{flag}_"
    max_idx = 0
    if out_dir.exists():
        for f in out_dir.iterdir():
            name = f.stem  # without extension
            if name.startswith(pattern):
                tail = name[len(pattern):]
                if tail.isdigit():
                    max_idx = max(max_idx, int(tail))
    return max_idx + 1


# -----------------------------
# ComfyUI Node
# -----------------------------

class AlphaOutlineMagickNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),

                "fuzz": ("STRING", {"default": "8%"}),
                "threshold": ("STRING", {"default": "60%"}),
                "gap": ("STRING", {"default": "88%"}),
                "edge": ("INT", {"default": 2, "min": 1, "max": 64, "step": 1}),

                # 可为空：自动用 ./magick/magick.exe（或 IM_CMD / PATH 兜底）
                "magick_exe": ("STRING", {"default": ""}),

                # ===== 保存控制 =====
                "filename_prefix": ("STRING", {"default": "alpha_outline"}),
                "subfolder": ("STRING", {"default": ""}),
                "invert_mask": ("BOOLEAN", {"default": False}),
            }
        }

    # 输出节点：不向下游传递任何数据
    RETURN_TYPES = ()
    FUNCTION = "apply"
    OUTPUT_NODE = True
    CATEGORY = "image/alpha"

    def apply(
        self,
        images: torch.Tensor,
        fuzz: str,
        threshold: str,
        gap: str,
        edge: int,
        magick_exe: str,
        filename_prefix: str,
        subfolder: str,
        invert_mask: bool,
    ):
        if not isinstance(images, torch.Tensor):
            raise TypeError("images must be a torch.Tensor")
        if images.dim() != 4 or images.shape[-1] != 3:
            raise ValueError("images must be [B,H,W,3] float 0..1")

        b = images.shape[0]

        # 确定保存目录
        out_base = Path(folder_paths.get_output_directory())
        out_dir = out_base / subfolder if subfolder else out_base
        out_dir.mkdir(parents=True, exist_ok=True)

        ui_images = []

        with tempfile.TemporaryDirectory(prefix="comfy_magick_alpha_") as td:
            td = Path(td)

            for i in range(b):
                in_png   = td / f"in_{i}.png"
                out_orig = td / f"out_{i}_orig.png"

                pil_in = _tensor_to_pil_rgb(images[i])
                pil_in.save(in_png, format="PNG", optimize=False)

                _process_one(
                    input_png    = in_png,
                    out_orig_png = out_orig,
                    fuzz       = str(fuzz),
                    threshold  = str(threshold),
                    gap        = str(gap),
                    edge       = int(edge),
                    magick_exe = str(magick_exe),
                )

                counter = _next_counter(out_dir, filename_prefix, "orig")
                name = f"{filename_prefix}_orig_{counter:05d}.png"
                dst = out_dir / name

                rgba_arr = _pil_rgba_to_numpy(Image.open(out_orig))
                if invert_mask:
                    rgba_arr = rgba_arr.copy()
                    rgba_arr[..., 3] = 255 - rgba_arr[..., 3]

                Image.fromarray(rgba_arr, mode="RGBA").save(dst, format="PNG")
                ui_images.append({
                    "filename": name,
                    "subfolder": str(subfolder) if subfolder else "",
                    "type": "output",
                })

        return {"ui": {"images": ui_images}}


NODE_CLASS_MAPPINGS = {
    "AlphaOutlineMagick": AlphaOutlineMagickNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AlphaOutlineMagick": "Alpha Outline Pipeline (ImageMagick)",
}
