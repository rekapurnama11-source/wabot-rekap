"""
===============================================================
  BOT WHATSAPP REKAP PEKERJAAN
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

# ── AMBIL & PROSES DATA CSV ────────────────────────────────────
def fetch_and_build(url):
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(StringIO(resp.text), header=0)
    df.columns = [f"COL_{chr(65+i)}" for i in range(len(df.columns))]
    df = df.dropna(subset=["COL_B"])
    df["COL_B"] = df["COL_B"].astype(str).str.strip().str.upper()
    df["COL_C"] = df["COL_C"].astype(str).str.strip()
    df["COL_D"] = df["COL_D"].astype(str).str.strip()
    rekap = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for _, row in df.iterrows():
        rekap[row["COL_B"]][row["COL_C"]][row["COL_D"]] += 1
    return rekap

# ── FORMAT PESAN WA ────────────────────────────────────────────
def format_pesan(rekap):
    MONTHS = ["Januari","Februari","Maret","April","Mei","Juni",
              "Juli","Agustus","September","Oktober","November","Desember"]
    now = datetime.now()
    tanggal = f"{now.day} {MONTHS[now.month-1]} {now.year}"
    lines = [
        "📊 *RESUME PEKERJAAN*",
        f"Tanggal: {tanggal}",
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
            for kat_c in sorted(data):
                lines.append(f"📌 _{kat_c}_")
                for kat_d in sorted(data[kat_c]):
                    lines.append(f"• {kat_d} : {data[kat_c][kat_d]}")
        else:
            lines.append("  _(tidak ada data)_")
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
    # Fonnte bisa kirim form-data atau JSON
    try:
        if request.content_type and "application/json" in request.content_type:
            data = request.get_json(force=True) or {}
        else:
            data = request.form.to_dict()
            if not data:
                # coba parse body manual
                try:
                    data = json.loads(request.data.decode("utf-8"))
                except:
                    data = {}
    except Exception as e:
        print(f"[PARSE ERROR] {e}")
        data = {}

    print(f"[WEBHOOK DATA] {data}")

    nomor = data.get("sender", "") or data.get("from", "") or data.get("phone", "")
    pesan_masuk = str(data.get("message", "") or data.get("text", "") or data.get("body", "")).strip().lower()

    print(f"[IN] nomor={nomor} pesan={pesan_masuk}")

    if nomor and any(kw in pesan_masuk for kw in TRIGGER_WORDS):
        try:
            rekap = fetch_and_build(CSV_URL)
            balasan = format_pesan(rekap)
        except Exception as e:
            balasan = f"❌ Gagal mengambil data:\n{str(e)}"
            print(f"[CSV ERROR] {e}")

        result = kirim_wa(nomor, balasan)
        print(f"[OUT] Terkirim ke {nomor}: {result}")

    return jsonify({"status": "ok"}), 200

# ── HEALTH CHECK ───────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return "✅ Bot Rekap WA aktif!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
