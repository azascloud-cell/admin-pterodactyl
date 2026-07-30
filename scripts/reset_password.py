#!/usr/bin/env python3
"""
Force-reset admin password via Laravel's artisan tinker.
Pakai Hash::make() bawaan Pterodactyl agar kompatibel 100%.
Juga disable 2FA (use_totp=0) agar login langsung bisa.

Usage: python3 scripts/reset_password.py [password]
Default password: admin
"""
import subprocess, sys, os

PASSWORD = sys.argv[1] if len(sys.argv) > 1 else 'admin'
PANEL_DIR = '/var/www/pterodactyl'

# PHP code untuk artisan tinker (satu baris, aman)
# Pterodactyl pakai namespace Pterodactyl\Models\User, bukan App\Models\User
php_code = (
    "$p='{pass}';"
    "\\Pterodactyl\\Models\\User::where('root_admin',1)->update("
    "['password'=>\\Illuminate\\Support\\Facades\\Hash::make($p),'use_totp'=>0]);"
    "$u=\\Pterodactyl\\Models\\User::where('root_admin',1)->first();"
    "echo 'LOGIN => user:'.$u->username.' | email:'.$u->email.' | pass:'.$p;"
).replace('{pass}', PASSWORD)

print(f'Resetting admin password via artisan tinker...')
r = subprocess.run(
    ['sudo', 'php', 'artisan', 'tinker', '--execute', php_code],
    capture_output=True, text=True, cwd=PANEL_DIR
)

output = (r.stdout + r.stderr).strip()
print('Tinker output:', output)

if r.returncode != 0:
    print('WARNING: artisan tinker failed. Trying direct SQL fallback...')
    # Fallback: generate hash via PHP dan update langsung ke DB
    hash_r = subprocess.run(
        ['php8.2', '-r', f"echo password_hash('{PASSWORD}', PASSWORD_BCRYPT);"],
        capture_output=True, text=True
    )
    h = hash_r.stdout.strip()
    if h.startswith('$2'):
        sql = f"UPDATE users SET password='{h}', use_totp=0 WHERE root_admin=1;"
        subprocess.run(
            ['sudo', 'mysql', '-u', 'root', 'panel', '-e', sql],
            capture_output=True, text=True
        )
        print(f'Fallback: SQL UPDATE done with hash {h[:10]}...')
    else:
        print('ERROR: hash generation also failed')
        sys.exit(1)

# Verify final state
r2 = subprocess.run(
    ['sudo', 'mysql', '-u', 'root', 'panel', '-se',
     'SELECT username, email, LEFT(password,7), use_totp FROM users WHERE root_admin=1 LIMIT 1;'],
    capture_output=True, text=True
)
print('Final DB state:', r2.stdout.strip())
print(f'✅ Password reset complete. Login: (see username above) / {PASSWORD}')
