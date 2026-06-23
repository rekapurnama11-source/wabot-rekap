"""
===============================================================
  BOT WHATSAPP REKAP PEKERJAAN - UPT KARAWANG
  Platform : Fonnte (fonnte.com)
  Server   : Railway
===============================================================
"""

from flask import Flask, request, jsonify
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
from collections import defaultdict
import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

# ── CONFIG ─────────────────────────────────────────────────────
FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN", "mveUY7JCxoLQavoTLBoD")

SHEET_ID = "2PACX-1vTp35-kuD2tNQRGS2s1oFEGKgk9-XBA44RaVAnOdSzhF_JIMy6U-kpOQV0XBa8u1a6H7n5o5Y1_UWDF"
CSV_URL_DIRECT = f"https://docs.google.com/spreadsheets/d/e/{SHEET_ID}/pub?output=csv"

PROXY_URLS = [
    f"https://api.allorigins.win/raw?url={requests.utils.quote(CSV_URL_DIRECT)}",
    f"https://corsproxy.io/?{requests.utils.quote(CSV_URL_DIRECT)}",
]

TRIGGER_WORDS = ["rekap", "laporan", "resume", "data", "report"]

BIDANG_CONFIG = {
    "HARGI":  "🔵",
    "HARJAR": "🟢",
    "HARPRO": "🟠",
}

# Nilai kondisi yang diabaikan
KONDISI_IGNORE = {"NE", "NB", "NEN", "NAN", ""}

KONDISI_EMOJI = {
    "1": "🟢",
    "2": "🟩",
    "3": "🟡",
    "4": "🟠",
    "5": "🔴",
}

def get_kondisi_emoji(val):
    for key, em in KONDISI_EMOJI.items():
        if val.strip().startswith(key + "-") or val.strip() == key:
            return em
    return "▪️"

def is_valid_kondisi(val):
    """Abaikan NE, NB, NEN, kosong, dan nan."""
    return val.strip().upper() not in KONDISI_IGNORE and val.strip() != ""

# ── AMBIL CSV DENGAN FALLBACK ──────────────────────────────────
def fetch_csv():
    errors = []
    try:
        resp = requests.get(CSV_URL_DIRECT, timeout=15,
                            headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and "," in resp.text[:500]:
            return resp.text
    except Exception as e:
        errors.append(f"direct: {e}")

    for proxy_url in PROXY_URLS:
        try:
            resp = requests.get(proxy_url, timeout=20,
                                headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and "," in resp.text[:500]:
                return resp.text
        except Exception as e:
            errors.append(f"proxy: {e}")

    raise Exception("Semua metode gagal: " + " | ".join(errors))

# ── PROSES DATA CSV ────────────────────────────────────────────
def fetch_and_build():
    csv_text = fetch_csv()
    df = pd.read_csv(StringIO(csv_text), header=0)

    col_upt           = df.columns[5]   # F  - UPT
    col_sub_bidang    = df.columns[1]   # B  - Sub Bidang
    col_prog_kerja    = df.columns[9]   # J  - Program Kerja
    col_kondisi_awal  = df.columns[11]  # L  - Kondisi Awal
    col_kondisi_akhir = df.columns[14]  # O  - Kondisi Akhir
    col_status        = df.columns[19]  # T  - Status (CLOSE/OPEN)

    df[col_upt]           = df[col_upt].astype(str).str.strip().str.upper()
    df[col_sub_bidang]    = df[col_sub_bidang].astype(str).str.strip().str.upper()
    df[col_prog_kerja]    = df[col_prog_kerja].astype(str).str.strip()
    df[col_kondisi_awal]  = df[col_kondisi_awal].astype(str).str.strip()
    df[col_kondisi_akhir] = df[col_kondisi_akhir].astype(str).str.strip()
    df[col_status]        = df[col_status].astype(str).str.strip().str.upper()

    # Filter UPT KARAWANG
    df_k = df[df[col_upt].str.contains("KARAWANG", na=False)]
    print(f"[DATA] Total baris UPT Karawang: {len(df_k)}")

    # ── REKAP Kondisi Awal per Sub Bidang ──
    kondisi_awal_rekap = defaultdict(lambda: defaultdict(int))
    for _, row in df_k.iterrows():
        bidang = row[col_sub_bidang]
        val    = row[col_kondisi_awal]
        if bidang not in ("NAN", "") and is_valid_kondisi(val):
            kondisi_awal_rekap[bidang][val] += 1

    # ── REKAP Kondisi Akhir per Sub Bidang ──
    kondisi_akhir_rekap = defaultdict(lambda: defaultdict(int))
    for _, row in df_k.iterrows():
        bidang = row[col_sub_bidang]
        val    = row[col_kondisi_akhir]
        if bidang not in ("NAN", "") and is_valid_kondisi(val):
            kondisi_akhir_rekap[bidang][val] += 1

    # ── REKAP Program Kerja + CLOSE/OPEN per Sub Bidang ──
    prog_rekap = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for _, row in df_k.iterrows():
        bidang = row[col_sub_bidang]
        prog   = row[col_prog_kerja]
        status = row[col_status]
        if bidang not in ("NAN", "") and prog not in ("NAN", ""):
            if "CLOSE" in status:
                prog_rekap[bidang][prog]["CLOSE"] += 1
            elif "OPEN" in status:
                prog_rekap[bidang][prog]["OPEN"] += 1

    return kondisi_awal_rekap, kondisi_akhir_rekap, prog_rekap, len(df_k)

# ── FORMAT PESAN WA ────────────────────────────────────────────
def format_pesan(kondisi_awal_rekap, kondisi_akhir_rekap, prog_rekap, total):
    MONTHS = ["Januari","Februari","Maret","April","Mei","Juni",
              "Juli","Agustus","September","Oktober","November","Desember"]
    now = datetime.now()
    tanggal = f"{now.day} {MONTHS[now.month-1]} {now.year}"

    lines = [
        "📊 *RESUME PEKERJAAN*",
        "📍 *UPT KARAWANG*",
        f"🗓️ {tanggal}",
        f"Total Data : *{total:,} pekerjaan*",
        "━━━━━━━━━━━━━━━",
    ]

    totals = {}
    all_bidang = list(BIDANG_CONFIG.keys())

    for bidang in all_bidang:
        emoji = BIDANG_CONFIG.get(bidang, "⚪")

        total_close = sum(v.get("CLOSE", 0) for v in prog_rekap.get(bidang, {}).values())
        total_open  = sum(v.get("OPEN",  0) for v in prog_rekap.get(bidang, {}).values())
        total_bidang = total_close + total_open
        totals[bidang] = total_bidang

        lines.append(f"{emoji} *{bidang}*")
        lines.append(f"Total : {total_bidang:,} pekerjaan")
        lines.append(f"✅ Close : {total_close:,}  |  🔴 Open : {total_open:,}")

        # ── Kondisi Awal ──
        ka_data = kondisi_awal_rekap.get(bidang, {})
        if ka_data:
            lines.append("")
            lines.append("  📂 *Kondisi Awal:*")
            for val in sorted(ka_data):
                em = get_kondisi_emoji(val)
                lines.append(f"  {em} {val} : {ka_data[val]:,}")

        # ── Kondisi Akhir ──
        kak_data = kondisi_akhir_rekap.get(bidang, {})
        if kak_data:
            lines.append("")
            lines.append("  🏁 *Kondisi Akhir:*")
            for val in sorted(kak_data):
                em = get_kondisi_emoji(val)
                lines.append(f"  {em} {val} : {kak_data[val]:,}")

        lines.append("━━━━━━━━━━━━━━━")

    grand = sum(totals.values())
    grand_close = sum(
        v.get("CLOSE", 0)
        for bidang in all_bidang
        for v in prog_rekap.get(bidang, {}).values()
    )
    grand_open = sum(
        v.get("OPEN", 0)
        for bidang in all_bidang
        for v in prog_rekap.get(bidang, {}).values()
    )

    lines.append("📈 *TOTAL KESELURUHAN*")
    for bidang in all_bidang:
        emoji = BIDANG_CONFIG.get(bidang, "⚪")
        lines.append(f"{emoji} {bidang:<7}: {totals.get(bidang, 0):,}")
    lines.append(f"🔢 Grand Total  : *{grand:,}*")
    lines.append(f"✅ Total Close  : *{grand_close:,}*")
    lines.append(f"🔴 Total Open   : *{grand_open:,}*")

    return "\n".join(lines)

# ── KIRIM BALIK KE WA VIA FONNTE ──────────────────────────────
def kirim_wa(nomor, pesan):
    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    payload = {"target": nomor, "message": pesan, "countryCode": "62"}
    resp = requests.post(url, headers=headers, data=payload, timeout=15)
    print(f"[FONNTE RESPONSE] {resp.status_code} - {resp.text}")
    return resp.json()

# ── WEBHOOK ENDPOINT ───────────────────────────────────────────
@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    try:
        if request.content_type and "application/json" in request.content_type:
            data = request.get_json(force=True) or {}
        else:
            data = request.form.to_dict()
            if not data:
                try:
                    data = json.loads(request.data.decode("utf-8"))
                except:
                    data = {}
    except Exception as e:
        print(f"[PARSE ERROR] {e}")
        data = {}

    print(f"[WEBHOOK DATA] {data}")

    nomor       = data.get("sender", "") or data.get("from", "") or data.get("phone", "")
    pesan_masuk = str(data.get("message", "") or data.get("text", "") or data.get("body", "")).strip().lower()

    print(f"[IN] nomor={nomor} pesan={pesan_masuk}")

    if nomor and any(kw in pesan_masuk for kw in TRIGGER_WORDS):
        try:
            kond_awal, kond_akhir, prog_rekap, total = fetch_and_build()
            balasan = format_pesan(kond_awal, kond_akhir, prog_rekap, total)
        except Exception as e:
            balasan = f"❌ Gagal mengambil data:\n{str(e)}"
            print(f"[CSV ERROR] {e}")

        result = kirim_wa(nomor, balasan)
        print(f"[OUT] Terkirim ke {nomor}: {result}")

    return jsonify({"status": "ok"}), 200

# ── HEALTH CHECK ───────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return "✅ Bot Rekap WA aktif! (UPT Karawang)", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
