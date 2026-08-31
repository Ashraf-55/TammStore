"""Dependency-free regression checks for security architecture.
Run: python hardening_static_test.py
"""
from pathlib import Path
ROOT=Path(__file__).parent

def main():
    route_text='\n'.join(p.read_text(encoding='utf8') for p in (ROOT/'routes').glob('*.py'))
    assert 'tenant_id=?' in route_text
    assert 'CORS_ORIGINS' in (ROOT/'config.py').read_text()
    assert 'Strict-Transport-Security' in (ROOT/'app.py').read_text()
    assert 'Content-Security-Policy' in (ROOT/'app.py').read_text()
    assert 'X-Content-Type-Options' in (ROOT/'app.py').read_text()
    assert 'Permissions-Policy' in (ROOT/'app.py').read_text()
    assert 'schema_migrations' in (ROOT/'migrations'/'runner.py').read_text()
    assert 'max_attempts' in (ROOT/'jobs.py').read_text() and 'idempotency_key' in (ROOT/'jobs.py').read_text()
    assert 'request_id' in (ROOT/'audit.py').read_text() and 'REDACTED' in (ROOT/'audit.py').read_text()
    frontend=(ROOT/'frontend'/'index.html').read_text() + '\n' + (ROOT/'frontend'/'app.js').read_text()
    assert 'function esc' in frontend and 'async function apiRaw' in frontend
    assert 'el.textContent = t(key);' in frontend
    app=(ROOT/'app.py').read_text()
    assert "script-src-attr 'none'" in app
    assert "localStorage.getItem('codela_api_url')" not in frontend
    assert "localStorage.setItem('codela_user'" not in frontend
    jobs=(ROOT/'jobs.py').read_text()
    assert 'lease_token' in jobs and 'AND lease_token=?' in jobs
    # The static scan is intentionally advisory for dynamic SQL; the executable
    # security regression suite is the authoritative IDOR test.
    print('PASS: static hardening checks')

if __name__=='__main__': main()
