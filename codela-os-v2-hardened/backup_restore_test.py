"""SQLite backup/restore integrity check using Python stdlib only."""
import os,sqlite3,tempfile,shutil

def main():
    root=tempfile.mkdtemp(prefix='codela-restore-'); src=os.path.join(root,'src.db'); dst=os.path.join(root,'restore.db')
    os.environ['CODELA_DB_PATH']=src; os.environ['CODELA_ENV']='testing'
    import database
    database.DB_PATH=src; database.USE_POSTGRES=False; database.init_db(); c=database.get_db()
    c.execute("INSERT INTO tenants(name,slug) VALUES('Restore Test','restore-test')"); c.commit()
    backup=sqlite3.connect(dst); c.backup(backup); backup.close(); c.close()
    r=sqlite3.connect(dst); ok=r.execute("SELECT COUNT(*) FROM tenants WHERE slug='restore-test'").fetchone()[0]==1
    integrity=r.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; r.close(); shutil.rmtree(root)
    assert ok and integrity; print('PASS: SQLite backup/restore integrity')
if __name__=='__main__': main()
