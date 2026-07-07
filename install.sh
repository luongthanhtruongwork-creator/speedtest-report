#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  install.sh — BeyondNet Speedtest Report — installer
#  Ubuntu 24.04.4 LTS (noble)
#  Chạy 1 lệnh, không hỏi gì, cài xong là có thể test ngay.
#  Telegram token/chat id điền sau vào config.json (xem README.md).
# ─────────────────────────────────────────────────────────────
set -e
INSTALL_DIR="/opt/speedtest"
VENV="$INSTALL_DIR/venv"
SCRIPT="$INSTALL_DIR/speedtest_report.py"
CONFIG_FILE="$INSTALL_DIR/config.json"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== BeyondNet Speedtest Report — Setup ==="

# 1. System packages
echo "[1/6] Cài system packages..."
sudo apt update -qq
sudo apt install -y python3 python3-venv cron iputils-ping curl

# 2. Ookla CLI (bắt buộc dùng jammy trên Ubuntu 24.04 noble)
echo "[2/6] Cài Ookla Official CLI..."
if ! command -v speedtest &>/dev/null || [ "$(stat -c%s "$(which speedtest)" 2>/dev/null || echo 0)" -lt 100000 ]; then
    curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
    sudo sed -i 's/noble/jammy/g' /etc/apt/sources.list.d/ookla_speedtest-cli.list
    sudo apt update -qq && sudo apt install -y speedtest
else
    echo "  Ookla CLI đã có sẵn: $(speedtest --version 2>/dev/null | head -1)"
fi
speedtest --accept-license --accept-gdpr > /dev/null 2>&1 || true

# 3. Cron service
echo "[3/6] Khởi động cron..."
sudo systemctl enable cron --quiet
sudo systemctl start cron || true

# 4. Python venv + packages
echo "[4/6] Tạo venv và cài Python packages..."
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER:$USER" "$INSTALL_DIR"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$SRC_DIR/requirements.txt"

# 5. Copy script + config mẫu (KHÔNG hỏi gì — user tự điền config.json sau)
echo "[5/6] Copy script..."
cp "$SRC_DIR/speedtest_report.py" "$SCRIPT"
if [ -f "$CONFIG_FILE" ]; then
    echo "  config.json đã tồn tại, giữ nguyên."
else
    cp "$SRC_DIR/config.example.json" "$CONFIG_FILE"
    echo "  Đã tạo $CONFIG_FILE từ mẫu — CHƯA điền Telegram, sửa sau bằng: nano $CONFIG_FILE"
fi

# 6. Đăng ký cron 23:59 hàng ngày (tự động, không hỏi)
echo "[6/6] Đăng ký cron..."
CRON_LINE="59 23 * * * $VENV/bin/python3 $SCRIPT >> $INSTALL_DIR/cron.log 2>&1"
(crontab -l 2>/dev/null | grep -qF "speedtest_report.py") \
    || ( (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab - )

echo ""
echo "✅ Cài đặt xong! (chưa cần điền Telegram cũng chạy được — PDF vẫn lưu local)"
echo ""
echo "Test thử ngay:"
echo "   $VENV/bin/python3 $SCRIPT"
echo ""
echo "Điền Telegram Bot Token / Chat ID sau khi có:"
echo "   nano $CONFIG_FILE"
echo ""
