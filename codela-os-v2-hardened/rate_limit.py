"""Distributed rate limiter with Redis in production and safe in-memory fallback for development."""
import os,time
from collections import defaultdict,deque
from threading import Lock
from urllib.parse import urlparse

class RateLimiter:
    def __init__(self):
        self.redis=None
        url=os.getenv("REDIS_URL")
        if os.getenv("CODELA_ENV") == "production":
            parsed=urlparse(url or "")
            if not parsed.password:
                raise RuntimeError("Production Redis requires authenticated REDIS_URL")
        if url:
            try:
                import redis
                self.redis=redis.Redis.from_url(url,decode_responses=True,socket_connect_timeout=2,socket_timeout=2)
                self.redis.ping()
            except Exception:
                if os.getenv("CODELA_ENV") == "production":
                    raise RuntimeError("REDIS_URL is configured but Redis is unavailable")
                self.redis=None
        if os.getenv("CODELA_ENV") == "production" and self.redis is None:
            raise RuntimeError("REDIS_URL is required for distributed production rate limiting")
        self._lock=Lock(); self._hits=defaultdict(deque)
    def allow(self,key,limit,window_seconds):
        if self.redis:
            bucket=f"codela:rl:{key}:{int(time.time()//window_seconds)}"
            try:
                pipe=self.redis.pipeline(); pipe.incr(bucket); pipe.expire(bucket,window_seconds+2); count,_=pipe.execute()
                if count>limit:
                    return False,max(1,int(window_seconds-(time.time()%window_seconds)))
                return True,0
            except Exception:
                if os.getenv("CODELA_ENV") == "production": raise
        now=time.monotonic(); cutoff=now-window_seconds
        with self._lock:
            q=self._hits[key]
            while q and q[0]<=cutoff:q.popleft()
            if len(q)>=limit:return False,max(1,int(q[0]+window_seconds-now+0.999))
            q.append(now); return True,0
    def cleanup(self,max_keys=10000):
        if self.redis:return
        now=time.monotonic()
        with self._lock:
            stale=[k for k,q in self._hits.items() if not q or q[-1]<now-3600]
            for k in stale[:max_keys]:self._hits.pop(k,None)
