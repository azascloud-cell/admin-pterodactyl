# 🦕 Pterodactyl Panel — Personal (GitHub Actions)

> Panel Pterodactyl pribadi yang jalan gratis di GitHub Actions + Cloudflare Tunnel.  
> Node.js egg sudah diimport otomatis setiap kali panel start.

---

## 🚀 Quick Start

### 1. Fork repo ini

### 2. Set GitHub Secrets

Buka repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Keterangan |
|--------|-----------|
| `ADMIN_USER` | Username login panel (contoh: `admin`) |
| `ADMIN_PASS` | Password login panel |
| `DB_PASSWORD` | Password database MySQL (bebas, buat baru) |

### 3. Jalankan panel

Buka tab **Actions** → pilih workflow **"🦕 Pterodactyl Panel — Personal"** → klik **Run workflow**

### 4. Ambil URL

Setelah workflow berjalan (~3-4 menit), buka tab **Summary** di job yang sedang running:

```
🌐 PANEL URL  : https://xxxx-xxxx.trycloudflare.com
🔓 BYPASS     : https://xxxx-xxxx.trycloudflare.com/go-admin
```

Klik **Bypass URL** untuk langsung masuk panel tanpa password.

---

## ✨ Fitur

| Fitur | Keterangan |
|-------|-----------|
| 🟢 Node.js Egg | Auto-import setiap start (nodejs 22/20/18/16) |
| 🔓 Bypass Login | Akses `/go-admin` tanpa ketik password |
| 💾 State Persist | Database tersimpan di cache, tidak reset setiap restart |
| 🔄 Auto-restart | Workflow otomatis restart setiap 5 jam |
| 🌐 Cloudflare Tunnel | URL publik gratis tanpa domain / VPS |

---

## ⏰ Cara kerja

```
GitHub Actions runner (ubuntu-22.04)
  → Install PHP, MariaDB, Nginx
  → Download Pterodactyl Panel
  → Restore database dari cache (state persist)
  → Import Node.js egg otomatis
  → Start Cloudflare Tunnel → dapat URL publik
  → Panel live selama ~5 jam 45 menit
  → Save database ke cache sebelum mati
  → Keepalive workflow restart otomatis
```

---

## 📝 Secrets yang diperlukan

```
ADMIN_USER   = admin
ADMIN_PASS   = password_kamu
DB_PASSWORD  = password_db_bebas
```

Opsional (untuk keepalive trigger via API):
```
GH_PAT       = github personal access token (repo scope)
```

---

## 🟢 Node.js Egg

Egg yang diimport otomatis setelah panel start:

| Property | Value |
|----------|-------|
| Nest | Node.js |
| Egg name | Node.js Generic |
| Docker images | `ghcr.io/pterodactyl/yolks:nodejs_22` (dan 20, 18, 16) |
| Startup | `node /home/container/{{JS_FILE}}` |
| Variable `JS_FILE` | File JS yang dijalankan (default: `index.js`) |
| Variable `GIT_ADDRESS` | Repo git yang di-clone saat install |

---

## ⚠️ Catatan

- **URL panel berubah setiap restart** — selalu cek tab Summary untuk URL terbaru
- Panel aktif **~5 jam 45 menit** per sesi, lalu restart otomatis
- Data panel (users, servers, eggs) **tersimpan** via GitHub Actions cache
- Untuk membuat server, kamu perlu **Wings** di VPS/server terpisah
- Panel ini untuk penggunaan **pribadi** — tidak ada bot jualan

---

## 📁 Struktur

```
.github/
└── workflows/
    ├── panel-runner.yml   ← Workflow utama (jalankan panel)
    └── keepalive.yml      ← Auto-restart setiap 5 jam
scripts/
    ├── import_nodejs_egg.py  ← Import Node.js egg ke database
    ├── sync_admin.py         ← Sync akun admin
    ├── reset_password.py     ← Reset password via artisan
    └── add_bypass.py         ← Tambah route /go-admin
config/
    └── panel.env.example     ← Template env panel
```
