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

CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTp35-kuD2tNQRGS2s1oFEGKgk9-XBA44RaVAnOdSzhF_JIMy6U-"
    "kpOQV0XBa8u1a6H7n5o5Y1_UWDF/pub?output=csv"
)

TRIGGER_WORDS = ["rekap", "laporan", "resume", "data", "report"]

BIDANG_CONFIG = {
    "HARGI":  "🔵",
    "HARJAR": "🟢",
    "HARPRO": "🟠",
}

# Kondisi Akhir emoji mapping
KONDISI_EMOJI = {
    "CLOSE":    "✅",
    "OPEN":     "🔴",
    "PROGRESS": "🔄",
    "HOLD":     "⏸️",
    "CANCEL":   "❌",
}

# ── AMBIL & PROSES DATA CSV ────────────────────────────────────
def fetch_and_build(url):
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(StringIO(resp.text), header=0)

    # Nama kolom berdasarkan header asli
    # Kolom: Kode, Sub Bidang, Level Anomali, Uraian, Hartrans,
    #        UPT, ULTG, Gardu Induk, Nama Ruas/Bay, Nama Tower,
    #        Kondisi Terkini, Kondisi Awal, TGL RENCANA, TGL REALISASI, Kondisi Akhir, ...
    col_upt         = df.columns[5]   # F - UPT
    col_sub_bidang  = df.columns[1]   # B - Sub Bidang
    col_level       = df.columns[2]   # C - Level Anomali
    col_uraian      = df.columns[3]   # D - Uraian
    col_kondisi_akhir = df.columns[14] # O - Kondisi Akhir

    # Bersihkan data
    df[col_upt]          = df[col_upt].astype(str).str.strip().str.upper()
    df[col_sub_bidang]   = df[col_sub_bidang].astype(str).str.strip().str.upper()
    df[col_level]        = df[col_level].astype(str).str.strip()
    df[col_uraian]       = df[col_uraian].astype(str).str.strip()
    df[col_kondisi_akhir]= df[col_kondisi_akhir].astype(str).str.strip().str.upper()

    # ── FILTER UPT KARAWANG ──
    df_karawang = df[df[col_upt].str.contains("KARAWANG", na=False)]

    # ── REKAP per Sub Bidang → Level Anomali → Uraian ──
    rekap = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for _, row in df_karawang.iterrows():
        bidang = row[col_sub_bidang]
        level  = row[col_level]
        uraian = row[col_uraian]
        if bidang and bidang != "NAN":
            rekap[bidang][level][uraian] += 1

    # ── REKAP Kondisi Akhir per Sub Bidang ──
    kondisi_rekap = defaultdict(lambda: defaultdict(int))
    for _, row in df_karawang.iterrows():
        bidang  = row[col_sub_bidang]
        kondisi = row[col_kondisi_akhir]
        if bidang and bidang != "NAN" and kondisi and kondisi != "NAN":
            kondisi_rekap[bidang][kondisi] += 1

    total_karawang = len(df_karawang)

    return rekap, kondisi_rekap, total_karawang

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
        emoji  = BIDANG_CONFIG.get(bidang, "⚪")
        data   = rekap.get(bidang, {})
        total  = sum(c for d in data.values() for c in d.values())
        totals[bidang] = total

        lines.append(f"{emoji} *{bidang}*")
        lines.append(f"Total : {total} pekerjaan")

        # Rekap Level Anomali → Uraian
        if data:
            for level in sorted(data):
                lines.append(f"📌 _{level}_")
                for uraian in sorted(data[level]):
                    lines.append(f"  • {uraian} : {data[level][uraian]}")
        else:
            lines.append("  _(tidak ada data)_")

        # Rekap Kondisi Akhir
        kondisi_bidang = kondisi_rekap.get(bidang, {})
        if kondisi_bidang:
            lines.append(f"")
            lines.append(f"  📋 *Kondisi Akhir:*")
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
    payload = {
        "target": nomor,
        "message": pesan,
        "countryCode": "62",
    }
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
            rekap, kondisi_rekap, total = fetch_and_build(CSV_URL)
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
