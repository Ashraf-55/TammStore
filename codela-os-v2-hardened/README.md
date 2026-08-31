# Codela OS — Backend + Frontend (Multi-tenant SaaS-ready)

نظام كامل (Flask + SQLite/PostgreSQL للباك إند، وواجهة ويب bilingual للفرونت إند) بيغطي:

**Core (Users/Auth/2FA) + CRM + Projects (List + Kanban) + Media (List + Calendar + Publishing) + Finance + Executive Dashboard + AI Center + HR & Academy + SOP Center + Assets + Requests**

بُني من الأول كـ **Multi-tenant**: كل شركة (workspace) بتسجل نفسها وبياناتها معزولة تمامًا عن أي شركة تانية بتستخدم نفس السيستم — ده أساس تحويله لـ Codela SaaS فعلي.

**الواجهة (`frontend/index.html`) بتدعم العربي والإنجليزي بالكامل** — RTL/LTR تلقائي، زرار تبديل لغة في أي وقت من غير logout.

---

## 0) إيه الجديد في النسخة دي

| الإضافة | الحالة | ملاحظة |
|---|---|---|
| 🎨 **تصميم احترافي جديد** | ✅ | ألوان زي LinkedIn/Facebook (أزرق على خلفية فاتحة) بدل الثيم الغامق القديم |
| ❌ **زرار إلغاء موحّد** | ✅ | كل نافذة (modal) دلوقتي فيها زرار ✕ ثابت فوق، بالإضافة لزرار Escape — مفيش أي حالة تحتاج ريفريش للسيستم |
| 🕵️ **حماية الحضور من التزوير** | ✅ مُختبر بالكامل | تحديد الموقع الجغرافي (Geofencing) + IP + كشف "بصمة مشتركة" (أكتر من شخص من نفس الـ IP)، مع شاشة "حضور الفريق" للمديرين ومراجعة الحالات المشتبه فيها |
| 🎬 **بوابة الموديلز (Creator Portal)** | ✅ مُختبر بالكامل | كل موديل/كرييتور ليها حساب دخول خاص بيها (رقم + باسورد منفصلين)، بتشوف مهامها بس وترفع محتواها الخاص — معزولة تمامًا عن باقي بيانات الشركة |
| 🔒 **Security أعمق** (2FA, Sessions) | ✅ مُختبر بالكامل | TOTP مبني من الصفر (RFC 6238)، Refresh tokens قابلة للإلغاء، حماية من brute-force |
| 🏢 **Multi-tenant** | ✅ مُختبر بالكامل | عزل بيانات كامل بين الشركات |
| 🗄️ **دعم PostgreSQL** | ⚠️ مبني لكن **غير مُختبر live** | مفيش سيرفر Postgres متاح في بيئة التطوير دي |
| 📱 **نشر تلقائي (Social Publishing)** | ✅ الجزء التجريبي (Mock) مُختبر بالكامل | الربط الفعلي بـ APIs المنصات محتاج مفاتيح حقيقية مش متاحة هنا |
| 🗂️ **Kanban Board** | ✅ مُختبر بالكامل | Drag & drop حقيقي بين أعمدة الحالة |
| 📅 **Content Calendar** | ✅ مُختبر بالكامل | Drag & drop لجدولة المحتوى |

---

## 0.0) V2 — الخمس Engines اللي كانوا ناقصين (Automation, Follow-up, Communication, Finance/Billing, SaaS Subscription)

بناءً على الـAudit، دي مش Features إضافية عشوائية — دي الخمس قطع اللي كانت بتفرّق بين "Dashboard قوي" و"Operating System حقيقي". كلها مبنية فوق نفس نمط الكود الموجود (Blueprints + tenant_id isolation + login_required/roles_required)، ومختبرة end-to-end عبر `smoke_test.py` (فعليًا بيسجل دخول، يعمل lead، يبدأ follow-up sequence، يبعت رسالة، يقفل صفقة ويتأكد من حساب العمولة، يعمل فاتورة ويدفعها، ويرقّي اشتراك SaaS — كله بينجح).

| الـEngine | الملفات | إيه اللي بيعمله فعليًا |
|---|---|---|
| 🤖 **Automation Engine** | `automation.py`, `routes/automation_routes.py` | محرك عام TRIGGER→CONDITION→ACTION. أي route ينادي `fire_event("lead.created", tenant_id, {...})`. القواعد (شروط + actions) مخزّنة كـJSON قابلة للتعديل من الـUI، وكل تنفيذ (نجح/فشل/اتخطى) مسجّل في `automation_runs`. مربوط فعليًا في: lead.created/assigned, deal.won/lost, request.created, attendance.flagged, task.overdue, followup.overdue |
| 📞 **Follow-up Engine** | `routes/followup_routes.py` | Sequences قابلة للتخصيص (خطوات + تأخير بالساعات + قناة). بدء sequence على lead بيولّد صفوف `followups` فعلية بمواعيد استحقاق حقيقية، مش مجرد حقل تاريخ. فيه scan endpoint بيحوّل المتأخر لـ`overdue` ويطلق `followup.overdue` |
| 💬 **Communication Center** | `routes/communication_routes.py` | WhatsApp/Email/SMS بنفس نمط الـmock/live الموجود أصلاً في `publish_routes.py` — كل رسالة (يدوية أو من الـAutomation Engine) بتتسجل في `messages` بغض النظر عن القناة. التفعيل الحقيقي محتاج API keys (متسجلة كـTODO واضح لكل قناة) |
| 💰 **Finance/Billing Engine** | إضافات في `routes/finance_routes.py` | (أ) محرك عمولة حقيقي: عند "Deal Won" بيدوّر على قاعدة عمولة تناسب دور البائع، يحسبها، ويضيفها لمرتبه الشهري تلقائيًا — مش حقل يدوي. (ب) نظام فواتير كامل (invoices/items/payments) مع AR summary حقيقي |
| 🏢 **SaaS Subscription Engine** | `routes/billing_routes.py` | Plans (trial/starter/pro/enterprise) بحدود استخدام فعلية (max_users, max_leads) بترجع HTTP 402 لو اتخطيت الحد. Trial تلقائي 14 يوم عند أي `/auth/register` جديد. بوابة دفع mock/live، وفحص انتهاء التجربة لتعليق الـtenant |

**تشغيل الـSmoke Test:**
```
python3 seed.py        # ينشئ قاعدة البيانات + بيانات تجريبية (شركات، مستخدمين، plans، قواعد عمولة، sequence افتراضي)
python3 smoke_test.py  # يضرب الـAPI فعليًا (test client) ويتأكد إن الخمس Engines شغالين end-to-end
```

**نقاط لازم تتعمل قبل الإنتاج:**
- الـpolling endpoints (`/api/automation/scan/*`, `/api/followups/scan`, `/api/billing/check-trials`) لازم تتنادى من cron خارجي — مفيش scheduler process في البيئة دي
- مفاتيح حقيقية لـWhatsApp Cloud API / SES-SendGrid / بوابة دفع (Stripe أو Paymob) لتفعيل الوضع Live بدل Mock
- الـcommission rule matching حاليًا بسيط (دور + حد أدنى لقيمة الصفقة) — لو محتاجين قواعد أعقد (شرائح، منتجات مختلفة) محتاج تمديد

---

## 0.1) تفاصيل إضافات الجولة دي

### حماية الحضور من التزوير
- كل Check-in بياخد **الموقع الجغرافي من المتصفح** (لو المستخدم سمح بيه) + **IP**
- لو حددت "موقع المكتب" (Security → مش، من صفحة الحضور → "موقع المكتب")، أي حضور خارج النطاق المسموح بيتعلّم **مشتبه فيه** تلقائيًا
- لو حد سجل حضور من غير ما يدي صلاحية الموقع، بيتعلّم "مشتبه فيه" برضه (`no_location_provided`) — عشان تراجعه بدل ما يمر من غير رقابة
- لو شخصين سجلوا حضور من نفس الـ IP في نفس اليوم، بيتعلّموا "مشتبه فيه" (`shared_ip_with_another_checkin_today`) — بيكشف حالة شخص واحد بيسجل حضور لزميله
- المديرين (founder/admin/sales_manager/project_manager/content_manager) بس هما اللي يقدروا يشوفوا "حضور الفريق" ويلغوا أي علامة اشتباه

### بوابة الموديلز (Creator Portal)
- من صفحة **"الموديلز"** (staff بس)، لما تضيف موديل جديد وتفعّل "إنشاء حساب دخول خاص"، السيستم بيولّد:
  - **رقم دخول فريد** (مثال: `MDL-4925`)
  - **باسورد مؤقت عشوائي**
  - حساب مستخدم بصلاحية `model` مربوط بالموديل دي بس
- الموديل بتسجل دخول بنفس شاشة الدخول العادية، لكن بتشوف **واجهة مختلفة تمامًا**: مهامها بس، محتواها بس، وفورم لرفع محتوى جديد (بعنوان، منصة، Hook، ورابط فيديو)
- **معزولة بالكامل**: لو حاولت توصل لأي endpoint تاني في السيستم (Leads, Finance, حتى موديل تانية)، السيستم بيرفض بـ 403 — الحماية دي على مستوى الـ backend نفسه مش بس إخفاء في الواجهة
- لما الموديل ترفع محتوى، بيوصل تلقائي لقسم المحتوى عند الفريق بحالة "مراجعة" + إشعار للمديرين

---

## 1) التشغيل محليًا

```bash
cd codela-os
pip install -r requirements.txt

# أول مرة فقط: يعمل الداتابيز وبيانات تجريبية (SQLite بشكل افتراضي)
python3 seed.py

# تشغيل السيرفر (الباك إند + الفرونت إند على نفس المنفذ)
python3 app.py
```

افتح `http://localhost:5000` — Flask بيقدّم `frontend/index.html` مباشرة من نفس الـ origin بتاع الـ API (ده برضه الإعداد المستخدم في الـ Docker Compose بتاع الإنتاج، اللي فيه سيرفس واحد بس هو `api`). أول شاشة فيها تابين: **دخول** و **إنشاء شركة جديدة**.

> ملاحظة: الفرونت إند بيستخدم مسار نسبي `/api` بافتراض إنه على نفس الـ origin بتاع الباك إند. لو حبيت تشغّل الفرونت إند من سيرفر ملفات منفصل (زي `python3 -m http.server`) هتحتاج تعدّل `API_URL` في `frontend/app.js` لعنوان مطلق، وتضيف origin بتاعه لـ `CODELA_CORS_ORIGINS`.

**بيانات دخول تجريبية (بعد الـ seed) — Workspace: `codela`:**
| الإيميل | الباسورد | الرول |
|---|---|---|
| founder@codela.com | password123 | founder (صلاحية كاملة) |
| ahmed@codela.com | password123 | sales |
| khaled@codela.com | password123 | accountant |
| laila@codela.com | password123 | project_manager |

---

## 2) Multi-tenant — إزاي يشتغل

كل جدول في الداتابيز (leads, projects, tasks, finance...) فيه عمود `tenant_id`، وكل query في الباك إند بيتفلتر بيه تلقائيًا حسب هوية المستخدم المسجل دخوله (مُستخرجة من الـ JWT).

**إزاي تعمل شركة جديدة:**
- من الواجهة: تاب "إنشاء شركة جديدة" في شاشة الدخول
- من الـ API مباشرة: `POST /api/auth/register` بـ `{name, email, password, company_name}` — بيرجع أول مستخدم بصلاحية `founder`

**لإضافة موظف لشركة موجودة** (مش شركة جديدة): `POST /api/auth/invite` (لازم تكون founder/admin)، بيرجع باسورد مؤقت للموظف الجديد.

**تسجيل الدخول لو نفس الإيميل مستخدم في أكتر من شركة:** السيستم بيطلب منك `tenant_slug` (معرّف الشركة) لتحديد أنهي شركة.

⚠️ **اختبرناها فعليًا**: سجّلنا شركة تانية ("Rival Agency")، وتأكدنا إنها معندهاش أي وصول لبيانات Codela — حتى لو حاولت توصل لـ Lead بالـ ID مباشرة، بترجع 404.

---

## 3) الأمان (Security)

### 2FA — التحقق بخطوتين
مبني من الصفر (RFC 6238 TOTP) — متوافق مع أي تطبيق مصادقة قياسي (Google Authenticator, Authy...).

- `POST /api/auth/2fa/setup` — بيرجع secret + رابط QR (`provisioning_uri`)
- `POST /api/auth/2fa/confirm` — تأكيد أول كود عشان يتفعل فعليًا
- `POST /api/auth/2fa/disable`
- بعد التفعيل، الـ login العادي بيرجع `{requires_2fa: true, pre_auth_token}` بدل التوكن مباشرة، وتكمل بـ:
- `POST /api/auth/2fa/login-verify` بـ `{pre_auth_token, code}`

من الواجهة: صفحة **"الأمان"** في القايمة الجانبية — فيها QR code بيتولد في المتصفح (محتاج إنترنت عشان يحمّل مكتبة الـ QR من CDN، لكن حتى من غيره الكود سرّي بيظهر نصي كـ fallback).

### Sessions (Refresh Tokens)
الدخول بيرجع `access_token` (ساعة واحدة) + `refresh_token` (30 يوم، بيتخزن الـ hash بتاعه بس في الداتابيز مش الأصلي). الواجهة بتعمل refresh تلقائي لو الـ access token خلص، من غير ما تحتاج تعمل login تاني.

- `GET /api/auth/sessions` — كل الأجهزة المسجل دخولها
- `POST /api/auth/sessions/<id>/revoke` — إلغاء جهاز معيّن
- `POST /api/auth/logout-all` — تسجيل خروج من كل الأجهزة دفعة واحدة

### حماية من Brute-force
5 محاولات دخول فاشلة بنفس الإيميل خلال 15 دقيقة → قفل مؤقت (429 Too Many Requests).

---

## 4) دعم PostgreSQL (⚠️ غير مُختبر live)

الباك إند بيدعم SQLite (افتراضي) أو PostgreSQL عن طريق environment variable:

```bash
pip install psycopg2-binary
export DATABASE_URL="postgresql://user:pass@localhost:5432/codela"
python3 app.py   # هيستخدم schema_postgres.sql تلقائيًا
```

**تنويه مهم:** الكود ده اتكتب صح بناءً على فروق SQLite/Postgres syntax، لكن معنديش سيرفر Postgres حقيقي في بيئة التطوير (مفيش إنترنت لتثبيته) عشان أختبره live. اختبره في بيئتك قبل ما تعتمد عليه في production، وابعتلي لو لاقيت أي مشكلة.

---

## 5) Publishing Center (📱 نشر تلقائي)

- `GET/POST /api/publish/connections` — ربط حساب منصة (platform, account_name, access_token)
- `POST /api/publish/content/<id>` — نشر محتوى على منصة معينة
- `GET /api/publish/log` — سجل كل محاولات النشر

**إزاي شغال:** كل منصة (TikTok, Instagram, YouTube, Facebook) ليها Adapter منفصل في `routes/publish_routes.py`. لو مفيش `access_token` مسجل للمنصة دي، بيشتغل في **Mock Mode** — بيحاكي نشر ناجح (بيولّد ID وهمي، ويحدّث حالة المحتوى لـ "published" فعليًا في الداتابيز) عشان تقدر تجرب الـ flow كامل من غير حسابات حقيقية.

**عشان تفعّل النشر الفعلي:** كل Adapter فيه `_publish_live()` method فاضلة بـ TODO واضح — تحتاج تسجّل تطبيق مطور عند المنصة، تجيب access token، وتنفّذ الـ API call بتاعها (كل منصة ليها flow مختلف تمامًا زي ما موضح في التعليقات). معملتش الجزء ده لأن مفيش مفاتيح حقيقية متاحة في بيئة التطوير.

من الواجهة: زرار "نشر" جنب كل محتوى في صفحة المحتوى، بيوريك وضوح إنه Mock Mode قبل ما تأكد.

---

## 5.1) Attendance (Anti-fraud) + Creator Portal — الـ Endpoints

### الحضور
- `POST /api/attendance/check-in` / `check-out` — بيقبلوا `{latitude, longitude}` اختياري من المتصفح
- `GET /api/attendance/team?flagged=true` — للمديرين بس
- `PATCH /api/attendance/<id>/clear-flag` — تأكيد إن الحضور سليم
- `GET/PATCH /api/company/settings` — تحديد موقع المكتب (`office_lat`, `office_lng`, `office_radius_m`)

### بوابة الموديلز
- `POST /api/creators` بـ `{stage_name, niche, create_login: true}` — بيرجع `portal_login_code` + `portal_temp_password` (مرة واحدة بس)
- `GET /api/creator-portal/me` — بروفايل الموديل
- `GET /api/creator-portal/my-content` / `my-tasks` — بس اللي متعلق بيها
- `POST /api/creator-portal/submit` — رفع محتوى جديد

## 6) هيكل المشروع


```
codela-os/
├── app.py                  # نقطة الدخول - بيسجل كل الـ Blueprints
├── database.py               # SQLite (افتراضي) أو PostgreSQL عبر DATABASE_URL
├── schema.sql                 # الجداول (SQLite) — فيها tenant_id على كل جدول
├── schema_postgres.sql          # نفس الجداول بصيغة PostgreSQL (غير مُختبرة live)
├── auth.py                       # Register/Login/2FA/Sessions + JWT + role-based access
├── totp.py                        # تطبيق TOTP من الصفر (2FA) — RFC 6238
├── seed.py                         # بيانات تجريبية (workspace واحد: "codela")
├── requirements.txt
├── frontend/
│   └── index.html                   # الواجهة بالكامل (بدون build tools)
└── routes/
    ├── users_routes.py               # CORE: Users, Notifications
    ├── crm_routes.py                  # CRM: Leads, Lead Scoring, Clients, Deals
    ├── projects_routes.py              # PROJECTS: Projects, Tasks, Comments, Kanban reorder
    ├── media_routes.py                  # MEDIA: Creators, Content Pipeline, Calendar, Analytics
    ├── finance_routes.py                 # FINANCE: Transactions, Salaries/Commissions
    ├── dashboard_routes.py                # Executive Dashboard (KPIs مجمّعة)
    ├── ai_routes.py                        # AI CENTER: Lead scoring, content ideas, messages
    ├── hr_routes.py                         # HR & ACADEMY: Attendance, Courses, Certificates
    ├── sop_routes.py                         # SOP CENTER: إجراءات الشركة الموثقة
    ├── assets_routes.py                       # ASSETS: كاميرات، معدات، صيانة
    ├── requests_routes.py                      # REQUESTS: طلب → Task تلقائي
    └── publish_routes.py                        # PUBLISHING: نشر على السوشيال ميديا (mock/live)
```

---

## 7) نظام الصلاحيات (Roles)

كل الـ Roles من المستند الأصلي متضمنة: founder, admin, sales, sales_manager, content_manager, content_creator, model, moderator, designer, video_editor, developer, project_manager, accountant.

الـ `founder` و `admin` عندهم صلاحية كاملة تلقائيًا على أي endpoint داخل الـ tenant بتاعهم فقط. باقي الـ Roles بتتقيد بـ `@roles_required(...)`.

---

## 8) أوتوميشن مبني بالفعل

- Lead جديد + Assigned Sales → Notification تلقائي
- Deal بيتقفل "won" → Income transaction بيتسجل تلقائي في الـ Finance
- Content بيتوافق عليه "approved" → Calendar entry بيتعمل تلقائي
- Content بينشر (حتى Mock) → حالته بتتحول "published" + الكالندر بيتحدث تلقائي
- Salary بتتدفع → Expense transaction بيتسجل تلقائي
- طلب (Request) جديد → Task بيتعمل تلقائي في مشروع "Requests Inbox"
- كورس يوصل 100% إتمام → شهادة بتتصدر تلقائي
- كل Create/Update بيتسجل في `audit_log` مع IP الطلب

---

## 9) الخطوات الجاية (Roadmap)

1. ~~AI Center~~ ✅ 2. ~~Frontend bilingual~~ ✅ 3. ~~HR & Academy~~ ✅ 4. ~~SOP Center~~ ✅ 5. ~~Assets~~ ✅ 6. ~~Requests automation~~ ✅ 7. ~~Multi-tenant~~ ✅ 8. ~~2FA + Sessions~~ ✅ 9. ~~Kanban + Calendar~~ ✅ 10. ~~Publishing (mock)~~ ✅ 11. ~~Attendance anti-fraud~~ ✅ 12. ~~Creator Portal~~ ✅ 13. ~~تصميم احترافي (LinkedIn/Facebook style)~~ ✅

**لسه محتاج شغل حقيقي (محتاج بيئة إنتاج فعلية عشان تختبره):**
- تفعيل الـ Publishing الفعلي (API keys حقيقية لكل منصة)
- اختبار PostgreSQL على سيرفر حقيقي
- Billing/subscription management للـ tenants (لو هيبقى SaaS مدفوع فعلي)
- Rate limiting على مستوى الـ API (مش بس الـ login)

**باقي من القايمة الأصلية (لسه معمولاش):**
- 📁 رفع وتخزين الملفات الفعلي (عقود، تصاميم، فيديوهات) — دلوقتي بس روابط نصية
- 💬 Internal Communication / Team Chat حقيقي
- 🔔 إشعارات فعلية (Push/Email/SMS) — دلوقتي بتتسجل في الداتابيز بس
- 📊 CEO Reports مجدولة تلقائيًا (يومي/أسبوعي/شهري)
- ⚙️ Automation Engine قابل للتخصيص من الواجهة (بدون كود)

---

## 10) ملاحظات تقنية مهمة

- الداتابيز الافتراضية SQLite (ملف `codela.db`) — مناسب للتطوير والتجربة وحتى مشاريع صغيرة. للـ SaaS فعلي بعدد tenants كبير، استخدم PostgreSQL (شوف قسم 4).
- الباسوردات متخزنة hashed (`werkzeug.security`)، والـ refresh tokens متخزنة كـ hash بس (SHA-256)، مش الأصلي.
- الـ `SECRET_KEY` الافتراضي للتطوير فقط — لازم يتغير عن طريق `CODELA_SECRET_KEY` قبل أي نشر حقيقي.
- الواجهة (`frontend/index.html` + `frontend/app.js`) تعمل بدون build step — عربي/إنجليزي بالكامل. JavaScript أصبح ملفًا خارجيًا مع CSP-safe event delegation، وكل النصوص في object واحد (`STR`) سهل تضيف عليه لغة تالتة.
- الـ AI Center بيستخدم Anthropic API لو `ANTHROPIC_API_KEY` متظبط، وبيرجع تلقائيًا لمنطق rule-based لو مفيش مفتاح — مفيش نقطة فشل حرجة في أي مكان في السيستم، كل حاجة ليها fallback.

## Security hardening update (Tenant Isolation)

This build adds a tenant-isolation regression layer and tightens common IDOR paths.

- Resource reads/updates that accept IDs are tenant-scoped where applicable.
- Cross-tenant foreign-key IDs (users, clients, projects, leads, deals) are rejected on key write paths.
- CORS no longer uses `*`; allowed origins come from `CODELA_CORS_ORIGINS`.
- Security headers include CSP, Permissions-Policy, Referrer-Policy, X-Content-Type-Options and X-Frame-Options. HSTS is enabled in production mode.
- Production requires `CODELA_SECRET_KEY` with at least 32 characters.
- Run `python security_regression_test.py` in an environment with the project requirements installed.

The test suite is intentionally focused on the highest-risk cross-tenant IDOR scenarios and should be expanded as new resources/endpoints are added.


## Production hardening (v3)

- Run `python manage.py migrate` (or `python migrate.py up`) before deployment.
- Run the durable worker with `python worker.py`; production automation can be made asynchronous with `CODELA_AUTOMATION_ASYNC=1`.
- Configure `CODELA_SECRET_KEY` (32+ random characters), `CODELA_CORS_ORIGINS` with HTTPS origins, `CODELA_METRICS_TOKEN`, and `CODELA_TRUSTED_PROXY_COUNT` when behind a proxy.
- `/api/health` is liveness, `/api/ready` is database readiness, and `/api/metrics` exposes minimal operational counters.
- Bearer authentication is not CSRF-vulnerable by itself. If cookie authentication is enabled (`CODELA_COOKIE_AUTH=1`), state-changing requests require `X-CSRF-Token`.
- API inputs have centralized size/depth/type validation; endpoint-specific strict schemas can be added through `strict_json`.
- Audit entries sanitize secrets and capture request ID, IP, and user agent.

## Production Hardening — V2

The current build includes the full hardening track before live integrations:

- Tenant isolation / IDOR checks, including tenant-owned foreign-key validation.
- Central JSON payload guard, field/type validation primitives, payload size/depth limits, and pagination limits.
- CORS allow-list, CSP, HSTS in production, Permissions-Policy, Referrer-Policy, COOP/CORP and `nosniff`.
- Optional cookie-auth CSRF enforcement via `CODELA_COOKIE_AUTH=1`; the normal Bearer-token API remains CSRF-resistant by design.
- Database migration/version tracking with `python manage.py migrate`, `version`, and `downgrade --to N`.
- Durable background jobs with retries, exponential backoff, timeout, failed/dead state and idempotency keys.
- Audit logging with tenant/actor/resource/request correlation, IP/user-agent and secret redaction.
- Production secret validation and current/previous signing-key rotation support.
- Structured request logs, request IDs, readiness and metrics endpoints.
- Security regression tests for cross-tenant access, FK IDOR, refresh rotation, logout revocation and headers.
- Frontend API centralization, request correlation, escaping helpers and safer URL handling.

### Production startup

Set at minimum:

```text
CODELA_ENV=production
CODELA_SECRET_KEY=<32+ random characters>
CODELA_CORS_ORIGINS=https://your-frontend.example
DATABASE_URL=postgresql://...
```

For secret rotation, temporarily set `CODELA_SECRET_KEY_PREVIOUS` to the old signing key while issuing new tokens with `CODELA_SECRET_KEY`.

### Migrations

```bash
python manage.py migrate
python manage.py version
python manage.py downgrade --to 1
```

Run migrations in a controlled deployment step and take a database backup before destructive downgrades.

### Background worker

```bash
python worker.py
```

One-shot processing for deployment checks:

```bash
python worker.py --once --limit 10
```

### Seeding

Demo users are no longer seeded with a hard-coded password. Set `CODELA_SEED_PASSWORD` (12+ characters) before running `seed.py`.

### Live integrations

WhatsApp, Email, Social Publishing and AI remain adapter-based. The hardened build provides the queue and isolation boundaries needed to wire real providers without coupling provider failures to the request path. Provider credentials belong in a secret manager/environment, never source control.

## Final hardening additions

- Dependency-free fixed-window rate limiting for API/auth endpoints (local safety net).
- SQLite busy timeout + WAL mode for safer concurrent access.
- Atomic background-job claim guard to reduce duplicate execution across workers.
- Gunicorn production configuration and hardened Docker deployment files.
- SQLite/PostgreSQL backup scripts with seven-day local retention.
- Production deployment/rollback/secret-rotation runbook.
- Production environment sanity-check script.

For horizontally scaled deployments, enforce rate limiting at the gateway/shared store rather than relying on the in-process limiter.

## Domain Foundation v13

The project now includes an additive domain foundation for the OS-level workflows:

- Organization: `departments`, `positions`, `employees`, status history
- RBAC foundation: `roles`, `permissions`, `role_permissions`, `user_roles`
- Client account model: `client_contacts`, `client_users`, `client_addresses`
- Delivery model: `project_members`, milestones, deliverables, approvals, activities
- Task execution: dependencies/watchers/time entries and project cost linkage
- Finance linkage: project budgets/costs, expenses, quotes, profitability read model
- Files and communication: `files`, `file_links`, conversations and attachments
- Academy foundation: students, instructors, course instructors, attendance, assessments
- Content workflow: briefs, versions, approvals and assets
- Request workflow extension: requester identity/type, project, assignment and resolution fields

The change is intentionally additive. Existing tables and legacy role fields remain for compatibility while new services/policies are introduced. Migration version `13` installs the foundation for existing databases; migration `14` completes the next operational workflow layer.

### New API groups

- `/api/departments`
- `/api/employees`
- `/api/clients/:id/contacts`
- `/api/clients/:id/users`
- `/api/projects/:id/members`
- `/api/projects/:id/milestones`
- `/api/projects/:id/deliverables`
- `/api/deliverables/:id/approval`
- `/api/approvals/:id`
- `/api/projects/:id/financials`
- `/api/tasks/:id/time`
- `/api/requests/:id/assign`
- `/api/requests/:id/resolve`
- `/api/client/me`
- `/api/client/projects`
- `/api/client/requests`

Run `python manage.py migrate` after deploying this version. Existing data is not deleted by migrations 13 or 14.

## Operational Workflow v14

Migration `14` completes the next operational layer without destructive changes:

- Won Deal -> Delivery Project handoff
- Project workspace aggregate: team, milestones, tasks, deliverables, requests, approvals, financials
- Project-member enforcement for task assignment
- Request -> Project -> Task assignment workflow
- Client Portal Project-linked requests
- Project budgets and expenses
- Project invoice creation from the delivery workspace for finance roles
- Deliverable approval lookup/decision flow
- Employee, position and workspace-user selectors
- Task completion/assignment domain events for automation

Run `python manage.py migrate` (or `python migrate.py up`) after deploying. Migration 14 is additive and does not delete existing data.

## v14 API additions

- `/api/positions`
- `/api/workspace/users`
- `/api/projects/:id/workspace`
- `/api/projects/:id/budget`
- `/api/projects/:id/expenses`
- `/api/deliverables/:id/approval` (GET/POST)
- `/api/requests/:id/assign` (workflow-aware)

## Current domain release
The current bundled release is **v15 Complete Operating Layer**. See `RELEASE_V15_COMPLETE.md` for the integrated organization, client portal, project delivery, HR/payroll, academy, content, communication, files, reporting, settings and notification additions.
