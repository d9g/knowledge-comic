#!/bin/bash
# ═══════════════════════════════════════════
# 知识漫画生成器 — 云端一键部署脚本
# 目标：Ubuntu 24.04 LTS
# ═══════════════════════════════════════════
set -e

APP_DIR="/opt/knowledge-comic"
FRP_VERSION="0.61.1"

echo "========================================"
echo "  知识漫画生成器 — 云端部署"
echo "========================================"

# ── 1. 系统依赖 ──
echo "[1/6] 安装系统依赖..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

# ── 2. 项目代码 ──
echo "[2/6] 部署项目代码..."
if [ ! -d "$APP_DIR" ]; then
    sudo mkdir -p "$APP_DIR"
    sudo chown $USER:$USER "$APP_DIR"
fi

# NOTE: 首次部署用 git clone，后续更新用 git pull
if [ -d "$APP_DIR/.git" ]; then
    echo "  项目已存在，执行 git pull..."
    cd "$APP_DIR" && git pull
else
    echo "  请手动 clone 或 rsync 代码到 $APP_DIR"
    echo "  示例: git clone https://github.com/d9g/knowledge-comic.git $APP_DIR"
    echo "  或者: rsync -avz --exclude='.git' --exclude='output/' ./ 云服务器:$APP_DIR/"
    # 如果当前目录有代码，直接复制
    if [ -f "./app.py" ]; then
        echo "  检测到当前目录有代码，直接复制..."
        cp -r ./* "$APP_DIR/"
    fi
fi

cd "$APP_DIR"

# ── 3. Python 虚拟环境 ──
echo "[3/6] 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# NOTE: 云端只需要 Playwright 做截图，不需要 GPU
playwright install chromium
playwright install-deps

# ── 4. 环境变量 ──
echo "[4/6] 配置环境变量..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  已创建 .env 文件，请编辑填写 API Key："
    echo "  sudo nano $APP_DIR/.env"
fi

# ── 5. frp 服务端 ──
echo "[5/6] 安装 frp 服务端..."
if [ ! -f "/usr/local/bin/frps" ]; then
    cd /tmp
    wget -q "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz"
    tar -xzf "frp_${FRP_VERSION}_linux_amd64.tar.gz"
    sudo cp "frp_${FRP_VERSION}_linux_amd64/frps" /usr/local/bin/
    sudo chmod +x /usr/local/bin/frps
    rm -rf "frp_${FRP_VERSION}_linux_amd64"*
    echo "  frps 已安装到 /usr/local/bin/frps"
else
    echo "  frps 已存在，跳过安装"
fi

# frp 配置
sudo mkdir -p /etc/frp
sudo cp "$APP_DIR/deploy/frps.toml" /etc/frp/frps.toml

# ── 6. systemd 服务 ──
echo "[6/6] 配置 systemd 服务..."

# Streamlit 服务
sudo cp "$APP_DIR/deploy/knowledge-comic.service" /etc/systemd/system/
# frps 服务
sudo cp "$APP_DIR/deploy/frps.service" /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable knowledge-comic frps
sudo systemctl start frps
# NOTE: 先不启动 Streamlit，等用户填完 .env
echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "后续步骤："
echo "  1. 编辑环境变量: sudo nano $APP_DIR/.env"
echo "  2. 修改 frp 密码: sudo nano /etc/frp/frps.toml"
echo "  3. 开放防火墙端口: sudo ufw allow 8550 && sudo ufw allow 7000"
echo "  4. 启动 Streamlit: sudo systemctl start knowledge-comic"
echo "  5. 本地 Windows 启动 frpc: frpc.exe -c frpc.toml"
echo ""
echo "访问地址: http://你的服务器IP:8550"
echo "frp 面板: http://你的服务器IP:7500"
echo ""
