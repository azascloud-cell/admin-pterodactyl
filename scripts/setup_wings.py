#!/usr/bin/env python3
"""
Setup Wings daemon node di Pterodactyl panel (via DB langsung).

Pterodactyl v1.x nodes table pakai CAMPURAN camelCase dan snake_case:
  camelCase  : daemonBase, daemonListen, daemonSFTP
  snake_case : daemon_token_id, daemon_token, behind_proxy, dll

PENTING: daemon_token harus disimpan sebagai PLAINTEXT (bukan bcrypt).
Pterodactyl panel menggunakan raw daemon_token untuk sign JWT ke Wings.
Wings memverifikasi JWT tersebut dengan token yang sama di config.yml.
Wings→Panel auth menggunakan Bearer token_id.token_plaintext.
"""
import subprocess, sys, uuid as uuidlib, os, secrets
from datetime import datetime

NOW              = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
WINGS_CONFIG_DIR = '/etc/pterodactyl'
WINGS_DATA_DIR   = '/var/lib/pterodactyl/volumes'

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

def q(s):
    return str(s).replace("'", "\\'")

def col(cols, *candidates):
    """Return first candidate column name that exists in schema."""
    for c in candidates:
        if c in cols:
            return c
    raise ValueError(f"None of {candidates} found in schema: {sorted(cols)}")

# ── 1. Probe nodes table schema ───────────────────────────────────────────────
print('→ Probing nodes table schema...')
cols_raw = mysql_val(
    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
    "WHERE TABLE_SCHEMA='panel' AND TABLE_NAME='nodes';"
)
cols = set(cols_raw.splitlines())
print(f'  ✓ Columns: {sorted(cols)}')

# Resolve kolom yang camelCase vs snake_case
C_BASE   = col(cols, 'daemonBase',   'daemon_base')
C_LISTEN = col(cols, 'daemonListen', 'daemon_listen')
C_SFTP   = col(cols, 'daemonSFTP',   'daemon_sftp')
HAS_TOKEN_ID = 'daemon_token_id' in cols
print(f'  ✓ daemon cols: {C_BASE}, {C_LISTEN}, {C_SFTP} | token_id col: {HAS_TOKEN_ID}')

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

# Generate token — simpan PLAINTEXT di DB agar panel bisa sign JWT ke Wings
# Wings verifikasi JWT panel pakai token yang sama (plaintext)
token_plaintext = secrets.token_hex(32)
token_id_val    = secrets.token_hex(8)   # 16-char hex string

if node_id:
    print(f'  ✓ Node already exists (id={node_id}) — updating token (plaintext)')
    if HAS_TOKEN_ID:
        mysql(f"UPDATE nodes SET daemon_token_id='{token_id_val}', "
              f"daemon_token='{q(token_plaintext)}' WHERE id={node_id};")
    else:
        mysql(f"UPDATE nodes SET daemon_token='{q(token_plaintext)}' WHERE id={node_id};")
else:
    node_uuid = str(uuidlib.uuid4())
    if HAS_TOKEN_ID:
        mysql(
            f"INSERT INTO nodes "
            f"(uuid, public, name, location_id, fqdn, scheme, behind_proxy, "
            f"memory, memory_overallocate, disk, disk_overallocate, upload_size, "
            f"`{C_BASE}`, `{C_SFTP}`, `{C_LISTEN}`, "
            f"daemon_token_id, daemon_token, "
            f"maintenance_mode, created_at, updated_at) VALUES "
            f"('{node_uuid}', 1, 'GitHub Actions Runner', {loc_id}, "
            f"'127.0.0.1', 'http', 0, "
            f"7168, 0, 102400, 0, 100, "
            f"'{WINGS_DATA_DIR}', 2022, 8080, "
            f"'{token_id_val}', '{q(token_plaintext)}', "
            f"0, '{NOW}', '{NOW}');"
        )
    else:
        mysql(
            f"INSERT INTO nodes "
            f"(uuid, public, name, location_id, fqdn, scheme, behind_proxy, "
            f"memory, memory_overallocate, disk, disk_overallocate, upload_size, "
            f"`{C_BASE}`, `{C_SFTP}`, `{C_LISTEN}`, daemon_token, "
            f"maintenance_mode, created_at, updated_at) VALUES "
            f"('{node_uuid}', 1, 'GitHub Actions Runner', {loc_id}, "
            f"'127.0.0.1', 'http', 0, "
            f"7168, 0, 102400, 0, 100, "
            f"'{WINGS_DATA_DIR}', 2022, 8080, '{q(token_plaintext)}', "
            f"0, '{NOW}', '{NOW}');"
        )
    node_id = mysql_val("SELECT id FROM nodes WHERE name='GitHub Actions Runner' LIMIT 1;")
    if not node_id:
        print('  ❌ Node INSERT failed — id still empty after insert')
        sys.exit(1)
    print(f'  ✓ Node created (id={node_id})')

node_uuid_db = mysql_val(f"SELECT uuid FROM nodes WHERE id={node_id};")
print(f'  ✓ node_id={node_id}  uuid={node_uuid_db}')

# ── 4. Tambah alokasi port jika belum ada ─────────────────────────────────────
print('→ Checking allocations...')
alloc_count = int(mysql_val(f"SELECT COUNT(*) FROM allocations WHERE node_id={node_id};") or '0')
if alloc_count == 0:
    ports = [3000, 3001, 3002, 8000, 8001, 8002, 25565, 25566, 25567, 25568, 25569, 25570]
    for port in ports:
        mysql(f"INSERT INTO allocations (node_id, ip, port, created_at, updated_at) "
              f"VALUES ({node_id}, '0.0.0.0', {port}, '{NOW}', '{NOW}');")
    print(f'  ✓ {len(ports)} allocations added')
else:
    print(f'  ✓ Allocations exist ({alloc_count})')

# ── 5. Tulis Wings config.yml ─────────────────────────────────────────────────
print('→ Writing Wings config...')
subprocess.run(['sudo', 'mkdir', '-p', WINGS_CONFIG_DIR], check=True)
subprocess.run(['sudo', 'mkdir', '-p', WINGS_DATA_DIR],   check=True)
subprocess.run(['sudo', 'mkdir', '-p', '/var/log/pterodactyl'], check=True)
subprocess.run(['sudo', 'touch', '/var/log/pterodactyl/wings.log'], check=True)
subprocess.run(['sudo', 'chmod', '666', '/var/log/pterodactyl/wings.log'], check=True)

config = (
    "debug: true\n"
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
    token_id=token_id_val,
    token=token_plaintext,
    data=WINGS_DATA_DIR,
)

tmp_cfg = '/tmp/wings_config.yml'
with open(tmp_cfg, 'w') as f:
    f.write(config)
subprocess.run(['sudo', 'cp', tmp_cfg, f'{WINGS_CONFIG_DIR}/config.yml'], check=True)
subprocess.run(['sudo', 'chmod', '600', f'{WINGS_CONFIG_DIR}/config.yml'], check=True)
print(f'  ✓ Config written: token_id={token_id_val}  token(plaintext, len={len(token_plaintext)})')

# ── 6. Export ke GITHUB_ENV ───────────────────────────────────────────────────
github_env = os.environ.get('GITHUB_ENV', '')
if github_env:
    with open(github_env, 'a') as f:
        f.write(f'WINGS_NODE_ID={node_id}\n')
    print(f'  ✓ WINGS_NODE_ID={node_id} exported to GITHUB_ENV')

print('')
print('══════════════════════════════════════════')
print(f'  ✅ Wings node ready!')
print(f'     Node ID  : {node_id}')
print(f'     UUID     : {node_uuid_db}')
print(f'     token_id : {token_id_val}')
print(f'     token    : (plaintext, {len(token_plaintext)} chars)')
print('══════════════════════════════════════════')
