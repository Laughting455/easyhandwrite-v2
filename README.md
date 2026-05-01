# Easy HandWrite — 手写稿生成器

将 Word (.docx) 或纯文本 (.txt) 文档转换为逼真的手写风格图片。

## 功能特性

- 📄 支持 .docx 和 .txt 格式
- 🖋 支持自定义 .ttf / .otf 字体
- 👁 实时预览效果
- 📊 生成进度实时显示
- ⚙️ 可调节字体大小、行距、页边距、页面尺寸
- 📦 输出为 ZIP 压缩包
- 🎨 现代化 UI，支持拖拽上传

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python app.py

# 3. 浏览器打开 http://localhost:5000
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 字体大小 | 50 px | 单个字的大小 |
| 行距 | 65 px | 行与行之间的间距（必须 ≥ 字体大小） |
| 页面宽度 | 2480 px | A4 纸 300dpi 宽度 |
| 页面高度 | 3508 px | A4 纸 300dpi 高度 |
| 边距 | 40 px | 上下左右页边距 |

## 技术栈

- Flask (后端)
- handright (手写模拟)
- Pillow (图像处理)
- Bulma CSS (前端样式)
