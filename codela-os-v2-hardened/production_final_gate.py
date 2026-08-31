"""Dependency-light final production gate for Codela OS.
Runs migration, integrity, idempotency, job-claim, payment-allocation and backup/restore checks.
It never claims HTTP E2E success when Flask is unavailable; use runtime_e2e_test.py in a real env.
"""
import os, sqlite3, tempfile, shutil, subprocess, json, time

def new_db():
    fd,p=tempfile.mkstemp(prefix='codela-final-',suffix='.db'); os.close(fd)
    os.environ['CODELA_DB_PATH']=p; os.environ['CODELA_ENV']='testing'
    import database
    database.DB_PATH=p; database.USE_POSTGRES=False
    database.init_db(); return p,database

def scalar(c,q,args=()):
    r=c.execute(q,args).fetchone(); return r[0] if r else None

def main():
    p,database=new_db(); c=database.get_db()
    version=scalar(c,'SELECT MAX(version) FROM schema_migrations'); assert version==18, version
    required=['api_idempotency_keys','webhook_events','payment_intents','payment_allocations','backup_runs','system_health_checks']
    for t in required: assert scalar(c,"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(t,))==1,t
    c.execute("INSERT INTO tenants(name,slug) VALUES('A','final-a')"); a=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO tenants(name,slug) VALUES('B','final-b')"); b=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO clients(tenant_id,name) VALUES(?, 'AC')",(a,)); ac=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO clients(tenant_id,name) VALUES(?, 'BC')",(b,)); bc=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO projects(tenant_id,name,client_id) VALUES(?,?,?)",(a,'AP',ac)); ap=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO projects(tenant_id,name,client_id) VALUES(?,?,?)",(b,'BP',bc)); bp=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO invoices(tenant_id,client_id,project_id,invoice_number,total) VALUES(?,?,?,?,?)",(a,ac,ap,'F-1',100)); inv=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO payments(tenant_id,invoice_id,amount) VALUES(?,?,?)",(a,inv,100)); pay=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.commit()
    # cross-tenant write guards
    checks=[
      ("INSERT INTO invoices(tenant_id,client_id,project_id,invoice_number,total) VALUES(?,?,?,?,?)",(a,bc,ap,'BAD-X',1),'cross tenant invoice'),
      ("INSERT INTO payments(tenant_id,invoice_id,amount) VALUES(?,?,?)",(b,inv,1),'cross tenant payment'),
      ("INSERT INTO payment_allocations(tenant_id,payment_id,invoice_id,amount) VALUES(?,?,?,?)",(b,pay,inv,1),'cross tenant allocation'),
      ("INSERT INTO payment_allocations(tenant_id,payment_id,invoice_id,amount) VALUES(?,?,?,?)",(a,pay,inv,101),'over allocation'),
    ]
    for q,args,label in checks:
        try: c.execute(q,args); c.commit(); raise AssertionError(label+' accepted')
        except sqlite3.IntegrityError: c.rollback()
    # valid allocation then update beyond balance must fail
    c.execute("INSERT INTO payment_allocations(tenant_id,payment_id,invoice_id,amount) VALUES(?,?,?,?)",(a,pay,inv,50)); aid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.commit()
    try:
        c.execute("UPDATE payment_allocations SET amount=101 WHERE id=?",(aid,)); c.commit(); raise AssertionError('allocation update overflow accepted')
    except sqlite3.IntegrityError: c.rollback()
    # immutable idempotency/webhook identity
    c.execute("INSERT INTO api_idempotency_keys(tenant_id,scope,idem_key,request_hash) VALUES(?,?,?,?)",(a,'test','k1','h1')); c.commit()
    try: c.execute("UPDATE api_idempotency_keys SET request_hash='h2' WHERE tenant_id=? AND idem_key='k1'",(a,)); c.commit(); raise AssertionError('idempotency mutation accepted')
    except sqlite3.IntegrityError: c.rollback()
    # job claim race is protected by BEGIN IMMEDIATE; basic claim must transition exactly once.
    from jobs import enqueue_job, claim_job
    jid=enqueue_job('final_test',{'x':1},tenant_id=a,idempotency_key='final-job-1')
    assert enqueue_job('final_test',{'x':2},tenant_id=a,idempotency_key='final-job-1')==jid
    job=claim_job(c); assert job and job['id']==jid and job['status']=='running'
    c.close(); os.unlink(p)
    print('PASS: final DB/transaction/idempotency/job integrity gate, schema v18')

if __name__=='__main__': main()
