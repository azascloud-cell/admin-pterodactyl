#!/usr/bin/env bash
# ============================================================
#  PteroShop — Auto Installer
#  Ubuntu 22.04 LTS | Pterodactyl Panel + Bot Telegram + Panel Admin Web
#  Jalankan: bash install.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${CYAN}[→]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
die()  { echo -e "${RED}[✗] ERROR: $*${NC}"; exit 1; }
sep()  { echo -e "${CYAN}────────────────────────────────────────────────${NC}"; }

# ── Cek root & OS ─────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Jalankan sebagai root: sudo bash install.sh"
. /etc/os-release 2>/dev/null || true
if [[ "${ID:-}" != "ubuntu" ]] || [[ "${VERSION_ID:-}" != "22.04" ]]; then
  warn "Script dioptimalkan untuk Ubuntu 22.04. OS saat ini: ${PRETTY_NAME:-unknown}"
  read -rp "Lanjutkan anyway? (y/N): " c; [[ "${c,,}" == "y" ]] || exit 1
fi

sep
echo -e "${BOLD}🦕 PteroShop Auto Installer${NC}"
echo "   Bot Telegram + Panel Admin + Pterodactyl"
sep

# ── Input konfigurasi ─────────────────────────────────────────────────────────
INSTALL_DIR="/opt/pteroshop"
ENV_FILE="$INSTALL_DIR/.env"

get_input() {
  local prompt="$1" var="$2" default="${3:-}"
  local value
  if [[ -n "$default" ]]; then
    read -rp "$(echo -e "${CYAN}  $prompt${NC} [${default}]: ")" value
    echo "${value:-$default}"
  else
    while true; do
      read -rp "$(echo -e "${CYAN}  $prompt${NC}: ")" value
      [[ -n "$value" ]] && echo "$value" && break
      echo -e "${RED}  Tidak boleh kosong.${NC}"
    done
  fi
}

echo ""
echo -e "${BOLD}Masukkan konfigurasi bot:${NC}"
echo ""

BOT_TOKEN=$(get_input "Telegram Bot Token (@BotFather)" "TELEGRAM_BOT_TOKEN")
BOT_OWNER=$(get_input "Telegram ID kamu (owner bot)" "BOT_OWNER_ID")
PAKASIR_KEY=$(get_input "API Key Pakasir" "PAKASIR_API_KEY")
PAKASIR_PROJ=$(get_input "Slug proyek Pakasir" "PAKASIR_PROJECT")
PTERO_URL=$(get_input "URL Panel Pterodactyl (https://...)" "PTERODACTYL_PANEL_URL")
PTERO_KEY=$(get_input "Application API Key Pterodactyl (ptla_...)" "PTERODACTYL_API_KEY")
NODEJS_EGG=$(get_input "Egg ID Node.js di panel" "NODEJS_EGG_ID" "15")
PYTHON_EGG=$(get_input "Egg ID Python di panel"  "PYTHON_EGG_ID"  "16")
LOC_ID=$(get_input     "Location ID default"      "LOCATION_ID"    "1")
NODE_ID=$(get_input    "Node ID default"           "NODE_ID"        "1")

echo ""
echo -e "${BOLD}Database MySQL (akan dibuat otomatis):${NC}"
DB_PASS=$(get_input "Password database bot (buat baru)" "DB_PASSWORD")

echo ""
echo -e "${BOLD}Panel Admin Web (port 8080):${NC}"
ADMIN_USER=$(get_input "Username panel admin" "ADMIN_USERNAME" "admin")
ADMIN_PASS=$(get_input "Password panel admin" "ADMIN_PASSWORD")
SESSION_KEY=$(LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*' < /dev/urandom | head -c 48 || true)
[[ -z "$SESSION_KEY" ]] && SESSION_KEY="defaultsecretkey$(date +%s)"

# ── Install system packages ────────────────────────────────────────────────────
sep; info "Menginstall system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  python3 python3-pip python3-venv python3-dev \
  mariadb-server mariadb-client \
  nginx curl wget git supervisor ufw \
  build-essential libssl-dev libffi-dev \
  2>&1 | tail -5
log "System packages installed"

# ── MariaDB setup ─────────────────────────────────────────────────────────────
sep; info "Mengkonfigurasi MariaDB..."
systemctl enable --now mariadb

mysql -u root <<SQL
CREATE DATABASE IF NOT EXISTS pterobot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'pterobot'@'127.0.0.1' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON pterobot.* TO 'pterobot'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
log "Database 'pterobot' siap"

# ── Clone / update repo ────────────────────────────────────────────────────────
sep; info "Mengambil kode dari GitHub..."
if [[ -d "$INSTALL_DIR/.git" ]]; then
  cd "$INSTALL_DIR"
  git pull --ff-only
  log "Repo diperbarui"
else
  git clone https://github.com/azascloud-cell/admin-pterodactyl "$INSTALL_DIR"
  log "Repo di-clone ke $INSTALL_DIR"
fi

# ── Python virtualenv & dependencies ─────────────────────────────────────────
sep; info "Membuat virtual environment Python..."
cd "$INSTALL_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
log "Python dependencies installed"

# ── Tulis .env ────────────────────────────────────────────────────────────────
sep; info "Menulis konfigurasi ke $ENV_FILE..."
cat > "$ENV_FILE" <<EOF
# PteroShop .env — dibuat oleh install.sh $(date '+%Y-%m-%d %H:%M:%S')
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}
BOT_OWNER_ID=${BOT_OWNER}

PAKASIR_API_KEY=${PAKASIR_KEY}
PAKASIR_PROJECT=${PAKASIR_PROJ}

PTERODACTYL_PANEL_URL=${PTERO_URL}
PTERODACTYL_API_KEY=${PTERO_KEY}

NODEJS_EGG_ID=${NODEJS_EGG}
PYTHON_EGG_ID=${PYTHON_EGG}
DEFAULT_LOCATION_ID=${LOC_ID}
DEFAULT_NODE_ID=${NODE_ID}

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=pterobot
DB_PASSWORD=${DB_PASS}
BOT_DB_NAME=pterobot

ADMIN_PANEL_PORT=8080
ADMIN_USERNAME=${ADMIN_USER}
ADMIN_PASSWORD=${ADMIN_PASS}
SESSION_SECRET=${SESSION_KEY}

PUBLIC_DOMAIN=
EOF
chmod 600 "$ENV_FILE"
log ".env ditulis (mode 600)"

# ── Systemd service: bot ──────────────────────────────────────────────────────
sep; info "Membuat systemd service untuk bot..."
cat > /etc/systemd/system/pteroshop-bot.service <<EOF
[Unit]
Description=PteroShop Telegram Bot + Panel Admin
After=network.target mariadb.service
Requires=mariadb.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${INSTALL_DIR}/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable pteroshop-bot
log "Service pteroshop-bot dibuat dan diaktifkan"

# ── Nginx: reverse proxy panel admin (port 8080) ─────────────────────────────
sep; info "Mengkonfigurasi Nginx..."
cat > /etc/nginx/sites-available/pteroshop-admin <<'NGINX'
server {
    listen 8888;
    server_name _;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
NGINX

# Aktifkan site
ln -sf /etc/nginx/sites-available/pteroshop-admin \
       /etc/nginx/sites-enabled/pteroshop-admin
nginx -t && systemctl restart nginx
log "Nginx dikonfigurasi (port 8888 → 8080)"

# ── UFW firewall ──────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null; then
  ufw allow OpenSSH    >/dev/null 2>&1 || true
  ufw allow 8888/tcp   >/dev/null 2>&1 || true   # panel admin
  ufw allow 5000/tcp   >/dev/null 2>&1 || true   # webhook pakasir
  log "UFW rules ditambahkan (8888, 5000)"
fi

# ── Start bot ─────────────────────────────────────────────────────────────────
sep; info "Menjalankan PteroShop..."
systemctl start pteroshop-bot
sleep 3
if systemctl is-active --quiet pteroshop-bot; then
  log "Bot berjalan!"
else
  warn "Bot gagal start. Cek log: journalctl -u pteroshop-bot -n 50"
fi

# ── Selesai ───────────────────────────────────────────────────────────────────
sep
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${BOLD}${GREEN}✅  INSTALASI SELESAI!${NC}"
echo ""
echo -e "  ${BOLD}Panel Admin Web:${NC}  http://${SERVER_IP}:8888"
echo -e "  ${BOLD}Username:${NC}         ${ADMIN_USER}"
echo -e "  ${BOLD}Password:${NC}         (yang kamu masukkan tadi)"
echo ""
echo -e "  ${BOLD}Perintah berguna:${NC}"
echo -e "  • Cek status  : ${CYAN}systemctl status pteroshop-bot${NC}"
echo -e "  • Lihat log   : ${CYAN}journalctl -u pteroshop-bot -f${NC}"
echo -e "  • Restart bot : ${CYAN}systemctl restart pteroshop-bot${NC}"
echo -e "  • Edit config : ${CYAN}nano ${ENV_FILE}${NC}"
echo ""
echo -e "  ${BOLD}File lokasi:${NC} ${INSTALL_DIR}"
sep
