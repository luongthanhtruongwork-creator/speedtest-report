#!/usr/bin/env python3
"""
Daily International Speedtest - PDF Report & Telegram Bot
BeyondNet VN | Engine: Ookla Official CLI v1.2.0
Servers: Korea / Singapore / Hong Kong / Vietnam
"""

import subprocess, requests, json, datetime, socket, time, sys, io
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Cấu hình riêng cho từng máy (Telegram token, chat id, tên vị trí) nằm ở
# config.json cạnh file này — KHÔNG commit lên git (xem config.example.json
# làm mẫu). Nếu user chưa điền/chưa tạo config.json, script vẫn chạy speedtest
# và lưu PDF bình thường — chỉ bỏ qua bước gửi Telegram (xem telegram_configured()).
#
# Các phần dùng chung cho mọi máy (danh sách server, ngưỡng rating...) để
# ngay trong code làm mặc định. Mỗi nhóm liệt kê nhiều server ID ứng viên
# (lấy từ danh mục thật của Ookla, xem
# https://www.speedtest.net/api/js/servers?search=<country>) — vì server có
# thể ngừng hoạt động theo thời gian, main() sẽ thử lần lượt từng ID và chỉ
# giữ lại TARGET_PER_GROUP server đang hoạt động thật sự cho báo cáo.
DEFAULT_CONFIG = {
    "TELEGRAM_BOT_TOKEN": "YOUR_BOT_TOKEN_HERE",
    "TELEGRAM_CHAT_ID":   "YOUR_CHAT_ID_HERE",
    "LOCATION_NAME":      "Chua dat ten",
    "LOG_FILE":           "speedtest_log.json",
    "SPEEDTEST_BIN":      "/usr/bin/speedtest",
    "TARGET_PER_GROUP":   3,
    "KEEP_PDF_COUNT":     10,
    "SERVER_GROUPS": {
        "Korea":     {"flag": "🇰🇷", "ids": [70133, 67564, 48402, 73226]},
        "Singapore": {"flag": "🇸🇬", "ids": [13623, 50344, 7311, 5935, 59016]},
        "Hong Kong": {"flag": "🇭🇰", "ids": [65463, 60177, 1536, 61296, 70128]},
        "Vietnam":   {"flag": "🇻🇳", "ids": [26853, 74354, 17758, 55436, 18250]},
    }
}

def load_config():
    config_path = Path(__file__).parent / "config.json"
    user_config = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            user_config = json.load(f)
    return {**DEFAULT_CONFIG, **user_config}

def telegram_configured():
    token = str(CONFIG.get("TELEGRAM_BOT_TOKEN", ""))
    chat_id = str(CONFIG.get("TELEGRAM_CHAT_ID", ""))
    return bool(token) and not token.startswith("YOUR_") \
       and bool(chat_id) and not chat_id.startswith("YOUR_")

CONFIG = load_config()
# ─────────────────────────────────────────────────────────────

LOG_PATH = Path(__file__).parent / CONFIG["LOG_FILE"]

def pdf_path_for(report_time):
    return Path(__file__).parent / f"speedtest_report_{report_time.strftime('%Y-%m-%d-%H%M%S')}.pdf"

RATING_HEX = {
    "EXCELLENT": "#22c55e", "GOOD": "#3b82f6",
    "FAIR": "#f59e0b", "POOR": "#ef4444", "FAILED": "#94a3b8",
}
GROUP_HEX = {"Korea": "#8b5cf6", "Singapore": "#22c55e",
             "Hong Kong": "#ec4899", "Vietnam": "#ef4444"}


def get_hostname():
    try: return socket.gethostname()
    except: return "unknown"


def run_speedtest(server_id, expected_group=None):
    cmd = [CONFIG["SPEEDTEST_BIN"], f"--server-id={server_id}",
           "--format=json", "--accept-license", "--accept-gdpr"]
    r = None
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return _err(server_id, (r.stderr or r.stdout or "exit error").strip()[:150])
        d = json.loads(r.stdout)
        country = d["server"].get("country", "?")
        # --server-id doesn't validate country: a stale/wrong id can silently
        # return a server from a totally different country, so check here.
        if expected_group and expected_group.lower() not in country.lower():
            return _err(server_id, f"Country mismatch: expected {expected_group}, got {country}")
        # "isp"/"interface.externalIp" describe OUR OWN connection (the client
        # running the test), not the remote test server — same on every row,
        # shown so the report records which public IP/ISP was used that day.
        client_ip  = d.get("interface", {}).get("externalIp", "?")
        client_isp = d.get("isp", "?")
        return {
            "server_id":     server_id,
            "server_name":   f"{d['server'].get('name','?')} - {d['server'].get('location','?')}",
            "country":       country,
            "isp":           f"{client_ip} - {client_isp}",
            "download_mbps": round(d["download"]["bandwidth"] * 8 / 1_000_000, 2),
            "upload_mbps":   round(d["upload"]["bandwidth"]   * 8 / 1_000_000, 2),
            "ping_ms":       round(d["ping"]["latency"],  2),
            "jitter_ms":     round(d["ping"]["jitter"],   2),
            "loss_pct":      round(d.get("packetLoss", 0), 1),
            "result_url":    d.get("result", {}).get("url", ""),
            "status":        "OK",
        }
    except subprocess.TimeoutExpired:
        return _err(server_id, "Timeout 120s")
    except (json.JSONDecodeError, KeyError) as e:
        raw = (r.stdout if r else "")[:200]
        return _err(server_id, f"Parse error: {e} raw={raw}")
    except FileNotFoundError:
        return _err(server_id, f"Binary not found: {CONFIG['SPEEDTEST_BIN']}")
    except Exception as e:
        return _err(server_id, str(e)[:150])


def _err(sid, msg):
    return {"server_id": sid, "server_name": f"Server {sid}",
            "country": "—", "isp": "—", "download_mbps": 0, "upload_mbps": 0,
            "ping_ms": 0, "jitter_ms": 0, "loss_pct": 0, "result_url": "",
            "status": f"ERROR: {msg}"}


def rating(dl, ping):
    if dl == 0: return "FAILED"
    if dl >= 500 and ping <= 80:  return "EXCELLENT"
    if dl >= 200 and ping <= 120: return "GOOD"
    if dl >= 50  and ping <= 200: return "FAIR"
    return "POOR"


def generate_pdf(all_results, report_time):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, Image, PageBreak)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    pdf_path = pdf_path_for(report_time)
    W, H = A4
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
        title=pdf_path.name,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm)

    CP = colors.HexColor('#1a3c5e'); CA = colors.HexColor('#2196F3')
    CLG = colors.HexColor('#f8fafc'); CL = colors.HexColor('#e8f4fd')
    CBR = colors.HexColor('#e2e8f0'); CGR = colors.HexColor('#64748b'); CW = colors.white

    # Common total width so the header banner, cards, detail tables and
    # legend all line up flush instead of drifting to different widths.
    CONTENT_W = 197*mm

    def P(txt, **kw): return Paragraph(txt, ParagraphStyle('x', **kw))

    story = []

    # HEADER
    sub = (f"{report_time.strftime('%A, %d %B %Y  –  %H:%M')}  "
           f"|  {CONFIG['LOCATION_NAME']}  |  {get_hostname()}")
    logo_title = ("<font size='14' color='#fb923c'><b>Beyond</b></font>"
                  "<font size='14' color='#60a5fa'><b>Net</b></font><br/>"
                  "📶  DAILY SPEEDTEST REPORT")
    ht = Table([
        [P(logo_title,
           fontName='Helvetica-Bold', fontSize=20, textColor=CW, alignment=TA_CENTER, leading=24)],
        [P(sub, fontName='Helvetica', fontSize=9,
           textColor=colors.HexColor('#cce5ff'), alignment=TA_CENTER)],
    ], colWidths=[CONTENT_W])
    ht.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),CP),
        ('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14),
        ('LEFTPADDING',(0,0),(-1,-1),16),('RIGHTPADDING',(0,0),(-1,-1),16)]))
    story.append(ht); story.append(Spacer(1,10))

    # SUMMARY CARDS
    flat_ok = [r for g in all_results.values() for r in g["results"] if r["status"]=="OK"]
    total = sum(len(g["results"]) for g in all_results.values())
    ok_n  = len(flat_ok)
    avg_dl   = round(sum(r["download_mbps"] for r in flat_ok)/ok_n,1) if flat_ok else 0
    avg_ul   = round(sum(r["upload_mbps"]   for r in flat_ok)/ok_n,1) if flat_ok else 0
    avg_pg   = round(sum(r["ping_ms"]       for r in flat_ok)/ok_n,1) if flat_ok else 0
    avg_loss = round(sum(r["loss_pct"]      for r in flat_ok)/ok_n,1) if flat_ok else 0

    CARD_W = CONTENT_W/5

    def card(lbl, val, unit, bg):
        t = Table([[P(lbl, fontName='Helvetica', fontSize=7, textColor=CGR, alignment=TA_CENTER)],
                   [P(f"<b>{val}</b> <font size='8'>{unit}</font>",
                      fontName='Helvetica-Bold', fontSize=17, textColor=CP, alignment=TA_CENTER)]],
                  colWidths=[CARD_W])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),bg),
            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
            ('ALIGN',(0,0),(-1,-1),'CENTER')]))
        return t

    cards = Table([[card("TESTS OK",f"{ok_n}/{total}","",CLG),
                    card("AVG DOWNLOAD",str(avg_dl),"Mbps",CL),
                    card("AVG UPLOAD",str(avg_ul),"Mbps",CL),
                    card("AVG PING",str(avg_pg),"ms",CLG),
                    card("PKT LOSS",f"{avg_loss}","%",
                         colors.HexColor('#fff3cd') if avg_loss>0 else CLG)]],
                  colWidths=[CARD_W]*5)
    cards.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2)]))
    story.append(cards); story.append(Spacer(1,12))

    # CHART DATA
    grp_names = list(all_results.keys())
    x_labels=[]; dl_vals=[]; ul_vals=[]; ping_vals=[]; bar_clrs=[]
    legend_patches=[mpatches.Patch(color=GROUP_HEX[g], label=g) for g in grp_names]
    for gi,grp in enumerate(grp_names):
        for r in all_results[grp]["results"]:
            x_labels.append(f"#{r['server_id']}")
            dl_vals.append(r["download_mbps"]); ul_vals.append(r["upload_mbps"])
            ping_vals.append(r["ping_ms"]); bar_clrs.append(GROUP_HEX[grp])

    def bar_chart(values, ylabel, h_in=2.5, fmt="{:.0f}"):
        fig,ax = plt.subplots(figsize=(7.2,h_in))
        fig.patch.set_facecolor('#f8fafc'); ax.set_facecolor('#f8fafc')
        bars=ax.bar(range(len(x_labels)),values,color=bar_clrs,width=0.6,edgecolor='white',linewidth=0.8)
        mx=max(values) if values else 1
        for b,v in zip(bars,values):
            if v>0:
                ax.text(b.get_x()+b.get_width()/2, b.get_height()+mx*0.01,
                        fmt.format(v),ha='center',va='bottom',fontsize=7,
                        fontweight='bold',color='#1a3c5e')
        ax.set_xticks(range(len(x_labels))); ax.set_xticklabels(x_labels,fontsize=7.5)
        ax.set_ylabel(ylabel,fontsize=8,color='#64748b')
        ax.tick_params(axis='y',labelsize=7.5,colors='#64748b')
        ax.tick_params(axis='x',colors='#374151')
        for sp in ['top','right']: ax.spines[sp].set_visible(False)
        ax.spines['left'].set_color('#e2e8f0'); ax.spines['bottom'].set_color('#e2e8f0')
        ax.yaxis.grid(True,color='#e2e8f0',linestyle='--',alpha=0.7); ax.set_axisbelow(True)
        ax.legend(handles=legend_patches,fontsize=7.5,loc='upper right',
                  framealpha=0.9,edgecolor='#e2e8f0')
        plt.tight_layout(pad=0.4)
        buf=io.BytesIO(); plt.savefig(buf,format='PNG',dpi=140,bbox_inches='tight')
        plt.close(); buf.seek(0); return buf

    # DETAIL TABLES
    HDR = ["ID","Server","Public IP - ISP","↓ DL (Mbps)","↑ UL (Mbps)","Ping","Jitter","Loss","Rating"]
    CW_ = [12*mm,34*mm,34*mm,26*mm,24*mm,17*mm,16*mm,14*mm,20*mm]  # sums to CONTENT_W (197mm)

    for grp in grp_names:
        info=all_results[grp]; flag=info["flag"]; results=info["results"]
        story.append(P(f"  {flag}  {grp}",
                       fontName='Helvetica-Bold',fontSize=11,
                       textColor=colors.HexColor(GROUP_HEX[grp]),spaceBefore=4,spaceAfter=2))
        hdr=[P(f"<b>{h}</b>",fontName='Helvetica-Bold',fontSize=7.5,textColor=CW,alignment=TA_CENTER)
             for h in HDR]
        rows=[hdr]; rstyles=[]
        for ri,r in enumerate(results):
            rat=rating(r["download_mbps"],r["ping_ms"]); ok=r["status"]=="OK"
            def c(txt,bold=False,hex='#374151'):
                return P(txt,fontName='Helvetica-Bold' if bold else 'Helvetica',
                         fontSize=8.5,textColor=colors.HexColor(hex),alignment=TA_CENTER)
            rows.append([
                c(str(r["server_id"]),bold=True),
                P(r["server_name"][:26],fontName='Helvetica',fontSize=8,
                  textColor=colors.HexColor('#374151')),
                P(r["isp"][:32],fontName='Helvetica',fontSize=7.5,
                  textColor=colors.HexColor('#374151')),
                c(f"<b>{r['download_mbps']:.1f}</b>" if ok else "—",bold=True,hex='#1a3c5e'),
                c(f"{r['upload_mbps']:.1f}"          if ok else "—"),
                c(f"{r['ping_ms']:.1f} ms"           if ok else "—"),
                c(f"{r['jitter_ms']:.1f} ms"         if ok else "—"),
                c(f"{r['loss_pct']:.1f}%"            if ok else "—",
                  hex='#ef4444' if r.get('loss_pct',0)>0 else '#374151'),
                P(f"<b>{rat}</b>",fontName='Helvetica-Bold',fontSize=8,
                  textColor=colors.HexColor(RATING_HEX[rat]),alignment=TA_CENTER),
            ])
            rstyles.append(('BACKGROUND',(0,ri+1),(-1,ri+1),CLG if ri%2==0 else CW))
        tbl=Table(rows,colWidths=CW_,repeatRows=1)
        tbl.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),CP),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('ROWHEIGHT',(0,0),(-1,-1),18),('TOPPADDING',(0,0),(-1,-1),3),
            ('BOTTOMPADDING',(0,0),(-1,-1),3),('LEFTPADDING',(0,0),(-1,-1),4),
            ('RIGHTPADDING',(0,0),(-1,-1),4),('GRID',(0,0),(-1,-1),0.3,CBR),
        ]+rstyles))
        story.append(tbl); story.append(Spacer(1,6))

    # PAGE BREAK before Download chart section (tables end their own page)
    story.append(PageBreak())

    # DOWNLOAD CHART
    story.append(P("📊  Download Speed Comparison (Mbps)",
                   fontName='Helvetica-Bold',fontSize=12,textColor=CP,spaceBefore=6,spaceAfter=3))
    story.append(Image(bar_chart(dl_vals,"Mbps",2.6,"{:.1f}"),width=165*mm,height=58*mm))
    story.append(Spacer(1,8))

    # UPLOAD CHART (right after Download — charts grouped together)
    story.append(P("⬆️  Upload Speed (Mbps)",fontName='Helvetica-Bold',fontSize=12,
                   textColor=CP,spaceBefore=4,spaceAfter=3))
    story.append(Image(bar_chart(ul_vals,"Mbps",2.1,"{:.1f}"),width=165*mm,height=48*mm))
    story.append(Spacer(1,8))

    # PING CHART
    story.append(P("⏱  Ping Latency (ms)",fontName='Helvetica-Bold',fontSize=12,
                   textColor=CP,spaceBefore=6,spaceAfter=3))
    story.append(Image(bar_chart(ping_vals,"ms",2.1,"{:.1f}"),width=165*mm,height=48*mm))
    story.append(Spacer(1,8))

    # LEGEND
    def rp(txt,hx):
        return P(f"<b>{txt}</b>",fontName='Helvetica-Bold',fontSize=8,
                 textColor=colors.HexColor(hx),alignment=TA_CENTER)
    def sp(txt):
        return P(txt,fontName='Helvetica',fontSize=7.5,textColor=CGR,alignment=TA_CENTER)
    leg=Table([
        [sp("Rating"),rp("EXCELLENT","#22c55e"),rp("GOOD","#3b82f6"),
         rp("FAIR","#f59e0b"),rp("POOR","#ef4444")],
        [sp("Criteria"),sp("DL≥500/Ping≤80ms"),sp("DL≥200/Ping≤120ms"),
         sp("DL≥50/Ping≤200ms"),sp("Below FAIR")],
    ],colWidths=[26*mm,49*mm,47*mm,45*mm,30*mm])  # sums to CONTENT_W (197mm)
    leg.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),CLG),('GRID',(0,0),(-1,-1),0.3,CBR),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(leg); story.append(Spacer(1,5))

    # FOOTER
    story.append(P(
        f"Generated: {report_time.strftime('%Y-%m-%d %H:%M:%S')}  "
        f"|  BeyondNet VN  |  Ookla Speedtest CLI v1.2.0",
        fontName='Helvetica',fontSize=7,textColor=CGR,alignment=TA_CENTER))

    doc.build(story)
    print(f"✅ PDF → {pdf_path}")
    return str(pdf_path)


def send_telegram_pdf(pdf_path, caption):
    url=f"https://api.telegram.org/bot{CONFIG['TELEGRAM_BOT_TOKEN']}/sendDocument"
    filename = Path(pdf_path).name
    with open(pdf_path,'rb') as f:
        resp=requests.post(url,data={"chat_id":CONFIG["TELEGRAM_CHAT_ID"],
            "caption":caption,"parse_mode":"Markdown"},
            files={"document":(filename,f,"application/pdf")},timeout=60)
    if resp.ok: print("✅ Telegram: sent!")
    else: print(f"❌ Telegram: {resp.status_code} {resp.text[:200]}")
    return resp.ok


def load_log():
    if LOG_PATH.exists():
        try:
            with open(LOG_PATH) as f: return json.load(f)
        except: pass
    return []

def save_log(r):
    with open(LOG_PATH,'w') as f:
        json.dump(r[-90:],f,indent=2,ensure_ascii=False)


def cleanup_old_pdfs(keep_count=None):
    keep_count = keep_count or CONFIG.get("KEEP_PDF_COUNT", 10)
    # filenames are speedtest_report_YYYY-MM-DD-HHMMSS.pdf, so sorting the
    # names alphabetically is the same as sorting them chronologically.
    pdfs = sorted(Path(__file__).parent.glob("speedtest_report_*.pdf"))
    to_remove = pdfs[:-keep_count] if len(pdfs) > keep_count else []
    for f in to_remove:
        try: f.unlink()
        except OSError: pass
    if to_remove:
        print(f"🗑️  Cleaned up {len(to_remove)} old PDF(s), keeping {keep_count} most recent")


def main():
    now=datetime.datetime.now()
    print(f"\n{'='*62}")
    print(f"  BeyondNet VN – Daily Speedtest  |  {now.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Host: {get_hostname()}  |  Engine: Ookla CLI")
    print(f"{'='*62}\n")

    # Check binary
    if not Path(CONFIG["SPEEDTEST_BIN"]).exists():
        for p in ["/usr/bin/speedtest","/usr/local/bin/speedtest"]:
            if Path(p).exists() and Path(p).stat().st_size>100_000:
                CONFIG["SPEEDTEST_BIN"]=p; break
        else:
            print("❌ Ookla CLI not found!\n"
                  "   sudo sed -i 's/noble/jammy/g' /etc/apt/sources.list.d/ookla_speedtest-cli.list\n"
                  "   sudo apt update && sudo apt install speedtest -y")
            sys.exit(1)
    print(f"✔ Binary: {CONFIG['SPEEDTEST_BIN']}\n")

    target = CONFIG.get("TARGET_PER_GROUP", 3)
    all_results={}
    for grp,info in CONFIG["SERVER_GROUPS"].items():
        print(f"{'─'*42}\n  {info['flag']}  {grp}\n{'─'*42}")
        results=[]
        for sid in info["ids"]:
            if len(results) >= target:
                break
            print(f"  🔄 Server {sid} ...",end=" ",flush=True)
            r=run_speedtest(sid, expected_group=grp)
            if r["status"]=="OK":
                print(f"✅  ↓{r['download_mbps']} Mbps  ↑{r['upload_mbps']} Mbps"
                      f"  Ping:{r['ping_ms']}ms  Loss:{r['loss_pct']}%")
                results.append(r)
            else:
                print(f"❌ skip  {r['status']}")
            time.sleep(5)
        if len(results) < target:
            print(f"  ⚠️  Only {len(results)}/{target} working servers found for {grp}")
        all_results[grp]={"flag":info["flag"],"results":results}

    # Log
    log=load_log()
    log.append({"timestamp":now.isoformat(),
                "results":{k:v["results"] for k,v in all_results.items()}})
    save_log(log)

    # PDF
    print(f"\n📄 Generating PDF..."); pdf_path = generate_pdf(all_results,now)
    cleanup_old_pdfs()

    # Caption
    flat_ok=[r for g in all_results.values() for r in g["results"] if r["status"]=="OK"]
    ok_n=len(flat_ok); total=sum(len(g["results"]) for g in all_results.values())
    avg_dl=round(sum(r["download_mbps"] for r in flat_ok)/ok_n,1) if flat_ok else 0
    avg_pg=round(sum(r["ping_ms"]       for r in flat_ok)/ok_n,1) if flat_ok else 0

    lines=[f"📶 *Daily Speedtest Report*",
           f"📅 {now.strftime('%d/%m/%Y %H:%M')}",
           f"📍 {CONFIG['LOCATION_NAME']}  |  `{get_hostname()}`","",
           f"✅ `{ok_n}/{total}` passed  ⬇️ Avg `{avg_dl} Mbps`  ⏱ Avg Ping `{avg_pg} ms`",""]
    for grp,info in all_results.items():
        ok_g=[r for r in info["results"] if r["status"]=="OK"]
        best_dl=max((r["download_mbps"] for r in ok_g),default=0)
        best_pg=min((r["ping_ms"]       for r in ok_g),default=0)
        lines.append(f"{info['flag']} *{grp}*: `{len(ok_g)}/{len(info['results'])}` OK"
                     f"  | ↓`{best_dl} Mbps`  Ping `{best_pg} ms`")
    lines.append("\n📎 _Chi tiết xem trong file PDF_")

    if telegram_configured():
        print(f"\n📤 Sending to Telegram...")
        send_telegram_pdf(pdf_path,"\n".join(lines))
    else:
        print(f"\n⚠️  Telegram chưa cấu hình (config.json) — bỏ qua gửi, PDF vẫn được lưu.")
    print(f"\n{'='*62}\n  ✅ Done!  {pdf_path}\n{'='*62}\n")


if __name__=="__main__":
    main()
