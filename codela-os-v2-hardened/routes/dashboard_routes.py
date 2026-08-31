from flask import Blueprint, jsonify, g
from database import get_db, rows_to_list
from auth import login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()

    # ---- Sales ----
    total_leads = conn.execute("SELECT COUNT(*) c FROM leads WHERE tenant_id=?", (tenant_id,)).fetchone()["c"]
    new_leads = conn.execute("SELECT COUNT(*) c FROM leads WHERE tenant_id=? AND status='new'", (tenant_id,)).fetchone()["c"]
    qualified_leads = conn.execute("SELECT COUNT(*) c FROM leads WHERE tenant_id=? AND status='qualified'", (tenant_id,)).fetchone()["c"]
    won_deals = conn.execute("SELECT COUNT(*) c FROM deals WHERE tenant_id=? AND status='won'", (tenant_id,)).fetchone()["c"]
    revenue = conn.execute("SELECT COALESCE(SUM(value),0) v FROM deals WHERE tenant_id=? AND status='won'", (tenant_id,)).fetchone()["v"]
    total_deals = conn.execute("SELECT COUNT(*) c FROM deals WHERE tenant_id=?", (tenant_id,)).fetchone()["c"]
    conversion_rate = round((won_deals / total_deals) * 100, 1) if total_deals else 0

    # ---- Projects ----
    active_projects = conn.execute("SELECT COUNT(*) c FROM projects WHERE tenant_id=? AND status='active'", (tenant_id,)).fetchone()["c"]
    delayed_projects = conn.execute("SELECT COUNT(*) c FROM projects WHERE tenant_id=? AND status='delayed'", (tenant_id,)).fetchone()["c"]
    completed_projects = conn.execute("SELECT COUNT(*) c FROM projects WHERE tenant_id=? AND status='completed'", (tenant_id,)).fetchone()["c"]

    # ---- Media ----
    total_content = conn.execute("SELECT COUNT(*) c FROM content_ideas WHERE tenant_id=?", (tenant_id,)).fetchone()["c"]
    published_content = conn.execute("SELECT COUNT(*) c FROM content_ideas WHERE tenant_id=? AND status='published'", (tenant_id,)).fetchone()["c"]
    total_views = conn.execute("SELECT COALESCE(SUM(views),0) v FROM content_analytics WHERE tenant_id=?", (tenant_id,)).fetchone()["v"]
    total_engagement = conn.execute(
        "SELECT COALESCE(SUM(likes+comments+shares+saves),0) v FROM content_analytics WHERE tenant_id=?", (tenant_id,)
    ).fetchone()["v"]

    # ---- Finance ----
    income = conn.execute("SELECT COALESCE(SUM(amount),0) v FROM finance_transactions WHERE tenant_id=? AND type='income'", (tenant_id,)).fetchone()["v"]
    expenses = conn.execute("SELECT COALESCE(SUM(amount),0) v FROM finance_transactions WHERE tenant_id=? AND type='expense'", (tenant_id,)).fetchone()["v"]
    pending_salaries = conn.execute("SELECT COUNT(*) c FROM salaries WHERE tenant_id=? AND status='pending'", (tenant_id,)).fetchone()["c"]

    # ---- Top performers ----
    top_sales = rows_to_list(conn.execute(
        """SELECT u.name, COUNT(d.id) as deals_won, COALESCE(SUM(d.value),0) as revenue
           FROM users u JOIN deals d ON d.sales_id = u.id AND d.status='won'
           WHERE u.tenant_id = ?
           GROUP BY u.id ORDER BY revenue DESC LIMIT 5""",
        (tenant_id,),
    ).fetchall())

    conn.close()

    return jsonify({
        "sales": {
            "total_leads": total_leads,
            "new_leads": new_leads,
            "qualified_leads": qualified_leads,
            "deals_won": won_deals,
            "revenue": revenue,
            "conversion_rate_pct": conversion_rate,
            "top_sales": top_sales,
        },
        "projects": {
            "active": active_projects,
            "delayed": delayed_projects,
            "completed": completed_projects,
        },
        "media": {
            "total_content": total_content,
            "published": published_content,
            "total_views": total_views,
            "total_engagement": total_engagement,
        },
        "finance": {
            "revenue": income,
            "expenses": expenses,
            "profit": income - expenses,
            "pending_salaries": pending_salaries,
        },
    })
