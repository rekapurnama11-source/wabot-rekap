# 📱 Bot WA Rekap Pekerjaan — Setup Guide

## Cara Kerja
Kirim kata **"rekap"** (atau: laporan / resume / data) ke nomor WA kamu
→ Bot otomatis ambil data Google Sheets → balas dengan rekap lengkap

---

## LANGKAH 1 — Daftar & Setup Fonnte

1. Buka https://fonnte.com → Daftar gratis
2. Klik **+ Add Device** → scan QR dengan WhatsApp kamu
3. Setelah tersambung, masuk ke **Settings → Token**
4. Copy token (contoh: `eyJhbGci...`)
5. Aktifkan **Webhook**: masukkan URL webhook (diisi setelah Railway selesai)

---

## LANGKAH 2 — Deploy ke Railway (gratis)

1. Buka https://github.com → buat repo baru (misal: `wabot-rekap`)
2. Upload semua file ini ke repo tersebut
3. Buka https://railway.app → Login dengan GitHub
4. Klik **New Project → Deploy from GitHub Repo**
5. Pilih repo `wabot-rekap`
6. Railway otomatis deploy, tunggu ±2 menit
7. Setelah selesai, klik **Settings → Domains → Generate Domain**
8. Copy URL yang muncul (contoh: `https://wabot-rekap.up.railway.app`)

---

## LANGKAH 3 — Set Environment Variable

Di Railway → tab **Variables**, tambahkan:

| Key            | Value                        |
|----------------|------------------------------|
| FONNTE_TOKEN   | (token dari Fonnte tadi)     |

---

## LANGKAH 4 — Pasang Webhook di Fonnte

1. Kembali ke Fonnte → **Device Settings → Webhook**
2. Isi URL: `https://wabot-rekap.up.railway.app/webhook`
3. Method: `POST`
4. Simpan

---

## LANGKAH 5 — Test!

Kirim pesan **"rekap"** ke nomor WA yang sudah di-scan di Fonnte.
Bot akan membalas otomatis dengan rekap data terbaru. ✅

---

## Kata Kunci yang Tersedia

| Kata       | Aksi                    |
|------------|-------------------------|
| rekap      | Kirim rekap lengkap     |
| laporan    | Kirim rekap lengkap     |
| resume     | Kirim rekap lengkap     |
| data       | Kirim rekap lengkap     |
| report     | Kirim rekap lengkap     |

---

## Troubleshooting

- **Bot tidak merespons** → Cek token Fonnte di Railway Variables
- **Data kosong** → Pastikan Google Sheets sudah di-publish (File → Share → Publish to web → CSV)
- **Error 500** → Cek log di Railway → tab Deployments → View Logs
