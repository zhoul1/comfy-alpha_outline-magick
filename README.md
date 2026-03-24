
# ComfyUI Alpha Outline Magick（中文文档）

> [English](#comfyui-alpha-outline-magick) | 中文

一个用于 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 的自定义**输出节点**。它借助 **ImageMagick** 去除白色背景、清理透明边缘的"白色描边/光晕伪影"，并可通过邻近点采样缩放到指定分辨率。处理结果将**直接保存为透明 RGBA PNG 文件**，节点无输出端口。

## 功能特点

- **白底去除**：使用 ImageMagick 的 floodfill 算法将白色背景转为透明。
- **白边伪影清理**：精准定位并去除 alpha 蒙版边界处的高亮"白色伪影"像素，同时保留主体内部细节。
- **直接保存，无输出端口**：作为终端节点使用，无需连接下游节点，处理完成后自动保存文件。
- **自动编号文件名**：文件按 `{前缀}_orig_{序号}.png` 格式命名，例如 `my_sprite_orig_00001.png`。

## 安装方法

1. 进入 ComfyUI 的 `custom_nodes` 目录。
2. 克隆本仓库（或直接复制文件夹）：
   ```bash
   git clone https://github.com/your-username/comfy-alpha_outline-magick.git
   ```
3. 重启 ComfyUI。

### ImageMagick 依赖

本节点**依赖** [ImageMagick](https://imagemagick.org/script/download.php)。查找 `magick` / `magick.exe` 的优先级如下：

1. **`magick_exe` 参数**：节点参数中填写的绝对路径。
2. **节点本地目录**：`custom_nodes/comfy-alpha_outline-magick/magick/magick.exe`（便携版）。
3. **环境变量**：`IM_CMD` 环境变量中定义的路径。
4. **系统 PATH**：系统中全局安装的 ImageMagick。

## 节点输入参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| **`images`** | `IMAGE` | 输入图像（通常为白色背景的图像）。 |
| **`fuzz`** | `STRING` | 背景 floodfill 的容差百分比。默认：`8%`。 |
| **`threshold`** | `STRING` | Alpha 蒙版二值化阈值。默认：`60%`。 |
| **`gap`** | `STRING` | 识别"白色描边/光晕"像素的亮度阈值。默认：`88%`。 |
| **`edge`** | `INT` | 形态学膨胀边缘厚度（Square 核），控制清理区域宽度。默认：`2`。 |
| **`magick_exe`** | `STRING` | （可选）ImageMagick 可执行文件的绝对路径，留空则自动检测。 |
| **`filename_prefix`** | `STRING` | 保存文件的名称前缀。默认：`alpha_outline`。 |
| **`subfolder`** | `STRING` | 在 ComfyUI 输出目录下的子文件夹名称。 |
| **`trim_transparent`** | `BOOLEAN` | 是否去除多余透明像素并保留1像素边框。 |

> **说明**：本节点是**输出节点**，**没有输出端口**。所有处理结果以 `{前缀}_orig_{序号:05d}.png` 格式自动保存到 ComfyUI 的输出目录。

## 工作原理

1. 使用 `-draw alpha floodfill` 对图像四角进行洪水填充，根据 `fuzz` 参数容差去除白色背景。
2. 提取基础二值化 Alpha 蒙版（AMASK），通过菱形形态学运算（Open/Close）清理噪点。
3. 根据 `edge` 参数在蒙版内侧靠近透明边界处定义"环形区域"（RING）。
4. 在该环形区域内，依据 `gap` 阈值定位亮度过高的像素点。
5. **仅**将这些边界处的高亮伪影像素置为透明，消除常规背景去除方法难以处理的白色描边。
6. 将结果直接保存为透明 RGBA PNG，文件名自动累加序号。
