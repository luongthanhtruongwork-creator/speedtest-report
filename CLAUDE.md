# Project: Daily Speedtest PDF Report
**BeyondNet VN** — Network Monitoring Tool  
**Status:** Working on production server  
**Last updated:** 24/06/2026

---

## 🎯 Mục tiêu dự án

Tool chạy tự động trên Ubuntu Server 24.04 lúc **23:59 mỗi ngày**:
1. Test tốc độ mạng đến **9 server quốc tế** (Korea / Singapore / Hong Kong)
2. Xuất **báo cáo PDF** có biểu đồ và bảng chi tiết
3. Gửi PDF qua **Telegram Bot**

---

## 🖥️ Môi trường production

```
OS:      Ubuntu Server 24.04.4 LTS (noble)
Python:  3.12.3
Path:    /opt/speedtest/
venv:    /opt/speedtest/venv/
Cron:    59 23 * * * /opt/speedtest/venv/bin/python3 /opt/speedtest/speedtest_report.py >> /opt/speedtest/cron.log 2>&1
```

---

## ⚠️ Các vấn đề đã giải quyết (QUAN TRỌNG — đừng thay đổi)

### 1. `speedtest-cli` Python bị Ookla chặn (403 Forbidden)
- **Đừng dùng:** `pip install speedtest-cli`
- **Dùng:** Ookla Official CLI binary `/usr/bin/speedtest`
- Cài: thêm repo ookla nhưng phải đổi `noble` → `jammy` vì chưa có package noble:
  ```bash
  curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
  sudo sed -i 's/noble/jammy/g' /etc/apt/sources.list.d/ookla_speedtest-cli.list
  sudo apt update && sudo apt install speedtest -y
  ```

### 2. Ubuntu 24.04 PEP 668 — không pip install global
- Phải dùng venv: `python3 -m venv /opt/speedtest/venv`
- Cron phải dùng python trong venv: `/opt/speedtest/venv/bin/python3`

### 3. Ookla CLI JSON format
- `download.bandwidth` và `upload.bandwidth` đơn vị là **bytes/s**
- Công thức: `Mbps = bandwidth * 8 / 1_000_000`
- Có thêm `packetLoss`, `ping.jitter` — cần include vào report

---

## 📋 Server IDs cần test

```python
SERVER_GROUPS = {
    "Korea":     {"flag": "🇰🇷", "ids": [70133, 67564, 48402]},
    "Singapore": {"flag": "🇸🇬", "ids": [13623, 50344, 7311]},
    "Hong Kong": {"flag": "🇭🇰", "ids": [65463, 60177, 37390]},
}
```

---

## 📦 Dependencies (trong venv)

```
requests      - HTTP calls + Telegram API
reportlab     - tạo PDF
matplotlib    - bar charts (backend: Agg — không cần GUI)
```
**Không cần** `speedtest-cli` Python package.

---

## 🏗️ Kiến trúc script (`speedtest_report.py`)

```
main()
├── Verify /usr/bin/speedtest binary exists
├── Loop SERVER_GROUPS (3 groups × 3 servers = 9 tests)
│   └── run_speedtest(server_id)
│       └── subprocess.run(["speedtest", "--server-id=X", "--format=json", ...])
│           └── parse JSON → dict {download_mbps, upload_mbps, ping_ms, jitter_ms, loss_pct, ...}
├── save_log() → speedtest_log.json (lưu 90 ngày)
├── generate_pdf(all_results, report_time)
│   ├── reportlab: Header banner, Summary cards (5 cards)
│   ├── matplotlib: Bar chart Download (9 servers, 3 màu theo quốc gia)
│   ├── reportlab: Detail table per group (ID, Server, ISP, DL, UL, Ping, Jitter, Loss, Rating)
│   ├── matplotlib: Bar chart Ping + Bar chart Upload
│   └── reportlab: Rating legend + Footer
└── send_telegram_pdf() → API sendDocument (multipart/form-data)
```

---

## 📊 Rating scale (đã điều chỉnh cho đường truyền quốc tế tốc độ cao)

| Rating | Download | Ping |
|--------|----------|------|
| EXCELLENT | ≥ 500 Mbps | ≤ 80 ms |
| GOOD | ≥ 200 Mbps | ≤ 120 ms |
| FAIR | ≥ 50 Mbps | ≤ 200 ms |
| POOR | < 50 Mbps | > 200 ms |

> Lý do threshold cao: server BeyondNet có đường truyền thực tế ~929 Mbps đến Singapore

---

## 📁 File structure

```
/opt/speedtest/
├── speedtest_report.py      ← script chính (file này)
├── venv/                    ← Python venv
├── speedtest_report.pdf     ← PDF mới nhất
├── speedtest_log.json       ← lịch sử 90 ngày
└── cron.log                 ← output cron
```

---

## 🔮 Các tính năng có thể thêm (backlog)

- [ ] So sánh với ngày hôm qua trong PDF (trend up/down)
- [ ] Alert Telegram riêng khi có server POOR hoặc packet loss > 0%
- [ ] Test thêm server Việt Nam (Viettel 26853, FPT 2515, VNPT 6106) để compare domestic vs international
- [ ] Weekly summary report mỗi thứ Hai
- [ ] Export chart theo tuần/tháng từ `speedtest_log.json`
- [ ] Web dashboard đơn giản đọc từ log JSON

---

## 📞 Telegram API snippet

```python
# Gửi PDF
requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendDocument",
    data={"chat_id": CHAT_ID, "caption": "...", "parse_mode": "Markdown"},
    files={"document": ("speedtest_report.pdf", open(path,'rb'), "application/pdf")},
    timeout=60
)

# Gửi text alert
requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": "...", "parse_mode": "Markdown"}
)
```

---

## 🧪 Test command

```bash
cd /opt/speedtest
source venv/bin/activate
python3 speedtest_report.py

# Test 1 server nhanh
speedtest --server-id=13623 --format=json | python3 -m json.tool
```
