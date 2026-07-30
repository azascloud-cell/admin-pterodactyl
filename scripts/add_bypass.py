#!/usr/bin/env python3
"""
Patch /var/www/pterodactyl/routes/web.php to add /go-admin bypass route.
Auto-login admin user tanpa password — langsung masuk admin panel.
"""
import subprocess, sys

WEB_PHP = '/var/www/pterodactyl/routes/web.php'

ROUTE_CODE = """

// ── Auto-login bypass route (added by CI) ──────────────────────
Route::get('/go-admin', function () {
    $user = \\App\\Models\\User::where('root_admin', 1)->first();
    if (!$user) {
        return response('No admin user found in database.', 500);
    }
    \\Illuminate\\Support\\Facades\\Auth::login($user, true);
    return redirect('/admin');
});
// ───────────────────────────────────────────────────────────────
"""

# Baca file yang sudah ada
try:
    with open(WEB_PHP, 'r') as f:
        content = f.read()
except FileNotFoundError:
    print(f'ERROR: {WEB_PHP} not found')
    sys.exit(1)

if '/go-admin' in content:
    print('Bypass route already exists, skipping.')
else:
    with open(WEB_PHP, 'a') as f:
        f.write(ROUTE_CODE)
    print('Route appended to web.php')

# Verifikasi PHP syntax
r = subprocess.run(['php8.2', '-l', WEB_PHP], capture_output=True, text=True)
syntax = r.stdout.strip() or r.stderr.strip()
print('PHP syntax:', syntax)
if r.returncode != 0:
    print('ERROR: PHP syntax error in web.php!')
    sys.exit(1)

print('✅ Bypass route /go-admin ready')
