"""
知识漫画 — 模板渲染引擎

将 LLM 输出的结构化 JSON + ComfyUI 插画 → 渲染为最终 PNG 长图

NOTE: Playwright 与 Streamlit 的 asyncio 事件循环冲突，
因此所有 Playwright 调用通过子进程执行，避免 event loop 死锁。
"""
import copy
import logging
import os
import subprocess
import sys
from pathlib import Path

import jinja2
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

# NOTE: 模板目录使用绝对路径，避免相对路径歧义
TEMPLATES_DIR = Path(__file__).parent.parent / "comic_templates"


def _convert_paths_to_uri(data: dict) -> dict:
    """
    递归遍历 data，将所有 image_path / mascot_image / header_image
    从 Windows 本地路径转为 file:// URI

    NOTE: 同时为缺失 image_path 的项补充默认空值，
    避免 Jinja2 模板 {% if panel.image_path %} 报 UndefinedError
    """
    data = copy.deepcopy(data)

    def _to_uri(path_str: str) -> str:
        if not path_str or path_str.startswith("http") or path_str.startswith("file:"):
            return path_str
        return Path(path_str).as_uri()

    # 顶层字段——补默认值
    for key in ["mascot_image", "header_image"]:
        val = data.get(key, "")
        data[key] = _to_uri(val) if val else ""

    # 列表中的 image_path——补默认值 + 转 URI
    for list_key in ["panels", "sections", "ingredients", "prep_steps", "cooking_steps"]:
        for item in data.get(list_key, []):
            val = item.get("image_path", "")
            item["image_path"] = _to_uri(val) if val else ""

    return data


def _render_html(template_name: str, data: dict) -> str:
    """Jinja2 渲染 HTML 字符串"""
    # NOTE: 渲染前先把所有图片路径转为 file:// URI + 补默认值
    data = _convert_paths_to_uri(data)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        # NOTE: 缺失变量不报错，返回空字符串
        undefined=jinja2.Undefined,
    )
    template = env.get_template(f"{template_name}.html")
    html_content = template.render(**data)

    # NOTE: 字体通过相对路径 ./fonts/ 加载
    # 临时 HTML 文件会放在 comic_templates/ 目录，与 fonts/ 同级
    return html_content


def render_comic(
    template_name: str,
    data: dict,
    output_path: str,
    page_width: int = 750,
) -> str:
    """
    渲染知识漫画长图

    @param template_name: 模板名（cute_panels / medical_guide / recipe_card 等）
    @param data: LLM 输出的结构化数据（已填充 image_path）
    @param output_path: 输出 PNG 路径
    @param page_width: 页面宽度（像素）
    @returns: 输出文件路径
    """
    html_content = _render_html(template_name, data)
    _screenshot_via_subprocess(html_content, output_path, page_width)
    logger.info("[渲染] 截图完成: %s", output_path)
    return output_path


def render_preview(template_name: str, data: dict, page_width: int = 750) -> bytes:
    """
    渲染预览（返回 PNG 字节流，不保存文件）

    NOTE: 用于 Streamlit 实时预览
    """
    html_content = _render_html(template_name, data)

    # 使用临时文件保存截图，读取后删除
    tmp_dir = TEMPLATES_DIR.parent / "output"
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_png = str(tmp_dir / "_preview_tmp.png")

    _screenshot_via_subprocess(html_content, tmp_png, page_width)

    with open(tmp_png, "rb") as f:
        png_bytes = f.read()

    # 清理临时文件
    try:
        os.remove(tmp_png)
    except OSError:
        pass

    return png_bytes


def _screenshot_via_subprocess(
    html_content: str,
    output_path: str,
    page_width: int,
) -> None:
    """
    通过子进程调用 Playwright 截图

    NOTE: 避免 Streamlit 主进程的 asyncio 事件循环与 Playwright 冲突
    """
    # NOTE: 临时 HTML 放在 comic_templates/ 目录
    # 这样字体的相对路径 ./fonts/ 和图片路径都能正确解析
    # 使用 UUID 避免多用户并发时文件竞争
    import uuid
    tmp_id = uuid.uuid4().hex[:8]
    tmp_html = str(TEMPLATES_DIR / f"_render_{tmp_id}.html")

    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 子进程脚本路径
    worker_script = Path(__file__).parent / "_playwright_worker.py"

    # NOTE: 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            str(worker_script),
            tmp_html,
            output_path,
            str(page_width),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    # 清理临时 HTML
    try:
        os.remove(tmp_html)
    except OSError:
        pass

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        raise RuntimeError(f"Playwright worker failed: {error_msg}")
