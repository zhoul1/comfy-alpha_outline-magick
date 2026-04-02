
# ComfyUI Alpha Outline（中文文档）

> [English](README_en.md) | 中文

一个用于 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 的自定义**输出节点**。使用纯 Python 实现的连通分量洪水填充（BFS）算法，从图像四角移除外部背景像素，并将结果**直接保存为透明 RGBA PNG 文件**。节点无输出端口。

## 功能特点

- **外部背景移除**：从图像四角开始洪水填充，仅移除与角落颜色相似且相连的外部背景像素，保证内部主体不受影响。
- **1-pixel 缺口自动封闭**：自动检测并封闭轮廓线中的单像素直线缺口，防止洪水填充通过缝隙泄入主体内部。
- **透明区域裁剪**：可选去除多余透明像素，保留 1 像素透明边框。
- **直接保存，无输出端口**：作为终端节点使用，处理完成后自动保存文件。
- **自动编号文件名**：文件按 `{前缀}_orig_{序号}.png` 格式命名，例如 `my_sprite_orig_00001.png`。

## 依赖

- Python 标准库（`collections`、`pathlib`）
- NumPy
- Pillow（PIL）
- PyTorch（ComfyUI 环境自带）

> **无外部依赖**：不依赖 ImageMagick 或任何外部可执行文件。

## 安装方法

1. 进入 ComfyUI 的 `custom_nodes` 目录。
2. 克隆本仓库：
   ```bash
   git clone https://github.com/zhoul1/comfy-alpha_outline-magick.git
   ```
3. 重启 ComfyUI。

## 节点输入参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| **`images`** | `IMAGE` | 输入图像（通常为纯色背景的图像）。 |
| **`fuzz`** | `STRING` | 背景颜色容差。支持百分比（如 `8%`）或绝对值（如 `20`）。默认：`8%`。 |
| **`filename_prefix`** | `STRING` | 保存文件的名称前缀。默认：`alpha_outline`。 |
| **`subfolder`** | `STRING` | 在 ComfyUI 输出目录下的子文件夹名称。 |
| **`trim_transparent`** | `BOOLEAN` | 是否去除多余透明像素并保留 1 像素边框。默认：`False`。 |

> **说明**：本节点是**输出节点**，**没有输出端口**。所有处理结果以 `{前缀}_orig_{序号:05d}.png` 格式自动保存到 ComfyUI 的输出目录。

## 工作原理

1. 从图像四角各取种子像素，以其自身颜色作为参考色。
2. 在整幅图像上计算每个像素与种子色的最大通道差值，判断是否在 `fuzz` 容差范围内。
3. 启用缺口封闭时，检测轮廓线中水平 / 垂直方向的单像素缺口并标记为不可通过。
4. 使用 4-连通 BFS 洪水填充，仅标记与角落相连的外部背景像素。
5. 将标记区域的 alpha 通道置为 0（透明）。
6. 可选执行透明区域裁剪（保留 1px 边框）。
7. 将结果保存为 RGBA PNG，文件名自动累加序号。
