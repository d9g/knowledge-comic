# 📚 知识漫画生成器 (Knowledge Comic)

AI 驱动的知识漫画自动生成工具 — 输入文案，一键生成精美漫画长图。

## ✨ 功能

- 🤖 **AI 内容分析** — 文案自动拆分为结构化知识点
- 🎨 **ComfyUI 插画** — SDXL 自动生成配图（可选）
- 📐 **多模板支持** — 内置 + 自定义模板，下拉选择
- 🖼️ **一键出图** — Playwright 截图生成高清 PNG 长图
- 🔐 **安全部署** — Admin 密码保护、API Key 加密、访问审计

## 🏗️ 架构

```
用户（手机/PC）
    ↓
云服务器（Streamlit + LLM API 调用）
    ↓ frp 隧道
本地 GPU 机器（ComfyUI 插画生成）
```

## 🚀 快速开始

### 本地开发

```bash
# Windows
start.bat

# 或手动启动
pip install -r requirements.txt
playwright install chromium
python -m streamlit run app.py --server.port 8550
```

### 云端部署（Ubuntu 24.04）

```bash
# 1. 克隆代码
git clone https://github.com/d9g/knowledge-comic.git /opt/knowledge-comic
cd /opt/knowledge-comic

# 2. 一键部署
bash deploy/deploy-cloud.sh

# 3. 编辑环境变量
sudo nano /opt/knowledge-comic/.env

# 4. 启动服务
sudo systemctl start knowledge-comic

# 5. 本地 Windows 启动 frpc（穿透 ComfyUI）
# 编辑 deploy/frpc.toml 填写云服务器 IP
# 下载 frpc.exe 放到项目目录
start_frpc.bat
```

## ⚙️ 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 百炼 API Key | — |
| `COMFYUI_URL` | ComfyUI 地址 | `http://127.0.0.1:8188` |
| `ADMIN_USERNAME` | 管理后台用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理后台密码（空=不验证） | — |
| `REQUIRE_WECHAT_FOLLOW` | 是否需要微信关注验证 | `false` |
| `WECHAT_FOLLOW_GUIDE` | 关注引导文案 | — |

## 📁 项目结构

```
├── app.py                  # 多页面入口
├── config.py               # 全局配置
├── pages/
│   ├── generate.py         # 首页（移动端适配）
│   ├── admin.py            # 管理后台（密码保护）
│   └── shared.py           # 共享逻辑
├── core/
│   ├── comic_generator.py  # LLM + ComfyUI 生成
│   ├── comic_renderer.py   # Jinja2 + Playwright 渲染
│   ├── template_analyzer.py # 设计图→模板解析
│   ├── crypto_utils.py     # API Key 加密
│   └── audit.py            # 访问审计日志
├── comic_templates/        # HTML 模板 + 字体
├── deploy/                 # 部署配置
│   ├── deploy-cloud.sh     # 云端一键部署
│   ├── frps.toml           # frp 服务端配置
│   ├── frpc.toml           # frp 客户端配置
│   └── *.service           # systemd 服务
└── docs/PRD.md             # 产品需求文档
```

## 📝 License

MIT
