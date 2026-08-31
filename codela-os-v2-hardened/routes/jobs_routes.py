from flask import Blueprint, jsonify, g
from database import get_db, rows_to_list
from auth import login_required, roles_required

jobs_bp = Blueprint("jobs", __name__)

@jobs_bp.route("/jobs", methods=["GET"])
@login_required
@roles_required()
def list_jobs():
    conn=get_db(); rows=conn.execute("SELECT id, job_type, status, attempts, max_attempts, run_after, started_at, finished_at, last_error, created_at FROM jobs WHERE tenant_id=? ORDER BY id DESC LIMIT 100", (g.current_user["tenant_id"],)).fetchall(); conn.close()
    return jsonify(rows_to_list(rows))
