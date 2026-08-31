import logging, os, time, uuid, secrets
from flask import Flask, jsonify, request, g, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from config import load_config, PRODUCTION
from database import init_db, get_db
from validation import before_request_validation
from rate_limit import RateLimiter
from auth import auth_bp
from routes.users_routes import users_bp
from routes.crm_routes import crm_bp
from routes.projects_routes import projects_bp
from routes.media_routes import media_bp
from routes.finance_routes import finance_bp
from routes.dashboard_routes import dashboard_bp
from routes.ai_routes import ai_bp
from routes.hr_routes import hr_bp
from routes.sop_routes import sop_bp
from routes.assets_routes import assets_bp
from routes.requests_routes import requests_bp
from routes.publish_routes import publish_bp
from routes.creator_portal_routes import creator_portal_bp
from routes.automation_routes import automation_bp
from routes.followup_routes import followup_bp
from routes.communication_routes import communication_bp
from routes.billing_routes import billing_bp
from routes.jobs_routes import jobs_bp
from routes.domain_routes import domain_bp
from routes.enterprise_routes import enterprise_bp
from routes.completion_routes import completion_bp

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger("codela")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")


def create_app():
    app = Flask(__name__)
    app.config.update(load_config())
    init_db()
    app.config["started_at"] = time.time()
    app.config["metrics"] = {"total": 0, "errors": 0, "by_status": {}}
    limiter = RateLimiter()
    app.config["rate_limiter"] = limiter
    app.config["redis"] = limiter.redis
    if app.config["TRUSTED_PROXY_COUNT"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["TRUSTED_PROXY_COUNT"], x_proto=app.config["TRUSTED_PROXY_COUNT"], x_host=app.config["TRUSTED_PROXY_COUNT"])

    @app.before_request
    def guard():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        g.started = time.monotonic()
        # Lightweight edge protection. Auth endpoints are intentionally stricter.
        if request.path.startswith("/api/"):
            ip = request.remote_addr or "unknown"
            if request.path.startswith("/api/auth/"):
                ok, retry = limiter.allow(f"auth:{ip}", int(os.getenv("CODELA_AUTH_RATE_LIMIT", "20")), int(os.getenv("CODELA_AUTH_RATE_WINDOW", "60")))
            else:
                ok, retry = limiter.allow(f"api:{ip}", int(os.getenv("CODELA_API_RATE_LIMIT", "300")), int(os.getenv("CODELA_API_RATE_WINDOW", "60")))
            if not ok:
                resp = jsonify({"error":"Too many requests","code":"rate_limited","retry_after":retry,"request_id":g.request_id})
                resp.status_code = 429
                resp.headers["Retry-After"] = str(retry)
                return resp
        for key in ("limit", "page_size", "per_page"):
            if key in request.args:
                try:
                    value = int(request.args[key])
                except ValueError:
                    return jsonify({"error": f"{key} must be an integer", "code": "validation_error", "request_id": g.request_id}), 400
                if value < 1 or value > 100:
                    return jsonify({"error": f"{key} must be between 1 and 100", "code": "pagination_limit", "request_id": g.request_id}), 400
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.path.startswith("/api/"):
            if request.content_length and request.content_length > app.config["MAX_CONTENT_LENGTH"]:
                return jsonify({"error": "Request body too large", "code": "payload_too_large", "request_id": g.request_id}), 413
            if request.method != "DELETE" and request.data and not request.is_json and request.path != "/api/health":
                return jsonify({"error": "JSON content type is required", "code": "json_required", "request_id": g.request_id}), 415
            if request.is_json:
                error = before_request_validation()
                if error:
                    body, status = error
                    body.json["request_id"] = g.request_id
                    return body, status
            cookie_auth = os.getenv("CODELA_COOKIE_AUTH", "1" if PRODUCTION else "0") == "1"
            if cookie_auth and request.cookies.get("codela_refresh") and request.path not in ("/api/auth/login", "/api/auth/register", "/api/auth/2fa/login-verify"):
                token=request.headers.get("X-CSRF-Token")
                if not token or token != request.cookies.get("codela_csrf"):
                    return jsonify({"error": "CSRF validation failed", "code": "csrf_failed", "request_id": g.request_id}), 403
        return None

    @app.after_request
    def headers(resp):
        if os.getenv("CODELA_COOKIE_AUTH", "1" if PRODUCTION else "0") == "1" and not request.cookies.get("codela_csrf"):
            resp.set_cookie("codela_csrf", secrets.token_urlsafe(32), max_age=2592000, httponly=False, secure=PRODUCTION, samesite="None" if PRODUCTION else "Lax", path="/")
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") in app.config["CORS_ORIGINS"]:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID, X-CSRF-Token"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, DELETE, OPTIONS"
            resp.headers["Access-Control-Max-Age"] = "600"
            if os.getenv("CODELA_COOKIE_AUTH", "1" if PRODUCTION else "0") == "1": resp.headers["Access-Control-Allow-Credentials"] = "true"
        elif origin and request.path.startswith("/api/"):
            resp.headers["Vary"] = "Origin"
        resp.headers["X-Request-ID"] = g.request_id
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        # Inline <script> blocks are prohibited. The legacy frontend still uses
        # a small number of inline event attributes, so they are isolated to
        # script-src-attr instead of weakening script-src for executable blocks.
        resp.headers["Content-Security-Policy"] = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self'; script-src-attr 'none'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: blob: https:; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self' https:; upgrade-insecure-requests"
        if PRODUCTION:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        metrics = app.config["metrics"]
        code = str(resp.status_code)
        rds=app.config.get("redis")
        if rds:
            pipe=rds.pipeline(); pipe.incr("codela:metrics:total"); pipe.incr(f"codela:metrics:status:{code}");
            if resp.status_code >= 500: pipe.incr("codela:metrics:errors")
            pipe.execute()
        else:
            metrics["total"] += 1; metrics["by_status"][code] = metrics["by_status"].get(code, 0) + 1
            if resp.status_code >= 500: metrics["errors"] += 1
        logger.info('{"request_id":"%s","method":"%s","path":"%s","status":%s,"duration_ms":%.1f}', g.request_id, request.method, request.path, resp.status_code, (time.monotonic() - g.started) * 1000)
        return resp

    @app.route("/api/<path:path>", methods=["OPTIONS"])
    def options(path):
        return ("", 204)

    # Serve the bundled frontend from the same origin as the API. This is the
    # only static-file service in the production Docker Compose stack (the
    # `api` container is the sole service that faces users), and it also
    # makes the frontend's relative `/api` calls work in local development
    # without needing a second `http.server` process or extra CORS config.
    @app.route("/")
    def frontend_index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/app.js")
    def frontend_app_js():
        return send_from_directory(FRONTEND_DIR, "app.js")

    for bp, prefix in [(auth_bp, "/api/auth"), (users_bp, "/api/users"), (crm_bp, "/api"), (projects_bp, "/api"), (media_bp, "/api"), (finance_bp, "/api"), (dashboard_bp, "/api"), (ai_bp, "/api"), (hr_bp, "/api"), (sop_bp, "/api"), (assets_bp, "/api"), (requests_bp, "/api"), (publish_bp, "/api"), (creator_portal_bp, "/api"), (automation_bp, "/api"), (followup_bp, "/api"), (communication_bp, "/api"), (billing_bp, "/api"), (jobs_bp, "/api"), (domain_bp, "/api"), (enterprise_bp, "/api"), (completion_bp, "/api")]:
        app.register_blueprint(bp, url_prefix=prefix)

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "system": "Codela OS API", "request_id": g.request_id})

    @app.route("/api/ready")
    def ready():
        try:
            conn = get_db(); conn.execute("SELECT 1").fetchone(); conn.close()
            if PRODUCTION:
                rds = app.config.get("redis")
                if not rds:
                    raise RuntimeError("Redis is not configured")
                rds.ping()
            return jsonify({"status": "ready", "database": "ok", "redis": "ok" if PRODUCTION else "not_required", "request_id": g.request_id})
        except Exception:
            logger.exception("readiness failure request_id=%s", g.request_id)
            return jsonify({"status": "not_ready", "error_id": g.request_id, "request_id": g.request_id}), 503

    @app.route("/api/metrics")
    def metrics():
        if PRODUCTION and request.headers.get("X-Metrics-Token") != os.getenv("CODELA_METRICS_TOKEN"):
            return jsonify({"error": "Forbidden", "request_id": g.request_id}), 403
        rds=app.config.get("redis")
        if rds:
            by_status={}
            for k in rds.scan_iter(match="codela:metrics:status:*"):
                by_status[k.rsplit(":",1)[-1]] = int(rds.get(k) or 0)
            data={"total":int(rds.get("codela:metrics:total") or 0),"errors":int(rds.get("codela:metrics:errors") or 0),"by_status":by_status}
        else: data=app.config["metrics"]
        return jsonify({"uptime_seconds": round(time.time() - app.config["started_at"], 2), **data})

    @app.errorhandler(404)
    def e404(e):
        return jsonify({"error": "Endpoint not found", "code": "not_found", "request_id": g.get("request_id")}), 404

    @app.errorhandler(413)
    def e413(e):
        return jsonify({"error": "Request body too large", "code": "payload_too_large", "request_id": g.get("request_id")}), 413

    @app.errorhandler(405)
    def e405(e):
        return jsonify({"error": "Method not allowed", "code": "method_not_allowed", "request_id": g.get("request_id")}), 405

    @app.errorhandler(400)
    def e400(e):
        return jsonify({"error": "Bad request", "code": "bad_request", "request_id": g.get("request_id")}), 400

    @app.errorhandler(500)
    def e500(e):
        logger.exception("unhandled request_id=%s", g.get("request_id"))
        return jsonify({"error": "Internal server error", "code": "internal_error", "error_id": g.get("request_id")}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=not PRODUCTION)
