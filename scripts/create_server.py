#!/usr/bin/env python3
"""
Auto-create server Node.js di Pterodactyl via DB langsung.
Dijalankan setelah Wings sudah running dan terhubung ke panel.

Server yang dibuat:
  - Nama     : "My Node.js App"
  - Egg      : Node.js Generic (dari import_nodejs_egg.py)
  - Memory   : 512 MB
  - Disk     : 1024 MB
  - CPU      : 100% (1 core)
  - Port     : 3000 (alokasi pertama yang tersedia di node)
"""
import subprocess, sys, uuid as uuidlib, os, json, time
from datetime import datetime

NOW      = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
NODE_ID  = os.environ.get('WINGS_NODE_ID', '')

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

# ── 1. Resolve node ───────────────────────────────────────────────────────────
print('→ Resolving node...')
if NODE_ID:
    node_id = NODE_ID
else:
    node_id = mysql_val("SELECT id FROM nodes WHERE name='GitHub Actions Runner' LIMIT 1;")
if not node_id:
    print('  ERROR: Node "GitHub Actions Runner" not found. Run setup_wings.py first.')
    sys.exit(1)
print(f'  ✓ Node ID: {node_id}')

# ── 2. Cek apakah server sudah ada ───────────────────────────────────────────
print('→ Checking existing servers...')
srv_count = int(mysql_val("SELECT COUNT(*) FROM servers;") or '0')
if srv_count > 0:
    print(f'  ✓ Server already exists ({srv_count} server(s)) — skip create')
    sys.exit(0)

# ── 3. Dapatkan data yang dibutuhkan ──────────────────────────────────────────
print('→ Gathering required data...')

# Owner (admin user)
owner_id = mysql_val("SELECT id FROM users WHERE root_admin=1 LIMIT 1;")
if not owner_id:
    print('  ERROR: No admin user found.')
    sys.exit(1)

# Egg Node.js Generic
egg_id = mysql_val("SELECT id FROM eggs WHERE name='Node.js Generic' LIMIT 1;")
if not egg_id:
    print('  ERROR: Egg "Node.js Generic" not found. Run import_nodejs_egg.py first.')
    sys.exit(1)
nest_id = mysql_val(f"SELECT nest_id FROM eggs WHERE id={egg_id};")

# Ambil startup command dari egg
startup = mysql_val(f"SELECT startup FROM eggs WHERE id={egg_id};")
if not startup:
    startup = "node /home/container/{{JS_FILE}}"

# Docker image default
docker_image = "ghcr.io/pterodactyl/yolks:nodejs_22"

# Alokasi bebas di node ini
alloc_id = mysql_val(
    f"SELECT id FROM allocations WHERE node_id={node_id} AND server_id IS NULL "
    f"ORDER BY port ASC LIMIT 1;"
)
if not alloc_id:
    print('  ERROR: No free allocation found on node.')
    sys.exit(1)
alloc_port = mysql_val(f"SELECT port FROM allocations WHERE id={alloc_id};")
print(f'  ✓ Owner: {owner_id} | Egg: {egg_id} | Alloc: {alloc_id} (port {alloc_port})')

# ── 4. Buat server ────────────────────────────────────────────────────────────
print('→ Creating server...')
srv_uuid       = str(uuidlib.uuid4())
srv_uuid_short = srv_uuid.replace('-', '')[:8]
srv_name       = "My Node.js App"
srv_desc       = "Auto-created by GitHub Actions CI"

mysql(
    f"INSERT INTO servers "
    f"(uuid, uuid_short, node_id, name, description, status, skip_scripts, "
    f"owner_id, memory, swap, disk, io, cpu, threads, oom_disabled, "
    f"allocation_id, nest_id, egg_id, "
    f"startup, image, installed, "
    f"allocation_limit, database_limit, backup_limit, "
    f"created_at, updated_at) VALUES "
    f"('{srv_uuid}', '{srv_uuid_short}', {node_id}, "
    f"'{q(srv_name)}', '{q(srv_desc)}', 'installing', 0, "
    f"{owner_id}, 512, 0, 1024, 500, 100, NULL, 0, "
    f"{alloc_id}, {nest_id}, {egg_id}, "
    f"'{q(startup)}', '{docker_image}', 1, "
    f"0, 0, 0, "
    f"'{NOW}', '{NOW}');"
)
srv_id = mysql_val(f"SELECT id FROM servers WHERE uuid='{srv_uuid}' LIMIT 1;")
if not srv_id:
    print('  ERROR: Server insert failed.')
    sys.exit(1)

# Tandai alokasi sebagai dipakai
mysql(f"UPDATE allocations SET server_id={srv_id} WHERE id={alloc_id};")
print(f'  ✓ Server created (id={srv_id}, uuid_short={srv_uuid_short})')

# ── 5. Buat server variables ──────────────────────────────────────────────────
print('→ Creating server variables...')
egg_vars = mysql_val(
    f"SELECT id, env_variable, default_value FROM egg_variables WHERE egg_id={egg_id};"
).splitlines()
for row in egg_vars:
    parts = row.split('\t')
    if len(parts) < 3:
        continue
    var_id, env_var, default_val = parts[0].strip(), parts[1].strip(), parts[2].strip()
    mysql(
        f"INSERT INTO server_variables (server_id, variable_id, variable_value, created_at, updated_at) "
        f"VALUES ({srv_id}, {var_id}, '{q(default_val)}', '{NOW}', '{NOW}');"
    )
    print(f'  ✓ Variable {env_var}={default_val}')

# ── 6. Summary ────────────────────────────────────────────────────────────────
print('')
print('══════════════════════════════════════════')
print(f'  ✅ Server Node.js berhasil dibuat!')
print(f'     Server ID   : {srv_id}')
print(f'     UUID Short  : {srv_uuid_short}')
print(f'     Allocation  : 0.0.0.0:{alloc_port}')
print(f'     Memory      : 512 MB')
print(f'     Disk        : 1024 MB')
print(f'     Egg         : Node.js Generic (id={egg_id})')
print(f'     Image       : {docker_image}')
print('══════════════════════════════════════════')

# Export ke GITHUB_ENV
github_env = os.environ.get('GITHUB_ENV', '')
if github_env:
    with open(github_env, 'a') as f:
        f.write(f'SERVER_UUID_SHORT={srv_uuid_short}\n')
        f.write(f'SERVER_PORT={alloc_port}\n')
