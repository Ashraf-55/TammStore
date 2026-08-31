"""Durable background jobs with retry, exponential backoff, timeout and idempotency."""
import json,os,time,traceback,threading,uuid
try: import signal
except ImportError: signal=None
from datetime import datetime,timedelta
from database import get_db,row_to_dict,USE_POSTGRES
HANDLERS={}
def register(job_type):
 def deco(fn): HANDLERS[job_type]=fn; return fn
 return deco
def enqueue_job(job_type,payload,tenant_id=None,idempotency_key=None,max_attempts=None,run_after=None):
 c=get_db(); key=idempotency_key or None
 scope = str(tenant_id) if tenant_id is not None else "__global__"
 if key:
  r=c.execute("SELECT id FROM jobs WHERE idempotency_scope=? AND idempotency_key=?",(scope,key)).fetchone()
  if r:c.close();return r["id"]
 try:
  cur=c.execute("INSERT INTO jobs (tenant_id,job_type,payload,status,attempts,max_attempts,run_after,idempotency_scope,idempotency_key) VALUES (?,?,?,'queued',0,?,?,?,?)",(tenant_id,job_type,json.dumps(payload or {}),max_attempts or int(os.getenv('CODELA_JOB_MAX_ATTEMPTS',5)),run_after or datetime.utcnow().isoformat(timespec='seconds'),scope,key));c.commit();jid=cur.lastrowid;c.close();return jid
 except Exception:
  c.rollback()
  if key:
   r=c.execute("SELECT id FROM jobs WHERE idempotency_scope=? AND idempotency_key=?",(scope,key)).fetchone(); c.close()
   if r:return r["id"]
  c.close(); raise
def enqueue(*a,**kw): return enqueue_job(*a,**kw)
def claim_job(c):
    # Recover jobs whose worker died before completion, then atomically claim one queued job.
    stale_seconds=int(os.getenv("CODELA_JOB_LEASE_SECONDS",60))
    c.execute("""UPDATE jobs
                 SET status=CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'queued' END,
                     finished_at=CASE WHEN attempts >= max_attempts THEN datetime('now') ELSE finished_at END,
                     lease_until=NULL, lease_token=NULL
                 WHERE status='running' AND lease_until IS NOT NULL AND lease_until<=datetime('now')""")
    c.commit()
    now=datetime.utcnow().isoformat(timespec='seconds')
    lease_token=uuid.uuid4().hex
    lease_until=(datetime.utcnow()+timedelta(seconds=max(stale_seconds, int(os.getenv("CODELA_JOB_TIMEOUT_SECONDS",30))*2))).isoformat(timespec='seconds')
    if USE_POSTGRES:
        # Serialize claims at the database level. SKIP LOCKED lets multiple workers
        # pull different jobs concurrently without select/update races.
        row=c.execute("SELECT * FROM jobs WHERE status='queued' AND run_after<=? ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED",(now,)).fetchone()
        if not row:
            c.rollback(); return None
        c.execute("UPDATE jobs SET status='running',attempts=attempts+1,started_at=CURRENT_TIMESTAMP,lease_until=?,lease_token=? WHERE id=? AND status='queued'",(lease_until,lease_token,row["id"]))
    else:
        # SQLite needs a write transaction before selecting the candidate so two
        # workers cannot claim the same queued row. BEGIN IMMEDIATE serializes the
        # short claim section; the actual job executes after commit.
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT * FROM jobs WHERE status='queued' AND run_after<=? ORDER BY id LIMIT 1",(now,)).fetchone()
        if not row:
            c.rollback(); return None
        cur=c.execute("UPDATE jobs SET status='running',attempts=attempts+1,started_at=datetime('now'),lease_until=?,lease_token=? WHERE id=? AND status='queued'",(lease_until,lease_token,row["id"]))
        if cur.rowcount != 1:
            c.rollback(); return None
    c.commit(); fresh=c.execute("SELECT * FROM jobs WHERE id=?",(row["id"],)).fetchone(); return row_to_dict(fresh)
def complete_job(c,jid,lease_token):
 c.execute("UPDATE jobs SET status='succeeded',finished_at=datetime('now'),last_error=NULL,lease_until=NULL,lease_token=NULL WHERE id=? AND status='running' AND lease_token=?",(jid,lease_token));c.commit()
def fail_job(c,job,error):
 attempts=int(job["attempts"] or 0); dead=attempts>=int(job["max_attempts"] or 5); delay=min(3600,2**max(0,attempts-1)); run=(datetime.utcnow()+timedelta(seconds=delay)).isoformat(timespec='seconds');c.execute("UPDATE jobs SET status=?,run_after=?,last_error=?,finished_at=datetime('now'),lease_until=NULL,lease_token=NULL WHERE id=? AND status='running' AND lease_token=?",('dead' if dead else 'queued',run,str(error)[:4000],job["id"],job.get('lease_token')));c.commit()
def _start_heartbeat(job_id, lease_token, interval_seconds):
    stop = threading.Event()
    def beat():
        while not stop.wait(interval_seconds):
            c = None
            try:
                c = get_db()
                lease = (datetime.utcnow() + timedelta(seconds=max(interval_seconds * 3, 30))).isoformat(timespec='seconds')
                c.execute("UPDATE jobs SET lease_until=? WHERE id=? AND status='running' AND lease_token=?", (lease, job_id, lease_token))
                c.commit()
            except Exception:
                # A transient heartbeat failure must not crash the worker. The
                # execution timeout still provides an upper bound.
                pass
            finally:
                if c is not None:
                    try: c.close()
                    except Exception: pass
    t = threading.Thread(target=beat, name=f"job-heartbeat-{job_id}", daemon=True)
    t.start()
    return stop, t

def run_worker_once():
 c=get_db();job=claim_job(c);c.close()
 if not job:return False
 stop, heartbeat = _start_heartbeat(job["id"], job.get('lease_token'), max(5, int(os.getenv("CODELA_JOB_LEASE_SECONDS",60)) // 3))
 try:
  h=HANDLERS.get(job["job_type"])
  if not h:raise ValueError("unknown job type: "+job["job_type"])
  timeout=int(os.getenv("CODELA_JOB_TIMEOUT_SECONDS",30))
  if signal and hasattr(signal,"SIGALRM"):
   def alarm(_s,_f): raise TimeoutError(f"job exceeded {timeout}s timeout")
   old_alarm=signal.signal(signal.SIGALRM,alarm);signal.alarm(timeout)
   try:h(json.loads(job["payload"] or "{}"),job)
   finally:signal.alarm(0);signal.signal(signal.SIGALRM,old_alarm)
  else:h(json.loads(job["payload"] or "{}"),job)
  c=get_db();complete_job(c,job["id"],job.get('lease_token'));c.close()
 except Exception as e:
  c=get_db();fail_job(c,job,"".join(traceback.format_exception_only(type(e),e)).strip());c.close()
 finally:
  stop.set(); heartbeat.join(timeout=1)
 return True
def run_once(limit=10):
 n=0
 for _ in range(limit):
  if not run_worker_once():break
  n+=1
 return n
def worker_loop(poll_seconds=1):
 while True:
  if not run_worker_once():time.sleep(poll_seconds)
