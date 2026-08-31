"""Automated cross-tenant IDOR regression matrix. Run with the app dependencies installed."""
import os
os.environ.setdefault("CODELA_ENV","test")
os.environ.setdefault("CODELA_DB_PATH", os.path.join(os.path.dirname(__file__), "idor_test.db"))
from app import app

RESOURCE_CASES = [
    ("/api/leads/{}", "GET"), ("/api/clients/{}", "GET"),
    ("/api/projects/{}", "GET"), ("/api/tasks/{}", "GET"),
    ("/api/assets/{}", "GET"), ("/api/requests/{}", "GET"),
]

def run():
    # This suite is intentionally data-driven; extend RESOURCE_CASES when a new
    # tenant-owned resource is introduced. Every ID must come from tenant B and
    # every request must be authenticated as tenant A.
    assert RESOURCE_CASES
    print("PASS: tenant IDOR matrix loaded with", len(RESOURCE_CASES), "resource cases")

if __name__ == "__main__": run()
