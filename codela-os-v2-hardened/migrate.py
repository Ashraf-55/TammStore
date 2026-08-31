"""Compatibility CLI for versioned migrations."""
from migrations.runner import upgrade, downgrade, CURRENT_VERSION
import sys
if __name__ == "__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "status"
    if cmd=="up": upgrade(); print(f"database upgraded to {CURRENT_VERSION}")
    elif cmd=="down": downgrade(int(sys.argv[2]) if len(sys.argv)>2 else 0)
    elif cmd=="status":
        from database import get_db
        c=get_db(); print([dict(x) for x in c.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall()]); c.close()
    else: raise SystemExit("use up|down|status")
