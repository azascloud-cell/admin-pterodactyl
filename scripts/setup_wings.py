#!/usr/bin/env python3
"""
Setup Wings daemon node di Pterodactyl panel (via DB langsung).
Membuat node, alokasi port, dan menulis config.yml untuk Wings.

Dijalankan SETELAH panel up dan TUNNEL_URL sudah di-set.
Output: WINGS_NODE_ID=<id> di stdout (dibaca oleh GitHub Actions)
"""
import subprocess, sys, uuid as uuidlib, os, secrets
from datetime import datetime

NOW   = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
PANEL_URL        = os.environ.get('TUNNEL_URL', 'http://localhost')
WINGS_CONFIG_DIR = '/etc/pterodactyl'
WINGS_DATA_DIR   = '/var/lib/pterodactyl/volumes'

# ── Helpers ───────────────────────────────────────────────────────────────────
def mysql(sql, db='panel'):
    r = subprocess.run(
        ['sudo', 'mysql', '-u', 'root', db, '-e', sql],
        capture_output=True, text=True)
    if r.returncode != 0:
        print('  MySQL error:', r.stderr.strip(), file=sys.stderr)
    return r

def mysql_val(sql, db='panel'):
    r = subprocess.run(
        ['sudo', 'mysql', '-u', 'root', db, '-se', sql],
        capture_output=True, text=True)
    return r.stdout.strip()

def q(s):
    return str(s).replace("'", "\\'")

# ── 1. Pastikan location ada ──────────────────────────────────────────────────
print('→ Checking location...')
loc_id = mysql_val("SELECT id FROM locations LIMIT 1;")
if not loc_id:
    mysql(f"INSERT INTO locations (short, long, created_at, updated_at) "
          f"VALUES ('local', 'Default Location', '{NOW}', '{NOW}');")
    loc_id = mysql_val("SELECT id FROM locations LIMIT 1;")
print(f'  ✓ Location ID: {loc_id}')

# ── 2. Buat/temukan node ──────────────────────────────────────────────────────
print('→ Checking node...')
node_id = mysql_val("SELECT id FROM nodes WHERE name='GitHub Actions Runner' LIMIT 1;")
if node_id:
    print(f'  ✓ Node already exists (id={node_id})')
    daemon_token = mysql_val(f"SELECT daemon_token FROM nodes WHERE id={node_id};")
else:
    node_uuid    = str(uuidlib.uuid4())
    daemon_token = secrets.token_hex(32)
    mysql(
        f"INSERT INTO nodes "
        f"(uuid, public, name, location_id, fqdn, scheme, behind_proxy, "
        f"memory, memory_overallocate, disk, disk_overallocate, upload_size, "
        f"daemon_base, daemon_sftp, daemon_listen, daemon_token, "
        f"maintenance_mode, created_at, updated_at) VALUES "
        f"('{node_uuid}', 1, 'GitHub Actions Runner', {loc_id}, "
        f"'127.0.0.1', 'http', 0, "
        f"7168, 0, 102400, 0, 100, "
        f"'{WINGS_DATA_DIR}', 2022, 8080, '{daemon_token}', "
        f"0, '{NOW}', '{NOW}');"
    )
    node_id = mysql_val("SELECT id FROM nodes WHERE name='GitHub Actions Runner' LIMIT 1;")
    print(f'  ✓ Node created (id={node_id})')

# ── 3. Tambah alokasi port jika belum ada ─────────────────────────────────────
print('→ Checking allocations...')
alloc_count = int(mysql_val(f"SELECT COUNT(*) FROM allocations WHERE node_id={node_id};") or '0')
if alloc_count == 0:
    ports = [3000, 3001, 3002, 8000, 8001, 8002, 25565, 25566, 25567, 25568, 25569, 25570]
    for port in ports:
        mysql(
            f"INSERT INTO allocations (node_id, ip, port, created_at, updated_at) "
            f"VALUES ({node_id}, '0.0.0.0', {port}, '{NOW}', '{NOW}');"
        )
    print(f'  ✓ {len(ports)} allocations added')
else:
    print(f'  ✓ Allocations exist ({alloc_count})')

# ── 4. Tulis Wings config.yml ─────────────────────────────────────────────────
print('→ Writing Wings config...')
subprocess.run(['sudo', 'mkdir', '-p', WINGS_CONFIG_DIR], check=True)
subprocess.run(['sudo', 'mkdir', '-p', WINGS_DATA_DIR],   check=True)

config = (
    "debug: false\n"
    "uuid: '{node_uuid}'\n"
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
    "remote: '{remote}'\n"
    "allowed_mounts: []\n"
    "allowed_origins: []\n"
).format(
    node_uuid=mysql_val(f"SELECT uuid FROM nodes WHERE id={node_id};"),
    token_id=daemon_token[:8],
    token=daemon_token,
    data=WINGS_DATA_DIR,
    remote='http://127.0.0.1:80',
)

# Tulis via temp file agar tidak ada masalah sudo
tmp_cfg = '/tmp/wings_config.yml'
with open(tmp_cfg, 'w') as f:
    f.write(config)
subprocess.run(['sudo', 'cp', tmp_cfg, f'{WINGS_CONFIG_DIR}/config.yml'], check=True)
print(f'  ✓ Config → {WINGS_CONFIG_DIR}/config.yml')

# ── 5. Output untuk GitHub Actions ───────────────────────────────────────────
print('')
print('══════════════════════════════════════════')
print(f'  ✅ Wings node ready!')
print(f'     Node ID      : {node_id}')
print(f'     Daemon token : {daemon_token[:8]}...(truncated)')
print(f'     Allocs       : ports 3000-3002, 8000-8002, 25565-25570')
print(f'     Wings remote : http://127.0.0.1:80')
print('══════════════════════════════════════════')

# Export ke GITHUB_ENV jika tersedia
github_env = os.environ.get('GITHUB_ENV', '')
if github_env:
    with open(github_env, 'a') as f:
        f.write(f'WINGS_NODE_ID={node_id}\n')
