from database import get_db
conn = get_db()
rows = conn.execute("SELECT id, email, role, tenant_id FROM users WHERE email='sondos@codela.com'").fetchall()
for r in rows:
    print(dict(r))
