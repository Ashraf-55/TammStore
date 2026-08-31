"""Concurrency-oriented finance guard checks. Full PostgreSQL concurrency belongs in staging."""
import os,tempfile,sqlite3

def main():
    fd,p=tempfile.mkstemp(prefix='codela-conc-',suffix='.db'); os.close(fd)
    os.environ['CODELA_DB_PATH']=p; os.environ['CODELA_ENV']='testing'
    import database
    database.DB_PATH=p; database.USE_POSTGRES=False; database.init_db(); c=database.get_db()
    c.execute("INSERT INTO tenants(name,slug) VALUES('C','conc')"); t=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO clients(tenant_id,name) VALUES(?, 'C')",(t,)); cl=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO invoices(tenant_id,client_id,invoice_number,total) VALUES(?,?,?,100)",(t,cl,'C-1')); inv=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute("INSERT INTO payments(tenant_id,invoice_id,amount) VALUES(?,?,100)",(t,inv)); pay=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.commit()
    try:
        c.execute("INSERT INTO payment_allocations(tenant_id,payment_id,invoice_id,amount) VALUES(?,?,?,60)",(t,pay,inv)); c.commit()
        try:
            c.execute("INSERT INTO payment_allocations(tenant_id,payment_id,invoice_id,amount) VALUES(?,?,?,50)",(t,pay,inv)); c.commit(); raise AssertionError('over-allocation accepted')
        except sqlite3.IntegrityError: c.rollback()
    finally:
        c.close(); os.unlink(p)
    print('PASS: allocation balance guard; PostgreSQL multi-session concurrency must run in staging')
if __name__=='__main__': main()
