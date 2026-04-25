"""
知识漫画 — 主控生成器

完整流水线：文案输入 → LLM 分析 → ComfyUI 插画 → 模板渲染 → 输出 PNG
"""
import io
import json
import logging
import os
import random
import re
import time
from pathlib import Path

import httpx
import requests
from openai import OpenAI
from PIL import Image

logger = logging.getLogger(__name__)

# NOTE: LLM 调用超时上限（秒），避免网络波动导致无限等待
LLM_REQUEST_TIMEOUT = 120
# NOTE: 最大重试次数
LLM_MAX_RETRIES = 2


def _load_llm_template() -> str:
    """加载 LLM 提示词模板"""
    template_path = Path(__file__).parent.parent / "templates" / "knowledge_comic_prompt.md"
    return template_path.read_text(encoding="utf-8")


def analyze_content(
    text: str,
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
    template_override: str = "",
) -> dict:
    """
    用 LLM 分析知识文案，输出结构化 JSON

    NOTE: 增加了显式 timeout 和重试机制，防止 API 长时间无响应

    @param text: 用户输入的知识文案
    @param api_key: LLM API Key
    @param base_url: LLM API 地址
    @param model: 模型名称
    @param template_override: 强制指定模板（留空则 LLM 自动选择）
    @returns: 结构化数据字典
    """
    system_prompt = _load_llm_template()

    if template_override:
        system_prompt += f"\n\n【强制要求】必须使用 `{template_override}` 模板。"

    # NOTE: 使用 httpx 显式设置连接和读取超时
    http_client = httpx.Client(
        timeout=httpx.Timeout(
            connect=15.0,
            read=LLM_REQUEST_TIMEOUT,
            write=15.0,
            pool=15.0,
        ),
    )

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=http_client,
        max_retries=LLM_MAX_RETRIES,
    )

    logger.info("[LLM] 开始分析文案（%d字）:\n%s", len(text), text)
    t0 = time.time()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=4000,
        )
    except httpx.TimeoutException:
        elapsed = time.time() - t0
        logger.error("[LLM] 请求超时（%.1fs），已达上限 %ds", elapsed, LLM_REQUEST_TIMEOUT)
        raise TimeoutError(
            f"AI 分析超时（{int(elapsed)}秒），请检查网络后重试。"
            f"建议：1. 缩短文案长度 2. 切换模型 3. 稍后再试"
        )
    finally:
        http_client.close()

    raw = response.choices[0].message.content.strip()
    elapsed = time.time() - t0
    logger.info("[LLM] 分析完成（%.1fs），提取 JSON...", elapsed)

    # NOTE: 提取 JSON 块——LLM 可能会包裹在 ```json ... ``` 中
    json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)

    data = json.loads(raw)
    logger.info("[LLM] 模板: %s, 标题: %s", data.get("template"), data.get("title"))
    return data


def generate_illustrations(
    data: dict,
    work_dir: str,
    comfyui_url: str = "",
    style: str = "kawaii",
    progress_callback=None,
) -> dict:
    """
    根据 LLM 输出的 JSON，调用 ComfyUI 批量生成插画

    NOTE: 复用 novel2video 的 ComfyUI 调用逻辑，但独立实现避免耦合

    @param data: LLM 输出的结构化数据
    @param work_dir: 工作目录（保存生成的图片）
    @param comfyui_url: ComfyUI 地址
    @param style: 画风预设
    @param progress_callback: 进度回调
    @returns: 填充了 image_path 的数据字典
    """
    from config import STYLE_PRESETS, ILLUST_SIZE, FOOD_PHOTO_STYLE, COMFYUI_URL

    # NOTE: 如果未传入 comfyui_url，使用 config 中的统一配置（支持环境变量）
    if not comfyui_url:
        comfyui_url = COMFYUI_URL

    style_info = STYLE_PRESETS.get(style, STYLE_PRESETS["kawaii"])
    os.makedirs(work_dir, exist_ok=True)

    template = data.get("template", "cute_panels")

    # 收集所有需要生成的插画任务
    # task 格式: (task_id, prompt, use_food_style)
    tasks = []

    if template == "cute_panels":
        if data.get("mascot_prompt"):
            tasks.append(("mascot", data["mascot_prompt"], False))
        for i, panel in enumerate(data.get("panels", [])):
            tasks.append((f"panel_{i}", panel.get("image_prompt", ""), False))

    elif template == "medical_guide":
        for i, section in enumerate(data.get("sections", [])):
            tasks.append((f"section_{i}", section.get("image_prompt", ""), False))

    elif template == "recipe_card":
        # 头部图——使用 LLM 生成的成品菜描述，回退为通用描述
        header_prompt = data.get("header_prompt", f"finished dish of {data.get('title', '')}, in a bowl, top view, white background")
        tasks.append(("header", header_prompt, True))
        # 食材图——必须食物摄影
        for i, item in enumerate(data.get("ingredients", [])):
            tasks.append((f"ingredient_{i}", item.get("image_prompt", ""), True))
        # 预处理步骤图——食物摄影
        for i, step in enumerate(data.get("prep_steps", [])):
            tasks.append((f"prep_{i}", step.get("image_prompt", ""), True))
        # 制作步骤图——食物摄影
        for i, step in enumerate(data.get("cooking_steps", [])):
            tasks.append((f"cook_{i}", step.get("image_prompt", ""), True))

    total = len(tasks)
    logger.info("[插画] 共 %d 张插画待生成", total)

    # 逐张生成
    image_paths = {}
    for idx, (task_id, prompt, use_food_style) in enumerate(tasks):
        if not prompt:
            continue

        # NOTE: 根据图片类型选择不同的风格和 negative prompt
        if use_food_style:
            cur_style = FOOD_PHOTO_STYLE
        else:
            cur_style = style_info

        full_prompt = f"{prompt}, {cur_style['suffix']}"
        negative = cur_style.get("negative", "text, words, letters, watermark, ugly, blurry, deformed")
        output_path = os.path.join(work_dir, f"{task_id}.png")

        logger.info("[插画] %d/%d: %s (food=%s)", idx + 1, total, task_id, use_food_style)
        success = _generate_single_image(
            full_prompt, output_path,
            cur_style["checkpoint"], cur_style["steps"], cur_style["cfg"],
            comfyui_url, ILLUST_SIZE, negative,
        )

        if success:
            image_paths[task_id] = output_path
        else:
            logger.warning("[插画] %s 生成失败", task_id)

        if progress_callback:
            progress_callback((idx + 1) / total)

    # 将 image_path 填回 data
    data = _fill_image_paths(data, image_paths)
    return data


def _generate_single_image(
    prompt: str,
    output_path: str,
    checkpoint: str,
    steps: int,
    cfg: float,
    comfyui_url: str,
    size: dict,
    negative: str = "text, words, letters, watermark, ugly, blurry, deformed",
) -> bool:
    """
    调用 ComfyUI 生成单张插画

    NOTE: 独立实现——不依赖 novel2video 的 image_generator
    """
    # NOTE: random, io, requests, Image 已在模块顶层导入

    seed = random.randint(1, 2**32 - 1)

    # SDXL 基础工作流
    workflow = {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": size["width"],
                "height": size["height"],
                "batch_size": 1,
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative,
                "clip": ["4", 1],
            },
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_sde",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "8": {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2],
                "tile_size": 256,
                "overlap": 64,
                "temporal_size": 64,
                "temporal_overlap": 8,
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "comic", "images": ["8", 0]},
        },
    }

    try:
        import time
        resp = requests.post(
            f"{comfyui_url}/prompt",
            json={"prompt": workflow},
            timeout=10,
        )
        resp_data = resp.json()

        if resp.status_code != 200 or "error" in resp_data:
            logger.error("[ComfyUI] 请求失败: %s", resp_data)
            return False

        prompt_id = resp_data.get("prompt_id")
        if not prompt_id:
            return False

        # 轮询等待
        for i in range(180):
            time.sleep(1)
            history = requests.get(
                f"{comfyui_url}/history/{prompt_id}", timeout=10
            ).json()

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                if "9" in outputs and "images" in outputs["9"]:
                    img_info = outputs["9"]["images"][0]
                    img_resp = requests.get(
                        f"{comfyui_url}/view",
                        params={
                            "filename": img_info["filename"],
                            "subfolder": img_info.get("subfolder", ""),
                            "type": img_info.get("type", "output"),
                        },
                        timeout=30,
                    )
                    if img_resp.status_code == 200:
                        img = Image.open(io.BytesIO(img_resp.content))
                        img.save(output_path)
                        return True

                status = history[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    return False

        return False

    except Exception as e:
        logger.error("[ComfyUI] 调用失败: %s", e)
        return False


def _fill_image_paths(data: dict, image_paths: dict) -> dict:
    """将生成的图片路径填回 LLM 输出的数据结构"""
    template = data.get("template", "cute_panels")

    if template == "cute_panels":
        if "mascot" in image_paths:
            data["mascot_image"] = image_paths["mascot"]
        for i, panel in enumerate(data.get("panels", [])):
            key = f"panel_{i}"
            if key in image_paths:
                panel["image_path"] = image_paths[key]

    elif template == "medical_guide":
        for i, section in enumerate(data.get("sections", [])):
            key = f"section_{i}"
            if key in image_paths:
                section["image_path"] = image_paths[key]

    elif template == "recipe_card":
        if "header" in image_paths:
            data["header_image"] = image_paths["header"]
        for i, item in enumerate(data.get("ingredients", [])):
            key = f"ingredient_{i}"
            if key in image_paths:
                item["image_path"] = image_paths[key]
        for i, step in enumerate(data.get("prep_steps", [])):
            key = f"prep_{i}"
            if key in image_paths:
                step["image_path"] = image_paths[key]
        for i, step in enumerate(data.get("cooking_steps", [])):
            key = f"cook_{i}"
            if key in image_paths:
                step["image_path"] = image_paths[key]

    return data
