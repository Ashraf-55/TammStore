"""Optional real HTTP E2E gate. Run in the actual Python environment after installing requirements.
Exits 0 with SKIP when Flask is unavailable, so CI can distinguish infrastructure absence from failure.
"""
import os, sys
try:
    import flask  # noqa
except Exception:
    print('SKIP: Flask is not installed; install requirements.txt and rerun runtime_e2e_test.py')
    raise SystemExit(0)
from app import create_app

def main():
    os.environ['CODELA_ENV']='testing'; os.environ['CODELA_COOKIE_AUTH']='0'
    app=create_app(); client=app.test_client()
    for path in ['/api/health','/api/ready']:
        r=client.get(path); assert r.status_code in (200,503), (path,r.status_code,r.data[:300])
    r=client.get('/api/health'); assert r.headers.get('X-Request-ID')
    print('PASS: HTTP health/readiness runtime smoke')
if __name__=='__main__': main()
