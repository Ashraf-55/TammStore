"""
AI Center — Codela OS
Uses the Anthropic API (Claude) when ANTHROPIC_API_KEY is configured, for:
  - Smarter lead scoring with a written rationale
  - Content idea / hook / script generation
  - Sales follow-up message drafting
  - Lead's next-best-action suggestion

If no API key is set (or the call fails), every endpoint falls back to the
existing rule-based logic already used in crm_routes.py, so the system keeps
working out of the box with zero configuration.
"""
import os
import json
import requests
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict
from auth import login_required, log_action
from routes.crm_routes import compute_lead_score

ai_bp = Blueprint("ai", __name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("CODELA_AI_MODEL", "claude-sonnet-4-6")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def call_claude(system_prompt, user_prompt, max_tokens=600):
    """Thin wrapper around the Anthropic Messages API. Returns text or None on failure."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        resp = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks).strip() or None
    except Exception:
        return None


def extract_json(text):
    """Best-effort extraction of a JSON object/array from a model response."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                return None
        return None


@ai_bp.route("/ai/status", methods=["GET"])
@login_required
def ai_status():
    return jsonify({
        "ai_enabled": bool(ANTHROPIC_API_KEY),
        "model": ANTHROPIC_MODEL if ANTHROPIC_API_KEY else None,
        "note": "Set the ANTHROPIC_API_KEY environment variable to enable AI features. "
                "Without it, the system uses rule-based fallbacks automatically.",
    })


# ---------------- SMARTER LEAD SCORING ----------------

@ai_bp.route("/ai/leads/<int:lead_id>/score", methods=["POST"])
@login_required
def ai_score_lead(lead_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id=? AND tenant_id=?", (lead_id, tenant_id)).fetchone()
    if lead is None:
        conn.close()
        return jsonify({"error": "Lead not found"}), 404
    activities = conn.execute(
        "SELECT type, content, created_at FROM lead_activities WHERE lead_id=? AND tenant_id=? ORDER BY created_at DESC LIMIT 10",
        (lead_id, tenant_id),
    ).fetchall()
    lead_dict = row_to_dict(lead)

    system_prompt = (
        "You are a B2B sales analyst for a marketing/media agency called Codela. "
        "Score how likely this lead is to close, from 0-100, and classify it as hot/warm/cold. "
        "Respond ONLY with JSON: {\"score\": int, \"tier\": \"hot|warm|cold\", \"rationale\": string, "
        "\"next_best_action\": string}. rationale and next_best_action must each be under 40 words."
    )
    user_prompt = json.dumps({
        "lead": {k: v for k, v in lead_dict.items() if k not in ("id",)},
        "recent_activities": [dict(a) for a in activities],
    }, ensure_ascii=False, default=str)

    ai_text = call_claude(system_prompt, user_prompt)
    parsed = extract_json(ai_text)

    if parsed and "score" in parsed:
        score = max(0, min(int(parsed["score"]), 100))
        tier = parsed.get("tier", "cold")
        rationale = parsed.get("rationale", "")
        next_action = parsed.get("next_best_action", "")
        source = "ai"
    else:
        score, tier = compute_lead_score(lead_dict)
        rationale = "AI غير متاح حاليًا — تم استخدام النظام الاحتسابي الافتراضي (budget + status + industry)."
        next_action = "تابع مع العميل حسب الـ Follow-up المجدول."
        source = "rule_based_fallback"

    conn.execute(
        "UPDATE leads SET score=?, score_tier=?, updated_at=datetime('now') WHERE id=? AND tenant_id=?",
        (score, tier, lead_id, tenant_id),
    )
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "ai_score", "lead", lead_id, details=source)

    return jsonify({
        "lead_id": lead_id,
        "score": score,
        "tier": tier,
        "rationale": rationale,
        "next_best_action": next_action,
        "source": source,
    })


# ---------------- CONTENT IDEA GENERATION ----------------

@ai_bp.route("/ai/content/ideas", methods=["POST"])
@login_required
def ai_generate_content_ideas():
    data = request.get_json(force=True) or {}
    niche = data.get("niche", "general")
    platform = data.get("platform", "tiktok")
    count = min(int(data.get("count", 3)), 8)
    language = data.get("language", "ar")  # ar | en

    system_prompt = (
        "You are a short-form social media strategist. Generate original content ideas. "
        f"Respond ONLY with a JSON array of {count} objects, each: "
        "{\"title\": string, \"hook\": string, \"category\": string, \"expected_goal\": string}. "
        f"Write all text in {'Arabic' if language == 'ar' else 'English'}. Keep hooks under 15 words."
    )
    user_prompt = f"Niche: {niche}\nPlatform: {platform}\nGenerate {count} content ideas."

    ai_text = call_claude(system_prompt, user_prompt, max_tokens=800)
    parsed = extract_json(ai_text)

    if isinstance(parsed, list) and parsed:
        return jsonify({"ideas": parsed, "source": "ai"})

    # rule-based fallback: simple templated ideas
    templates_ar = [
        {"title": f"5 أخطاء شائعة في {niche}", "hook": "ده بيحصل مع أغلب الناس وملحوظوش!",
         "category": "education", "expected_goal": "engagement"},
        {"title": f"قصة نجاح عميل في مجال {niche}", "hook": "من صفر لنتيجة حقيقية في وقت قصير",
         "category": "case_study", "expected_goal": "trust"},
        {"title": f"وراء الكواليس - {niche}", "hook": "شوف إزاي بنشتغل من الداخل", "category": "bts",
         "expected_goal": "reach"},
    ]
    templates_en = [
        {"title": f"5 common mistakes in {niche}", "hook": "Most people don't notice this!",
         "category": "education", "expected_goal": "engagement"},
        {"title": f"Client success story in {niche}", "hook": "From zero to real results, fast",
         "category": "case_study", "expected_goal": "trust"},
        {"title": f"Behind the scenes - {niche}", "hook": "See how we really work", "category": "bts",
         "expected_goal": "reach"},
    ]
    ideas = (templates_ar if language == "ar" else templates_en)[:count]
    return jsonify({"ideas": ideas, "source": "rule_based_fallback"})


# ---------------- SALES MESSAGE DRAFTING ----------------

@ai_bp.route("/ai/leads/<int:lead_id>/message", methods=["POST"])
@login_required
def ai_draft_message(lead_id):
    data = request.get_json(force=True) or {}
    tone = data.get("tone", "friendly")  # friendly | formal | urgent
    channel = data.get("channel", "whatsapp")
    language = data.get("language", "ar")

    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id=? AND tenant_id=?", (lead_id, g.current_user["tenant_id"])).fetchone()
    conn.close()
    if lead is None:
        return jsonify({"error": "Lead not found"}), 404
    lead_dict = row_to_dict(lead)

    system_prompt = (
        f"You are a sales rep at Codela, a marketing agency. Draft a short {channel} follow-up message "
        f"in a {tone} tone, in {'Arabic' if language == 'ar' else 'English'}. "
        "Keep it under 60 words, no generic filler, mention their specific status/service if relevant. "
        "Respond with the message text only, no preamble."
    )
    user_prompt = json.dumps({k: v for k, v in lead_dict.items() if v}, ensure_ascii=False, default=str)

    ai_text = call_claude(system_prompt, user_prompt, max_tokens=300)
    if ai_text:
        return jsonify({"message": ai_text.strip('"'), "source": "ai"})

    fallback = {
        "ar": f"أهلاً {lead_dict.get('name','')}، بنتابع معاك بخصوص {lead_dict.get('service_interested') or 'خدماتنا'}. "
              "لو عندك وقت النهاردة نتكلم بسرعة؟",
        "en": f"Hi {lead_dict.get('name','')}, following up on {lead_dict.get('service_interested') or 'our services'}. "
              "Do you have a few minutes today to chat?",
    }
    return jsonify({"message": fallback.get(language, fallback["ar"]), "source": "rule_based_fallback"})


# ---------------- SALES / CONTENT SUMMARY ----------------

@ai_bp.route("/ai/summary", methods=["GET"])
@login_required
def ai_daily_summary():
    language = request.args.get("language", "ar")
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    stats = {
        "new_leads_today": conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE tenant_id=? AND date(created_at) = date('now')", (tenant_id,)).fetchone()["c"],
        "deals_won_today": conn.execute(
            "SELECT COUNT(*) c FROM deals WHERE tenant_id=? AND status='won' AND date(closed_at) = date('now')", (tenant_id,)).fetchone()["c"],
        "tasks_due_today": conn.execute(
            "SELECT COUNT(*) c FROM tasks WHERE tenant_id=? AND date(deadline) = date('now') AND status != 'done'", (tenant_id,)).fetchone()["c"],
        "content_published_today": conn.execute(
            "SELECT COUNT(*) c FROM content_ideas WHERE tenant_id=? AND status='published' "
            "AND id IN (SELECT content_id FROM content_calendar WHERE tenant_id=? AND date(publish_date) = date('now'))",
            (tenant_id, tenant_id)
        ).fetchone()["c"],
    }
    conn.close()

    system_prompt = (
        f"Write a short, motivating one-paragraph daily business summary in "
        f"{'Arabic' if language == 'ar' else 'English'} for a marketing agency CEO, based on these stats. "
        "Under 60 words. No headers, plain text only."
    )
    ai_text = call_claude(system_prompt, json.dumps(stats), max_tokens=200)

    if ai_text:
        return jsonify({"summary": ai_text, "stats": stats, "source": "ai"})

    fallback = {
        "ar": f"النهاردة: {stats['new_leads_today']} Lead جديد، {stats['deals_won_today']} صفقة اتقفلت، "
              f"{stats['tasks_due_today']} مهمة مستحقة، و{stats['content_published_today']} محتوى اتنشر.",
        "en": f"Today: {stats['new_leads_today']} new leads, {stats['deals_won_today']} deals won, "
              f"{stats['tasks_due_today']} tasks due, and {stats['content_published_today']} content published.",
    }
    return jsonify({"summary": fallback.get(language, fallback["ar"]), "stats": stats, "source": "rule_based_fallback"})
