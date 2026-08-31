import os
bind = os.getenv("BIND", "0.0.0.0:8000")
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "gthread"
threads = int(os.getenv("WEB_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
keepalive = 5
accesslog = "-"
errorlog = "-"
preload_app = False
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")
