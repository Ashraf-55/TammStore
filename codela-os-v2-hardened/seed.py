"""Seed Codela OS with demo data. Run: python3 seed.py"""
from werkzeug.security import generate_password_hash
from database import get_db, init_db
import os
SEED_PASSWORD=os.getenv("CODELA_SEED_PASSWORD")
if not SEED_PASSWORD or len(SEED_PASSWORD)<12: raise SystemExit("Set CODELA_SEED_PASSWORD to a 12+ character password before seeding.")

init_db()
conn = get_db()

# Tenant (company workspace)
cur = conn.execute("INSERT INTO tenants (name, slug, plan) VALUES ('Codela Agency', 'codela', 'pro')")
tenant_id = cur.lastrowid
conn.commit()

users = [
    ("Mahmoud Founder", "founder@codela.com", "founder"),
    ("Mahmoud Manager", "sales.manager@codela.com", "sales_manager"),
    ("sondos Sales", "sondos@codela.com", "sales"),
    ("Omar Editor", "omar@codela.com", "video_editor"),
    ("Nour Designer", "nour@codela.com", "designer"),
    ("Laila PM", "laila@codela.com", "project_manager"),
    ("Khaled Accountant", "khaled@codela.com", "accountant"),
]
user_ids = {}
for name, email, role in users:
    cur = conn.execute(
        "INSERT INTO users (tenant_id, name, email, password_hash, role) VALUES (?,?,?,?,?)",
        (tenant_id, name, email, generate_password_hash(SEED_PASSWORD), role),
    )
    user_ids[email] = cur.lastrowid
conn.commit()

# Leads
leads = [
    ("Dental Clinic Cairo", "Bright Smile", "clinic", 50000, "qualified"),
    ("Fashion Store", "Trendy", "ecommerce", 20000, "new"),
    ("Tech Startup", "NovaTech", "tech", 150000, "negotiation"),
]
lead_ids = []
for name, company, industry, budget, status in leads:
    cur = conn.execute(
        """INSERT INTO leads (tenant_id, name, company, industry, budget, status, source, assigned_sales_id, score, score_tier)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (tenant_id, name, company, industry, budget, status, "referral", user_ids["sondos@codela.com"], 60, "warm"),
    )
    lead_ids.append(cur.lastrowid)
conn.commit()

# Client + project
cur = conn.execute(
    "INSERT INTO clients (tenant_id, lead_id, name, company, account_manager_id, industry) VALUES (?,?,?,?,?,?)",
    (tenant_id, lead_ids[0], "Dental Clinic Cairo", "Bright Smile", user_ids["sondos@codela.com"], "clinic"),
)
client_id = cur.lastrowid
conn.commit()

cur = conn.execute(
    "INSERT INTO projects (tenant_id, client_id, name, project_manager_id, status) VALUES (?,?,?,?,?)",
    (tenant_id, client_id, "Social Media Management", user_ids["laila@codela.com"], "active"),
)
project_id = cur.lastrowid
conn.execute(
    "INSERT INTO tasks (tenant_id, project_id, title, assignee_id, priority, status, deadline) VALUES (?,?,?,?,?,?,?)",
    (tenant_id, project_id, "Edit Reel #1", user_ids["omar@codela.com"], "high", "in_progress", "2026-08-25"),
)
conn.execute(
    "INSERT INTO tasks (tenant_id, project_id, title, assignee_id, priority, status, deadline) VALUES (?,?,?,?,?,?,?)",
    (tenant_id, project_id, "Design carousel post", user_ids["nour@codela.com"], "medium", "todo", "2026-08-27"),
)
conn.commit()

# Creator + content
cur = conn.execute(
    "INSERT INTO creators (tenant_id, stage_name, niche) VALUES (?,?,?)", (tenant_id, "Tech Creator", "tech"),
)
creator_id = cur.lastrowid
cur = conn.execute(
    "INSERT INTO content_ideas (tenant_id, title, category, platform, creator_id, status) VALUES (?,?,?,?,?,?)",
    (tenant_id, "5 AI Tools You Need", "education", "tiktok", creator_id, "published"),
)
content_id = cur.lastrowid
conn.execute(
    "INSERT INTO content_analytics (tenant_id, content_id, views, reach, likes, comments, shares) VALUES (?,?,?,?,?,?,?)",
    (tenant_id, content_id, 125000, 98000, 8500, 320, 410),
)
conn.commit()

# Finance
conn.execute(
    "INSERT INTO finance_transactions (tenant_id, type, category, amount, description, client_id) VALUES (?,'income','service',50000,'Retainer - Bright Smile',?)",
    (tenant_id, client_id),
)
conn.execute(
    "INSERT INTO finance_transactions (tenant_id, type, category, amount, description) VALUES (?,'expense','ads',5000,'Meta Ads Campaign')",
    (tenant_id,),
)
conn.commit()

# HR & Academy
cur = conn.execute(
    "INSERT INTO courses (tenant_id, title, description, weeks) VALUES (?,?,?,?)",
    (tenant_id, "Creator Training", "8-week onboarding for new content creators", 8),
)
course_id = cur.lastrowid
for i, lesson_title in enumerate(["Intro to Codela Brand Voice", "Hook Writing 101", "Filming Basics"], start=1):
    conn.execute(
        "INSERT INTO lessons (course_id, title, order_index) VALUES (?,?,?)",
        (course_id, lesson_title, i),
    )
conn.execute(
    "INSERT INTO enrollments (tenant_id, course_id, user_id, status, progress_pct) VALUES (?,?,?,?,?)",
    (tenant_id, course_id, user_ids["omar@codela.com"], "in_progress", 33),
)
conn.execute(
    "INSERT INTO attendance (tenant_id, user_id, date, check_in, status) VALUES (?, ?, date('now'), '09:05', 'present')",
    (tenant_id, user_ids["sondos@codela.com"]),
)
conn.commit()

# SOP Center
cur = conn.execute("INSERT INTO sop_categories (tenant_id, name) VALUES (?, 'Client Onboarding')", (tenant_id,))
cat_id = cur.lastrowid
conn.execute(
    "INSERT INTO sops (tenant_id, category_id, title, content, created_by) VALUES (?,?,?,?,?)",
    (tenant_id, cat_id, "How to onboard a new client",
     "1) Send welcome email. 2) Collect brand assets. 3) Schedule kickoff call. 4) Create project in Codela OS.",
     user_ids["laila@codela.com"]),
)
conn.commit()

# Assets & Equipment
conn.execute(
    "INSERT INTO assets (tenant_id, name, category, owner_id, location, status, value) VALUES (?,?,?,?,?,?,?)",
    (tenant_id, "Sony A7IV Camera", "camera", user_ids["omar@codela.com"], "Studio A", "available", 85000),
)
conn.commit()

# Requests -> auto Task
cur = conn.execute(
    "INSERT INTO projects (tenant_id, name, description, status) VALUES (?, 'Requests Inbox', 'Auto-created tasks from submitted requests', 'active')",
    (tenant_id,),
)
inbox_id = cur.lastrowid
task_cur = conn.execute(
    "INSERT INTO tasks (tenant_id, project_id, title, priority, status) VALUES (?,?,?,?,?)",
    (tenant_id, inbox_id, "[Request] Need extra shooting day next week", "high", "todo"),
)
conn.execute(
    """INSERT INTO requests (tenant_id, requester_name, requester_contact, request_type, title, priority, status, created_task_id)
       VALUES (?,?,?,?,?,?,?,?)""",
    (tenant_id, "Bright Smile Clinic", "whatsapp: 0100xxxxxxx", "production", "Need extra shooting day next week", "high", "triaged", task_cur.lastrowid),
)
conn.commit()

# ---------------- V2 seed data: commission rule + default follow-up sequence ----------------
# (the plan catalog itself is now bootstrapped by migration 12, not the demo seeder)

cur = conn.execute(
    "INSERT INTO subscriptions (tenant_id, plan_id, status, billing_cycle, current_period_end) "
    "SELECT ?, id, 'active', 'monthly', datetime('now', '+30 days') FROM plans WHERE code='pro'",
    (tenant_id,),
)
conn.commit()

conn.execute(
    "INSERT INTO commission_rules (tenant_id, name, role, rule_type, rate, min_deal_value) VALUES (?,?,?,?,?,?)",
    (tenant_id, "Default sales commission", "sales", "percent_of_deal", 10, 0),
)
conn.execute(
    "INSERT INTO commission_rules (tenant_id, name, role, rule_type, rate, min_deal_value) VALUES (?,?,?,?,?,?)",
    (tenant_id, "Sales manager override", "sales_manager", "percent_of_deal", 5, 0),
)
conn.commit()

cur = conn.execute(
    "INSERT INTO followup_sequences (tenant_id, name, applies_to, is_default, is_active) VALUES (?,?,?,?,?)",
    (tenant_id, "Standard Lead Follow-up", "lead", 1, 1),
)
seq_id = cur.lastrowid
steps = [
    (1, 2, "whatsapp", "First contact", "Hi {name}, thanks for reaching out — following up on your inquiry."),
    (2, 24, "whatsapp", "Day 1 follow-up", "Just checking in — happy to answer any questions."),
    (3, 72, "call", "Day 3 call", None),
    (4, 168, "email", "Week 1 recap", "Following up in case now's a better time to reconnect."),
]
for order, delay, channel, title, tmpl in steps:
    conn.execute(
        "INSERT INTO followup_steps (tenant_id, sequence_id, step_order, delay_hours, channel, title, message_template) VALUES (?,?,?,?,?,?,?)",
        (tenant_id, seq_id, order, delay, channel, title, tmpl),
    )
conn.commit()

conn.execute(
    "INSERT INTO automation_rules (tenant_id, name, trigger_event, conditions, actions, is_active, created_by) VALUES (?,?,?,?,?,?,?)",
    (tenant_id, "Hot lead -> notify sales manager", "lead.created",
     '[{"field": "lead.score", "op": ">=", "value": 50}]',
     '[{"type": "send_notification", "user_id": %d, "message": "Hot lead created: {lead_name}"}, '
     '{"type": "create_followup", "delay_hours": 2, "title": "Call hot lead", "channel": "call"}]' % user_ids["sales.manager@codela.com"],
     1, user_ids["founder@codela.com"]),
)
conn.execute(
    "INSERT INTO automation_rules (tenant_id, name, trigger_event, conditions, actions, is_active, created_by) VALUES (?,?,?,?,?,?,?)",
    (tenant_id, "Deal won -> notify founder", "deal.won", '[]',
     '[{"type": "send_notification", "user_id": %d, "message": "Deal won: {deal_title}"}]' % user_ids["founder@codela.com"],
     1, user_ids["founder@codela.com"]),
)
conn.commit()
conn.close()

print("✅ Seed complete. Workspace slug: 'codela'")
print("   Demo users created. Use the CODELA_SEED_PASSWORD value used for this seed run.")
print("V2 seed data added: plans, commission rules, follow-up sequence, automation rules")
