import os
from urllib.parse import urlparse
PRODUCTION=os.getenv("CODELA_ENV",os.getenv("FLASK_ENV","development")).lower()=="production"
def load_config():
    secret=os.getenv("CODELA_SECRET_KEY") or ("dev-only-change-me" if not PRODUCTION else None)
    if PRODUCTION and (not secret or len(secret)<32 or secret.lower() in {"change-me","dev-only-change-me","dev-secret-change-in-production"}): raise RuntimeError("CODELA_SECRET_KEY must be a strong 32+ character secret in production")
    origins={x.strip().rstrip("/") for x in os.getenv("CODELA_CORS_ORIGINS","http://localhost:5000,http://127.0.0.1:5000").split(",") if x.strip()}
    for o in origins:
        p=urlparse(o)
        if p.scheme not in {"http","https"} or not p.netloc: raise RuntimeError(f"Invalid CORS origin: {o}")
        if PRODUCTION and p.scheme!="https": raise RuntimeError(f"Production CORS origins must use HTTPS: {o}")
    prev=os.getenv("CODELA_SECRET_KEY_PREVIOUS")
    if PRODUCTION and prev and len(prev)<32: raise RuntimeError("CODELA_SECRET_KEY_PREVIOUS must be 32+ characters")
    if PRODUCTION and not os.getenv("REDIS_URL"): raise RuntimeError("REDIS_URL is required in production")
    if PRODUCTION:
        db_url=os.getenv("DATABASE_URL","")
        if not db_url.lower().startswith(("postgres://","postgresql://")):
            raise RuntimeError("DATABASE_URL must be PostgreSQL in production; SQLite is not allowed")
        redis_url=os.getenv("REDIS_URL","")
        parsed_redis=urlparse(redis_url)
        if parsed_redis.scheme not in {"redis","rediss"} or not parsed_redis.hostname:
            raise RuntimeError("REDIS_URL must be a valid redis:// or rediss:// URL in production")
        if not parsed_redis.password:
            raise RuntimeError("REDIS_URL must include Redis authentication in production")
    if PRODUCTION and not os.getenv("CODELA_ENCRYPTION_KEY"): raise RuntimeError("CODELA_ENCRYPTION_KEY is required in production")
    if PRODUCTION and not os.getenv("CODELA_PLATFORM_ADMIN_EMAILS"): raise RuntimeError("CODELA_PLATFORM_ADMIN_EMAILS is required in production")
    return {"SECRET_KEY":secret,"SECRET_KEYS":[k for k in (secret,prev) if k],"CORS_ORIGINS":origins,"MAX_CONTENT_LENGTH":int(os.getenv("CODELA_MAX_BODY_BYTES",2097152)),"TRUSTED_PROXY_COUNT":int(os.getenv("CODELA_TRUSTED_PROXY_COUNT",0)),"JOB_MAX_ATTEMPTS":int(os.getenv("CODELA_JOB_MAX_ATTEMPTS",5)),"AUTH_RATE_LIMIT":int(os.getenv("CODELA_AUTH_RATE_LIMIT",20)),"API_RATE_LIMIT":int(os.getenv("CODELA_API_RATE_LIMIT",300)),"REDIS_URL":os.getenv("REDIS_URL"),"ENCRYPTION_KEY":os.getenv("CODELA_ENCRYPTION_KEY"),"PLATFORM_ADMIN_EMAILS":{e.strip().lower() for e in os.getenv("CODELA_PLATFORM_ADMIN_EMAILS","").split(",") if e.strip()}}
