#!/usr/bin/env python3
"""
Patch Pterodactyl routes untuk tambah /go-admin bypass route.
Pterodactyl tidak pakai routes/web.php standar Laravel,
melainkan routes/base.php sebagai entry point utama.
"""
import subprocess, sys, os

PANEL_DIR = '/var/www/pterodactyl'

# Pterodactyl pakai base.php, bukan web.php
CANDIDATES = [
    os.path.join(PANEL_DIR, 'routes', 'base.php'),
    os.path.join(PANEL_DIR, 'routes', 'web.php'),
]

TARGET = None
for c in CANDIDATES:
    if os.path.exists(c):
        TARGET = c
        break

if TARGET is None:
    # List routes dir untuk debug
    routes_dir = os.path.join(PANEL_DIR, 'routes')
    if os.path.isdir(routes_dir):
        files = os.listdir(routes_dir)
        print(f'Routes dir exists. Files: {files}')
        # Fallback: pakai file pertama yang ada
        if files:
            TARGET = os.path.join(routes_dir, files[0])
    else:
        print(f'ERROR: Routes directory {routes_dir} not found')
        sys.exit(1)

print(f'Patching: {TARGET}')

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

with open(TARGET, 'r') as f:
    content = f.read()

if '/go-admin' in content:
    print('Bypass route already exists, skipping.')
else:
    with open(TARGET, 'a') as f:
        f.write(ROUTE_CODE)
    print(f'Route appended to {TARGET}')

# Verifikasi PHP syntax
r = subprocess.run(['php8.2', '-l', TARGET], capture_output=True, text=True)
syntax = r.stdout.strip() or r.stderr.strip()
print('PHP syntax:', syntax)
if r.returncode != 0:
    print('ERROR: PHP syntax error!')
    sys.exit(1)

print('✅ Bypass route /go-admin ready')
