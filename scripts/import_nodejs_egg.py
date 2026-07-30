#!/usr/bin/env python3
"""
Auto-import Node.js egg ke Pterodactyl Panel via database langsung.
Dijalankan setelah migrate --seed di GitHub Actions.

Buat:
  - Nest "Node.js" (jika belum ada)
  - Egg "Node.js Generic" dengan docker image ghcr.io/pterodactyl/yolks:nodejs_22
  - Egg variables: JS_FILE, NODE_VERSION
  - Install script otomatis (npm install)
"""
import subprocess, sys, uuid as uuidlib, json
from datetime import datetime

NOW = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

def mysql(sql, db='panel'):
    r = subprocess.run(
        ['sudo', 'mysql', '-u', 'root', db, '-e', sql],
        capture_output=True, text=True)
    if r.returncode != 0:
        print('MySQL error:', r.stderr.strip())
    return r

def mysql_val(sql, db='panel'):
    r = subprocess.run(
        ['sudo', 'mysql', '-u', 'root', db, '-se', sql],
        capture_output=True, text=True)
    return r.stdout.strip()

def q(s):
    """Escape single quotes untuk SQL string."""
    return s.replace("'", "\\'")

# ── 1. Cek / buat Nest "Node.js" ─────────────────────────────────────────────
print('→ Checking nest...')
nest_id = mysql_val("SELECT id FROM nests WHERE name='Node.js' LIMIT 1;")
if not nest_id:
    nest_uuid = str(uuidlib.uuid4())
    mysql(
        f"INSERT INTO nests (uuid, author, name, description, created_at, updated_at) "
        f"VALUES ('{nest_uuid}', 'support@pterodactyl.io', 'Node.js', "
        f"'Node.js applications.', '{NOW}', '{NOW}');"
    )
    nest_id = mysql_val("SELECT id FROM nests WHERE name='Node.js' LIMIT 1;")
    print(f'  ✓ Nest "Node.js" dibuat (id={nest_id})')
else:
    print(f'  ✓ Nest "Node.js" sudah ada (id={nest_id})')

# ── 2. Cek apakah egg sudah ada ───────────────────────────────────────────────
print('→ Checking egg...')
egg_id = mysql_val(f"SELECT id FROM eggs WHERE name='Node.js Generic' AND nest_id={nest_id} LIMIT 1;")
if egg_id:
    print(f'  ✓ Egg "Node.js Generic" sudah ada (id={egg_id}) — skip')
    sys.exit(0)

# ── 3. Buat egg "Node.js Generic" ─────────────────────────────────────────────
print('→ Creating Node.js egg...')
egg_uuid  = str(uuidlib.uuid4())
docker_images = json.dumps({
    "ghcr.io/pterodactyl/yolks:nodejs_22": "Node.js 22",
    "ghcr.io/pterodactyl/yolks:nodejs_20": "Node.js 20",
    "ghcr.io/pterodactyl/yolks:nodejs_18": "Node.js 18",
    "ghcr.io/pterodactyl/yolks:nodejs_16": "Node.js 16",
})
config_startup = json.dumps({"done": "Listening on", "userInteraction": []})
config_stop    = "^C"
startup        = "if [ -f /home/container/package.json ]; then npm install; fi; node /home/container/{{JS_FILE}}"

install_script = r"""#!/bin/bash
# Install Node.js project
apt-get update -y
apt-get install -y git curl

cd /mnt/server
if [ -n "${GIT_ADDRESS}" ] && [ "${GIT_ADDRESS}" != "none" ]; then
    git clone "${GIT_ADDRESS}" .
fi
if [ -f package.json ]; then
    npm install --production
fi
echo "Node.js egg install complete."
"""

docker_images_esc = q(docker_images)
config_startup_esc = q(config_startup)
startup_esc = q(startup)
install_script_esc = q(install_script)
desc = "Generic Node.js egg. Supports Node 16/18/20/22 via yolks images."

mysql(
    f"INSERT INTO eggs "
    f"(uuid, nest_id, author, name, description, features, docker_images, "
    f"config_files, config_startup, config_logs, config_stop, startup, "
    f"script_container, script_entry, script_is_privileged, script_install, "
    f"created_at, updated_at) "
    f"VALUES ("
    f"'{egg_uuid}', {nest_id}, 'support@pterodactyl.io', 'Node.js Generic', "
    f"'{desc}', NULL, '{docker_images_esc}', "
    f"NULL, '{config_startup_esc}', NULL, '{config_stop}', "
    f"'{startup_esc}', 'ghcr.io/pterodactyl/yolks:nodejs_22', 'bash', 1, "
    f"'{install_script_esc}', '{NOW}', '{NOW}');"
)
egg_id = mysql_val(f"SELECT id FROM eggs WHERE uuid='{egg_uuid}' LIMIT 1;")
print(f'  ✓ Egg "Node.js Generic" dibuat (id={egg_id})')

# ── 4. Buat egg variables ─────────────────────────────────────────────────────
print('→ Creating egg variables...')
variables = [
    {
        "name":         "Startup File",
        "description":  "File JS yang dijalankan saat startup.",
        "env_variable": "JS_FILE",
        "default":      "index.js",
        "viewable":     1,
        "editable":     1,
        "rules":        "required|string",
    },
    {
        "name":         "Git Repository",
        "description":  "URL git repo untuk di-clone saat install (kosongkan jika tidak perlu).",
        "env_variable": "GIT_ADDRESS",
        "default":      "none",
        "viewable":     1,
        "editable":     1,
        "rules":        "nullable|string",
    },
]
for v in variables:
    mysql(
        f"INSERT INTO egg_variables "
        f"(egg_id, name, description, env_variable, default_value, "
        f"user_viewable, user_editable, rules, created_at, updated_at) "
        f"VALUES ({egg_id}, '{q(v['name'])}', '{q(v['description'])}', "
        f"'{v['env_variable']}', '{v['default']}', "
        f"{v['viewable']}, {v['editable']}, '{v['rules']}', '{NOW}', '{NOW}');"
    )
    print(f"  ✓ Variable {v['env_variable']} ditambahkan")

# ── 5. Buat default Location jika belum ada ───────────────────────────────────
print('→ Checking default location...')
loc_count = mysql_val("SELECT COUNT(*) FROM locations;")
if loc_count == '0':
    mysql(
        f"INSERT INTO locations (short, long, created_at, updated_at) "
        f"VALUES ('local', 'Default Location', '{NOW}', '{NOW}');"
    )
    print('  ✓ Default location "local" dibuat')
else:
    print(f'  ✓ Location sudah ada ({loc_count})')

# ── 6. Summary ────────────────────────────────────────────────────────────────
print('')
print('══════════════════════════════════════════')
print('  ✅ Node.js Egg berhasil diimport!')
print(f'     Nest ID : {nest_id}')
print(f'     Egg ID  : {egg_id}')
print('  Startup  : node /home/container/{{JS_FILE}}')
print('  Images   : nodejs_22 / 20 / 18 / 16')
print('══════════════════════════════════════════')
