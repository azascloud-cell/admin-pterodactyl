#!/usr/bin/env python3
"""
Sync admin user credentials via direct MySQL — no shell $ expansion issues.
bcrypt hash is passed as a Python string through subprocess list args,
so the $ chars in the hash never touch a shell interpreter.

Usage: python3 scripts/sync_admin.py [username] [password]
Defaults: username=admin, password=admin
"""
import subprocess, sys, uuid as uuidlib

USERNAME = sys.argv[1] if len(sys.argv) > 1 else 'admin'
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else 'admin'

def mysql(sql):
    r = subprocess.run(
        ['sudo', 'mysql', '-u', 'root', 'panel', '-e', sql],
        capture_output=True, text=True)
    if r.returncode != 0:
        print('MySQL error:', r.stderr.strip())
    return r

def mysql_se(sql):
    r = subprocess.run(
        ['sudo', 'mysql', '-u', 'root', 'panel', '-se', sql],
        capture_output=True, text=True)
    return r.stdout.strip()

# 1. Generate bcrypt hash via PHP (captured as plain Python string, no shell)
r = subprocess.run(
    ['php8.2', '-r', "echo password_hash('{}', PASSWORD_BCRYPT);".format(PASSWORD)],
    capture_output=True, text=True)
h = r.stdout.strip()
if not h.startswith('$2'):
    print('ERROR: hash generation failed:', r.stderr)
    sys.exit(1)
print('Hash generated: {}...'.format(h[:10]))

# 2. Show current users
print('Current users:')
print(mysql_se('SELECT id, username, email, root_admin FROM users;') or '(none)')

# 3. UPDATE existing user OR INSERT new one
# UPDATE any existing first user (change username + password to admin/admin)
update_sql = (
    "UPDATE users SET username='{}', password='{}', root_admin=1 "
    "WHERE 1=1 LIMIT 1;".format(USERNAME, h)
)
r3 = mysql(update_sql)
print('UPDATE result:', r3.returncode, r3.stderr.strip() or 'OK')

count = int(mysql_se('SELECT COUNT(*) FROM users;') or '0')
print('User count after update:', count)

if count == 0:
    # No users at all — INSERT fresh admin
    new_uuid = str(uuidlib.uuid4())
    insert_sql = (
        "INSERT INTO users "
        "(uuid, username, email, name_first, name_last, password, language, root_admin, use_totp, created_at, updated_at) "
        "VALUES ('{}', '{}', 'admin@pterodactyl.local', 'Admin', 'User', '{}', 'en', 1, 0, NOW(), NOW());"
        .format(new_uuid, USERNAME, h)
    )
    r5 = mysql(insert_sql)
    print('INSERT result:', r5.returncode, r5.stderr.strip() or 'OK')

# 4. Final verification
print('Final state:')
print(mysql_se("SELECT id, username, email, root_admin, LEFT(password,10) AS pwd FROM users;"))
print('✅ Done — login: {} / {}'.format(USERNAME, PASSWORD))
