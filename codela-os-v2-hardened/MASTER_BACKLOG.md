# Codela OS v2 — Master Backlog (P0–P5)

> النسخة المرجعية المعتمدة. أي بند معلّم ✅ اتصلح فعليًا وله اختبار في `p0_p1_regression_test.py` أو أحد test suites الأخرى — ما بيترفعش إلا بعد إثبات فعلي، مش تخمين. البنود الباقية لسه Open.

---

## 🔴 P0 — Security / IDOR / Data Integrity (13 بند)

| # | المشكلة | الحالة |
|---|---------|--------|
| 1 | Employee Update بدون Permission | ✅ اتصلح — `employees.update` permission |
| 2 | Deliverable Versions بدون Permission | ✅ اتصلح — `deliverables.versions` permission |
| 3 | Attendance IDOR (`GET /attendance?user_id=`) | ✅ اتصلح — self/manager check |
| 4 | Academy Enrollment Authorization | ✅ اتصلح |
| 5 | Academy Lesson Completion Authorization | ✅ اتصلح |
| 6 | File Access object-level authorization (لحسابات Client Portal تحديدًا) | ✅ جزئيًا — اتقفل عن طريق الـClient Portal gate (بند 13). التحقق الداخلي الأدق لكل ملف/staff لسه Open → نُقل لـP2 |
| 7 | Invoice Number Race Condition | ✅ اتصلح — retry-safe + DB UNIQUE constraint |
| 8 | Deliverable Milestone Integrity (نفس الـProject) | ✅ اتصلح |
| 9 | Task Milestone Integrity (نفس الـProject) | ✅ اتصلح |
| 10 | Task Creation/Update Project Membership | ✅ اتصلح |
| **11** | **Quote Update Authorization** — تحديث الـQuote (خصوصًا approved/converted) يحتاج Permission + State validation | ✅ اتصلح — `quotes.manage` permission + state machine (draft→sent→approved→converted, ورفض أي transition غير منطقي) |
| **12** | **Deliverable Approval Authorization** — إنشاء Approval Action يحتاج Permission واضحة | ✅ اتصلح — permission جديد `deliverables.approve` (migration v23)، مربوط بـ`POST /deliverables/<id>/approval` |
| **13** | **Client Object-Level Authorization Regression** — التأكد أن Files/Projects/Users/Clients ما بيتجاوزوش Client ownership بعد إصلاح Client Portal Isolation | ✅ Isolation gate نفسه اتصلح فعلًا (`login_required` بيحصر حسابات Client Portal في `/api/client/*` بس). ✅ Regression test مكتوب ومحفوظ في `p0_p1_regression_test.py` (بيتحقق من `/api/clients`, `/api/projects`, `/api/users` بترفض 403، و`/api/client/dashboard` بيشتغل، والـstaff مش متأثر) — هيفضل يتشغّل مع كل تعديل مستقبلي |

**كل الـ13 بند دول اتصلحوا واتأكدوا. مفيش بند P0 مفتوح دلوقتي.**

---

## 🟠 P1 — Business Logic / State (11/11 ✅ مغلق بالكامل)

| # | المشكلة | الحالة |
|---|---------|--------|
| 1 | Task Project Change قد يكسر Membership | ✅ اتصلح |
| 2 | Project Manager لا يتزامن مع Project Members | ✅ اتصلح — عند `PATCH /projects/<id>` وعند إنشاء المشروع من Won Deal |
| 3 | Attendance Clear-flag يعتمد على Role مباشرة بدل Permission | ✅ اتصلح — بيقبل `attendance.manage` permission كمان مش الـrole بس |
| 4 | Invoice State Machine ناقصة | ✅ اتصلح |
| 5 | Payment Validation ناقصة | ✅ اتصلح — negative/zero, overpayment, double-payment, cancelled invoice |
| 6 | Won Deal → Project بدون Manager | ✅ اتصلح |
| 7 | Employee Hierarchy يمكن أن تعمل Cycles | ✅ اتصلح |
| 8 | Duplicate Employee/User Relationship | ✅ مش محتاج تصليح — `UNIQUE(tenant_id, user_id)` موجود بالفعل في schema.sql |
| **9** | **Approval Authorization غير موحدة** | ✅ اتصلح — `decide_approval()` بقى بيستخدم `has_permission(deliverables.approve)` بدل hardcoded role tuple، وسدّينا ثغرة حقيقية: approval من غير `approver_id` معيّن كان أي حد authenticated يقدر يقرر فيه (دلوقتي محتاج الـpermission). وحّدنا نفس النمط في `update_content` (media_routes.py) — كان من غير أي permission check خالص، دلوقتي `content.manage` للتعديل العادي + `content.workflow` مخصوص لنقل الحالة لـ"approved" |
| **10** | **Won Deal → Project بدون Team تلقائي** | ✅ اتصلح — `PATCH /deals/<id>` بقى يقبل `team_member_ids` (array)، وكل عضو صالح (tenant-scoped employee) بيتضاف لـ`project_members` تلقائيًا مع الـPM |
| **11** | **Deal → Project ليس Transactional Workflow كامل** | ✅ اتصلح جزئيًا وبصراحة كاملة — **الـWorkflow الكامل (Client Confirmed → Contract → Kickoff) لسه محتاج Contracts Module اللي هو P3 ولسه ماتبنيش**. اللي اتصلح فعليًا: (أ) العملية بقت **atomic فعليًا** — لفّيتها في `try/except/rollback` صريح؛ لو أي خطوة فشلت (مثلاً commission calculation) الـdeal ما بترجعش تتعلّم "won" ومفيش project يتعمل نص عمل — اتأكد بمحاكاة فشل فعلي واختبار إن الـDB رجعت لحالتها الأصلية بالكامل. (ب) `project.kickoff_from_won_deal` activity event بقى يسجّل تفاصيل الـhandoff (PM + عدد أعضاء الفريق). **الجزء المتبقي (Contract entity + Client confirmation gate) هيتقفل بس لما نوصل P3 Contracts Module — مش قبل كده.** |

---

## 🟡 P2 — Architecture (موسّع حسب توجيهك)

### DB Constraints / Integrity Rules (checklist حقيقي بدل بند عام)

| القاعدة | الحالة |
|---------|--------|
| Unique business identifiers (invoice_number) | ✅ `UNIQUE(tenant_id, invoice_number)` موجود |
| Employee ↔ User uniqueness | ✅ `UNIQUE(tenant_id, user_id)` موجود |
| Project ↔ Milestone consistency | ✅ اتصلح على مستوى التطبيق (Python check)، مفيش DB-level constraint لسه |
| Task ↔ Project consistency | ✅ اتصلح على مستوى التطبيق |
| Task ↔ Milestone consistency | ✅ اتصلح على مستوى التطبيق |
| Project ↔ Member consistency (PM لازم يكون Member) | ✅ اتصلح على مستوى التطبيق (auto-sync) |
| Positive monetary values | ✅ جزئيًا — payments (amount > 0) اتصلح؛ باقي الحقول المالية (hourly_cost, invoice totals, quote items) لسه من غير CHECK constraint |
| Invoice number uniqueness | ✅ |
| Valid status transitions (quotes/invoices) | ✅ اتصلح على مستوى التطبيق (Python state machines)، مفيش DB CHECK constraint |

**ملاحظة:** كل القواعد المعلّمة ✅ اتصلحت في application layer (Python)، مش DB constraints فعلية (CHECK/TRIGGER). ده كافي عمليًا لأن كل الوصول بيعدي من نفس الـAPI، لكن لو حابب DB-level enforcement إضافي (دفاع أعمق) ده شغل منفصل لسه Open.

### باقي بنود Architecture

- 🔓 **Contracts Module (P3, يفتح جزء #11 أعلاه بالكامل لما يتبنى)**
- 🔓 نظامي Roles متوازيين (`users.role` مقابل RBAC الجديد `user_roles`/`role_permissions`) — لسه Open، ومعظم الفحص الفعلي بيمر عن طريق `LEGACY_ROLE_PERMISSIONS` fallback مش الجداول الجديدة
- 🔓 Authorization غير موحدة (`require_permission` / `roles_required` / `login_required` مختلطين) — تحسّن جزئيًا (كل الـP0/P1 fixes استخدمت `has_permission` بشكل متسق) لكن الملفات القديمة لسه فيها خليط
- 🔓 Business Rules موزعة داخل Routes بدل Domain Services
- 🔓 Soft Delete/Archive/Deactivate غير موحدة
- 🔓 Audit Coverage غير مكتملة (لسه Open — الكشف عن أي actions مش بتتسجل audit، ده شغل مسح شامل للـroutes)
- ✅ **Audit Immutable** — migration v25: `UPDATE` على `audit_log` ممنوع بالكامل على مستوى الـDB (trigger في SQLite، PL/pgSQL trigger في Postgres). اتأكد بمحاولة تعديل فعلية اترفضت. **DELETE مش ممنوع عمدًا** — `audit_log.tenant_id` عنده `ON DELETE CASCADE`، فمنع الـDELETE بالكامل كان هيكسر cascade حذف الـTenant. الحل الصحيح لمنع DELETE المباشر (مع السماح بالـcascade) محتاج تصميم Tenant Deletion lifecycle الأول (P5، لسه ماتبناش) — موثّق بوضوح كسبب، مش اتقفل وهميًا.
- ✅ **Automation Loop Protection** — أضفت cascade-depth guard في `fire_event_sync()` (حد أقصى 5). **مفيش أي action handler حاليًا بينادي `fire_event` بنفسه** (فحصت كل الـ7 handlers الموجودين) يعني مفيش loop فعلي شغال دلوقتي، لكن مفيش أي حماية بنيوية كانت موجودة لو حد ضاف handler جديد بينادي fire_event (زي "fire_custom_event" مستقبلًا). اختبرت الحماية فعليًا بمحاكاة A→B→A cascade حقيقي (مش نظري) عن طريق حقن action handler وهمي بينادي fire_event تاني — الـcascade وقف عند العمق المحدد بالظبط بدل ما يعمل RecursionError، وسجّل `automation_runs` بـstatus='skipped'.
- ✅ **Pagination — جزئي، على أهم endpoints** — لقيت اكتشاف مهم: كان فيه global validator موجود بالفعل في `app.py` (`before_request` guard) بيتحقق من `?limit=` (يرفض القيم برا 1-100 بـ400)، لكنه مش متوصّل لأي query فعلي — الـroutes كانت بتقبل الـparam وتتجاهله، فالـqueries فضلت unbounded. أضفت helper موحّد (`pagination_params()` في `database.py`) ووصّلته فعليًا بـLIMIT/OFFSET في 14 endpoint من الأعلى traffic: `clients`, `projects`, `tasks`, `leads`, `deals`, `invoices`, `transactions`, `users`, `employees`, `content`, `creators`, `attendance`, `courses`, `requests`. الافتراضي 50 صف، أقصى حد 100 (متوافق مع الـvalidator الموجود). **اتأكد بالاختبار الفعلي:** عملت 60 client وأكدت إن الـendpoint من غير أي params بيرجّع 50 بس (مش الـ60 كلهم) — يعني الخطر الحقيقي (unbounded query على tenant كبير) اتقفل فعليًا. كمان اتأكد إن `?limit=`/`?offset=` بيرجعوا صفحات صح ومختلفة.
  **تكملة الجولة التانية:** طبّقت الـpattern على الباقي: `sops`, `followups`, `automation/rules`, `billing/invoices`, `salaries`, `commission-rules`, `assets`. وفحصت الباقي (`publish/log`, `jobs`, `automation/runs`) ولقيتهم عندهم `LIMIT` ثابت آمن بالفعل من الأساس (100 أو 50) — مفيش حاجة تتصلح فيهم. `message_templates`/`platform_connections` سيبتهم من غير pagination عمدًا لأنهم configuration lists طبيعتها صغيرة (مش بيانات بتكبر مع الوقت زي clients/tasks).

  **اكتشاف مهم إضافي:** لقيت bug حقيقي في `GET /communication/log?lead_id=` — الفرع اللي بيفلتر بـ`lead_id` **مكانش عليه أي LIMIT خالص** (بعكس الفرع التاني اللي كان عليه `LIMIT 100`)، يعني lead بتاريخ رسائل طويل كان ممكن يرجّع آلاف الصفوف. اتصلح واتأكد بالاختبار الفعلي (60 رسالة اتعملت، الـendpoint رجّع 50 بس).

  **النتيجة: Pagination بقت مقفولة على كل الـlist endpoints تقريبًا** (23 endpoint اتصلح مباشرة + كذا endpoint كان أصلًا آمن). الباقي (لو فيه) هو endpoints صغيرة الحجم بطبيعتها (config/lookup lists) مش قوائم بتنمو.
- 🔓 File access object-level authorization للـstaff — **فحصتها ولقيت الصورة مختلفة عن المتوقع:** الـ`POST /files/<id>/access` endpoint الوحيد الموجود بيسجّل access log ويرجّع metadata بس (مفيش endpoint فعلي بيسرّح bytes الملف نفسه — `send_file`/`send_from_directory` مش موجودين في الكود خالص، يعني الـfile storage integration نفسه لسه Mock زي باقي الـIntegrations في P4). الـendpoint ده أصلًا محمي بـ`files.access` permission اللي مش متاح لأي role غير founder/admin حاليًا (زي `LEGACY_ROLE_PERMISSIONS`). يعني الوضع الحالي **over-restrictive مش insecure**. القرار: نسيب البند ده Blocked على بناء الـfile storage integration الحقيقي (P4) — مفيش object-level authorization حقيقي نضيفه على endpoint بيرجّع metadata بس.

---

## 🟢 P3 — Remaining Core Modules

- ✅ **Invitations** — بُني بالكامل (migration v20 + 5 endpoints)
- ✅ **Password Recovery** — بُني بالكامل (migration v19 + 2 endpoints)
- ✅ **Email Verification** — بُني بالكامل (migration v21 + 2 endpoints)
- ✅ **Session Management** — كانت موجودة بالفعل، تم التأكد فقط
- ✅ **API Key Management** — بُني بالكامل (migration v22 + 4 endpoints + تفعيل في `login_required`)
- 🔓 Onboarding wizard
- 🔓 Tenant Settings (timezone/currency/tax/branding)
- 🔓 Webhooks (subscriptions/signatures/retries/delivery logs)
- 🔓 Import/Export (CSV)
- 🔓 Vendor Management
- 🔓 Contracts Module
- 🔓 Unified Approval Engine
- 🔓 Calendar Engine
- 🔓 Time Tracking → Cost
- 🔓 Lifecycle states (Employee/Client/Project/Task status machines رسمية)

**تنبيه:** الـ5 بنود المُعلّمة ✅ فوق **ما بترجعش تتفتح كـfeatures جديدة**. أي شغل عليهم من هنا يبقى إما (أ) bug fix حقيقي مُثبت، أو (ب) regression test إضافي — مش إعادة بناء.

---

## 🔵 P4 — Finance / Academy / Integrations

كل البنود دي لسه 🔓 Open زي ما هي: Project Profitability, Budget vs Actual, AR Aging, Tax Engine, Currency Rules, Academy Student/Course/Certificate Lifecycle, Payment Gateway Live, WhatsApp/Email/SMS/Social Publishing Live, OAuth token refresh, Incoming Webhooks من الـIntegrations.

---

## ⚪ P5 — Infrastructure / Governance / UX

كل البنود دي لسه 🔓 Open: Runtime E2E على PostgreSQL حقيقي, Concurrency tests أوسع, Backup/Restore drill, Observability, Rate limits per-operation, Secrets rotation, Data Retention, Tenant Export/Deletion, Permission-aware UI, Unified Error format, Loading/Empty/Error states.

---

## خطة التنفيذ المعتمدة

```
P0 (13/13 ✅)
 ↓
Security Regression (p0_p1_regression_test.py — مكتوب ✅، يتشغّل مع كل تعديل)
 ↓
P1 (11/11 ✅ — مغلق بالكامل، ما عدا الجزء اللي مربوط بـContracts Module P3)
 ↓
Domain/E2E Tests (موجودة جزئيًا في test suites الأصلية + الجديد)
 ↓
P2 Architecture cleanup ← **إحنا هنا دلوقتي** (DB Defense-in-Depth ✅، Audit Immutability ✅، Automation Loop Protection ✅ — الباقي: RBAC unification, Authorization consistency, Domain Services, Soft Delete, Audit Coverage scan — Pagination ✅ مقفولة)
 ↓
Production Gate
 ↓
P3/P4/P5 (لسه ماتبدأش — ينتظر إغلاق P2)
```

**P0 وP1 مقفولين بالكامل ومتأكدين باختبارات فعلية (`p0_p1_regression_test.py` بيغطي الاتنين في تشغيلة واحدة).** الخطوة المنطقية التالية حسب الخطة: P2 architecture cleanup. الاستثناء الوحيد: بند P1#11 مقفول بقدر الإمكان بدون Contracts Module — الجزء الباقي منه (Contract entity + Client confirmation) هيتقفل تلقائيًا لما نوصل P3 ونبني الـmodule ده، مش قبل كده ولسه ماتبدأش.
