"""Dependency-free checks for production wiring; does not start the Flask app."""
import os
from config import load_config


def main():
    os.environ.setdefault("CODELA_ENV", "development")
    cfg = load_config()
    assert cfg["MAX_CONTENT_LENGTH"] > 0
    assert cfg["JOB_MAX_ATTEMPTS"] >= 1
    assert cfg["CORS_ORIGINS"]
    if os.getenv("CODELA_ENV") == "production":
        required=("CODELA_SECRET_KEY","CODELA_ENCRYPTION_KEY","REDIS_URL","REDIS_PASSWORD","DATABASE_URL")
        missing=[k for k in required if not os.getenv(k)]
        assert not missing, "Missing production secrets: " + ", ".join(missing)
        from urllib.parse import urlparse
        dbp=urlparse(os.environ["DATABASE_URL"]); assert dbp.scheme in {"postgres","postgresql"}, "Production DATABASE_URL must be PostgreSQL"
        rp=urlparse(os.environ["REDIS_URL"]); assert rp.scheme in {"redis","rediss"} and rp.password, "Production REDIS_URL must include authentication"
        from database import get_db
        c=get_db(); rows=c.execute("SELECT id, access_token FROM platform_connections WHERE access_token IS NOT NULL AND access_token != ''").fetchall(); c.close()
        assert all(str(r["access_token"]).startswith("enc:v1:") for r in rows), "Plaintext integration secret detected"
    print("PASS: production configuration primitives")


if __name__ == "__main__":
    main()
