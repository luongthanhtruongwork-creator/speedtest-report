# Speedtest Report

Tool tự động test tốc độ mạng quốc tế (Korea / Singapore / Hong Kong / Vietnam), xuất báo cáo PDF và gửi qua Telegram. Chạy bằng Ookla Speedtest CLI chính thức, tự chọn server đang hoạt động (bỏ qua server chết), lưu lịch sử 90 ngày (JSON) và **10 bản PDF gần nhất** (PDF cũ hơn tự xoá).

## Yêu cầu

- Ubuntu Server 22.04/24.04 (đã test trên 24.04.4 LTS)
- Quyền `sudo`
- (Tuỳ chọn) 1 Telegram Bot Token + Chat ID (tạo qua [@BotFather](https://t.me/BotFather)) — **không bắt buộc để cài đặt hoặc chạy**, chỉ cần nếu muốn tự động gửi PDF qua Telegram.

## Cài đặt nhanh (máy mới)

```bash
git clone <URL_REPO_CUA_BAN> speedtest-report
cd speedtest-report
chmod +x install.sh
./install.sh
```

`install.sh` chạy **hoàn toàn tự động, không hỏi gì**:
1. Cài `python3`, `python3-venv`, `cron`, `curl`, `iputils-ping`
2. Cài Ookla Speedtest CLI (tự xử lý vụ Ubuntu 24.04 chưa có package `noble`)
3. Bật service `cron`
4. Tạo Python venv tại `/opt/speedtest/venv` + cài package trong `requirements.txt`
5. Copy `speedtest_report.py` vào `/opt/speedtest/`, copy `config.example.json` → `config.json` nếu chưa có (giữ nguyên placeholder, **chưa điền Telegram**)
6. Tự đăng ký cron chạy 23:59 hàng ngày

Cài xong là chạy được ngay — **chưa cần điền Telegram Token/Chat ID**. Lúc chưa điền, script vẫn test speedtest và lưu PDF vào `/opt/speedtest/` bình thường để xem, chỉ bỏ qua bước gửi Telegram (in cảnh báo, không lỗi, không crash).

## Điền Telegram Token sau (khi nào có thì điền)

Mỗi máy có 1 file `/opt/speedtest/config.json` riêng (không nằm trong git, không bị ghi đè khi `git pull`):

```json
{
  "TELEGRAM_BOT_TOKEN": "YOUR_BOT_TOKEN_HERE",
  "TELEGRAM_CHAT_ID": "YOUR_CHAT_ID_HERE",
  "LOCATION_NAME": "Ten cong ty - Thanh pho"
}
```

Sửa trực tiếp:

```bash
nano /opt/speedtest/config.json
```

Không cần restart gì cả — lần chạy tiếp theo (thủ công hoặc cron) sẽ tự đọc giá trị mới và bắt đầu gửi Telegram.

## Chạy thủ công (test hoặc lấy kết quả ngay lập tức)

```bash
cd /opt/speedtest
./venv/bin/python3 speedtest_report.py
```

Chạy tay hay để cron tự chạy đều dùng chung 1 script, ra cùng 1 chỗ lưu PDF (`/opt/speedtest/speedtest_report_*.pdf`) và dùng chung cơ chế giữ 10 bản gần nhất — chạy tay nhiều lần không làm phình thư mục.

## Cron

Đã tự đăng ký lúc cài. Kiểm tra / sửa tay:

```bash
crontab -l
crontab -e
```

Dòng mặc định:
```
59 23 * * * /opt/speedtest/venv/bin/python3 /opt/speedtest/speedtest_report.py >> /opt/speedtest/cron.log 2>&1
```

## Cấu trúc thư mục sau khi cài

```
/opt/speedtest/
├── speedtest_report.py       # script chính
├── config.json                # secret riêng máy này (không ở trong git)
├── venv/                      # Python venv
├── speedtest_report_*.pdf     # PDF các lần chạy gần nhất — tự giữ 10 bản, xoá bản cũ
├── speedtest_log.json         # lịch sử 90 ngày (JSON, không phải PDF)
└── cron.log                   # output cron
```

## Tuỳ chỉnh

- **Số lượng PDF giữ lại**: thêm `"KEEP_PDF_COUNT": 20` (ví dụ) vào `config.json`, mặc định là 10.
- **Danh sách server test**: nằm trong `speedtest_report.py` ở biến `DEFAULT_CONFIG["SERVER_GROUPS"]` (nhiều ID dự phòng mỗi nước, tự bỏ qua ID chết). Muốn đổi server/quốc gia, sửa trực tiếp phần này rồi copy lại vào `/opt/speedtest/speedtest_report.py`.

## Xử lý sự cố

Xem `CLAUDE.md` — ghi lại các lỗi hay gặp trên Ubuntu 24.04 (Ookla CLI bị 403, PEP 668, format JSON...) và cách đã xử lý.
