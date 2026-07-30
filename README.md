# 🦕 PteroShop — Bot Telegram Jualan Hosting Pterodactyl

> **Jual hosting Pterodactyl panel otomatis via Telegram + pembayaran Pakasir (QRIS/VA)**  
> User beli → bayar → akun Pterodactyl dibuat otomatis + server aktif.

---

## 🚀 Install di VPS (1 perintah)

```bash
# 1. Clone repo
git clone https://github.com/azascloud-cell/admin-pterodactyl
cd admin-pterodactyl

# 2. Jalankan installer (Ubuntu 22.04, jalankan sebagai root)
sudo bash install.sh
```

Installer akan:
- Install semua dependencies (Python, MariaDB, Nginx)
- Buat database MySQL otomatis
- Minta input konfigurasi (bot token, API keys, dll)
- Setup systemd service (auto-start saat VPS reboot)
- Konfigurasi Nginx sebagai reverse proxy panel admin

Selesai, akses **Panel Admin Web** di: `http://IP_VPS:8888`

---

## ✨ Fitur

### Bot Telegram
| Fitur | Status |
|-------|--------|
| Katalog paket dengan harga | ✅ |
| Pilih Node.js atau Python egg | ✅ |
| Pembayaran via Pakasir (QRIS/VA) | ✅ |
| Webhook Pakasir (otomatis) | ✅ |
| Fallback polling status bayar | ✅ |
| Auto-buat user Pterodactyl | ✅ |
| Auto-buat server Pterodactyl | ✅ |
| Kirim invoice/credentials via DM | ✅ |
| Ganti egg setelah beli | ✅ |
| Cek status pesanan | ✅ |

### Panel Admin Web (port 8080 / nginx 8888)
| Fitur | Status |
|-------|--------|
| Dashboard statistik penjualan | ✅ |
| Kelola produk & harga (CRUD) | ✅ |
| Lihat & konfirmasi pesanan | ✅ |
| Manajemen pelanggan | ✅ |
| Konfigurasi bot dari web | ✅ |
| Login aman dengan password | ✅ |

---

## 🗂️ Struktur

```
admin-pterodactyl/
├── install.sh              ← Auto installer VPS
├── main.py                 ← Entry point (bot + panel admin)
├── requirements.txt
├── .env.example            ← Template konfigurasi
├── bot/
│   ├── config.py           ← Konfigurasi dari env + DB
│   ├── database.py         ← MySQL (orders, users, products, config)
│   ├── pakasir.py          ← Pakasir payment API
│   ├── pterodactyl.py      ← Pterodactyl Application API
│   ├── webhook.py          ← Flask webhook server (port 5000)
│   ├── scheduler.py        ← Background polling pembayaran
│   └── handlers/
│       ├── start.py        ← /start, /help, menu
│       ├── buy.py          ← Alur pembelian
│       ├── server.py       ← Ganti egg, lihat pesanan
│       └── admin.py        ← Admin commands
├── panel_admin/
│   ├── app.py              ← Flask admin panel (port 8080)
│   └── templates/          ← HTML templates (Bootstrap 5 dark)
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── orders.html
│       ├── products.html
│       ├── product_form.html
│       ├── users.html
│       └── config.html
└── .github/workflows/
    ├── panel-runner.yml    ← Jalankan panel via GitHub Actions
    └── keepalive.yml       ← Auto-restart setiap 5 jam
```

---

## ⚙️ Konfigurasi Manual (tanpa installer)

Copy `.env.example` ke `.env` dan isi nilainya:

```bash
cp .env.example .env
nano .env
```

Variabel penting:

| Variabel | Keterangan |
|----------|-----------|
| `TELEGRAM_BOT_TOKEN` | Token dari @BotFather |
| `BOT_OWNER_ID` | Telegram ID owner (untuk /admin) |
| `PAKASIR_API_KEY` | API key dari dashboard Pakasir |
| `PAKASIR_PROJECT` | Slug proyek Pakasir |
| `PTERODACTYL_PANEL_URL` | URL panel Pterodactyl |
| `PTERODACTYL_API_KEY` | Application API key panel admin |
| `NODEJS_EGG_ID` | Egg ID Node.js (lihat Admin → Nests) |
| `PYTHON_EGG_ID` | Egg ID Python |
| `DB_HOST` | Host MySQL (default: 127.0.0.1) |
| `DB_PASSWORD` | Password MySQL bot |
| `ADMIN_USERNAME` | Username panel admin web |
| `ADMIN_PASSWORD` | Password panel admin web |
| `PUBLIC_DOMAIN` | Domain publik VPS (untuk webhook Pakasir) |

---

## 🔧 Perintah Bot

### User
| Perintah | Keterangan |
|----------|-----------|
| `/start` | Menu utama |
| `/beli` | Lihat & beli paket |
| `/pesanan` | Cek status pesanan |
| `/gantiegg` | Ganti runtime (Node.js/Python) |
| `/help` | Cara pakai |

### Admin
| Perintah | Keterangan |
|----------|-----------|
| `/admin` | Menu admin |
| `/orders` | List order pending |
| `/confirm <trx_id>` | Konfirmasi bayar manual |
| `/setconfig` | Lihat konfigurasi aktif |
| `/stats` | Statistik penjualan |

---

## 🔁 Alur Pembayaran

```
User /beli
  → Pilih paket
  → Pilih Node.js / Python
  → Bot buat Pakasir payment link
  → User bayar (QRIS / VA)
  → Pakasir POST ke webhook /pakasir/callback
      + Polling otomatis setiap 60 detik (fallback)
  → Bot buat user Pterodactyl
  → Bot buat server Pterodactyl
  → Bot kirim credentials ke user via Telegram
```

---

## 🖥️ Jalankan Manual

```bash
# Install dependencies
pip install -r requirements.txt

# Salin dan isi konfigurasi
cp .env.example .env && nano .env

# Jalankan (bot + panel admin berjalan bersamaan)
python main.py
```

---

## ⚠️ Panel Pterodactyl via GitHub Actions

Panel berjalan via **GitHub Actions + Cloudflare Tunnel** (lihat `panel-runner.yml`).  
URL panel berubah setiap restart — update `PTERODACTYL_PANEL_URL` setelah restart,  
atau gunakan tab **Konfigurasi** di Panel Admin Web.

Auto-restart setiap 5 jam via `keepalive.yml`.

---

## 📊 Panel Admin Web

Akses setelah install: **http://IP_VPS:8888**

Login dengan `ADMIN_USERNAME` / `ADMIN_PASSWORD` dari `.env`.

Fitur:
- **Dashboard** — total order, revenue, pending, pelanggan
- **Pesanan** — filter by status, konfirmasi manual, hapus
- **Produk** — tambah/edit/hapus paket hosting
- **Pelanggan** — lihat semua user + total belanja
- **Konfigurasi** — ubah API keys, egg IDs, dll tanpa edit file
