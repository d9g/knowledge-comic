# 知识漫画生成器 — 产品需求文档（PRD）

> **版本**: v2.0  
> **最后更新**: 2026-04-25  
> **维护人**: AI 辅助生成  

---

## 1. 项目概述

### 1.1 产品定位

知识漫画生成器是一款 **AI 驱动的自动化内容创作工具**，将知识文案（养生、食谱、生活技巧等）自动转化为精美的漫画长图，适用于微信公众号、小红书、抖音等内容平台发布。

### 1.2 核心价值

| 维度 | 说明 |
|------|------|
| **内容创作者** | 一键将文字变图片，无需设计技能 |
| **自媒体运营** | 批量生产高质量知识图文内容 |
| **效率提升** | 传统需要 1-2 小时的设计工作压缩到 5 分钟 |

### 1.3 技术架构

```
用户输入文案
    ↓
LLM 分析（OpenAI 兼容协议）→ 结构化 JSON
    ↓
ComfyUI 生成插画（SDXL）→ PNG 图片
    ↓
Jinja2 模板渲染 + Playwright 截图 → 最终长图
```

---

## 2. 功能需求

### 2.1 首页 — 漫画生成（移动端优先）

**路由**: `/`（默认页面）  
**目标用户**: 手机端内容创作者

#### 2.1.1 功能清单

| 功能 | 描述 | 优先级 |
|------|------|--------|
| 文案输入 | 支持输入主题关键词或粘贴完整文案 | P0 |
| AI 分析 | 调用 LLM 将文案转为结构化 JSON | P0 |
| 内容审核 | 展开编辑 JSON，修正 AI 输出 | P0 |
| 模板选择 | 自动/手动选择漫画模板 | P0 |
| 画风选择 | 可爱卡通/扁平插画/韩漫风 | P1 |
| 预览布局 | 不生成插画，仅渲染模板骨架 | P1 |
| 生成图片 | 调用 ComfyUI 生成插画 + 渲染最终长图 | P0 |
| 下载图片 | PNG 格式下载 | P0 |
| API 设置 | 齿轮按钮展开设置面板 | P0 |

#### 2.1.2 移动端适配要求

- 单列布局，最大宽度 600px
- 按钮最小高度 48px（触摸友好）
- 文件上传区域放大点击热区
- 隐藏 Streamlit 默认导航和头部
- 所有交互元素使用 `use_container_width=True`

#### 2.1.3 超时处理

- LLM 分析：连接超时 15s，读取超时 120s
- 超时后显示用户友好提示，包含建议操作
- 自动重试 2 次

### 2.2 管理后台

**路由**: `/admin`  
**目标用户**: 桌面端运营/管理人员

#### 2.2.1 功能清单

| 功能 | 描述 | 优先级 |
|------|------|--------|
| 完整设置 | 侧边栏配置 LLM 提供商/模型/Key | P0 |
| 漫画生成 | 与首页相同的生成流程（桌面布局） | P0 |
| 模板管理 | 上传设计图 → AI 解析 → 生成模板 | P1 |
| 模板保存 | 将 AI 生成的模板保存到 comic_templates | P1 |
| 语法校验 | 自动校验 Jinja2 模板语法 | P1 |

#### 2.2.2 模板管理流程

```
上传设计图 (PNG/JPG)
    ↓
视觉 AI 解析布局（qwen-vl / gpt-4o）
    ↓
生成 Jinja2 HTML 模板
    ↓
自动修复常见语法错误
    ↓
Jinja2 语法校验（通过/警告）
    ↓
渲染预览（Playwright 截图）
    ↓
保存 .html 模板文件 + 写入 custom_templates.json 清单
```

### 2.3 共享设置管理

#### 2.3.1 API 配置

| 提供商 | Base URL | 默认模型 |
|--------|----------|----------|
| 百炼 (DashScope) | `https://coding.dashscope.aliyuncs.com/v1` | qwen-plus |
| DeepSeek | `https://api.deepseek.com` | deepseek-chat |
| OpenAI | `https://api.openai.com/v1` | gpt-4o-mini |
| 自定义 | 用户填写 | 用户填写 |

#### 2.3.2 安全存储

- API Key 使用 **Fernet 对称加密**存储于 `.local_settings.json`
- 密钥由机器特征（用户名 + 主机名 + 盐值）派生
- 兼容旧版明文数据（`sk-` 开头自动识别为未加密）
- 未安装 `cryptography` 库时回退为 base64 编码

---

## 3. 模板体系

### 3.1 内置模板

| 模板 ID | 名称 | 面板数 | 适用场景 |
|---------|------|--------|----------|
| `cute_panels` | 🎀 可爱四宫格 | 3-6 | 生活技巧、养生习惯、日常建议 |
| `medical_guide` | 🏥 图解教程 | 2-4 | 动作指导、穴位按摩、健身教程 |
| `recipe_card` | 🍲 食谱卡片 | 动态 | 食谱、药膳、饮品制作 |

### 3.2 画风预设

| 画风 ID | 名称 | 说明 |
|---------|------|------|
| `kawaii` | 🎀 可爱卡通 | 软糊色、圆形设计、绘本风 |
| `flat` | 📐 扁平插画 | 纯色块、几何图形、信息图风 |
| `manhwa` | 📱 韩漫风 | 清线稿、柔和色调、Webtoon 风 |

### 3.3 自定义模板

支持通过管理后台上传设计图，由 AI 自动生成 Jinja2 HTML 模板。

**动态模板发现机制**（v2.1 新增）：

```
get_all_templates() 合并三种来源：
  1. TEMPLATE_PRESETS（内置，config.py 硬编码）
  2. custom_templates.json（自定义清单，admin 保存时自动写入）
  3. comic_templates/*.html（磁盘扫描，兜底发现未注册模板）
```

- 保存模板时自动注册到 `custom_templates.json` 清单
- 重启后自定义模板仍出现在下拉选择器中
- 手动放入 HTML 文件也会被自动发现（显示为文件名）

模板需满足：

- 页面宽度固定 750px
- 使用 `KuaiLe` 字体（标题）和 `MSYH` 字体（正文）
- 支持 `{{ title }}`、`{% for panel in panels %}` 等标准变量
- 面板数量动态、奇数面板居中

---

## 4. 技术规格

### 4.1 项目结构

```
knowledge_comic/
├── app.py                      # 多页面入口
├── config.py                   # 全局配置（模板/画风/LLM/动态发现）
├── requirements.txt            # Python 依赖
├── start.bat                   # Windows 启动脚本
├── .local_settings.json        # 本地设置（加密 API Key）
│
├── pages/
│   ├── generate.py             # 首页 — 移动端生成漫画
│   ├── admin.py                # 管理后台
│   └── shared.py               # 共享配置/Session/生成逻辑
│
├── core/
│   ├── comic_generator.py      # LLM 分析 + ComfyUI 插画生成
│   ├── comic_renderer.py       # Jinja2 渲染 + Playwright 截图
│   ├── template_analyzer.py    # 设计图 → 模板解析 + 语法校验
│   ├── crypto_utils.py         # API Key 加密/解密
│   └── _playwright_worker.py   # 截图子进程
│
├── comic_templates/            # HTML 漫画模板
│   ├── cute_panels.html        # 内置：可爱四宫格
│   ├── medical_guide.html      # 内置：图解教程
│   ├── recipe_card.html        # 内置：食谱卡片
│   ├── three_gongge.html       # 自定义：三宫格（米色）
│   ├── three_gongge2.html      # 自定义：三宫格（茶方）
│   ├── custom_templates.json   # 自定义模板元数据清单
│   └── fonts/                  # 字体文件
│
├── templates/
│   └── knowledge_comic_prompt.md  # LLM 提示词模板
│
├── docs/
│   └── PRD.md                  # 产品需求文档
│
└── output/                     # 生成的漫画输出目录
```

### 4.2 依赖清单

| 包 | 版本 | 用途 |
|------|------|------|
| streamlit | ≥1.30 | Web UI 框架 |
| openai | ≥1.10 | LLM API 调用 |
| jinja2 | ≥3.1 | HTML 模板渲染 |
| playwright | ≥1.40 | 浏览器截图 |
| requests | ≥2.31 | ComfyUI API 调用 |
| Pillow | ≥10.0 | 图片处理 |
| httpx | ≥0.27 | HTTP 超时控制 |
| cryptography | ≥42.0 | API Key 加密（可选） |

### 4.3 外部服务依赖

| 服务 | 说明 | 必需 |
|------|------|------|
| LLM API | 文案分析（OpenAI 兼容协议） | ✅ 是 |
| ComfyUI | SDXL 插画生成 | ❌ 可选（无则用占位图） |

### 4.4 超时与重试策略

| 场景 | 连接超时 | 读取超时 | 重试次数 |
|------|----------|----------|----------|
| LLM 文案分析 | 15s | 120s | 2 |
| 模板解析（视觉 AI） | 15s | 180s | 1 |
| ComfyUI 提交 | 10s | — | 0 |
| ComfyUI 轮询 | 10s | — | 180 轮 |
| Playwright 截图 | — | 30s | 0 |

---

## 5. 安全设计

### 5.1 API Key 存储

```
用户输入 API Key
    ↓
Fernet 加密（密钥 = SHA256(用户名 + 主机名 + 盐)）
    ↓
写入 .local_settings.json
    ↓
读取时解密，仅在内存中存在明文
```

**兼容策略**：
- `sk-` 开头 → 旧版明文，直接使用
- `b64:` 开头 → base64 编码（`cryptography` 未安装时的回退）
- 其他 → Fernet 密文，解密使用

### 5.2 安全边界

| 措施 | 说明 |
|------|------|
| Key 加密 | Fernet + 机器特征派生密钥 |
| 环境变量支持 | 优先读取 `DASHSCOPE_API_KEY` 等环境变量 |
| 内存生命周期 | 明文 Key 仅存在于运行时 Session |
| 传输安全 | 所有 API 调用走 HTTPS |

### 5.3 已知限制

- `.local_settings.json` 文件本身未做文件系统权限控制
- 密钥派生基于机器特征，同机器同用户可解密
- 本方案适用于 **个人/小团队本地部署** 场景，生产环境建议使用 Vault 等方案

---

## 6. AI 模板语法校验

### 6.1 问题背景

AI 生成的 Jinja2 模板经常包含语法错误：
- `{% if var is defined %}` — 简单 Environment 未注册 `defined` test
- `{% if var is not none %}` — 同上
- `{% if var is string %}` — 未注册 `string` test

### 6.2 解决方案

```
AI 生成 HTML 模板
    ↓
自动修复（正则替换常见错误模式）
    ├── is defined → 删除
    ├── is not none → 删除
    └── is string/mapping/iterable → 删除
    ↓
Jinja2 语法校验（env.parse）
    ├── 通过 → 正常流程
    └── 失败 → 显示警告 + 仍保存（允许手动修改）
```

### 6.3 提示词优化

在系统提示词中新增 **Jinja2 语法注意事项** 章节，明确禁止使用 `is defined`、`is not none` 等 test 语法，从源头减少错误。

---

## 7. 运行与部署

### 7.1 快速启动

```bash
# 方式一：双击 start.bat（Windows）
start.bat

# 方式二：手动启动
pip install -r requirements.txt
playwright install chromium
python -m streamlit run app.py --server.port 8550
```

### 7.2 访问地址

| 页面 | URL | 说明 |
|------|-----|------|
| 首页（生成漫画） | `http://localhost:8550/` | 移动端适配 |
| 管理后台 | `http://localhost:8550/admin` | 桌面端 |

### 7.3 环境变量（可选）

| 变量名 | 说明 |
|--------|------|
| `DASHSCOPE_API_KEY` | 百炼 API Key |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `OPENAI_API_KEY` | OpenAI API Key |

---

## 8. 版本记录

### v2.1（2026-04-25）

- ✅ 动态模板发现机制（内置 + 自定义清单 + 磁盘扫描）
- ✅ 自定义模板元数据清单（custom_templates.json）
- ✅ 模板选择器改为下拉菜单（支持无限扩展）
- ✅ 保存模板时自动注册到清单
- ✅ 代码审计：消除 generate/admin 的重复逻辑（提取到 shared.py）
- ✅ 代码审计：清理未使用的 import 和死代码
- ✅ 修复 admin 侧边栏默认导航泄露
- ✅ PRD 文档和 README 更新

### v2.0（2026-04-25）

- ✅ 多页面架构重构（生成页 + 管理后台）
- ✅ 移动端首页适配（触摸友好、单列布局）
- ✅ API 超时优化（httpx 显式超时 + 重试）
- ✅ AI 模板语法校验与自动修复
- ✅ API Key 加密存储（Fernet + 机器特征）
- ✅ 共享设置管理（shared.py）
- ✅ 百炼 API 配置修复
- ✅ Jinja2 渲染健壮性修复

### v1.0（初始版本）

- 单页面 Streamlit 应用
- LLM 文案分析
- ComfyUI 插画生成
- Jinja2 模板渲染
- 3 种内置模板 + 3 种画风
