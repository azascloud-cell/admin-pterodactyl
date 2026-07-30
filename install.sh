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

INSTALL_DIR="/opt/pteroshop"
ENV_FILE="$INSTALL_DIR/.env"

get_input() {
  local prompt="$1" default="${2:-}" value
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

# ═══════════════════════════════════════════════════════════════════════════════
# BAGIAN 1 — Pterodactyl Panel
# ═══════════════════════════════════════════════════════════════════════════════
sep
echo -e "${BOLD}[ BAGIAN 1 ] Pterodactyl Panel${NC}"
echo ""
echo "  Pilih opsi panel Pterodactyl:"
echo -e "  ${CYAN}1)${NC} Install panel Pterodactyl di VPS ini sekarang (rekomendasikan)"
echo -e "  ${CYAN}2)${NC} Sudah punya panel — masukkan URL yang ada"
echo -e "  ${CYAN}3)${NC} Skip — isi URL nanti lewat Panel Admin Web"
echo ""
read -rp "$(echo -e "${CYAN}  Pilihan (1/2/3):${NC} ")" PANEL_CHOICE
PANEL_CHOICE="${PANEL_CHOICE:-1}"

INSTALL_PTERODACTYL=false
PTERO_URL=""
PTERO_KEY=""
PTERO_DOMAIN=""
PTERO_EMAIL=""
PTERO_ADMIN_PASS=""

if [[ "$PANEL_CHOICE" == "1" ]]; then
  INSTALL_PTERODACTYL=true
  echo ""
  echo -e "${BOLD}Konfigurasi Pterodactyl Panel:${NC}"
  SERVER_IP=$(hostname -I | awk '{print $1}')
  PTERO_DOMAIN=$(get_input "Domain atau IP VPS ini" "$SERVER_IP")
  PTERO_EMAIL=$(get_input "Email admin panel" "admin@domain.com")
  PTERO_ADMIN_PASS=$(get_input "Password admin panel" "Admin123!")
  # URL akan menggunakan domain/IP yang dimasukkan
  PTERO_URL="http://${PTERO_DOMAIN}"
  PTERO_KEY=""   # Akan diisi setelah install selesai
  warn "API Key Pterodactyl akan dibuat manual setelah panel install."
  warn "Masukkan di: nano $ENV_FILE  lalu: systemctl restart pteroshop-bot"

elif [[ "$PANEL_CHOICE" == "2" ]]; then
  echo ""
  PTERO_URL=$(get_input "URL Panel Pterodactyl (contoh: https://panel.domain.com)")
  PTERO_KEY=$(get_input "Application API Key (ptla_...)" "")

else
  warn "Panel URL dilewati. Isi nanti lewat Panel Admin Web → Konfigurasi."
  PTERO_URL=""
  PTERO_KEY=""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# BAGIAN 2 — Konfigurasi Bot
# ═══════════════════════════════════════════════════════════════════════════════
sep
echo -e "${BOLD}[ BAGIAN 2 ] Konfigurasi Bot Telegram${NC}"
echo ""
BOT_TOKEN=$(get_input "Telegram Bot Token (@BotFather)")
BOT_OWNER=$(get_input "Telegram ID kamu (owner bot)")
PAKASIR_KEY=$(get_input "API Key Pakasir" "")
PAKASIR_PROJ=$(get_input "Slug proyek Pakasir" "")

echo ""
echo -e "${BOLD}Egg IDs (Admin → Nests → pilih egg → lihat URL /admin/nests/x/eggs/Y):${NC}"
NODEJS_EGG=$(get_input "Egg ID Node.js" "15")
PYTHON_EGG=$(get_input "Egg ID Python"  "16")
LOC_ID=$(get_input     "Location ID default" "1")
NODE_ID=$(get_input    "Node ID default"     "1")

# ═══════════════════════════════════════════════════════════════════════════════
# BAGIAN 3 — Database & Panel Admin
# ═══════════════════════════════════════════════════════════════════════════════
sep
echo -e "${BOLD}[ BAGIAN 3 ] Database & Panel Admin Web${NC}"
echo ""
DB_PASS=$(get_input "Password database MySQL bot (buat baru)")
ADMIN_USER=$(get_input "Username Panel Admin Web" "admin")
ADMIN_PASS=$(get_input "Password Panel Admin Web")
SESSION_KEY=$(LC_ALL=C tr -dc 'A-Za-z0-9!@#^&*' </dev/urandom 2>/dev/null | head -c 48 || echo "secret$(date +%s%N)")

sep
echo ""
echo -e "${BOLD}Ringkasan instalasi:${NC}"
echo -e "  Panel Pterodactyl : ${CYAN}${PTERO_URL:-'(diisi nanti)'}${NC}"
echo -e "  Bot Token         : ${CYAN}${BOT_TOKEN:0:20}...${NC}"
echo -e "  Panel Admin Web   : ${CYAN}http://$(hostname -I | awk '{print $1}'):8888${NC}"
echo ""
read -rp "$(echo -e "${YELLOW}  Lanjutkan instalasi? (y/N): ${NC}")" CONFIRM
[[ "${CONFIRM,,}" == "y" ]] || exit 0

# ═══════════════════════════════════════════════════════════════════════════════
# INSTALL SYSTEM PACKAGES
# ═══════════════════════════════════════════════════════════════════════════════
sep; info "Menginstall system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  python3 python3-pip python3-venv python3-dev \
  mariadb-server mariadb-client \
  nginx curl wget git supervisor ufw \
  build-essential libssl-dev libffi-dev \
  software-properties-common 2>&1 | tail -5
log "System packages installed"

# ═══════════════════════════════════════════════════════════════════════════════
# MARIADB SETUP
# ═══════════════════════════════════════════════════════════════════════════════
sep; info "Mengkonfigurasi MariaDB..."
systemctl enable --now mariadb

mysql -u root <<SQL
CREATE DATABASE IF NOT EXISTS pterobot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'pterobot'@'127.0.0.1' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON pterobot.* TO 'pterobot'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
log "Database 'pterobot' siap"

# ═══════════════════════════════════════════════════════════════════════════════
# INSTALL PTERODACTYL PANEL (opsional — pilihan 1)
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$INSTALL_PTERODACTYL" == "true" ]]; then
  sep; info "Menginstall Pterodactyl Panel di VPS ini..."

  # PHP 8.2
  add-apt-repository -y ppa:ondrej/php 2>/dev/null
  apt-get update -qq
  apt-get install -y -qq \
    php8.2 php8.2-cli php8.2-gd php8.2-mysql php8.2-pdo \
    php8.2-mbstring php8.2-tokenizer php8.2-bcmath \
    php8.2-xml php8.2-fpm php8.2-curl php8.2-zip \
    redis-server cron 2>&1 | tail -5

  # Composer
  curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

  # Database untuk panel
  PTERO_DB_PASS="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || echo "ptero$(date +%s)")"
  mysql -u root <<SQL2
CREATE DATABASE IF NOT EXISTS panel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'pterodactyl'@'127.0.0.1' IDENTIFIED BY '${PTERO_DB_PASS}';
GRANT ALL PRIVILEGES ON panel.* TO 'pterodactyl'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL2

  # Download panel
  mkdir -p /var/www/pterodactyl
  cd /var/www/pterodactyl
  LATEST=$(curl -s https://api.github.com/repos/pterodactyl/panel/releases/latest \
    | grep browser_download_url | grep panel.tar.gz | cut -d'"' -f4)
  curl -Lo panel.tar.gz "$LATEST"
  tar -xzf panel.tar.gz && rm panel.tar.gz
  chmod -R 755 storage bootstrap/cache

  # Composer install
  COMPOSER_ALLOW_SUPERUSER=1 composer install --no-dev --optimize-autoloader --no-interaction -q

  # .env
  cp .env.example .env
  php artisan key:generate --force

  sed -i "s|APP_URL=.*|APP_URL=http://${PTERO_DOMAIN}|"         .env
  sed -i "s|APP_ENVIRONMENT=.*|APP_ENVIRONMENT=production|"     .env
  sed -i "s|APP_DEBUG=.*|APP_DEBUG=false|"                      .env
  sed -i "s|DB_HOST=.*|DB_HOST=127.0.0.1|"                      .env
  sed -i "s|DB_DATABASE=.*|DB_DATABASE=panel|"                  .env
  sed -i "s|DB_USERNAME=.*|DB_USERNAME=pterodactyl|"            .env
  sed -i "s|DB_PASSWORD=.*|DB_PASSWORD=${PTERO_DB_PASS}|"       .env
  sed -i "s|CACHE_DRIVER=.*|CACHE_DRIVER=redis|"                .env
  sed -i "s|SESSION_DRIVER=.*|SESSION_DRIVER=redis|"            .env
  sed -i "s|QUEUE_CONNECTION=.*|QUEUE_CONNECTION=redis|"        .env
  grep -q '^RECAPTCHA_ENABLED=' .env \
    && sed -i "s|RECAPTCHA_ENABLED=.*|RECAPTCHA_ENABLED=false|" .env \
    || echo "RECAPTCHA_ENABLED=false" >> .env

  # Migrate & seed
  php artisan migrate --seed --force -q

  # Buat admin user
  php artisan p:user:make \
    --email="${PTERO_EMAIL}" \
    --username="admin" \
    --name-first="Admin" \
    --name-last="PteroShop" \
    --password="${PTERO_ADMIN_PASS}" \
    --admin=1 || warn "User mungkin sudah ada, lanjutkan..."

  # Permissions & services
  chown -R www-data:www-data /var/www/pterodactyl/
  chmod -R 755 storage bootstrap/cache

  # Supervisor queue worker
  cat > /etc/supervisor/conf.d/ptero.conf <<CONF
[program:ptero-worker]
command=php /var/www/pterodactyl/artisan queue:work --sleep=3 --tries=3 --max-time=3600
autostart=true
autorestart=true
user=www-data
numprocs=2
redirect_stderr=true
stdout_logfile=/var/log/supervisor/ptero.log
CONF
  supervisorctl reread && supervisorctl update
  supervisorctl start ptero-worker:* 2>/dev/null || true

  # Cron
  echo "* * * * * www-data php /var/www/pterodactyl/artisan schedule:run >> /dev/null 2>&1" \
    > /etc/cron.d/pterodactyl
  systemctl restart cron
  systemctl restart php8.2-fpm redis-server

  # Nginx untuk panel (port 80)
  cat > /etc/nginx/sites-available/pterodactyl <<NGINX
server {
    listen 80;
    server_name ${PTERO_DOMAIN};
    root /var/www/pterodactyl/public;
    index index.php;
    client_max_body_size 100m;

    location / {
        try_files \$uri \$uri/ /index.php?\$query_string;
    }
    location ~ \.php$ {
        fastcgi_split_path_info ^(.+\.php)(/.+)$;
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
        fastcgi_index index.php;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME \$document_root\$fastcgi_script_name;
        fastcgi_param HTTP_PROXY "";
    }
    location ~ /\.ht { deny all; }
}
NGINX
  ln -sf /etc/nginx/sites-available/pterodactyl /etc/nginx/sites-enabled/pterodactyl
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl restart nginx

  # Buat Application API key via artisan
  APP_KEY_OUTPUT=$(php /var/www/pterodactyl/artisan p:api:key --user=1 --memo="pteroshop-bot" 2>/dev/null || echo "")
  PTERO_KEY=$(echo "$APP_KEY_OUTPUT" | grep -oP 'ptla_[A-Za-z0-9]+' | head -1 || echo "")
  if [[ -z "$PTERO_KEY" ]]; then
    warn "API Key tidak bisa dibuat otomatis."
    warn "Buat manual: buka http://${PTERO_DOMAIN} → Account → API Credentials → Create"
    warn "Lalu: nano $ENV_FILE  →  isi PTERODACTYL_API_KEY=ptla_..."
  else
    log "Application API Key: ${PTERO_KEY:0:20}..."
  fi

  PTERO_URL="http://${PTERO_DOMAIN}"
  log "Pterodactyl Panel installed → http://${PTERO_DOMAIN}"

  cd /
fi  # end INSTALL_PTERODACTYL

# ═══════════════════════════════════════════════════════════════════════════════
# CLONE / UPDATE BOT REPO
# ═══════════════════════════════════════════════════════════════════════════════
sep; info "Mengambil kode bot dari GitHub..."
if [[ -d "$INSTALL_DIR/.git" ]]; then
  cd "$INSTALL_DIR" && git pull --ff-only
  log "Repo diperbarui"
else
  git clone https://github.com/azascloud-cell/admin-pterodactyl "$INSTALL_DIR"
  log "Repo di-clone ke $INSTALL_DIR"
fi

# ── Python venv ────────────────────────────────────────────────────────────────
sep; info "Membuat virtual environment Python..."
cd "$INSTALL_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
log "Python dependencies installed"

# ── Tulis .env ─────────────────────────────────────────────────────────────────
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

# ── Systemd service bot ────────────────────────────────────────────────────────
sep; info "Membuat systemd service..."
cat > /etc/systemd/system/pteroshop-bot.service <<EOF
[Unit]
Description=PteroShop Telegram Bot + Panel Admin Web
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

# ── Nginx untuk panel admin web (port 8888) ────────────────────────────────────
sep; info "Mengkonfigurasi Nginx untuk Panel Admin Web..."
cat > /etc/nginx/sites-available/pteroshop-admin <<'NGINX'
server {
    listen 8888;
    server_name _;
    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/pteroshop-admin /etc/nginx/sites-enabled/pteroshop-admin
nginx -t && systemctl restart nginx
log "Nginx dikonfigurasi (port 8888)"

# ── UFW ────────────────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null; then
  ufw allow OpenSSH  >/dev/null 2>&1 || true
  ufw allow 80/tcp   >/dev/null 2>&1 || true   # pterodactyl panel
  ufw allow 8888/tcp >/dev/null 2>&1 || true   # panel admin web
  ufw allow 5000/tcp >/dev/null 2>&1 || true   # webhook pakasir
  log "UFW rules ditambahkan"
fi

# ── Start bot ──────────────────────────────────────────────────────────────────
sep; info "Menjalankan PteroShop..."
systemctl start pteroshop-bot
sleep 4
if systemctl is-active --quiet pteroshop-bot; then
  log "Bot berjalan!"
else
  warn "Bot gagal start — cek log: journalctl -u pteroshop-bot -n 50"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SELESAI
# ═══════════════════════════════════════════════════════════════════════════════
sep
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${BOLD}${GREEN}✅  INSTALASI SELESAI!${NC}"
echo ""
if [[ "$INSTALL_PTERODACTYL" == "true" ]]; then
echo -e "  ${BOLD}Pterodactyl Panel:${NC} http://${PTERO_DOMAIN}"
echo -e "  ${BOLD}Login panel:${NC}      ${PTERO_EMAIL} / (password yang kamu masukkan)"
[[ -n "$PTERO_KEY" ]] && echo -e "  ${BOLD}API Key panel:${NC}    ${PTERO_KEY:0:30}..."
echo ""
fi
echo -e "  ${BOLD}Panel Admin Web:${NC}  http://${SERVER_IP}:8888"
echo -e "  ${BOLD}Username:${NC}         ${ADMIN_USER}"
echo -e "  ${BOLD}Password:${NC}         (yang kamu masukkan tadi)"
echo ""
echo -e "  ${BOLD}Perintah berguna:${NC}"
echo -e "  • Cek status   : ${CYAN}systemctl status pteroshop-bot${NC}"
echo -e "  • Lihat log    : ${CYAN}journalctl -u pteroshop-bot -f${NC}"
echo -e "  • Restart bot  : ${CYAN}systemctl restart pteroshop-bot${NC}"
echo -e "  • Edit config  : ${CYAN}nano ${ENV_FILE}${NC}"
echo ""
if [[ -z "${PTERO_KEY}" ]] && [[ "$PANEL_CHOICE" != "3" ]]; then
echo -e "  ${YELLOW}⚠  Jangan lupa isi PTERODACTYL_API_KEY di:${NC}"
echo -e "     ${CYAN}nano ${ENV_FILE}${NC}"
echo -e "     Buat di panel: Account → API Credentials → Create"
echo -e "     Lalu: ${CYAN}systemctl restart pteroshop-bot${NC}"
echo ""
fi
echo -e "  ${BOLD}File lokasi:${NC} ${INSTALL_DIR}"
sep
