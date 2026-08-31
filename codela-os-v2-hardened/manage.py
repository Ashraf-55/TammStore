import argparse
from migrations.runner import upgrade,downgrade,CURRENT_VERSION
from database import get_db
p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True); s.add_parser("migrate"); d=s.add_parser("downgrade"); d.add_argument("--to",type=int,default=0); s.add_parser("version"); a=p.parse_args()
if a.cmd=="migrate": upgrade(); print("database upgraded to",CURRENT_VERSION)
elif a.cmd=="downgrade": downgrade(a.to); print("database downgraded to",a.to)
else:
 c=get_db(); print([dict(x) for x in c.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall()]); c.close()
