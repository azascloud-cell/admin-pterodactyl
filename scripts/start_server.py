#!/usr/bin/env python3
"""
Auto-start server via artisan + panel client API.
Dibuat untuk dipanggil setelah Wings restart agar server langsung online.
"""
import subprocess, sys, secrets, urllib.request, json, os
from datetime import datetime

NOW = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

def mysql(sql, db='panel'):
    r = subprocess.run(['sudo', 'mysql', '-u', 'root', db, '-e', sql],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f'  MySQL error: {r.stderr.strip()}')
        sys.exit(1)
    return r

def mysql_val(sql, db='panel'):
    r = subprocess.run(['sudo', 'mysql', '-u', 'root', db, '-se', sql],
                       capture_output=True, text=True)
    return r.stdout.strip()

def bcrypt(plaintext):
    r = subprocess.run(
        ['php8.2', '-r', f"echo password_hash('{plaintext}', PASSWORD_BCRYPT);"],
        capture_output=True, text=True)
    h = r.stdout.strip()
    if not h.startswith('$2'):
        raise RuntimeError(f'bcrypt failed: {r.stderr}')
    return h

def q(s):
    return str(s).replace("'", "\\'")

def call_api(method, path, data=None, token=None):
    url = 'http://127.0.0.1' + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', 'application/json')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else {}
    except Exception as ex:
        return 0, {'error': str(ex)}

# ── 1. Get server info ────────────────────────────────────────────────────────
print('Mencari server...')
srv_uuid = mysql_val("SELECT uuid FROM servers ORDER BY id DESC LIMIT 1;")
if not srv_uuid:
    print('  Tidak ada server — skip')
    sys.exit(0)

# Cari uuidShort (kolom name bisa camelCase atau snake_case)
srv_uuid_short = (
    mysql_val("SELECT uuidShort FROM servers ORDER BY id DESC LIMIT 1;") or
    mysql_val("SELECT uuid_short FROM servers ORDER BY id DESC LIMIT 1;") or
    srv_uuid.replace('-', '')[:8]
)
print(f'  UUID: {srv_uuid}  short: {srv_uuid_short}')

# ── 2. Coba artisan p:server:bulk-power dulu ──────────────────────────────────
print('Mencoba artisan bulk-power start...')
for flag in [f'--servers={srv_uuid}', f'--server={srv_uuid}']:
    r = subprocess.run(
        ['sudo', 'php', 'artisan', 'p:server:bulk-power', 'start', flag],
        capture_output=True, text=True, cwd='/var/www/pterodactyl')
    print(f'  artisan {flag}: exit={r.returncode}')
    if r.stdout.strip():
        print(' ', r.stdout.strip()[-400:])
    if r.returncode == 0:
        print('  Artisan berhasil!')
        break

# ── 3. Fallback: client API dengan temp key ───────────────────────────────────
print('Mencoba client API...')
user_id = mysql_val("SELECT id FROM users WHERE root_admin=1 LIMIT 1;")
identifier = secrets.token_hex(8)
token_plain = secrets.token_hex(32)
identifier_ref = [identifier]  # mutable ref for finally

try:
    token_hashed = bcrypt(token_plain)
    full_key = identifier + token_plain

    api_cols = set(mysql_val(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='panel' AND TABLE_NAME='api_keys';"
    ).splitlines())

    if 'key_type' in api_cols:
        mysql(
            f"INSERT INTO api_keys "
            f"(user_id, key_type, identifier, token, memo, allowed_ips, created_at, updated_at) "
            f"VALUES ({user_id}, 1, '{identifier}', '{q(token_hashed)}', "
            f"'ci-autostart', '[]', '{NOW}', '{NOW}');"
        )
    else:
        mysql(
            f"INSERT INTO api_keys "
            f"(user_id, identifier, token, memo, allowed_ips, created_at, updated_at) "
            f"VALUES ({user_id}, '{identifier}', '{q(token_hashed)}', "
            f"'ci-autostart', '[]', '{NOW}', '{NOW}');"
        )

    # Flush cache
    subprocess.run(['sudo', 'php', 'artisan', 'cache:clear', '-q'],
                   capture_output=True, cwd='/var/www/pterodactyl')

    for uuid_try in [srv_uuid_short, srv_uuid]:
        status, resp = call_api(
            'POST', f'/api/client/servers/{uuid_try}/power',
            data={'signal': 'start'}, token=full_key)
        print(f'  Client API /power ({uuid_try[:8]}): HTTP {status}')
        if status in [200, 201, 204]:
            print('  Berhasil lewat client API!')
            break
    else:
        print('  Client API tidak berhasil — Wings mungkin perlu beberapa saat')

finally:
    subprocess.run(
        ['sudo', 'mysql', '-u', 'root', 'panel', '-e',
         f"DELETE FROM api_keys WHERE identifier='{identifier_ref[0]}';"],
        capture_output=True)

print('')
print('Selesai — server sedang booting. Tunggu 30-60 detik lalu cek Console.')
