"""End-to-end smoke test for the 5 new engines, run against a real Flask test client.

Run `python3 seed.py` first with the same CODELA_SEED_PASSWORD so the seeded
users' passwords match what this script logs in with.
"""
import os
import sys
sys.path.insert(0, ".")
from app import app

# Must match the value seed.py was run with (both enforce a 12+ char minimum).
SEED_PASSWORD = os.getenv("CODELA_SEED_PASSWORD")
if not SEED_PASSWORD or len(SEED_PASSWORD) < 12:
    raise SystemExit("Set CODELA_SEED_PASSWORD (12+ chars, same value used for seed.py) before running the smoke test.")

c = app.test_client()
errors = []

def check(label, resp, expected=(200, 201)):
    ok = resp.status_code in expected
    print(f"{'OK ' if ok else 'FAIL'} [{resp.status_code}] {label}")
    if not ok:
        print("     ", resp.get_data(as_text=True)[:300])
        errors.append(label)
    return resp.get_json()

# ---- login as founder ----
r = c.post("/api/auth/login", json={"email": "founder@codela.com", "password": SEED_PASSWORD})
data = check("login founder", r)
token = data["access_token"]
H = {"Authorization": f"Bearer {token}"}

# ---- login as sales manager (used for role-gated actions) ----
r = c.post("/api/auth/login", json={"email": "sales.manager@codela.com", "password": SEED_PASSWORD})
sm_token = check("login sales manager", r)["access_token"]
SM = {"Authorization": f"Bearer {sm_token}"}

# ---- Automation Engine ----
r = c.get("/api/automation/meta", headers=H)
check("automation meta", r)

r = c.get("/api/automation/rules", headers=H)
rules = check("list automation rules (seeded)", r)
print("     seeded rules:", [x["name"] for x in rules])

# create a fresh lead -> should fire lead.created (and hot-lead rule if score high)
r = c.post("/api/leads", json={"name": "Smoke Test Lead", "budget": 200000, "industry": "tech",
                                "source": "referral", "assigned_sales_id": None}, headers=H)
lead = check("create lead (high budget -> hot score)", r)
lead_id = lead["id"]
print("     lead score/tier:", lead["score"], lead["score_tier"])

r = c.get("/api/automation/runs", headers=H)
runs = check("automation runs log", r)
print("     runs recorded:", len(runs), [x["status"] for x in runs][:5])

# ---- Follow-up Engine ----
r = c.get("/api/followups/sequences", headers=H)
seqs = check("list followup sequences (seeded)", r)
seq_id = seqs[0]["id"]
print("     default sequence steps:", len(seqs[0]["steps"]))

r = c.post(f"/api/leads/{lead_id}/followups/start", json={"sequence_id": seq_id}, headers=H)
started = check("start followup sequence on lead", r)
print("     followups scheduled:", len(started["followups"]))

r = c.get("/api/followups", headers=H)
check("list followups", r)

fu_id = started["followups"][0]["id"]
r = c.post(f"/api/followups/{fu_id}/complete", json={"notes": "smoke test contact"}, headers=H)
check("complete a followup", r)

r = c.post("/api/followups/scan", headers=H)
check("scan overdue followups", r)

# ---- Communication Center ----
r = c.post("/api/communication/templates", json={"name": "Welcome WA", "channel": "whatsapp", "body": "Hi {name}!"}, headers=H)
tmpl = check("create message template", r)

r = c.post("/api/communication/send", json={"channel": "whatsapp", "to": "+201000000000",
                                             "body": "Hello from smoke test", "lead_id": lead_id}, headers=H)
msg = check("send message (mock adapter)", r)
print("     message status/mode:", msg["status"], msg["mode"])

r = c.get(f"/api/communication/log?lead_id={lead_id}", headers=H)
check("message log for lead", r)

# ---- Finance / Commission Engine ----
r = c.post("/api/deals", json={"title": "Smoke Test Deal", "value": 50000, "sales_id": None}, headers=H)
deal = check("create deal", r)
deal_id = deal["id"]

# assign the deal to Ahmed (a 'sales' role user, matches seeded commission rule)
r = c.get("/api/users", headers=H)
users = check("list users", r)
ahmed = next(u for u in users if u["email"] == "ahmed@codela.com")

r = c.patch(f"/api/deals/{deal_id}", json={"sales_id": ahmed["id"], "status": "won"}, headers=H)
won_deal = check("mark deal won (should trigger commission calc)", r)
print("     commission_calculated:", won_deal.get("commission_calculated"))

month = __import__("datetime").date.today().strftime("%Y-%m")
r = c.get(f"/api/salaries?month={month}", headers=H)
salaries = check("list salaries for this month", r)
ahmed_salary = next((s for s in salaries if s["user_id"] == ahmed["id"]), None)
print("     ahmed commission on file:", ahmed_salary["commission"] if ahmed_salary else "NOT FOUND")

# invoicing
r = c.get("/api/clients", headers=H)
clients = check("list clients", r)
client_id = clients[0]["id"]

r = c.post("/api/invoices", json={"client_id": client_id, "due_date": "2026-09-01",
            "items": [{"description": "Social media package", "quantity": 1, "unit_price": 15000}]}, headers=H)
invoice = check("create invoice", r)
invoice_id = invoice["id"]
print("     invoice total:", invoice["total"])

r = c.patch(f"/api/invoices/{invoice_id}", json={"status": "sent"}, headers=H)
check("send invoice", r)

r = c.post(f"/api/invoices/{invoice_id}/payments", json={"amount": 15000, "method": "bank_transfer"}, headers=H)
paid_invoice = check("record full payment", r)
print("     invoice status after payment:", paid_invoice["status"])

r = c.get("/api/finance/ar-summary", headers=H)
check("AR summary", r)

# ---- SaaS Billing Engine ----
r = c.get("/api/billing/plans", headers={})
plans = check("public plan list (no auth)", r)
print("     plans:", [p["code"] for p in plans])

r = c.get("/api/billing/subscription", headers=H)
sub = check("current subscription", r)
print("     plan/status/usage:", sub["plan_code"], sub["status"], sub["usage"])

r = c.post("/api/billing/subscribe", json={"plan_code": "enterprise", "billing_cycle": "monthly"}, headers=H)
new_sub = check("upgrade to enterprise", r)
print("     new plan status:", new_sub["status"])

r = c.get("/api/billing/invoices", headers=H)
check("billing invoice history", r)

r = c.post("/api/billing/check-trials", headers=H)
check("check-trials cron endpoint", r)

# ---- plan limit enforcement (register a brand new trial tenant with tiny usage) ----
r = c.post("/api/auth/register", json={"name": "Limit Tester", "email": "owner@limittest.com",
                                        "password": SEED_PASSWORD, "company_name": "Limit Test Co"})
reg = check("register new tenant (auto trial subscription)", r)
lt_token = reg["access_token"]
LT = {"Authorization": f"Bearer {lt_token}"}
r = c.get("/api/billing/subscription", headers=LT)
lt_sub = check("new tenant has an active trial subscription", r)
print("     new tenant plan/status:", lt_sub["plan_code"], lt_sub["status"])

print("\n" + "=" * 50)
if errors:
    print(f"SMOKE TEST: {len(errors)} FAILURE(S):", errors)
    sys.exit(1)
else:
    print("SMOKE TEST: ALL CHECKS PASSED")
