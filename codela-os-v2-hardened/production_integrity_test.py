"""Dependency-light database integrity gate for Codela OS."""
import os, sqlite3, tempfile

def main():
    fd,path=tempfile.mkstemp(prefix='codela-integrity-',suffix='.db'); os.close(fd)
    os.environ['CODELA_DB_PATH']=path
    os.environ['CODELA_ENV']='testing'
    import database
    database.DB_PATH=path; database.USE_POSTGRES=False
    database.init_db(); c=database.get_db()
    v=c.execute('SELECT MAX(version) v FROM schema_migrations').fetchone()['v']; assert v==25, v
    required=['api_idempotency_keys','webhook_events','payment_intents']
    for t in required: assert c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone(), t
    # Seed two tenants/users/projects and prove cross-tenant write triggers reject.
    c.execute("INSERT INTO tenants(name,slug) VALUES ('A','a')"); a=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("INSERT INTO tenants(name,slug) VALUES ('B','b')"); b=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("INSERT INTO users(tenant_id,name,email,password_hash,role) VALUES (?,?,?,?,?)",(a,'A','a@x','x','admin')); au=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("INSERT INTO users(tenant_id,name,email,password_hash,role) VALUES (?,?,?,?,?)",(b,'B','b@x','x','admin')); bu=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("INSERT INTO clients(tenant_id,name) VALUES (?,?)",(a,'AC')); ac=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("INSERT INTO clients(tenant_id,name) VALUES (?,?)",(b,'BC')); bc=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("INSERT INTO projects(tenant_id,name,client_id) VALUES (?,?,?)",(a,'AP',ac)); ap=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("INSERT INTO projects(tenant_id,name,client_id) VALUES (?,?,?)",(b,'BP',bc)); bp=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit()
    try:
        c.execute("INSERT INTO invoices(tenant_id,client_id,project_id,invoice_number,total) VALUES (?,?,?,?,?)",(a,bc,ap,'BAD-1',10)); c.commit(); raise AssertionError('cross-tenant invoice accepted')
    except sqlite3.IntegrityError: c.rollback()
    c.close(); os.unlink(path)
    print('PASS: migration v18, idempotency/webhook/payment-intent tables, cross-tenant DB trigger gate')
if __name__=='__main__': main()
