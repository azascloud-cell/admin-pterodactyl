#!/usr/bin/env python3
"""
Auto-create server Node.js di Pterodactyl via DB langsung.
Probe schema servers table dulu agar tidak error kolom camelCase/snake_case.
"""
import subprocess, sys, uuid as uuidlib, os
from datetime import datetime

NOW     = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
NODE_ID = os.environ.get('WINGS_NODE_ID', '')

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
    for c in candidates:
        if c in cols:
            return c
    raise ValueError(f'None of {candidates} found in schema')

# ── 1. Probe servers table schema ─────────────────────────────────────────────
print('→ Probing servers table schema...')
srv_cols_raw = mysql_val(
    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
    "WHERE TABLE_SCHEMA='panel' AND TABLE_NAME='servers';"
)
srv_cols = set(srv_cols_raw.splitlines())
print(f'  ✓ Columns: {sorted(srv_cols)}')

# Resolve camelCase vs snake_case
C_UUID_SHORT  = col(srv_cols, 'uuidShort',        'uuid_short')
C_SKIP        = col(srv_cols, 'skip_scripts',     'skipScripts')
C_OOM         = col(srv_cols, 'oom_disabled',     'oomDisabled',  'oom_killer')
C_INSTALLED   = col(srv_cols, 'installed',        'status')
C_ALLOC_LIM   = col(srv_cols, 'allocation_limit', 'allocationLimit') if (
    'allocation_limit' in srv_cols or 'allocationLimit' in srv_cols) else None
C_DB_LIM      = col(srv_cols, 'database_limit',   'databaseLimit') if (
    'database_limit' in srv_cols or 'databaseLimit' in srv_cols) else None
C_BACKUP_LIM  = col(srv_cols, 'backup_limit',     'backupLimit') if (
    'backup_limit' in srv_cols or 'backupLimit' in srv_cols) else None
# Cek apakah ada kolom 'status' terpisah dari 'installed'
HAS_STATUS_COL = 'status' in srv_cols and 'installed' in srv_cols

print(f'  ✓ uuid_short col  : {C_UUID_SHORT}')
print(f'  ✓ skip_scripts col: {C_SKIP}')
print(f'  ✓ oom col         : {C_OOM}')
print(f'  ✓ installed col   : {C_INSTALLED}')
print(f'  ✓ limit cols      : alloc={C_ALLOC_LIM} db={C_DB_LIM} backup={C_BACKUP_LIM}')

# ── 2. Resolve node ───────────────────────────────────────────────────────────
print('→ Resolving node...')
node_id = NODE_ID or mysql_val("SELECT id FROM nodes WHERE name='GitHub Actions Runner' LIMIT 1;")
if not node_id:
    print('  ❌ Node not found. Run setup_wings.py first.')
    sys.exit(1)
print(f'  ✓ Node ID: {node_id}')

# ── 3. Cek server sudah ada ───────────────────────────────────────────────────
print('→ Checking existing servers...')
srv_count = int(mysql_val("SELECT COUNT(*) FROM servers;") or '0')
if srv_count > 0:
    print(f'  ✓ Server already exists ({srv_count}) — skip')
    sys.exit(0)

# ── 4. Gather dependencies ────────────────────────────────────────────────────
print('→ Gathering dependencies...')

owner_id = mysql_val("SELECT id FROM users WHERE root_admin=1 LIMIT 1;")
if not owner_id:
    print('  ❌ No admin user found.')
    sys.exit(1)

egg_id = mysql_val("SELECT id FROM eggs WHERE name='Node.js Generic' LIMIT 1;")
if not egg_id:
    print('  ❌ Egg "Node.js Generic" not found. Run import_nodejs_egg.py first.')
    sys.exit(1)
nest_id = mysql_val(f"SELECT nest_id FROM eggs WHERE id={egg_id};")
startup = mysql_val(f"SELECT startup FROM eggs WHERE id={egg_id};") or \
          "node /home/container/{{JS_FILE}}"
docker_image = "ghcr.io/pterodactyl/yolks:nodejs_22"

alloc_id = mysql_val(
    f"SELECT id FROM allocations WHERE node_id={node_id} AND server_id IS NULL "
    f"ORDER BY port ASC LIMIT 1;"
)
if not alloc_id:
    print('  ❌ No free allocation on node.')
    sys.exit(1)
alloc_port = mysql_val(f"SELECT port FROM allocations WHERE id={alloc_id};")
print(f'  ✓ owner={owner_id} egg={egg_id} nest={nest_id} alloc={alloc_id}(:{alloc_port})')

# ── 5. Build INSERT dynamically ───────────────────────────────────────────────
print('→ Creating server...')
srv_uuid      = str(uuidlib.uuid4())
srv_uuid_short = srv_uuid.replace('-', '')[:8]

# Nilai installed — bisa tinyint(1) atau enum/string tergantung versi
installed_val = '1'

# Build kolom + nilai
insert_cols = [
    'uuid', f'`{C_UUID_SHORT}`', 'node_id', 'name', 'description',
    f'`{C_SKIP}`', 'owner_id',
    'memory', 'swap', 'disk', 'io', 'cpu', 'threads', f'`{C_OOM}`',
    'allocation_id', 'nest_id', 'egg_id',
    'startup', 'image', f'`{C_INSTALLED}`',
    'created_at', 'updated_at',
]
insert_vals = [
    f"'{srv_uuid}'", f"'{srv_uuid_short}'", node_id,
    f"'{q('My Node.js App')}'", f"'{q('Auto-created by GitHub Actions CI')}'",
    '1', owner_id,              # skip_scripts=1 → langsung skip install container
    '512', '0', '1024', '500', '100', 'NULL', '0',
    alloc_id, nest_id, egg_id,
    f"'{q(startup)}'", f"'{docker_image}'", installed_val,
    f"'{NOW}'", f"'{NOW}'",
]

# Tambah limit cols jika ada
for lim_col, lim_val in [(C_ALLOC_LIM, '0'), (C_DB_LIM, '0'), (C_BACKUP_LIM, '0')]:
    if lim_col:
        insert_cols.append(f'`{lim_col}`')
        insert_vals.append(lim_val)

# Jika installed col == status (enum), set NULL = installed (bukan 'installing')
if C_INSTALLED == 'status':
    idx = insert_cols.index(f'`{C_INSTALLED}`')
    insert_vals[idx] = 'NULL'   # NULL = server installed di Pterodactyl v1.x

# Jika ada KEDUA kolom installed + status, tambahkan status=NULL secara eksplisit
if HAS_STATUS_COL:
    insert_cols.append('`status`')
    insert_vals.append('NULL')   # NULL = installed / no pending action

sql = (
    f"INSERT INTO servers ({', '.join(insert_cols)}) "
    f"VALUES ({', '.join(str(v) for v in insert_vals)});"
)
mysql(sql)

srv_id = mysql_val(f"SELECT id FROM servers WHERE uuid='{srv_uuid}' LIMIT 1;")
if not srv_id:
    print('  ❌ Server INSERT failed.')
    sys.exit(1)
mysql(f"UPDATE allocations SET server_id={srv_id} WHERE id={alloc_id};")
print(f'  ✓ Server created (id={srv_id}, uuidShort={srv_uuid_short})')

# ── 6. Server variables ───────────────────────────────────────────────────────
print('→ Creating server variables...')
egg_vars_raw = mysql_val(
    f"SELECT id, env_variable, default_value FROM egg_variables WHERE egg_id={egg_id};"
).splitlines()
for row in egg_vars_raw:
    parts = row.split('\t')
    if len(parts) < 3:
        continue
    var_id, env_var, default_val = parts[0].strip(), parts[1].strip(), parts[2].strip()
    mysql(
        f"INSERT INTO server_variables "
        f"(server_id, variable_id, variable_value, created_at, updated_at) "
        f"VALUES ({srv_id}, {var_id}, '{q(default_val)}', '{NOW}', '{NOW}');"
    )
    print(f'  ✓ {env_var}={default_val}')

# ── 7. Export & summary ───────────────────────────────────────────────────────
github_env = os.environ.get('GITHUB_ENV', '')
if github_env:
    with open(github_env, 'a') as f:
        f.write(f'SERVER_UUID_SHORT={srv_uuid_short}\n')
        f.write(f'SERVER_PORT={alloc_port}\n')

print('')
print('══════════════════════════════════════════')
print(f'  ✅ Server Node.js berhasil dibuat!')
print(f'     Server ID  : {srv_id}')
print(f'     UUID Short : {srv_uuid_short}')
print(f'     Port       : {alloc_port}')
print(f'     Memory     : 512 MB | Disk: 1024 MB')
print(f'     Image      : {docker_image}')
print('══════════════════════════════════════════')
