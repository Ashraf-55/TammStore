import uuid
import math
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, pagination_params
from auth import login_required, roles_required, log_action
from automation import fire_event
from policies.permissions import has_permission

hr_bp = Blueprint("hr", __name__)

MANAGER_ROLES = ("founder", "admin", "sales_manager", "project_manager", "content_manager")


def _is_manager(user):
    return user.get("role") in MANAGER_ROLES or has_permission(user, "attendance.manage")


def haversine_m(lat1, lng1, lat2, lng2):
    """Distance in meters between two lat/lng points."""
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------- COMPANY / OFFICE LOCATION SETTINGS ----------------

@hr_bp.route("/company/settings", methods=["GET"])
@login_required
def get_company_settings():
    conn = get_db()
    tenant = conn.execute(
        "SELECT id, name, slug, office_lat, office_lng, office_radius_m FROM tenants WHERE id=?",
        (g.current_user["tenant_id"],),
    ).fetchone()
    conn.close()
    return jsonify(row_to_dict(tenant))


@hr_bp.route("/company/settings", methods=["PATCH"])
@login_required
@roles_required()
def update_company_settings():
    data = request.get_json(force=True) or {}
    fields, values = [], []
    for key in ("office_lat", "office_lng", "office_radius_m"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    values.append(g.current_user["tenant_id"])
    conn = get_db()
    conn.execute(f"UPDATE tenants SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    row = conn.execute("SELECT id, name, slug, office_lat, office_lng, office_radius_m FROM tenants WHERE id=?",
                        (g.current_user["tenant_id"],)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "company_settings", g.current_user["tenant_id"])
    return jsonify(row_to_dict(row))


# ---------------- ATTENDANCE (with anti-fraud checks) ----------------

@hr_bp.route("/attendance/check-in", methods=["POST"])
@login_required
def check_in():
    tenant_id = g.current_user["tenant_id"]
    data = request.get_json(force=True) or {}
    lat, lng = data.get("latitude"), data.get("longitude")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM attendance WHERE user_id=? AND tenant_id=? AND date=date('now')", (g.current_user["user_id"], tenant_id)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Already checked in today"}), 409

    tenant = conn.execute("SELECT office_lat, office_lng, office_radius_m FROM tenants WHERE id=?", (tenant_id,)).fetchone()

    distance_m = None
    is_flagged = 0
    flag_reasons = []

    if lat is None or lng is None:
        # Location wasn't provided (denied permission, or non-browser client) — flag for manager review
        is_flagged = 1
        flag_reasons.append("no_location_provided")
    elif tenant["office_lat"] is not None and tenant["office_lng"] is not None:
        distance_m = round(haversine_m(tenant["office_lat"], tenant["office_lng"], lat, lng))
        if distance_m > (tenant["office_radius_m"] or 200):
            is_flagged = 1
            flag_reasons.append(f"outside_geofence_{distance_m}m")

    # Same IP used by a different user checking in today is suspicious (possible buddy punching)
    if ip:
        ip_collision = conn.execute(
            "SELECT user_id FROM attendance WHERE tenant_id=? AND date=date('now') AND check_in_ip=? AND user_id!=?",
            (tenant_id, ip, g.current_user["user_id"]),
        ).fetchone()
        if ip_collision:
            is_flagged = 1
            flag_reasons.append("shared_ip_with_another_checkin_today")

    conn.execute(
        """INSERT INTO attendance (tenant_id, user_id, date, check_in, status, check_in_ip, check_in_lat, check_in_lng,
           check_in_distance_m, is_flagged, flag_reason)
           VALUES (?, ?, date('now'), time('now'), 'present', ?, ?, ?, ?, ?, ?)""",
        (tenant_id, g.current_user["user_id"], ip, lat, lng, distance_m, is_flagged, ",".join(flag_reasons) or None),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM attendance WHERE user_id=? AND tenant_id=? AND date=date('now')", (g.current_user["user_id"], tenant_id)
    ).fetchone()
    conn.close()
    attendance_dict = row_to_dict(row)
    if is_flagged:
        log_action(g.current_user["user_id"], "flagged_check_in", "attendance", row["id"], details=",".join(flag_reasons))
        fire_event("attendance.flagged", tenant_id, {"attendance": attendance_dict})
    return jsonify(attendance_dict), 201


@hr_bp.route("/attendance/check-out", methods=["POST"])
@login_required
def check_out():
    tenant_id = g.current_user["tenant_id"]
    data = request.get_json(force=True) or {}
    lat, lng = data.get("latitude"), data.get("longitude")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    conn = get_db()
    conn.execute(
        "UPDATE attendance SET check_out = time('now'), check_out_ip=?, check_out_lat=?, check_out_lng=? WHERE user_id=? AND tenant_id=? AND date=date('now')",
        (ip, lat, lng, g.current_user["user_id"], tenant_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM attendance WHERE user_id=? AND tenant_id=? AND date=date('now')", (g.current_user["user_id"], tenant_id)
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "No check-in found for today"}), 404
    return jsonify(row_to_dict(row))


@hr_bp.route("/attendance", methods=["GET"])
@login_required
def list_attendance():
    tenant_id = g.current_user["tenant_id"]
    user_id = request.args.get("user_id", g.current_user["user_id"])
    if str(user_id) != str(g.current_user["user_id"]) and not _is_manager(g.current_user):
        return jsonify({"error": "Permission denied"}), 403
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    conn = get_db()
    query = "SELECT * FROM attendance WHERE user_id=? AND tenant_id=?"
    params = [user_id, tenant_id]
    if date_from:
        query += " AND date >= ?"; params.append(date_from)
    if date_to:
        query += " AND date <= ?"; params.append(date_to)
    query += " ORDER BY date DESC"
    limit, offset = pagination_params(request)
    query += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@hr_bp.route("/attendance/team", methods=["GET"])
@login_required
@roles_required(*MANAGER_ROLES)
def team_attendance():
    """Manager view: everyone's attendance, with a filter for flagged-only records."""
    tenant_id = g.current_user["tenant_id"]
    flagged_only = request.args.get("flagged") == "true"
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    conn = get_db()
    query = """SELECT a.*, u.name AS user_name, u.role FROM attendance a
               JOIN users u ON u.id = a.user_id WHERE a.tenant_id=?"""
    params = [tenant_id]
    if flagged_only:
        query += " AND a.is_flagged = 1"
    if date_from:
        query += " AND a.date >= ?"; params.append(date_from)
    if date_to:
        query += " AND a.date <= ?"; params.append(date_to)
    query += " ORDER BY a.date DESC, a.is_flagged DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@hr_bp.route("/attendance/<int:attendance_id>/clear-flag", methods=["PATCH"])
@login_required
def clear_attendance_flag(attendance_id):
    if not _is_manager(g.current_user):
        return jsonify({"error": "Permission denied"}), 403
    conn = get_db()
    conn.execute("UPDATE attendance SET is_flagged=0 WHERE id=? AND tenant_id=?", (attendance_id, g.current_user["tenant_id"]))
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "clear_flag", "attendance", attendance_id)
    return jsonify({"message": "Flag cleared"})


# ---------------- COURSES (ACADEMY) ----------------

@hr_bp.route("/courses", methods=["GET"])
@login_required
def list_courses():
    conn = get_db()
    limit, offset = pagination_params(request)
    rows = conn.execute("SELECT * FROM courses WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (g.current_user["tenant_id"], limit, offset)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@hr_bp.route("/courses", methods=["POST"])
@login_required
@roles_required("content_manager", "project_manager")
def create_course():
    data = request.get_json(force=True) or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO courses (tenant_id, title, description, weeks) VALUES (?,?,?,?)",
        (g.current_user["tenant_id"], data["title"], data.get("description"), data.get("weeks", 1)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM courses WHERE id=? AND tenant_id=?", (cur.lastrowid, g.current_user["tenant_id"])).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@hr_bp.route("/courses/<int:course_id>", methods=["GET"])
@login_required
def get_course(course_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    course = conn.execute("SELECT * FROM courses WHERE id=? AND tenant_id=?", (course_id, tenant_id)).fetchone()
    if course is None:
        conn.close()
        return jsonify({"error": "Course not found"}), 404
    lessons = conn.execute("SELECT * FROM lessons WHERE course_id=? ORDER BY order_index", (course_id,)).fetchall()
    conn.close()
    result = row_to_dict(course)
    result["lessons"] = rows_to_list(lessons)
    return jsonify(result)


@hr_bp.route("/courses/<int:course_id>/lessons", methods=["POST"])
@login_required
@roles_required("content_manager", "project_manager")
def add_lesson(course_id):
    data = request.get_json(force=True) or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    conn = get_db()
    course = conn.execute("SELECT id FROM courses WHERE id=? AND tenant_id=?", (course_id, g.current_user["tenant_id"])).fetchone()
    if course is None:
        conn.close()
        return jsonify({"error": "Course not found"}), 404
    cur = conn.execute(
        "INSERT INTO lessons (course_id, title, order_index, content) VALUES (?,?,?,?)",
        (course_id, data["title"], data.get("order_index", 0), data.get("content")),
    )
    conn.commit()
    row = conn.execute("SELECT l.* FROM lessons l JOIN courses c ON c.id=l.course_id WHERE l.id=? AND c.tenant_id=?", (cur.lastrowid, g.current_user["tenant_id"])).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@hr_bp.route("/courses/<int:course_id>/enroll", methods=["POST"])
@login_required
def enroll(course_id):
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id", g.current_user["user_id"])
    tenant_id = g.current_user["tenant_id"]
    if str(user_id) != str(g.current_user["user_id"]) and not has_permission(g.current_user, "employees.manage"):
        return jsonify({"error": "Permission denied"}), 403
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO enrollments (tenant_id, course_id, user_id) VALUES (?,?,?)", (tenant_id, course_id, user_id)
        )
        conn.commit()
    except Exception:
        conn.close()
        return jsonify({"error": "Already enrolled"}), 409
    row = conn.execute("SELECT * FROM enrollments WHERE id=? AND tenant_id=?", (cur.lastrowid, g.current_user["tenant_id"])).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@hr_bp.route("/enrollments/<int:enrollment_id>/lessons/<int:lesson_id>/complete", methods=["POST"])
@login_required
def complete_lesson(enrollment_id, lesson_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    enrollment = conn.execute("SELECT * FROM enrollments WHERE id=? AND tenant_id=?", (enrollment_id, tenant_id)).fetchone()
    if enrollment is None:
        conn.close()
        return jsonify({"error": "Enrollment not found"}), 404
    if enrollment["user_id"] != g.current_user["user_id"] and not has_permission(g.current_user, "employees.manage"):
        conn.close()
        return jsonify({"error": "Permission denied"}), 403
    lesson_owner = conn.execute("SELECT course_id FROM lessons WHERE id=?", (lesson_id,)).fetchone()
    if lesson_owner is None or lesson_owner["course_id"] != enrollment["course_id"]:
        conn.close()
        return jsonify({"error": "Lesson does not belong to this enrollment's course"}), 400

    conn.execute(
        """INSERT INTO lesson_progress (enrollment_id, lesson_id, completed, score, completed_at)
           VALUES (?,?,1,?,datetime('now'))
           ON CONFLICT(enrollment_id, lesson_id) DO UPDATE SET completed=1, score=excluded.score, completed_at=datetime('now')""",
        (enrollment_id, lesson_id, data.get("score")),
    )
    conn.commit()

    total_lessons = conn.execute("SELECT COUNT(*) c FROM lessons WHERE course_id=?", (enrollment["course_id"],)).fetchone()["c"]
    done_lessons = conn.execute(
        "SELECT COUNT(*) c FROM lesson_progress WHERE enrollment_id=? AND completed=1", (enrollment_id,)
    ).fetchone()["c"]
    progress_pct = int((done_lessons / total_lessons) * 100) if total_lessons else 0
    new_status = "completed" if progress_pct >= 100 else "in_progress"
    conn.execute("UPDATE enrollments SET progress_pct=?, status=? WHERE id=? AND tenant_id=?", (progress_pct, new_status, enrollment_id, tenant_id))

    cert = None
    if new_status == "completed":
        existing_cert = conn.execute(
            "SELECT * FROM certificates WHERE user_id=? AND course_id=? AND tenant_id=?",
            (enrollment["user_id"], enrollment["course_id"], tenant_id)
        ).fetchone()
        if not existing_cert:
            code = f"CODELA-{uuid.uuid4().hex[:8].upper()}"
            conn.execute(
                "INSERT INTO certificates (tenant_id, user_id, course_id, certificate_code) VALUES (?,?,?,?)",
                (tenant_id, enrollment["user_id"], enrollment["course_id"], code),
            )
            cert = code
    conn.commit()
    conn.close()
    return jsonify({"progress_pct": progress_pct, "status": new_status, "certificate_issued": cert})


@hr_bp.route("/certificates", methods=["GET"])
@login_required
def list_certificates():
    tenant_id = g.current_user["tenant_id"]
    user_id = request.args.get("user_id", g.current_user["user_id"])
    if str(user_id) != str(g.current_user["user_id"]) and not has_permission(g.current_user, "employees.manage"):
        return jsonify({"error": "Permission denied"}), 403
    conn = get_db()
    rows = conn.execute(
        """SELECT c.*, co.title AS course_title FROM certificates c
           JOIN courses co ON co.id = c.course_id WHERE c.user_id=? AND c.tenant_id=? ORDER BY c.issued_at DESC""",
        (user_id, tenant_id),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))
