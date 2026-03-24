"""Alpha Outline – 纯 Python 背景移除节点
=========================================
使用连通分量洪水填充（BFS）算法，仅移除与图像四角相连的外部背景像素。
内置 1-pixel 缺口自动封闭功能，防止洪水填充通过轮廓线缝隙泄入主体内部。
"""

from collections import deque
from pathlib import Path

import numpy as np
import torch
from PIL import Image

import folder_paths


# -----------------------------
# Core Algorithm
# -----------------------------

def _parse_fuzz(fuzz_str: str) -> float:
    """
    解析 fuzz 容差字符串。
    - "8%"  -> 8% of 255 ≈ 20.4
    - "20"  -> 绝对值 20
    """
    s = fuzz_str.strip()
    if s.endswith("%"):
        return float(s[:-1]) * 255.0 / 100.0
    return float(s)


def _remove_external_background(
    rgba: np.ndarray,
    fuzz: float,
    close_gaps: bool = True,
) -> np.ndarray:
    """
    从图像四角开始洪水填充，移除与角落颜色相似且 4-连通相连的外部背景像素。

    关键特性：
    1. 仅从 4 个角落像素开始填充（非全部边界），减少泄漏风险
    2. 每个角落使用自身颜色作为参考色（非平均值）
    3. 4-连通 BFS，不走对角线
    4. close_gaps=True 时，自动封闭轮廓线中的 1-pixel 直线缺口

    保证：只要主体被封闭轮廓包围（允许对角连接），
    内部像素永远不会被移除。
    """
    h, w = rgba.shape[:2]
    rgb = rgba[:, :, :3].astype(np.float64)

    corners = [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]
    visited = np.zeros((h, w), dtype=bool)

    for cy, cx in corners:
        if visited[cy, cx]:
            continue

        # 以该角落像素自身的颜色作为参考（匹配 ImageMagick floodfill 行为）
        seed_color = rgb[cy, cx]
        diff = np.max(np.abs(rgb - seed_color), axis=2)
        similar = diff <= fuzz

        if close_gaps:
            # 检测并封闭轮廓线中的 1-pixel 直线缺口
            # 原理：如果一个"类似背景"的像素，其水平或垂直方向的两个邻居
            # 都是"非背景"像素，则该像素位于轮廓缺口中，应视为屏障
            non_bg = ~similar

            # 水平缺口：左右邻居都是非背景
            h_gap = np.zeros((h, w), dtype=bool)
            h_gap[:, 1:-1] = similar[:, 1:-1] & non_bg[:, :-2] & non_bg[:, 2:]

            # 垂直缺口：上下邻居都是非背景
            v_gap = np.zeros((h, w), dtype=bool)
            v_gap[1:-1, :] = similar[1:-1, :] & non_bg[:-2, :] & non_bg[2:, :]

            # 将缺口像素标记为"不可通过"
            similar = similar & ~h_gap & ~v_gap

        if not similar[cy, cx]:
            continue

        visited[cy, cx] = True
        queue = deque([(cy, cx)])

        while queue:
            y, x = queue.popleft()
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and similar[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx))

    # 仅将与角落相连的外部背景像素设为透明
    result = rgba.copy()
    result[visited, 3] = 0
    return result


# -----------------------------
# Utilities
# -----------------------------

def _tensor_to_pil_rgb(img: torch.Tensor) -> Image.Image:
    """img: (H,W,3) float32 0..1"""
    x = img.detach().cpu().numpy()
    x = np.clip(x * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(x, mode="RGB")


def _next_counter(out_dir: Path, prefix: str, flag: str) -> int:
    """扫描 out_dir 里已存在的文件，找到当前最大序号并 +1。"""
    pattern = f"{prefix}_{flag}_"
    max_idx = 0
    if out_dir.exists():
        for f in out_dir.iterdir():
            name = f.stem
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
                "filename_prefix": ("STRING", {"default": "alpha_outline"}),
                "subfolder": ("STRING", {"default": ""}),
                "trim_transparent": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "apply"
    OUTPUT_NODE = True
    CATEGORY = "image/alpha"

    def apply(
        self,
        images: torch.Tensor,
        fuzz: str,
        filename_prefix: str,
        subfolder: str,
        trim_transparent: bool,
    ):
        if not isinstance(images, torch.Tensor):
            raise TypeError("images must be a torch.Tensor")
        if images.dim() != 4 or images.shape[-1] != 3:
            raise ValueError("images must be [B,H,W,3] float 0..1")

        b = images.shape[0]
        fuzz_val = _parse_fuzz(fuzz)

        out_base = Path(folder_paths.get_output_directory())
        out_dir = out_base / subfolder if subfolder else out_base
        out_dir.mkdir(parents=True, exist_ok=True)

        for i in range(b):
            pil_rgb = _tensor_to_pil_rgb(images[i])
            rgba = np.array(pil_rgb.convert("RGBA"))

            result_rgba = _remove_external_background(rgba, fuzz_val, close_gaps=True)
            result_img = Image.fromarray(result_rgba, "RGBA")

            if trim_transparent:
                bbox = result_img.getbbox()
                if bbox:
                    x0, y0, x1, y1 = bbox
                    # 保留 1px 透明边框
                    x0 = max(0, x0 - 1)
                    y0 = max(0, y0 - 1)
                    x1 = min(result_img.width, x1 + 1)
                    y1 = min(result_img.height, y1 + 1)
                    result_img = result_img.crop((x0, y0, x1, y1))

            counter = _next_counter(out_dir, filename_prefix, "orig")
            name = f"{filename_prefix}_orig_{counter:05d}.png"
            dst = out_dir / name
            result_img.save(str(dst), format="PNG", optimize=False)

        return {}


NODE_CLASS_MAPPINGS = {
    "AlphaOutlineMagick": AlphaOutlineMagickNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AlphaOutlineMagick": "Alpha Outline (Background Removal)",
}
