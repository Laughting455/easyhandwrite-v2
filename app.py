from flask import Flask, request, send_file, render_template, jsonify, Response
import docx, io, tempfile, os, zipfile, json, threading, time, uuid
from pathlib import Path
from PIL import Image, ImageFont
from handright import Template, handwrite
import chardet

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 上传限制

# ── 工具函数 ──────────────────────────

def read_txt(file_bytes):
    enc = chardet.detect(file_bytes)['encoding'] or 'utf-8'
    return file_bytes.decode(enc).replace('\r\n', '\n')

def read_docx(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in doc.paragraphs])

def read_text(file_bytes, filename: str):
    if filename.lower().endswith('.txt'):
        return read_txt(file_bytes)
    else:
        return read_docx(file_bytes)

# ── 核心生成函数 ──────────────────────

def generate_handwritten_image(text, font_bytes, font_size, line_spacing,
                               page_width, page_height,
                               ml, mt, mr, mb,
                               progress_callback=None):
    """
    生成手写图片，支持进度回调
    progress_callback(current_page, total_pages)
    """
    fd, font_path = tempfile.mkstemp(suffix='.ttf')
    os.close(fd)
    with open(font_path, 'wb') as f:
        f.write(font_bytes)

    if line_spacing < font_size:
        raise ValueError(f"行距必须 ≥ 字体大小 ({font_size})")

    w = page_width - ml - mr
    h = page_height - mt - mb
    bg = Image.new("RGB", (w, h), (255, 255, 255))
    font = ImageFont.truetype(font_path, font_size)
    template = Template(
        background=bg, font=font, line_spacing=line_spacing,
        left_margin=ml, top_margin=mt,
        right_margin=mr, bottom_margin=mb
    )

    # handwrite 返回生成器，我们需要先收集所有页面
    images = list(handwrite(text, template))
    total = len(images)

    tmpdir = tempfile.mkdtemp()
    for i, im in enumerate(images):
        im.save(Path(tmpdir) / f"handwritten_image_{i:03d}.png")
        if progress_callback:
            progress_callback(i + 1, total)

    zip_path = Path(tmpdir) / "handwritten.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for png in sorted(Path(tmpdir).glob("*.png")):
            zf.write(png, arcname=png.name)

    return zip_path, total

# ── 全局进度存储 ──────────────────────
# 简单内存存储，生产环境建议用 Redis
generate_tasks = {}

# ── 路由 ─────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    try:
        word_file = request.files["word"].read()
        font_file = request.files["font"].read()
        filename = request.files["word"].filename

        # 参数解析
        font_size = int(request.form.get("font_size", 50))
        line_spacing = float(request.form.get("line_spacing", font_size + 10))
        page_width = int(request.form.get("page_width", 2480))
        page_height = int(request.form.get("page_height", 3508))
        ml = int(request.form.get("ml", 40))
        mt = int(request.form.get("mt", 40))
        mr = int(request.form.get("mr", 40))
        mb = int(request.form.get("mb", 40))

        # 读取文本
        text = read_text(word_file, filename)
        if not text.strip():
            return "文档内容为空", 400

        # 生成任务 ID
        task_id = str(uuid.uuid4())[:8]
        generate_tasks[task_id] = {"status": "running", "progress": 0, "total": 0}

        def progress_callback(current, total):
            generate_tasks[task_id]["progress"] = current
            generate_tasks[task_id]["total"] = total

        zip_path, total_pages = generate_handwritten_image(
            text, font_file, font_size, line_spacing,
            page_width, page_height,
            ml, mt, mr, mb,
            progress_callback=progress_callback
        )

        generate_tasks[task_id]["status"] = "done"
        generate_tasks[task_id]["total_pages"] = total_pages

        # 将 zip 路径临时保存，供下载接口使用
        generate_tasks[task_id]["zip_path"] = str(zip_path)

        return jsonify({
            "success": True,
            "task_id": task_id,
            "total_pages": total_pages,
            "message": f"生成完成，共 {total_pages} 页"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/progress/<task_id>", methods=["GET"])
def get_progress(task_id):
    task = generate_tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(task)

@app.route("/download/<task_id>", methods=["GET"])
def download(task_id):
    task = generate_tasks.get(task_id)
    if not task or task.get("status") != "done":
        return jsonify({"error": "文件未准备好"}), 400

    zip_path = task.get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({"error": "文件已过期"}), 400

    return send_file(zip_path, as_attachment=True,
                     download_name="handwritten.zip")

@app.route("/preview", methods=["POST"])
def preview():
    """生成第一页预览"""
    try:
        word_file = request.files["word"].read()
        font_file = request.files["font"].read()
        filename = request.files["word"].filename

        font_size = int(request.form.get("font_size", 50))
        line_spacing = float(request.form.get("line_spacing", font_size + 10))
        page_width = int(request.form.get("page_width", 2480))
        page_height = int(request.form.get("page_height", 3508))
        ml = int(request.form.get("ml", 40))
        mt = int(request.form.get("mt", 40))
        mr = int(request.form.get("mr", 40))
        mb = int(request.form.get("mb", 40))

        text = read_text(word_file, filename)
        if not text.strip():
            return "文档内容为空", 400

        # 只取前 300 字做预览
        preview_text = text[:300] + ("..." if len(text) > 300 else "")

        fd, font_path = tempfile.mkstemp(suffix='.ttf')
        os.close(fd)
        with open(font_path, 'wb') as f:
            f.write(font_file)

        w = page_width - ml - mr
        h = page_height - mt - mb
        bg = Image.new("RGB", (w, h), (255, 255, 255))
        font = ImageFont.truetype(font_path, font_size)
        template = Template(
            background=bg, font=font, line_spacing=line_spacing,
            left_margin=ml, top_margin=mt,
            right_margin=mr, bottom_margin=mb
        )

        images = list(handwrite(preview_text, template))
        if not images:
            return "无法生成预览", 400

        img_io = io.BytesIO()
        images[0].save(img_io, format='PNG')
        img_io.seek(0)

        return send_file(img_io, mimetype='image/png')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return str(e), 400

# ── 静态文件 ──────────────────────────
# 提供一个简单的 favicon
@app.route('/favicon.ico')
def favicon():
    # 返回一个 1x1 透明像素
    img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    img_io = io.BytesIO()
    img.save(img_io, format='PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
