"""
知识漫画 — 模板解析器

上传设计图 → 视觉 AI 解析 → 生成 Jinja2 HTML 模板

NOTE: 增加了 httpx 超时控制和 Jinja2 语法校验
"""
import base64
import json
import logging
import re
import time
from pathlib import Path

import httpx
import jinja2
from openai import OpenAI

logger = logging.getLogger(__name__)

# NOTE: 视觉 AI 解析超时（秒）——图片解析比文本慢，给更长时间
TEMPLATE_PARSE_TIMEOUT = 180
TEMPLATE_MAX_RETRIES = 1

# NOTE: 模板解析的系统提示词
TEMPLATE_ANALYZE_PROMPT = """你是一个前端工程师。用户会上传一张知识漫画/信息图的设计截图。

你的任务是：分析这张图的布局、配色、排版，然后生成一个等效的 Jinja2 HTML 模板。

## 要求

1. **输出完整的 HTML 文件**（包含 <!DOCTYPE html>、<head>、<style>、<body>）
2. **页面宽度固定 750px**
3. **字体引用**：
   - 标题用 `font-family: 'KuaiLe', cursive;`，引用 `url('./fonts/ZCOOLKuaiLe-Regular.ttf')`
   - 正文用 `font-family: 'MSYH', sans-serif;`，引用 `url('./fonts/msyh.ttc')`
4. **使用 Jinja2 变量**，变量命名规则：
   - 大标题：`{{ title }}`
   - 面板列表用 `{% for panel in panels %}`，每个 panel 包含：
     - `{{ panel.heading }}` 小标题
     - `{{ panel.text }}` 内容文字
     - `{{ panel.image_path }}` 图片路径（用 `{% if panel.image_path %}<img src="{{ panel.image_path }}">{% else %}<div class="placeholder">占位</div>{% endif %}`）
     - `{{ panel.icons }}` emoji 列表
   - 底部：`{{ footer }}`
   - 主角图：`{{ mascot_image }}`
5. **配色和布局尽量还原原图的风格**
6. **面板数量动态**：用 for 循环，不要硬编码固定数量
7. **奇数面板**：最后一个面板如果是奇数，要居中显示

## Jinja2 语法注意事项（必须严格遵守）

1. **变量输出**使用双花括号：`{{ variable }}`
2. **控制语句**使用 `{% %}`：如 `{% for %}`, `{% if %}`, `{% endif %}`, `{% endfor %}`
3. **禁止使用 Jinja2 test**：不要写 `{% if variable is defined %}`，改用 `{% if variable %}`
4. **禁止使用过滤器链**：不要写复杂的过滤器组合
5. **图片判断**只使用简单 if：`{% if panel.image_path %}`，不要用 `is not none` 或 `is defined`

## 输出格式

只输出 HTML 代码，用 ```html ... ``` 包裹。不要输出其他文字。
"""


def validate_jinja2_syntax(html_code: str) -> tuple[bool, str]:
    """
    校验 Jinja2 模板语法是否合法

    NOTE: 在保存或预览前调用，捕获 AI 生成的语法错误

    @param html_code: HTML 模板代码
    @returns: (is_valid, error_message)
    """
    try:
        env = jinja2.Environment(undefined=jinja2.Undefined)
        env.parse(html_code)
        return True, ""
    except jinja2.TemplateSyntaxError as e:
        error_msg = f"第 {e.lineno} 行语法错误: {e.message}"
        logger.warning("[模板校验] Jinja2 语法错误: %s", error_msg)
        return False, error_msg
    except Exception as e:
        return False, str(e)


def _auto_fix_template(html_code: str) -> str:
    """
    自动修复 AI 生成模板中的常见 Jinja2 语法问题

    NOTE: 针对反馈中高频出现的错误模式进行正则替换
    """
    # FIXME: AI 经常生成 `{% if var is defined %}` 这种 Jinja2 test 语法
    # 但在简单的 Environment 中没有注册 'defined' test
    # 替换为简单的 truthy 判断
    html_code = re.sub(
        r'{%\s*if\s+(\S+)\s+is\s+defined\s*%}',
        r'{% if \1 %}',
        html_code,
    )
    html_code = re.sub(
        r'{%\s*if\s+(\S+)\s+is\s+not\s+none\s*%}',
        r'{% if \1 %}',
        html_code,
    )
    # 修复 `{% if var is not defined %}` → `{% if not var %}`
    html_code = re.sub(
        r'{%\s*if\s+(\S+)\s+is\s+not\s+defined\s*%}',
        r'{% if not \1 %}',
        html_code,
    )
    # 修复常见的 test 错误：`is string`, `is mapping` 等
    html_code = re.sub(
        r'{%\s*if\s+(\S+)\s+is\s+(string|mapping|iterable|number|sequence)\s*%}',
        r'{% if \1 %}',
        html_code,
    )
    return html_code


def analyze_design_image(
    image_bytes: bytes,
    api_key: str,
    base_url: str = "https://coding.dashscope.aliyuncs.com/v1",
    model: str = "qwen3.6-plus",
) -> str:
    """
    用视觉 AI 分析设计图并生成 HTML 模板

    NOTE: 增加了显式超时控制和 Jinja2 语法校验/自动修复

    @param image_bytes: 上传的图片字节流
    @param api_key: API Key
    @param base_url: API 地址
    @param model: 视觉模型名称
    @returns: 生成的 HTML 模板代码
    """
    # 图片转 base64
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    # NOTE: 自动检测图片类型
    if image_bytes[:4] == b'\x89PNG':
        mime = "image/png"
    elif image_bytes[:2] == b'\xff\xd8':
        mime = "image/jpeg"
    else:
        mime = "image/png"

    data_uri = f"data:{mime};base64,{img_b64}"

    # NOTE: 显式设置 httpx 超时，视觉模型解析需要更长时间
    http_client = httpx.Client(
        timeout=httpx.Timeout(
            connect=15.0,
            read=TEMPLATE_PARSE_TIMEOUT,
            write=15.0,
            pool=15.0,
        ),
    )

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=http_client,
        max_retries=TEMPLATE_MAX_RETRIES,
    )

    logger.info("[模板解析] 开始分析设计图...")
    t0 = time.time()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": TEMPLATE_ANALYZE_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        },
                        {
                            "type": "text",
                            "text": "请分析这张设计图，生成等效的 Jinja2 HTML 模板。",
                        },
                    ],
                },
            ],
            temperature=0.2,
            max_tokens=8000,
        )
    except httpx.TimeoutException:
        elapsed = time.time() - t0
        logger.error("[模板解析] 请求超时（%.1fs），已达上限 %ds", elapsed, TEMPLATE_PARSE_TIMEOUT)
        raise TimeoutError(
            f"模板解析超时（{int(elapsed)}秒）。"
            f"建议：1. 使用更小的图片 2. 切换模型 3. 稍后再试"
        )
    finally:
        http_client.close()

    raw = response.choices[0].message.content.strip()
    elapsed = time.time() - t0
    logger.info("[模板解析] 完成（%.1fs）", elapsed)

    # 提取 HTML 代码块
    html_match = re.search(r"```html\s*(.*?)\s*```", raw, re.DOTALL)
    if html_match:
        html_code = html_match.group(1)
    elif raw.strip().startswith("<!DOCTYPE") or raw.strip().startswith("<html"):
        html_code = raw
    else:
        raise ValueError("AI 未返回有效的 HTML 模板代码")

    # NOTE: 自动修复常见语法问题，然后校验
    html_code = _auto_fix_template(html_code)

    is_valid, error_msg = validate_jinja2_syntax(html_code)
    if not is_valid:
        logger.warning("[模板解析] 自动修复后仍有语法错误: %s", error_msg)
        # NOTE: 不阻断流程，仍然返回代码但在日志中记录警告
        # 用户可以在 admin 界面手动修改

    return html_code


def save_template(
    template_name: str,
    html_content: str,
    templates_dir: str,
) -> str:
    """
    保存 HTML 模板到 comic_templates 目录

    NOTE: 保存前会进行 Jinja2 语法校验

    @param template_name: 模板名（英文，如 my_custom）
    @param html_content: HTML 模板代码
    @param templates_dir: 模板目录路径
    @returns: 保存的文件路径
    """
    # 规范化文件名
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", template_name).lower()
    file_path = Path(templates_dir) / f"{safe_name}.html"

    # NOTE: 保存前校验语法
    is_valid, error_msg = validate_jinja2_syntax(html_content)
    if not is_valid:
        logger.warning("[模板保存] 语法校验失败: %s（仍保存，但可能渲染出错）", error_msg)

    file_path.write_text(html_content, encoding="utf-8")
    logger.info("[模板保存] %s -> %s", template_name, file_path)
    return str(file_path)
