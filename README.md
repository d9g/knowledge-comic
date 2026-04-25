# 📚 知识漫画生成器 (Knowledge Comic)

AI 驱动的知识漫画自动生成工具 — 输入文案，一键生成精美漫画长图。

## ✨ 功能

- 🤖 **AI 内容分析** — 文案自动拆分为结构化知识点
- 🎨 **ComfyUI 插画** — SDXL 自动生成配图（可选）
- 📐 **多模板支持** — 内置 + 自定义模板，下拉选择
- 🖼️ **一键出图** — Playwright 截图生成高清 PNG 长图
- 🔐 **安全部署** — Admin 密码保护、API Key 加密、访问审计

## 🚀 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 启动（Windows 可直接双击 start.bat）
python -m streamlit run app.py --server.port 8550
```

访问 `http://localhost:8550` 即可使用。

## ⚙️ 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 百炼 API Key | — |
| `COMFYUI_URL` | ComfyUI 地址 | `http://127.0.0.1:8188` |
| `ADMIN_USERNAME` | 管理后台用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理后台密码（空=不验证） | — |
| `REQUIRE_WECHAT_FOLLOW` | 微信关注验证开关 | `false` |

## 🏗️ 云端部署

推荐架构：**云端跑 Streamlit + 本地 GPU 跑 ComfyUI**，通过 frp 隧道连接。

```
用户（手机/PC）
    ↓
云服务器（Streamlit + LLM API）
    ↓ frp 隧道（仅转发 8188 端口）
本地 GPU 机器（ComfyUI）
```

**云服务器（Ubuntu）：**
1. 克隆代码，创建 venv，`pip install -r requirements.txt && playwright install chromium`
2. 复制 `.env.example` 为 `.env`，填写 API Key 和 `ADMIN_PASSWORD`
3. 安装 [frps](https://github.com/fatedier/frp/releases)，配置监听端口
4. 用 systemd 管理 Streamlit 和 frps 服务

**本地 GPU 机器（Windows）：**
1. 启动 ComfyUI（默认 8188 端口）
2. 下载 [frpc](https://github.com/fatedier/frp/releases)，配置 `serverAddr` 为云服务器 IP
3. 运行 `frpc -c frpc.toml`

## 📁 项目结构

```
├── app.py                  # 多页面入口
├── config.py               # 全局配置（LLM/ComfyUI/访问控制）
├── pages/
│   ├── generate.py         # 首页（移动端适配）
│   ├── admin.py            # 管理后台（密码保护）
│   └── shared.py           # 共享逻辑
├── core/
│   ├── comic_generator.py  # LLM 分析 + ComfyUI 生成
│   ├── comic_renderer.py   # Jinja2 + Playwright 渲染
│   ├── template_analyzer.py # 设计图→模板解析
│   ├── crypto_utils.py     # API Key 加密
│   └── audit.py            # 访问审计日志
├── comic_templates/        # HTML 模板 + 字体
├── templates/              # LLM 提示词模板
└── docs/PRD.md             # 产品需求文档
```

## 📝 License

MIT
