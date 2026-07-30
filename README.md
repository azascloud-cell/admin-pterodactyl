# 🦕 PteroShop — Bot Telegram Jualan Hosting Pterodactyl

> **Jual hosting Pterodactyl panel otomatis via Telegram + pembayaran Pakasir (QRIS/VA)**  
> User beli → bayar → akun Pterodactyl dibuat otomatis + server aktif.

---

## 🚀 Fitur

| Fitur | Status |
|-------|--------|
| List paket dengan harga | ✅ |
| Pilih Node.js atau Python egg | ✅ |
| Pembayaran via Pakasir (QRIS/VA) | ✅ |
| Webhook Pakasir (otomatis) | ✅ |
| Fallback polling status bayar | ✅ |
| Auto-buat user Pterodactyl | ✅ |
| Auto-buat server Pterodactyl | ✅ |
| Ganti egg setelah beli | ✅ |
| Cek status pesanan | ✅ |
| Admin: konfirmasi manual | ✅ |
| Admin: statistik penjualan | ✅ |

---

## ⚙️ Setup

### 1. Secrets yang Diperlukan (sudah di-set)
| Secret | Keterangan |
|--------|-----------|
| `TELEGRAM_BOT_TOKEN` | Token dari @BotFather |
| `PAKASIR_API_KEY` | API key dari dashboard Pakasir |
| `PTERODACTYL_API_KEY` | Application API key dari panel Admin |
| `PTERODACTYL_PANEL_URL` | URL panel Pterodactyl |

### 2. Environment Variables (optional)
Set di Replit Secrets atau `.env`:

```env
# Admin Telegram ID (untuk /admin commands)
BOT_OWNER_ID=123456789

# Slug proyek Pakasir (lihat dashboard Pakasir → Proyek)
PAKASIR_PROJECT=nama-proyek-kamu

# Egg IDs di panel Pterodactyl (Admin → Nests → lihat ID di URL)
NODEJS_EGG_ID=15
PYTHON_EGG_ID=16

# Location & Node ID untuk server baru
DEFAULT_LOCATION_ID=1
DEFAULT_NODE_ID=1
```

### 3. Cek Egg IDs
Buka panel Pterodactyl → Admin → Nests → pilih Nest → pilih Egg → lihat URL:
`/admin/nests/X/eggs/Y` → Y adalah Egg ID

---

## 📦 Paket yang Dijual

| Paket | RAM | CPU | Disk | Harga/30hr |
|-------|-----|-----|------|-----------|
| Paket 1 | 1GB | 30% | 5GB | Rp 3.500 |
| Paket 2 | 2GB | 40% | 10GB | Rp 4.500 |
| ... | ... | ... | ... | ... |
| Unlimited | ∞ | ∞ | ∞ | Rp 16.500 |

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

## 📁 Struktur

```
PteroShop/
├── main.py                 ← Entry point
├── requirements.txt
├── bot/
│   ├── config.py           ← Konfigurasi dari env
│   ├── database.py         ← SQLite (orders, users)
│   ├── pakasir.py          ← Pakasir payment API
│   ├── pterodactyl.py      ← Pterodactyl Application API
│   ├── webhook.py          ← Flask webhook server (port 5000)
│   ├── scheduler.py        ← Background polling pembayaran
│   └── handlers/
│       ├── start.py        ← /start, /help, menu
│       ├── buy.py          ← Alur pembelian
│       ├── server.py       ← Ganti egg, lihat pesanan
│       └── admin.py        ← Admin commands
└── .github/workflows/      ← Panel runner (GitHub Actions)
```

---

## ⚠️ Catatan Panel Pterodactyl

Panel berjalan via **GitHub Actions + Cloudflare Tunnel** (lihat `panel-runner.yml`).  
URL panel berubah setiap restart — update `PTERODACTYL_PANEL_URL` setelah restart.

Auto-restart setiap 5 jam via `keepalive.yml`.
