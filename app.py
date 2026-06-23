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

# Google Sheets CSV URL (langsung)
SHEET_ID = "2PACX-1vTp35-kuD2tNQRGS2s1oFEGKgk9-XBA44RaVAnOdSzhF_JIMy6U-kpOQV0XBa8u1a6H7n5o5Y1_UWDF"
CSV_URL_DIRECT = f"https://docs.google.com/spreadsheets/d/e/{SHEET_ID}/pub?output=csv"

# Proxy fallback list
PROXY_URLS = [
    f"https://api.allorigins.win/raw?url={requests.utils.quote(CSV_URL_DIRECT)}",
    f"https://corsproxy.io/?{requests.utils.quote(CSV_URL_DIRECT)}",
    f"https://proxy.cors.sh/{CSV_URL_DIRECT}",
]

TRIGGER_WORDS = ["rekap", "laporan", "resume", "data", "report"]

BIDANG_CONFIG = {
    "HARGI":  "🔵",
    "HARJAR": "🟢",
    "HARPRO": "🟠",
}

KONDISI_EMOJI = {
    "CLOSE":    "✅",
    "OPEN":     "🔴",
    "PROGRESS": "🔄",
    "HOLD":     "⏸️",
    "CANCEL":   "❌",
}

# ── AMBIL CSV DENGAN FALLBACK ──────────────────────────────────
def fetch_csv():
    """Coba ambil CSV langsung dulu, kalau gagal pakai proxy."""
    errors = []

    # Coba langsung dulu
    try:
        resp = requests.get(CSV_URL_DIRECT, timeout=15,
                            headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and "," in resp.text[:500]:
            print("[CSV] Berhasil langsung")
            return resp.text
    except Exception as e:
        errors.append(f"direct: {e}")

    # Coba proxy satu per satu
    for proxy_url in PROXY_URLS:
        try:
            resp = requests.get(proxy_url, timeout=20,
                                headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and "," in resp.text[:500]:
                print(f"[CSV] Berhasil via proxy: {proxy_url[:50]}")
                return resp.text
        except Exception as e:
            errors.append(f"proxy: {e}")

    raise Exception("Semua metode gagal: " + " | ".join(errors))

# ── PROSES DATA CSV ────────────────────────────────────────────
def fetch_and_build():
    csv_text = fetch_csv()
    df = pd.read_csv(StringIO(csv_text), header=0)

    col_upt           = df.columns[5]   # F - UPT
    col_sub_bidang    = df.columns[1]   # B - Sub Bidang
    col_level         = df.columns[2]   # C - Level Anomali
    col_uraian        = df.columns[3]   # D - Uraian
    col_kondisi_akhir = df.columns[14]  # O - Kondisi Akhir

    df[col_upt]           = df[col_upt].astype(str).str.strip().str.upper()
    df[col_sub_bidang]    = df[col_sub_bidang].astype(str).str.strip().str.upper()
    df[col_level]         = df[col_level].astype(str).str.strip()
    df[col_uraian]        = df[col_uraian].astype(str).str.strip()
    df[col_kondisi_akhir] = df[col_kondisi_akhir].astype(str).str.strip().str.upper()

    # Filter UPT KARAWANG
    df_karawang = df[df[col_upt].str.contains("KARAWANG", na=False)]
    print(f"[DATA] Total baris UPT Karawang: {len(df_karawang)}")

    # Rekap per Sub Bidang → Level → Uraian
    rekap = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for _, row in df_karawang.iterrows():
        bidang = row[col_sub_bidang]
        level  = row[col_level]
        uraian = row[col_uraian]
        if bidang not in ("NAN", ""):
            rekap[bidang][level][uraian] += 1

    # Rekap Kondisi Akhir per Sub Bidang
    kondisi_rekap = defaultdict(lambda: defaultdict(int))
    for _, row in df_karawang.iterrows():
        bidang  = row[col_sub_bidang]
        kondisi = row[col_kondisi_akhir]
        if bidang not in ("NAN", "") and kondisi not in ("NAN", ""):
            kondisi_rekap[bidang][kondisi] += 1

    return rekap, kondisi_rekap, len(df_karawang)

# ── FORMAT PESAN WA ────────────────────────────────────────────
def format_pesan(rekap, kondisi_rekap, total_karawang):
    MONTHS = ["Januari","Februari","Maret","April","Mei","Juni",
              "Juli","Agustus","September","Oktober","November","Desember"]
    now = datetime.now()
    tanggal = f"{now.day} {MONTHS[now.month-1]} {now.year}"

    lines = [
        "📊 *RESUME PEKERJAAN*",
        f"📍 UPT KARAWANG",
        f"🗓️ {tanggal}",
        f"Total Data : *{total_karawang} pekerjaan*",
        "━━━━━━━━━━━━━━━",
    ]

    totals = {}
    all_bidang = list(BIDANG_CONFIG.keys())
    for b in rekap:
        if b not in all_bidang:
            all_bidang.append(b)

    for bidang in all_bidang:
        emoji = BIDANG_CONFIG.get(bidang, "⚪")
        data  = rekap.get(bidang, {})
        total = sum(c for d in data.values() for c in d.values())
        totals[bidang] = total

        lines.append(f"{emoji} *{bidang}*")
        lines.append(f"Total : {total} pekerjaan")

        if data:
            for level in sorted(data):
                lines.append(f"📌 _{level}_")
                for uraian in sorted(data[level]):
                    lines.append(f"  • {uraian} : {data[level][uraian]}")
        else:
            lines.append("  _(tidak ada data)_")

        # Kondisi Akhir
        kondisi_bidang = kondisi_rekap.get(bidang, {})
        if kondisi_bidang:
            lines.append("")
            lines.append("  📋 *Kondisi Akhir:*")
            for kondisi in sorted(kondisi_bidang):
                em = KONDISI_EMOJI.get(kondisi, "▪️")
                lines.append(f"  {em} {kondisi} : {kondisi_bidang[kondisi]}")

        lines.append("━━━━━━━━━━━━━━━")

    grand = sum(totals.values())
    lines.append("📈 *TOTAL KESELURUHAN*")
    for bidang in all_bidang:
        emoji = BIDANG_CONFIG.get(bidang, "⚪")
        lines.append(f"{emoji} {bidang:<7}: {totals.get(bidang, 0)}")
    lines.append(f"🔢 Grand Total : *{grand}*")

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
            rekap, kondisi_rekap, total = fetch_and_build()
            balasan = format_pesan(rekap, kondisi_rekap, total)
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
