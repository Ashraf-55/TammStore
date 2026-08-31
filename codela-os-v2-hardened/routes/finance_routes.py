import datetime as dt
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists, pagination_params
from auth import login_required, roles_required, log_action

finance_bp = Blueprint("finance", __name__)


@finance_bp.route("/transactions", methods=["GET"])
@login_required
@roles_required("accountant", "sales_manager")
def list_transactions():
    tenant_id = g.current_user["tenant_id"]
    tx_type = request.args.get("type")
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    conn = get_db()
    query = "SELECT * FROM finance_transactions WHERE tenant_id = ?"
    params = [tenant_id]
    if tx_type:
        query += " AND type = ?"
        params.append(tx_type)
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    query += " ORDER BY date DESC"
    limit, offset = pagination_params(request)
    query += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@finance_bp.route("/transactions", methods=["POST"])
@login_required
@roles_required("accountant")
def create_transaction():
    data = request.get_json(force=True) or {}
    if data.get("type") not in ("income", "expense") or not data.get("amount") or not data.get("category"):
        return jsonify({"error": "type (income/expense), category, and amount are required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    for fk,table in (("client_id","clients"),("project_id","projects")):
        if data.get(fk) and not tenant_resource_exists(conn,table,data[fk],tenant_id): conn.close(); return jsonify({"error":f"{fk} must belong to this workspace"}),400
    cur = conn.execute(
        "INSERT INTO finance_transactions (tenant_id, type, category, amount, description, client_id, project_id, date) VALUES (?,?,?,?,?,?,?,COALESCE(?, date('now')))",
        (tenant_id, data["type"], data["category"], data["amount"], data.get("description"),
         data.get("client_id"), data.get("project_id"), data.get("date")),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM finance_transactions WHERE id=? AND tenant_id=?", (cur.lastrowid, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "finance_transaction", cur.lastrowid)
    return jsonify(row_to_dict(row)), 201


@finance_bp.route("/summary", methods=["GET"])
@login_required
@roles_required("accountant", "sales_manager")
def finance_summary():
    tenant_id = g.current_user["tenant_id"]
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    conn = get_db()
    query = "SELECT type, SUM(amount) as total FROM finance_transactions WHERE tenant_id = ?"
    params = [tenant_id]
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    query += " GROUP BY type"
    rows = rows_to_list(conn.execute(query, params).fetchall())
    conn.close()

    income = next((r["total"] for r in rows if r["type"] == "income"), 0) or 0
    expenses = next((r["total"] for r in rows if r["type"] == "expense"), 0) or 0
    return jsonify({
        "income": income,
        "expenses": expenses,
        "gross_profit": income - expenses,
    })


# ---------------- SALARIES / COMMISSIONS ----------------

@finance_bp.route("/salaries", methods=["GET"])
@login_required
@roles_required("accountant")
def list_salaries():
    tenant_id = g.current_user["tenant_id"]
    month = request.args.get("month")
    conn = get_db()
    limit, offset = pagination_params(request)
    if month:
        rows = conn.execute(
            """SELECT s.*, u.name AS user_name, u.role
               FROM salaries s JOIN users u ON u.id = s.user_id
               WHERE s.tenant_id = ? AND s.month = ? ORDER BY u.name LIMIT ? OFFSET ?""",
            (tenant_id, month, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT s.*, u.name AS user_name, u.role
               FROM salaries s JOIN users u ON u.id = s.user_id
               WHERE s.tenant_id = ?
               ORDER BY s.month DESC, u.name LIMIT ? OFFSET ?""",
            (tenant_id, limit, offset),
        ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@finance_bp.route("/salaries", methods=["POST"])
@login_required
@roles_required("accountant")
def create_salary():
    data = request.get_json(force=True) or {}
    if not data.get("user_id") or not data.get("month"):
        return jsonify({"error": "user_id and month are required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    if not tenant_resource_exists(conn, "users", data["user_id"], tenant_id):
        conn.close()
        return jsonify({"error": "user_id must belong to this workspace"}), 400
    cur = conn.execute(
        """INSERT INTO salaries (tenant_id, user_id, month, base_salary, commission, bonus, deductions, status)
           VALUES (?,?,?,?,?,?,?,?)""",
        (tenant_id, data["user_id"], data["month"], data.get("base_salary", 0), data.get("commission", 0),
         data.get("bonus", 0), data.get("deductions", 0), data.get("status", "pending")),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM salaries WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@finance_bp.route("/salaries/<int:salary_id>/pay", methods=["PATCH"])
@login_required
@roles_required("accountant")
def pay_salary(salary_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    salary = conn.execute("SELECT * FROM salaries WHERE id=? AND tenant_id=?", (salary_id, tenant_id)).fetchone()
    if salary is None:
        conn.close()
        return jsonify({"error": "Salary record not found"}), 404
    total = salary["base_salary"] + salary["commission"] + salary["bonus"] - salary["deductions"]
    conn.execute("UPDATE salaries SET status='paid' WHERE id=? AND tenant_id=?", (salary_id, tenant_id))
    conn.execute(
        "INSERT INTO finance_transactions (tenant_id, type, category, amount, description, date) VALUES (?,'expense','salary',?,?,date('now'))",
        (tenant_id, total, f"Salary payment for user #{salary['user_id']} ({salary['month']})"),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM salaries WHERE id=? AND tenant_id=?", (salary_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "pay", "salary", salary_id)
    return jsonify(row_to_dict(row))


# ================================================================
# COMMISSION ENGINE
# Deal Won -> find applicable rule for the closer's role -> compute
# commission -> add it to that user's salary row for the current month
# (creating it if missing) -> record the calculation itself for audit.
# Called from routes/crm_routes.py right after a deal is marked 'won'.
# ================================================================

def calculate_and_record_commission(conn, tenant_id, deal):
    """deal is a dict (already committed) with at least: id, value, sales_id, title.
    Returns the computed commission amount (0 if no sales_id or no matching rule).
    Does not commit — caller owns the transaction."""
    if not deal.get("sales_id"):
        return 0

    salesperson = conn.execute("SELECT * FROM users WHERE id=? AND tenant_id=?", (deal["sales_id"], tenant_id)).fetchone()
    if salesperson is None:
        return 0

    rule = conn.execute(
        """SELECT * FROM commission_rules WHERE tenant_id=? AND is_active=1
           AND (role=? OR role IS NULL) AND min_deal_value <= ?
           ORDER BY role IS NULL, min_deal_value DESC LIMIT 1""",
        (tenant_id, salesperson["role"], deal["value"]),
    ).fetchone()
    if rule is None:
        return 0

    commission = (deal["value"] * rule["rate"] / 100.0) if rule["rule_type"] == "percent_of_deal" else rule["flat_amount"]
    commission = round(commission, 2)
    if commission <= 0:
        return 0

    month = dt.date.today().strftime("%Y-%m")
    salary_row = conn.execute("SELECT * FROM salaries WHERE tenant_id=? AND user_id=? AND month=?",
                               (tenant_id, deal["sales_id"], month)).fetchone()
    if salary_row:
        conn.execute("UPDATE salaries SET commission = commission + ? WHERE id=? AND tenant_id=?", (commission, salary_row["id"], tenant_id))
    else:
        conn.execute(
            "INSERT INTO salaries (tenant_id, user_id, month, base_salary, commission, bonus, deductions, status) VALUES (?,?,?,0,?,0,0,'pending')",
            (tenant_id, deal["sales_id"], month, commission),
        )
    conn.execute(
        "INSERT INTO finance_transactions (tenant_id, type, category, amount, description, client_id, date) VALUES (?,'expense','commission',?,?,?,date('now'))",
        (tenant_id, commission, f"Commission on deal '{deal['title']}' (#{deal['id']}) — rule '{rule['name']}'", deal.get("client_id")),
    )
    return commission


@finance_bp.route("/commission-rules", methods=["GET"])
@login_required
@roles_required("accountant", "sales_manager")
def list_commission_rules():
    conn = get_db()
    limit, offset = pagination_params(request)
    rows = conn.execute("SELECT * FROM commission_rules WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (g.current_user["tenant_id"], limit, offset)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@finance_bp.route("/commission-rules", methods=["POST"])
@login_required
@roles_required("accountant", "sales_manager")
def create_commission_rule():
    data = request.get_json(force=True) or {}
    if not data.get("name") or data.get("rule_type", "percent_of_deal") not in ("percent_of_deal", "flat"):
        return jsonify({"error": "name is required and rule_type must be percent_of_deal or flat"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO commission_rules (tenant_id, name, role, rule_type, rate, flat_amount, min_deal_value, is_active)
           VALUES (?,?,?,?,?,?,?,?)""",
        (tenant_id, data["name"], data.get("role"), data.get("rule_type", "percent_of_deal"),
         data.get("rate", 0), data.get("flat_amount", 0), data.get("min_deal_value", 0),
         1 if data.get("is_active", True) else 0),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM commission_rules WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "commission_rule", cur.lastrowid)
    return jsonify(row_to_dict(row)), 201


@finance_bp.route("/commission-rules/<int:rule_id>", methods=["PATCH"])
@login_required
@roles_required("accountant", "sales_manager")
def update_commission_rule(rule_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    fields, values = [], []
    for key in ("name", "role", "rule_type", "rate", "flat_amount", "min_deal_value"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if "is_active" in data:
        fields.append("is_active = ?")
        values.append(1 if data["is_active"] else 0)
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    values += [rule_id, tenant_id]
    conn = get_db()
    conn.execute(f"UPDATE commission_rules SET {', '.join(fields)} WHERE id=? AND tenant_id=?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM commission_rules WHERE id=? AND tenant_id=?", (rule_id, tenant_id)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify(row_to_dict(row))


# ================================================================
# INVOICING (Accounts Receivable)
# ================================================================

def _next_invoice_number(conn, tenant_id):
    year = dt.date.today().year
    prefix = f"INV-{year}-"
    row = conn.execute(
        "SELECT invoice_number FROM invoices WHERE tenant_id=? AND invoice_number LIKE ? ORDER BY invoice_number DESC LIMIT 1",
        (tenant_id, prefix + "%"),
    ).fetchone()
    if row and row["invoice_number"]:
        try:
            last_seq = int(row["invoice_number"].rsplit("-", 1)[-1])
        except ValueError:
            last_seq = 0
    else:
        last_seq = 0
    return f"{prefix}{last_seq + 1:04d}"


def _insert_invoice_with_unique_number(conn, tenant_id, insert_fn, max_attempts=5):
    """Runs insert_fn(invoice_number) in a retry loop to survive a concurrent
    request claiming the same invoice_number (protected by the UNIQUE(tenant_id,
    invoice_number) DB constraint)."""
    last_error = None
    for _ in range(max_attempts):
        invoice_number = _next_invoice_number(conn, tenant_id)
        try:
            return invoice_number, insert_fn(invoice_number)
        except Exception as e:
            conn.rollback()
            last_error = e
            continue
    raise last_error


def _recompute_invoice_totals(conn, invoice_id, tenant_id):
    items = conn.execute("SELECT * FROM invoice_items WHERE invoice_id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchall()
    subtotal = sum(i["amount"] for i in items)
    invoice = conn.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchone()
    total = round(subtotal * (1 + (invoice["tax_pct"] or 0) / 100.0), 2)
    conn.execute("UPDATE invoices SET subtotal=?, total=? WHERE id=? AND tenant_id=?", (subtotal, total, invoice_id, tenant_id))
    return subtotal, total


@finance_bp.route("/invoices", methods=["GET"])
@login_required
@roles_required("accountant", "sales_manager")
def list_invoices():
    tenant_id = g.current_user["tenant_id"]
    status = request.args.get("status")
    conn = get_db()
    limit, offset = pagination_params(request)
    if status:
        rows = conn.execute("SELECT * FROM invoices WHERE tenant_id=? AND status=? ORDER BY issue_date DESC LIMIT ? OFFSET ?", (tenant_id, status, limit, offset)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM invoices WHERE tenant_id=? ORDER BY issue_date DESC LIMIT ? OFFSET ?", (tenant_id, limit, offset)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@finance_bp.route("/invoices/<int:invoice_id>", methods=["GET"])
@login_required
@roles_required("accountant", "sales_manager")
def get_invoice(invoice_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    invoice = conn.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchone()
    if invoice is None:
        conn.close()
        return jsonify({"error": "Invoice not found"}), 404
    items = rows_to_list(conn.execute("SELECT * FROM invoice_items WHERE invoice_id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchall())
    payments = rows_to_list(conn.execute("SELECT * FROM payments WHERE invoice_id=? AND tenant_id=? ORDER BY paid_at DESC", (invoice_id, tenant_id)).fetchall())
    conn.close()
    result = row_to_dict(invoice)
    result["items"] = items
    result["payments"] = payments
    return jsonify(result)


@finance_bp.route("/invoices", methods=["POST"])
@login_required
@roles_required("accountant")
def create_invoice():
    """Body: {client_id, project_id?, deal_id?, due_date?, tax_pct?, notes?, items: [{description, quantity, unit_price}]}"""
    data = request.get_json(force=True) or {}
    if not data.get("client_id") or not data.get("items"):
        return jsonify({"error": "client_id and at least one item are required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    if data.get("deal_id") and not tenant_resource_exists(conn,"deals",data["deal_id"],tenant_id):
        conn.close(); return jsonify({"error":"deal_id must belong to this workspace"}),400
    if not tenant_resource_exists(conn, "clients", data["client_id"], tenant_id):
        conn.close()
        return jsonify({"error": "client_id must belong to this workspace"}), 400
    for fk in ("project_id", "deal_id"):
        if data.get(fk) and not tenant_resource_exists(conn, "projects" if fk == "project_id" else "deals", data[fk], tenant_id):
            conn.close()
            return jsonify({"error": f"{fk} must belong to this workspace"}), 400
    def _do_insert(invoice_number):
        cur = conn.execute(
            """INSERT INTO invoices (tenant_id, client_id, project_id, deal_id, invoice_number, status, due_date, tax_pct, notes)
               VALUES (?,?,?,?,?, 'draft', ?,?,?)""",
            (tenant_id, data["client_id"], data.get("project_id"), data.get("deal_id"), invoice_number,
             data.get("due_date"), data.get("tax_pct", 0), data.get("notes")),
        )
        return cur.lastrowid

    try:
        invoice_number, invoice_id = _insert_invoice_with_unique_number(conn, tenant_id, _do_insert)
    except Exception:
        conn.close()
        return jsonify({"error": "Could not allocate a unique invoice number, please retry"}), 409
    for item in data["items"]:
        qty, price = item.get("quantity", 1), item.get("unit_price", 0)
        conn.execute(
            "INSERT INTO invoice_items (tenant_id, invoice_id, description, quantity, unit_price, amount) VALUES (?,?,?,?,?,?)",
            (tenant_id, invoice_id, item.get("description", ""), qty, price, round(qty * price, 2)),
        )
    _recompute_invoice_totals(conn, invoice_id, tenant_id)
    conn.commit()
    row = conn.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchone()
    items = rows_to_list(conn.execute("SELECT * FROM invoice_items WHERE invoice_id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchall())
    conn.close()
    log_action(g.current_user["user_id"], "create", "invoice", invoice_id, details=invoice_number)
    result = row_to_dict(row)
    result["items"] = items
    return jsonify(result), 201


@finance_bp.route("/invoices/<int:invoice_id>", methods=["PATCH"])
@login_required
@roles_required("accountant")
def update_invoice(invoice_id):
    """Status transitions: draft -> sent -> paid/overdue/cancelled."""
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    valid_statuses = ("draft", "sent", "paid", "overdue", "cancelled")
    if "status" in data and data["status"] not in valid_statuses:
        return jsonify({"error": f"status must be one of {valid_statuses}"}), 400
    conn = get_db()
    existing = conn.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Invoice not found"}), 404
    if "status" in data and data["status"] != existing["status"]:
        INVOICE_TRANSITIONS = {
            "draft": {"sent", "cancelled"},
            "sent": {"paid", "overdue", "cancelled"},
            "overdue": {"paid", "cancelled"},
            "paid": set(),
            "cancelled": set(),
        }
        if data["status"] not in INVOICE_TRANSITIONS.get(existing["status"], set()):
            conn.close()
            return jsonify({"error": f"Cannot transition invoice from '{existing['status']}' to '{data['status']}'"}), 409
    fields, values = [], []
    for key in ("status", "due_date", "tax_pct", "notes"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if fields:
        values += [invoice_id, tenant_id]
        conn.execute(f"UPDATE invoices SET {', '.join(fields)} WHERE id=? AND tenant_id=?", values)
    if "tax_pct" in data:
        _recompute_invoice_totals(conn, invoice_id, tenant_id)
    conn.commit()
    row = conn.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "invoice", invoice_id)
    return jsonify(row_to_dict(row))


@finance_bp.route("/invoices/<int:invoice_id>/payments", methods=["POST"])
@login_required
@roles_required("accountant")
def record_payment(invoice_id):
    """Body: {amount, method?, reference?}. Auto-marks the invoice 'paid' once amount_paid >= total."""
    data = request.get_json(force=True) or {}
    if not data.get("amount"):
        return jsonify({"error": "amount is required"}), 400
    try:
        amount = float(data["amount"])
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a number"}), 400
    if amount <= 0:
        return jsonify({"error": "amount must be greater than zero"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    invoice = conn.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchone()
    if invoice is None:
        conn.close()
        return jsonify({"error": "Invoice not found"}), 404
    if invoice["status"] == "cancelled":
        conn.close()
        return jsonify({"error": "Cannot record a payment on a cancelled invoice"}), 409
    if invoice["status"] == "paid":
        conn.close()
        return jsonify({"error": "Invoice is already fully paid"}), 409
    already_paid = invoice["amount_paid"] or 0
    if already_paid + amount > invoice["total"] + 1e-9:
        conn.close()
        return jsonify({"error": "Payment would exceed the invoice total", "remaining": round(invoice["total"] - already_paid, 2)}), 400

    conn.execute(
        "INSERT INTO payments (tenant_id, invoice_id, amount, method, reference) VALUES (?,?,?,?,?)",
        (tenant_id, invoice_id, amount, data.get("method"), data.get("reference")),
    )
    new_paid = already_paid + amount
    new_status = "paid" if new_paid >= invoice["total"] else invoice["status"]
    conn.execute("UPDATE invoices SET amount_paid=?, status=? WHERE id=? AND tenant_id=?", (new_paid, new_status, invoice_id, tenant_id))

    conn.execute(
        "INSERT INTO finance_transactions (tenant_id, type, category, amount, description, client_id, date) VALUES (?,'income','invoice_payment',?,?,?,date('now'))",
        (tenant_id, amount, f"Payment for {invoice['invoice_number']}", invoice["client_id"]),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "record_payment", "invoice", invoice_id, details=str(amount))
    return jsonify(row_to_dict(row))


@finance_bp.route("/finance/ar-summary", methods=["GET"])
@login_required
@roles_required("accountant", "sales_manager")
def accounts_receivable_summary():
    """Outstanding balance across all unpaid invoices — the 'Accounts Receivable' the audit flagged as missing."""
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    rows = rows_to_list(conn.execute(
        "SELECT id, invoice_number, client_id, total, amount_paid, due_date, status FROM invoices WHERE tenant_id=? AND status IN ('sent','overdue') ORDER BY due_date",
        (tenant_id,),
    ).fetchall())
    conn.execute(
        "UPDATE invoices SET status='overdue' WHERE tenant_id=? AND status='sent' AND due_date IS NOT NULL AND due_date < date('now')",
        (tenant_id,),
    )
    conn.commit()
    conn.close()
    outstanding = sum(r["total"] - r["amount_paid"] for r in rows)
    overdue = [r for r in rows if r["due_date"] and r["due_date"] < dt.date.today().isoformat()]
    return jsonify({
        "total_outstanding": round(outstanding, 2),
        "invoice_count": len(rows),
        "overdue_count": len(overdue),
        "overdue_amount": round(sum(r["total"] - r["amount_paid"] for r in overdue), 2),
        "invoices": rows,
    })
