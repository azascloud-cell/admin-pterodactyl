# 🦕 admin-pterodactyl

> **Pterodactyl Panel gratis — berjalan 100% di GitHub Actions, tanpa VPS!**  
> Diekspos ke internet via Cloudflare Tunnel. State database disimpan otomatis antar-run.

[![Panel Runner](https://github.com/azascloud-cell/admin-pterodactyl/actions/workflows/panel-runner.yml/badge.svg)](https://github.com/azascloud-cell/admin-pterodactyl/actions/workflows/panel-runner.yml)
[![Keep Alive](https://github.com/azascloud-cell/admin-pterodactyl/actions/workflows/keepalive.yml/badge.svg)](https://github.com/azascloud-cell/admin-pterodactyl/actions/workflows/keepalive.yml)

---

## 🚀 Cara Pakai

### 1. Jalankan Panel

Buka tab **Actions → 🦕 Run Pterodactyl Panel → Run workflow** → klik **Run workflow**.

Tunggu ~3–5 menit sampai step **"Start Cloudflare Tunnel"** selesai.

### 2. Dapatkan URL Panel

Buka run yang sedang berjalan → klik tab **Summary**.  
URL akan muncul seperti:

```
🌐 Panel URL: https://xxxx-xxxx-xxxx.trycloudflare.com
```

> ⚠️ URL berubah setiap kali workflow di-restart. Selalu cek Summary untuk URL terbaru.

### 3. Login ke Panel

| Field    | Value |
|----------|-------|
| Username | `admin` |
| Password | *(lihat secret `ADMIN_PASS` di repo Settings)* |

---

## ♾️ Keep Alive 24/7

Panel aktif **~5 jam 50 menit** per-run. Workflow `keepalive.yml` otomatis me-restart panel setiap 5 jam via schedule cron.

Kamu juga bisa ping dari luar (UptimeRobot, cron-job.org) agar panel selalu jalan:

### 🔗 URL Ping Eksternal

```
POST https://api.github.com/repos/azascloud-cell/admin-pterodactyl/dispatches
```

**Headers:**
```
Authorization: token <GITHUB_PAT_KAMU>
Content-Type: application/json
```

**Body:**
```json
{"event_type": "keepalive-ping"}
```

**Test via cURL:**
```bash
curl -X POST \
  -H "Authorization: token GITHUB_PAT_KAMU" \
  -H "Content-Type: application/json" \
  https://api.github.com/repos/azascloud-cell/admin-pterodactyl/dispatches \
  -d '{"event_type": "keepalive-ping"}'
# HTTP 204 = berhasil ✅
```

---

## 💾 Persistensi Data

Database dan konfigurasi disimpan ke **GitHub Actions Cache** setiap akhir run, dan di-restore di awal run berikutnya. Data kamu tidak hilang meski runner berganti.

> Cache GitHub gratis hingga 10GB per repo. Cache dihapus setelah 7 hari tidak dipakai.

---

## 🔐 GitHub Secrets yang Diperlukan

Pergi ke **Settings → Secrets and variables → Actions**:

| Secret | Keterangan |
|--------|-----------|
| `ADMIN_PASS` | Password login panel |
| `ADMIN_USER` | Username admin (default: `admin`) |
| `ADMIN_EMAIL` | Email admin |
| `DB_PASSWORD` | Password database internal |
| `GH_PAT` | GitHub Personal Access Token (untuk keepalive re-trigger) |

---

## 📁 Struktur Repo

```
admin-pterodactyl/
├── .github/
│   └── workflows/
│       ├── panel-runner.yml    # ← Main: jalankan panel di GitHub runner
│       └── keepalive.yml       # ← Auto-restart panel setiap 5 jam
├── config/
│   └── panel.env.example
└── README.md
```

---

## ⚠️ Keterbatasan

| Hal | Keterangan |
|-----|-----------|
| URL berubah | Setiap restart, URL Cloudflare Tunnel berbeda (random) |
| Wings / Game Server | Wings perlu VPS terpisah untuk menjalankan server game |
| Uptime | Panel bisa offline beberapa menit saat restart otomatis |
| Cache | Data bisa hilang jika cache tidak dipakai >7 hari |

---

<div align="center">
  <sub>Dibuat untuk komunitas game server Indonesia 🇮🇩</sub>
</div>
