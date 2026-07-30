#!/usr/bin/env python3
"""
Setup Wings daemon node di Pterodactyl panel (via DB langsung).

Pterodactyl v1.x nodes table memerlukan:
  - daemon_token_id : char(16) unique  — plaintext identifier (dikirim ke Wings)
  - daemon_token    : text             — bcrypt hash dari token  (disimpan di panel)

Wings config.yml menggunakan:
  token_id: <daemon_token_id>   (16-char identifier)
  token:    <plaintext_token>   (token asli sebelum di-hash)
"""
import subprocess, sys, uuid as uuidlib, os, secrets
from datetime import datetime

NOW              = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
PANEL_URL        = os.environ.get('TUNNEL_URL', 'http://localhost')
WINGS_CONFIG_DIR = '/etc/pterodactyl'
WINGS_DATA_DIR   = '/var/lib/pterodactyl/volumes'
PANEL_DIR        = '/var/www/pterodactyl'

# ── Helpers ───────────────────────────────────────────────────────────────────
def mysql(sql, db='panel'):
    r = subprocess.run(
        ['sudo', 'mysql', '-u', 'root', db, '-e', sql],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(f'  ❌ MySQL error: {r.stderr.strip()}')
        sys.exit(1)
    return r

def mysql_val(sql, db='panel'):
    r = subprocess.run(
        ['sudo', 'mysql', '-u', 'root', db, '-se', sql],
        capture_output=True, text=True)
    return r.stdout.strip()

def bcrypt(plaintext):
    """Hash string pakai PHP bcrypt (kompatibel dengan Pterodactyl)."""
    r = subprocess.run(
        ['php8.2', '-r', f"echo password_hash('{plaintext}', PASSWORD_BCRYPT);"],
        capture_output=True, text=True)
    h = r.stdout.strip()
    if not h.startswith('$2'):
        print(f'  ❌ bcrypt failed: {r.stderr.strip()}')
        sys.exit(1)
    return h

def q(s):
    return str(s).replace("'", "\\'")

# ── 1. Cek schema nodes (pastikan kolom daemon_token_id ada) ──────────────────
print('→ Checking nodes table schema...')
cols_raw = mysql_val("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='panel' AND TABLE_NAME='nodes';")
cols = set(cols_raw.splitlines())
print(f'  ✓ Columns found: {sorted(cols)}')
has_token_id_col = 'daemon_token_id' in cols
print(f'  ✓ daemon_token_id column exists: {has_token_id_col}')

# ── 2. Pastikan location ada ──────────────────────────────────────────────────
print('→ Checking location...')
loc_id = mysql_val("SELECT id FROM locations LIMIT 1;")
if not loc_id:
    mysql(f"INSERT INTO locations (short, long, created_at, updated_at) "
          f"VALUES ('local', 'Default Location', '{NOW}', '{NOW}');")
    loc_id = mysql_val("SELECT id FROM locations LIMIT 1;")
print(f'  ✓ Location ID: {loc_id}')

# ── 3. Buat/temukan node ──────────────────────────────────────────────────────
print('→ Checking node...')
node_id = mysql_val("SELECT id FROM nodes WHERE name='GitHub Actions Runner' LIMIT 1;")

if node_id:
    print(f'  ✓ Node already exists (id={node_id})')
    # Ambil token yang disimpan — kita perlu plaintext, tapi hashed disimpan di DB
    # Jadi kita generate token baru dan update
    print('  ↻ Regenerating token for Wings config...')
    token_plaintext = secrets.token_hex(32)
    token_id        = secrets.token_hex(8)   # 16-char hex
    token_hashed    = bcrypt(token_plaintext)
    if has_token_id_col:
        mysql(f"UPDATE nodes SET daemon_token_id='{token_id}', daemon_token='{q(token_hashed)}' WHERE id={node_id};")
    else:
        mysql(f"UPDATE nodes SET daemon_token='{q(token_hashed)}' WHERE id={node_id};")
        token_id = token_plaintext[:16]
else:
    node_uuid       = str(uuidlib.uuid4())
    token_plaintext = secrets.token_hex(32)
    token_id        = secrets.token_hex(8)   # 16-char hex
    token_hashed    = bcrypt(token_plaintext)

    if has_token_id_col:
        mysql(
            f"INSERT INTO nodes "
            f"(uuid, public, name, location_id, fqdn, scheme, behind_proxy, "
            f"memory, memory_overallocate, disk, disk_overallocate, upload_size, "
            f"daemon_base, daemon_sftp, daemon_listen, "
            f"daemon_token_id, daemon_token, "
            f"maintenance_mode, created_at, updated_at) VALUES "
            f"('{node_uuid}', 1, 'GitHub Actions Runner', {loc_id}, "
            f"'127.0.0.1', 'http', 0, "
            f"7168, 0, 102400, 0, 100, "
            f"'{WINGS_DATA_DIR}', 2022, 8080, "
            f"'{token_id}', '{q(token_hashed)}', "
            f"0, '{NOW}', '{NOW}');"
        )
    else:
        mysql(
            f"INSERT INTO nodes "
            f"(uuid, public, name, location_id, fqdn, scheme, behind_proxy, "
            f"memory, memory_overallocate, disk, disk_overallocate, upload_size, "
            f"daemon_base, daemon_sftp, daemon_listen, daemon_token, "
            f"maintenance_mode, created_at, updated_at) VALUES "
            f"('{node_uuid}', 1, 'GitHub Actions Runner', {loc_id}, "
            f"'127.0.0.1', 'http', 0, "
            f"7168, 0, 102400, 0, 100, "
            f"'{WINGS_DATA_DIR}', 2022, 8080, '{q(token_hashed)}', "
            f"0, '{NOW}', '{NOW}');"
        )

    node_id = mysql_val("SELECT id FROM nodes WHERE name='GitHub Actions Runner' LIMIT 1;")
    if not node_id:
        print('  ❌ Node INSERT failed — node_id still empty after insert')
        sys.exit(1)
    print(f'  ✓ Node created (id={node_id})')

node_uuid_db = mysql_val(f"SELECT uuid FROM nodes WHERE id={node_id};")
print(f'  ✓ Node UUID: {node_uuid_db}')

# ── 4. Tambah alokasi port jika belum ada ─────────────────────────────────────
print('→ Checking allocations...')
alloc_count = int(mysql_val(f"SELECT COUNT(*) FROM allocations WHERE node_id={node_id};") or '0')
if alloc_count == 0:
    ports = [3000, 3001, 3002, 8000, 8001, 8002, 25565, 25566, 25567, 25568, 25569, 25570]
    for port in ports:
        mysql(
            f"INSERT INTO allocations (node_id, ip, port, created_at, updated_at) "
            f"VALUES ({node_id}, '0.0.0.0', {port}, '{NOW}', '{NOW}');"
        )
    print(f'  ✓ {len(ports)} allocations added (3000-3002, 8000-8002, 25565-25570)')
else:
    print(f'  ✓ Allocations exist ({alloc_count})')

# ── 5. Tulis Wings config.yml ─────────────────────────────────────────────────
print('→ Writing Wings config...')
subprocess.run(['sudo', 'mkdir', '-p', WINGS_CONFIG_DIR], check=True)
subprocess.run(['sudo', 'mkdir', '-p', WINGS_DATA_DIR],   check=True)
subprocess.run(['sudo', 'mkdir', '-p', '/var/log/pterodactyl'], check=True)

# Wings config.yml — pakai token_id + plaintext token
config = (
    "debug: false\n"
    "uuid: '{uuid}'\n"
    "token_id: '{token_id}'\n"
    "token: '{token}'\n"
    "api:\n"
    "  host: 0.0.0.0\n"
    "  port: 8080\n"
    "  ssl:\n"
    "    enabled: false\n"
    "  upload_limit: 100\n"
    "system:\n"
    "  data: {data}\n"
    "  sftp:\n"
    "    bind_port: 2022\n"
    "remote: 'http://127.0.0.1:80'\n"
    "allowed_mounts: []\n"
    "allowed_origins: []\n"
).format(
    uuid=node_uuid_db,
    token_id=token_id,
    token=token_plaintext,
    data=WINGS_DATA_DIR,
)

tmp_cfg = '/tmp/wings_config.yml'
with open(tmp_cfg, 'w') as f:
    f.write(config)
subprocess.run(['sudo', 'cp', tmp_cfg, f'{WINGS_CONFIG_DIR}/config.yml'], check=True)
subprocess.run(['sudo', 'chmod', '600', f'{WINGS_CONFIG_DIR}/config.yml'], check=True)

# Buat log file dengan permission yang benar
subprocess.run(['sudo', 'touch', '/var/log/pterodactyl/wings.log'], check=True)
subprocess.run(['sudo', 'chmod', '666', '/var/log/pterodactyl/wings.log'], check=True)

print(f'  ✓ Config → {WINGS_CONFIG_DIR}/config.yml')
print(f'  ✓ token_id: {token_id}')

# ── 6. Export ke GITHUB_ENV ───────────────────────────────────────────────────
github_env = os.environ.get('GITHUB_ENV', '')
if github_env:
    with open(github_env, 'a') as f:
        f.write(f'WINGS_NODE_ID={node_id}\n')
    print(f'  ✓ WINGS_NODE_ID={node_id} exported')
else:
    print('  ⚠ GITHUB_ENV not set — skipping export')

print('')
print('══════════════════════════════════════════')
print(f'  ✅ Wings node ready!')
print(f'     Node ID  : {node_id}')
print(f'     UUID     : {node_uuid_db}')
print(f'     token_id : {token_id}')
print(f'     Remote   : http://127.0.0.1:80')
print('══════════════════════════════════════════')
