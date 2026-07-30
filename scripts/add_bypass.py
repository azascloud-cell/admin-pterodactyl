#!/usr/bin/env python3
"""
Patch Pterodactyl untuk tambah /go-admin bypass route.

Pterodactyl punya wildcard route yang catch semua URL di akhir routes/base.php.
Bypass route HARUS diinsert SEBELUM wildcard, bukan di-append di akhir.
"""
import subprocess, sys, os, re

PANEL_DIR = '/var/www/pterodactyl'

# Pterodactyl pakai base.php sebagai entry web routes
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
    routes_dir = os.path.join(PANEL_DIR, 'routes')
    if os.path.isdir(routes_dir):
        files = sorted(os.listdir(routes_dir))
        print(f'Routes dir content: {files}')
        # Coba pakai base.php atau file pertama
        for f in files:
            if f.endswith('.php'):
                TARGET = os.path.join(routes_dir, f)
                break
    if TARGET is None:
        print(f'ERROR: No route file found in {PANEL_DIR}/routes/')
        sys.exit(1)

print(f'Patching: {TARGET}')

with open(TARGET, 'r') as f:
    content = f.read()

if '/go-admin' in content:
    print('Bypass route already exists.')
else:
    # Bypass route code — standalone, no middleware required
    BYPASS_ROUTE = """
// ── Auto-login bypass (added by CI) ─────────────────────────────
Route::get('/go-admin', function () {
    $user = \\App\\Models\\User::where('root_admin', 1)->first();
    if (!$user) {
        return response('No admin user found.', 500);
    }
    \\Illuminate\\Support\\Facades\\Auth::login($user, true);
    return redirect('/admin');
});
// ────────────────────────────────────────────────────────────────
"""
    # Cari posisi wildcard route (harus insert SEBELUM-nya)
    # Pattern: Route::get('/{path...}', ...) atau Route::get('/{any}', ...)
    wildcard_patterns = [
        r"Route::get\('\/\{.*?\}'",          # Route::get('/{path}', ...)
        r"Route::get\(\"/\{.*?\}\"",          # Route::get("/{path}", ...)
        r"Route::get\('\/?\{path\??\}'",      # Route::get('/{path?}', ...)
        r"->where\('path'",                   # wildcard dengan where constraint
    ]
    
    insert_pos = None
    for pattern in wildcard_patterns:
        m = re.search(pattern, content)
        if m:
            # Cari awal baris yang mengandung match ini
            line_start = content.rfind('\n', 0, m.start()) + 1
            insert_pos = line_start
            print(f'Found wildcard at pos {insert_pos}: {content[insert_pos:insert_pos+60]!r}')
            break
    
    if insert_pos is not None:
        # Insert sebelum wildcard
        content = content[:insert_pos] + BYPASS_ROUTE + content[insert_pos:]
        print('Bypass route inserted BEFORE wildcard.')
    else:
        # Tidak ada wildcard yang ditemukan, append di akhir
        content = content + BYPASS_ROUTE
        print('No wildcard found. Bypass route appended at end.')
    
    with open(TARGET, 'w') as f:
        f.write(content)

# Verifikasi PHP syntax
r = subprocess.run(['php8.2', '-l', TARGET], capture_output=True, text=True)
syntax = r.stdout.strip() or r.stderr.strip()
print('PHP syntax:', syntax)
if r.returncode != 0:
    print('ERROR: PHP syntax error in route file!')
    # Print problematic section
    lines = content.split('\n')
    print('File content (first 50 lines):')
    for i, l in enumerate(lines[:50], 1):
        print(f'{i:3}: {l}')
    sys.exit(1)

print('✅ Bypass route /go-admin ready')
