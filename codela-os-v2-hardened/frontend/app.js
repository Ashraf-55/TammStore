
/* ============================================================
   CODELA OS — Frontend (vanilla JS, bilingual AR/EN)
   ============================================================ */

const API_URL = '/api';
let ACCESS_TOKEN = null;
let REFRESH_TOKEN = null;
let COOKIE_AUTH = true;
let CURRENT_USER = null;
let PRE_AUTH_TOKEN = null; // transient, only used mid-2FA-challenge, never persisted
let LANG = localStorage.getItem('codela_lang') || 'ar';
let currentPage = 'dashboard';

/* ---------------- i18n ---------------- */
const STR = {
  loginTitle: {ar:'تسجيل الدخول', en:'Sign in'},
  email: {ar:'البريد الإلكتروني', en:'Email'},
  password: {ar:'كلمة المرور', en:'Password'},
  loginBtn: {ar:'دخول', en:'Sign in'},
  demoHint: {ar:'استخدم بيانات الدخول التي يحددها مدير النظام',
             en:'Use the credentials configured by your administrator.'},
  apiUrlLabel: {ar:'رابط الـ API', en:'API URL'},
  tagline: {ar:'مركز إدارة العمليات', en:'Operations Command Center'},
  logout: {ar:'تسجيل الخروج', en:'Log out'},
  nav_dashboard: {ar:'الرئيسية', en:'Dashboard'},
  nav_leads: {ar:'العملاء المحتملين', en:'Leads'},
  nav_clients: {ar:'العملاء', en:'Clients'},
  nav_deals: {ar:'الصفقات', en:'Deals'},
  nav_projects: {ar:'المشاريع', en:'Projects'},
  nav_people: {ar:'الموظفون', en:'People'},
  nav_client_portal: {ar:'بوابة العميل', en:'Client Portal'},
  page_people: {ar:'الموظفون والتنظيم', en:'People & Organization'},
  page_client_portal: {ar:'بوابة العميل', en:'Client Portal'},
  employee: {ar:'موظف', en:'Employee'},
  department: {ar:'القسم', en:'Department'},
  position: {ar:'المنصب', en:'Position'},
  projectMembers: {ar:'فريق المشروع', en:'Project Team'},
  milestones: {ar:'المراحل', en:'Milestones'},
  deliverables: {ar:'التسليمات', en:'Deliverables'},
  approvals: {ar:'الموافقات', en:'Approvals'},
  financials: {ar:'الملخص المالي', en:'Financial Summary'},
  contacts: {ar:'جهات الاتصال', en:'Contacts'},
  createRequest: {ar:'إنشاء طلب', en:'Create Request'},
  approve: {ar:'اعتماد', en:'Approve'},
  reject: {ar:'رفض', en:'Reject'},
  assign: {ar:'تعيين', en:'Assign'},
  addMember: {ar:'+ عضو', en:'+ Member'},
  addMilestone: {ar:'+ مرحلة', en:'+ Milestone'},
  addDeliverable: {ar:'+ تسليم', en:'+ Deliverable'},
  setBudget: {ar:'تحديد الميزانية', en:'Set Budget'},
  addExpense: {ar:'إضافة مصروف', en:'Add Expense'},
  logTime: {ar:'تسجيل وقت', en:'Log Time'},
  requestApproval: {ar:'طلب اعتماد', en:'Request Approval'},
  approve: {ar:'اعتماد', en:'Approve'},
  changesRequested: {ar:'طلب تعديلات', en:'Request Changes'},
  invoice: {ar:'فاتورة', en:'Invoice'},
  createInvoice: {ar:'إنشاء فاتورة', en:'Create Invoice'},
  recordPayment: {ar:'تسجيل دفعة', en:'Record Payment'},
  budget: {ar:'الميزانية', en:'Budget'},
  hours: {ar:'الساعات', en:'Hours'},
  workDate: {ar:'تاريخ العمل', en:'Work Date'},
  requestAssignment: {ar:'تعيين الطلب', en:'Assign Request'},
  project: {ar:'المشروع', en:'Project'},
  employee: {ar:'موظف', en:'Employee'},
  user: {ar:'مستخدم', en:'User'},
  nav_media: {ar:'المحتوى', en:'Media'},
  nav_finance: {ar:'المالية', en:'Finance'},
  page_dashboard: {ar:'اللوحة الرئيسية', en:'Executive Dashboard'},
  page_leads: {ar:'العملاء المحتملين (CRM)', en:'Leads (CRM)'},
  page_clients: {ar:'العملاء', en:'Clients'},
  page_deals: {ar:'الصفقات', en:'Deals'},
  page_projects: {ar:'المشاريع والمهام', en:'Projects & Tasks'},
  page_media: {ar:'المحتوى والنشر', en:'Media & Content'},
  page_finance: {ar:'المالية', en:'Finance'},
  sales: {ar:'المبيعات', en:'Sales'},
  projectsKpi: {ar:'المشاريع', en:'Projects'},
  media: {ar:'المحتوى', en:'Media'},
  finance: {ar:'المالية', en:'Finance'},
  totalLeads: {ar:'إجمالي الـ Leads', en:'Total Leads'},
  newLeads: {ar:'جديدة', en:'New'},
  qualified: {ar:'مؤهلة', en:'Qualified'},
  dealsWon: {ar:'صفقات مقفولة', en:'Deals Won'},
  revenue: {ar:'الإيرادات', en:'Revenue'},
  conversion: {ar:'معدل التحويل', en:'Conversion'},
  active: {ar:'نشطة', en:'Active'},
  delayed: {ar:'متأخرة', en:'Delayed'},
  completed: {ar:'مكتملة', en:'Completed'},
  totalContent: {ar:'إجمالي المحتوى', en:'Total Content'},
  published: {ar:'منشور', en:'Published'},
  views: {ar:'المشاهدات', en:'Views'},
  engagement: {ar:'التفاعل', en:'Engagement'},
  income: {ar:'الدخل', en:'Income'},
  expenses: {ar:'المصروفات', en:'Expenses'},
  profit: {ar:'الأرباح', en:'Profit'},
  pendingSalaries: {ar:'رواتب معلقة', en:'Pending Salaries'},
  aiBriefing: {ar:'ملخص اليوم الذكي', en:'AI Daily Briefing'},
  refresh: {ar:'تحديث', en:'Refresh'},
  addLead: {ar:'+ إضافة Lead', en:'+ Add Lead'},
  name: {ar:'الاسم', en:'Name'},
  company: {ar:'الشركة', en:'Company'},
  status: {ar:'الحالة', en:'Status'},
  score: {ar:'التقييم', en:'Score'},
  budget: {ar:'الميزانية', en:'Budget'},
  actions: {ar:'إجراءات', en:'Actions'},
  all: {ar:'الكل', en:'All'},
  save: {ar:'حفظ', en:'Save'},
  cancel: {ar:'إلغاء', en:'Cancel'},
  delete: {ar:'حذف', en:'Delete'},
  requests: {ar:'الطلبات', en:'Requests'},
  aiRescore: {ar:'✦ إعادة تقييم AI', en:'✦ AI Re-score'},
  convert: {ar:'تحويل لعميل', en:'Convert to Client'},
  draftMsg: {ar:'✦ صياغة رسالة', en:'✦ Draft Message'},
  addProject: {ar:'+ مشروع جديد', en:'+ New Project'},
  addTask: {ar:'+ مهمة', en:'+ Task'},
  addContent: {ar:'+ فكرة محتوى', en:'+ Content Idea'},
  aiGenerate: {ar:'✦ توليد أفكار AI', en:'✦ Generate with AI'},
  bestContent: {ar:'أفضل محتوى', en:'Best Performing Content'},
  addTransaction: {ar:'+ عملية مالية', en:'+ Transaction'},
  noAccess: {ar:'ليس لديك صلاحية لعرض هذا القسم', en:'You do not have access to this section'},
  loading: {ar:'جارِ التحميل...', en:'Loading...'},
  noData: {ar:'لا توجد بيانات بعد', en:'No data yet'},
  source: {ar:'المصدر', en:'Source'},
  industry: {ar:'المجال', en:'Industry'},
  phone: {ar:'الهاتف', en:'Phone'},
  followup: {ar:'المتابعة القادمة', en:'Next Follow-up'},
  addActivity: {ar:'+ إضافة نشاط', en:'+ Add Activity'},
  activityType: {ar:'نوع النشاط', en:'Activity Type'},
  content: {ar:'التفاصيل', en:'Content'},
  saved: {ar:'تم الحفظ', en:'Saved'},
  errorOccurred: {ar:'حدث خطأ', en:'An error occurred'},
  niche: {ar:'المجال', en:'Niche'},
  platform: {ar:'المنصة', en:'Platform'},
  title: {ar:'العنوان', en:'Title'},
  hook: {ar:'الافتتاحية (Hook)', en:'Hook'},
  category: {ar:'التصنيف', en:'Category'},
  priority: {ar:'الأولوية', en:'Priority'},
  deadline: {ar:'الموعد النهائي', en:'Deadline'},
  assignee: {ar:'المسؤول', en:'Assignee'},
  amount: {ar:'المبلغ', en:'Amount'},
  type: {ar:'النوع', en:'Type'},
  description: {ar:'الوصف', en:'Description'},
  invalidCreds: {ar:'بيانات الدخول غير صحيحة', en:'Invalid credentials'},
  tier_hot: {ar:'ساخن', en:'Hot'},
  tier_warm: {ar:'دافئ', en:'Warm'},
  tier_cold: {ar:'بارد', en:'Cold'},

  nav_requests: {ar:'الطلبات', en:'Requests'},
  nav_hr: {ar:'الحضور', en:'Attendance'},
  nav_academy: {ar:'الأكاديمية', en:'Academy'},
  nav_sop: {ar:'الإجراءات', en:'SOP Center'},
  nav_assets: {ar:'الأصول والمعدات', en:'Assets'},
  nav_creators: {ar:'الموديلز', en:'Creators'},
  nav_portal_tasks: {ar:'مهامي', en:'My Tasks'},
  nav_portal_content: {ar:'محتواي', en:'My Content'},
  nav_portal_submit: {ar:'ارفع محتوى', en:'Submit Content'},
  page_creators: {ar:'إدارة الموديلز', en:'Creator Management'},
  page_portal_tasks: {ar:'مهامي', en:'My Tasks'},
  page_portal_content: {ar:'محتواي', en:'My Content'},
  page_portal_submit: {ar:'ارفع محتوى جديد', en:'Submit New Content'},
  page_requests: {ar:'الطلبات', en:'Requests'},
  page_hr: {ar:'الحضور والانصراف', en:'Attendance'},
  page_academy: {ar:'أكاديمية Codela', en:'Codela Academy'},
  page_sop: {ar:'مركز الإجراءات', en:'SOP Center'},
  page_assets: {ar:'الأصول والمعدات', en:'Assets & Equipment'},

  addRequest: {ar:'+ طلب جديد', en:'+ New Request'},
  requesterName: {ar:'اسم مقدم الطلب', en:'Requester Name'},
  requesterContact: {ar:'وسيلة التواصل', en:'Contact'},
  requestType: {ar:'نوع الطلب', en:'Request Type'},
  linkedTask: {ar:'المهمة المرتبطة', en:'Linked Task'},
  autoTaskNote: {ar:'ملحوظة: أي طلب جديد بيتحول تلقائيًا لمهمة في المشاريع.', en:'Note: every new request automatically creates a linked task in Projects.'},

  checkIn: {ar:'تسجيل حضور', en:'Check In'},
  checkOut: {ar:'تسجيل انصراف', en:'Check Out'},
  myAttendance: {ar:'سجل حضوري', en:'My Attendance'},
  date: {ar:'التاريخ', en:'Date'},

  courses: {ar:'الدورات', en:'Courses'},
  addCourse: {ar:'+ دورة جديدة', en:'+ New Course'},
  enroll: {ar:'التحاق', en:'Enroll'},
  lessons: {ar:'الدروس', en:'Lessons'},
  progress: {ar:'التقدم', en:'Progress'},
  myCertificates: {ar:'شهاداتي', en:'My Certificates'},
  weeks: {ar:'أسابيع', en:'weeks'},
  markComplete: {ar:'إتمام الدرس', en:'Mark Complete'},

  addSop: {ar:'+ إجراء جديد', en:'+ New SOP'},
  searchSop: {ar:'بحث في الإجراءات...', en:'Search procedures...'},
  category: {ar:'التصنيف', en:'Category'},

  addAsset: {ar:'+ أصل جديد', en:'+ New Asset'},
  logMaintenance: {ar:'تسجيل صيانة', en:'Log Maintenance'},
  owner: {ar:'المسؤول', en:'Owner'},
  location: {ar:'الموقع', en:'Location'},
  value: {ar:'القيمة', en:'Value'},

  tabLogin: {ar:'دخول', en:'Log In'},
  tabRegister: {ar:'إنشاء شركة جديدة', en:'Create Workspace'},
  workspaceSlug: {ar:'معرّف الشركة (لو عندك أكتر من شركة بنفس الإيميل)', en:'Workspace ID (if this email is used in multiple workspaces)'},
  twoFaCode: {ar:'كود التحقق من تطبيق المصادقة', en:'Code from your authenticator app'},
  verify: {ar:'تأكيد', en:'Verify'},
  companyName: {ar:'اسم الشركة', en:'Company Name'},
  yourName: {ar:'اسمك', en:'Your Name'},
  createWorkspace: {ar:'إنشاء الشركة', en:'Create Workspace'},

  nav_kanban: {ar:'لوحة المهام', en:'Kanban'},
  nav_calendar: {ar:'التقويم', en:'Calendar'},
  nav_security: {ar:'الأمان', en:'Security'},
  page_security: {ar:'إعدادات الأمان', en:'Security Settings'},
  listView: {ar:'عرض قائمة', en:'List View'},
  kanbanView: {ar:'لوحة Kanban', en:'Kanban Board'},
  calendarView: {ar:'عرض تقويم', en:'Calendar View'},

  enable2fa: {ar:'تفعيل التحقق بخطوتين', en:'Enable Two-Factor Auth'},
  disable2fa: {ar:'تعطيل التحقق بخطوتين', en:'Disable Two-Factor Auth'},
  scanQr: {ar:'امسح الكود ده بتطبيق المصادقة (Google Authenticator أو مشابه)، وبعدين أدخل الكود اللي هيظهر', en:'Scan this with your authenticator app (Google Authenticator or similar), then enter the code it shows'},
  confirmCode: {ar:'كود التأكيد', en:'Confirmation Code'},
  activeSessions: {ar:'الجلسات النشطة', en:'Active Sessions'},
  revoke: {ar:'إلغاء', en:'Revoke'},
  logoutAllSessions: {ar:'تسجيل الخروج من كل الأجهزة', en:'Log Out All Devices'},
  device: {ar:'الجهاز', en:'Device'},
  lastActive: {ar:'آخر نشاط', en:'Last Active'},
  twoFaStatus: {ar:'حالة التحقق بخطوتين', en:'2FA Status'},
  enabled: {ar:'مفعّل', en:'Enabled'},
  notEnabled: {ar:'غير مفعّل', en:'Not enabled'},

  publish: {ar:'نشر', en:'Publish'},
  publishNow: {ar:'انشر الآن', en:'Publish Now'},
  publishLog: {ar:'سجل النشر', en:'Publish Log'},
  mockModeNote: {ar:'ملحوظة: النشر بيشتغل في وضع تجريبي (Mock) لحد ما تربط حساب حقيقي.', en:'Note: publishing runs in mock mode until you connect a real account.'},

  teamAttendance: {ar:'حضور الفريق', en:'Team Attendance'},
  flagged: {ar:'مشتبه فيه', en:'Flagged'},
  ok: {ar:'سليم', en:'OK'},
  clearFlag: {ar:'تأكيد سليم', en:'Clear Flag'},
  officeLocation: {ar:'موقع المكتب', en:'Office Location'},
  officeLocationNote: {ar:'أي حضور خارج النطاق ده هيتعلّم كـ"مشتبه فيه" تلقائيًا عشان تراجعه.', en:'Any check-in outside this radius is automatically flagged for your review.'},
  latitude: {ar:'خط العرض', en:'Latitude'},
  longitude: {ar:'خط الطول', en:'Longitude'},
  radiusMeters: {ar:'النطاق المسموح (متر)', en:'Allowed radius (meters)'},
  useMyLocation: {ar:'استخدم موقعي الحالي', en:'Use My Current Location'},
  locatingNote: {ar:'جارِ تحديد موقعك...', en:'Detecting your location...'},
  noLocationNote: {ar:'مفيش وصول لموقعك — هيتسجل الحضور لكن هيتعلّم للمراجعة', en:'No location access — check-in will still be recorded but flagged for review'},

  creatorPortal: {ar:'بوابة الموديلز', en:'Creator Portal'},
  myTasks: {ar:'مهامي', en:'My Tasks'},
  myContent: {ar:'محتواي', en:'My Content'},
  submitContent: {ar:'ارفع محتوى جديد', en:'Submit New Content'},
  createLogin: {ar:'إنشاء حساب دخول خاص', en:'Create dedicated login'},
  loginCode: {ar:'رقم الدخول', en:'Login ID'},
  tempPassword: {ar:'كلمة مرور مؤقتة', en:'Temporary password'},
  portalCredentialsNote: {ar:'احفظ البيانات دي وابعتها للموديل — مش هتتعرض تاني', en:'Save these and send them to the model — they will not be shown again'},
  videoUrl: {ar:'رابط الفيديو', en:'Video URL'},
  submitted: {ar:'المُرسِل', en:'Submitted by'},
};
function t(key){ return (STR[key] && STR[key][LANG]) || key; }

// Escape untrusted API data before inserting it into HTML. Keep this small
// helper centralized so every table/card renderer can safely use innerHTML
// for trusted UI templates without exposing stored user content as markup.
function esc(value){
  return String(value ?? '').replace(/[&<>\"']/g, ch => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  })[ch]);
}
function safeUrl(value){
  try{
    const u = new URL(String(value ?? ''), window.location.origin);
    return ['http:', 'https:'].includes(u.protocol) ? u.href : '';
  }catch(e){ return ''; }
}
function jsArg(value){ return esc(JSON.stringify(String(value ?? ''))); }


function applyStaticTranslations(){
  document.querySelectorAll('[data-t]').forEach(el=>{
    const key = el.getAttribute('data-t');
    el.textContent = t(key);
  });
  document.getElementById('htmlRoot').setAttribute('lang', LANG);
  document.getElementById('htmlRoot').setAttribute('dir', LANG === 'ar' ? 'rtl' : 'ltr');
  document.querySelectorAll('.lang-toggle span').forEach(s=>{
    s.classList.toggle('active', s.getAttribute('data-lang') === LANG);
  });
}
function setLang(lang){
  LANG = lang;
  localStorage.setItem('codela_lang', lang);
  applyStaticTranslations();
  if(ACCESS_TOKEN){ renderNav(); loadPage(currentPage); checkAiStatus(); }
}
document.getElementById('langToggleLogin').addEventListener('click', (e)=>{
  const l = e.target.getAttribute('data-lang'); if(l) setLang(l);
});
document.getElementById('langToggleApp').addEventListener('click', (e)=>{
  const l = e.target.getAttribute('data-lang'); if(l) setLang(l);
});

/* ---------------- API helper (with auto-refresh on expired access token) ---------------- */
async function apiRaw(path, options={}){
  const opts = Object.assign({ headers: {} }, options);
  opts.headers['Content-Type'] = 'application/json';
  opts.headers['X-Request-ID'] = (crypto.randomUUID ? crypto.randomUUID() : ('req-' + Date.now()));
  if(ACCESS_TOKEN) opts.headers['Authorization'] = 'Bearer ' + ACCESS_TOKEN;
  opts.credentials = 'include';
  const csrf = document.cookie.split('; ').find(x=>x.startsWith('codela_csrf='));
  if(csrf) opts.headers['X-CSRF-Token'] = decodeURIComponent(csrf.split('=')[1]);
  if(opts.body && typeof opts.body !== 'string') opts.body = JSON.stringify(opts.body);
  const res = await fetch(API_URL + path, opts);
  let data = null;
  try{ data = await res.json(); }catch(e){}
  return { res, data };
}

async function api(path, options={}){
  let { res, data } = await apiRaw(path, options);
  if(!res.ok && data && data.code === 'token_expired'){
    // transparently refresh once, then retry the original call
    try{
      const r = await apiRaw('/auth/refresh', { method:'POST' });
      if(r.res.ok){
        ACCESS_TOKEN = r.data.access_token;
        // access token stays memory-only; refresh uses the HttpOnly cookie
        ({ res, data } = await apiRaw(path, options));
      }
    }catch(e){}
  }
  if(!res.ok){
    if(res.status === 401 && data && data.code === 'token_expired'){
      logout(); // refresh failed too — session is truly gone
    }
    const msg = (data && data.error) ? data.error : t('errorOccurred');
    throw new Error(msg);
  }
  return data;
}

function showToast(msg, isError=false){
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast visible' + (isError ? ' error' : '');
  setTimeout(()=> el.classList.remove('visible'), 2800);
}

/* ---------------- Auth ---------------- */
function switchAuthTab(tab){
  document.querySelectorAll('.auth-tab').forEach(el=>{
    const active = el.getAttribute('data-tab') === tab;
    el.style.color = active ? 'var(--gold)' : 'var(--text-faint)';
    el.style.borderBottomColor = active ? 'var(--gold)' : 'transparent';
  });
  document.getElementById('loginFormBlock').classList.toggle('hidden', tab !== 'login');
  document.getElementById('registerFormBlock').classList.toggle('hidden', tab !== 'register');
  document.getElementById('twoFaBlock').classList.add('hidden');
  document.getElementById('authTabs').classList.toggle('hidden', tab === '2fa');
  document.getElementById('loginError').classList.add('hidden');
}

function persistSession(data){
  ACCESS_TOKEN = data.access_token; REFRESH_TOKEN = null; CURRENT_USER = data.user;
  // access token stays memory-only; refresh uses the HttpOnly cookie
}

async function doLogin(){
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  const tenantSlug = document.getElementById('loginTenantSlug').value.trim();
  const errEl = document.getElementById('loginError');
  errEl.classList.add('hidden');
  if(!email || !password) return;
  const btn = document.getElementById('loginBtn');
  btn.disabled = true;
  try{
    const body = {email, password};
    if(tenantSlug) body.tenant_slug = tenantSlug;
    const data = await api('/auth/login', { method:'POST', body });
    if(data.requires_2fa){
      PRE_AUTH_TOKEN = data.pre_auth_token;
      document.getElementById('authTabs').classList.add('hidden');
      document.getElementById('loginFormBlock').classList.add('hidden');
      document.getElementById('twoFaBlock').classList.remove('hidden');
      return;
    }
    persistSession(data);
    enterApp();
  }catch(e){
    if(e.message === 'tenant_ambiguous' || /Multiple workspaces/.test(e.message)){
      document.getElementById('tenantSlugField').classList.remove('hidden');
    }
    errEl.textContent = e.message || t('invalidCreds');
    errEl.classList.remove('hidden');
  }finally{
    btn.disabled = false;
  }
}
document.getElementById('loginPassword').addEventListener('keydown', e=>{ if(e.key==='Enter') doLogin(); });

async function submitTwoFaLogin(){
  const code = document.getElementById('twoFaCodeInput').value.trim();
  const errEl = document.getElementById('loginError');
  try{
    const data = await api('/auth/2fa/login-verify', { method:'POST', body:{ pre_auth_token: PRE_AUTH_TOKEN, code } });
    persistSession(data);
    enterApp();
  }catch(e){
    errEl.textContent = e.message; errEl.classList.remove('hidden');
  }
}

async function doRegister(){
  const body = {
    company_name: val('regCompany'), name: val('regName'),
    email: val('regEmail'), password: val('regPassword'),
  };
  const errEl = document.getElementById('loginError');
  errEl.classList.add('hidden');
  const btn = document.getElementById('registerBtn');
  btn.disabled = true;
  try{
    const data = await api('/auth/register', { method:'POST', body });
    persistSession(data);
    enterApp();
  }catch(e){
    errEl.textContent = e.message; errEl.classList.remove('hidden');
  }finally{
    btn.disabled = false;
  }
}

async function logout(){
  try{ if(ACCESS_TOKEN) await apiRaw('/auth/logout', {method:'POST'}); }catch(e){}
  ACCESS_TOKEN = null; REFRESH_TOKEN = null; CURRENT_USER = null;
  ACCESS_TOKEN = null;
  document.getElementById('appShell').classList.remove('visible');
  document.getElementById('loginScreen').style.display = 'flex';
  switchAuthTab('login');
}


/* ---------------- Nav / role visibility ---------------- */
const NAV_ITEMS = [
  {key:'dashboard', icon:'◆', roles:null},
  {key:'leads', icon:'→', roles:null},
  {key:'clients', icon:'◈', roles:null},
  {key:'deals', icon:'$', roles:null},
  {key:'projects', icon:'▤', roles:null},
  {key:'people', icon:'♙', roles:['founder','admin','project_manager','sales_manager','content_manager']},
  {key:'media', icon:'▶', roles:null},
  {key:'finance', icon:'£', roles:['accountant','sales_manager','founder','admin']},
  {key:'requests', icon:'✉', roles:null},
  {key:'hr', icon:'◷', roles:null},
  {key:'academy', icon:'◫', roles:null},
  {key:'sop', icon:'▦', roles:null},
  {key:'assets', icon:'⚙', roles:null},
  {key:'creators', icon:'★', roles:['content_manager','founder','admin']},
  {key:'security', icon:'⛨', roles:null},
  {key:'ops', icon:'⌘', roles:null},
];
const CREATOR_PORTAL_NAV_ITEMS = [
  {key:'portal-tasks', icon:'▤'},
  {key:'portal-content', icon:'▶'},
  {key:'portal-submit', icon:'✦'},
  {key:'security', icon:'⛨'},
];
function isCreatorPortalUser(){ return CURRENT_USER && CURRENT_USER.role === 'model'; }
function canSee(item){
  if(!item.roles) return true;
  if(!CURRENT_USER) return false;
  return item.roles.includes(CURRENT_USER.role) || CURRENT_USER.role === 'founder' || CURRENT_USER.role === 'admin';
}
function renderNav(){
  const nav = document.getElementById('navList');
  nav.innerHTML = '';
  const items = isCreatorPortalUser() ? CREATOR_PORTAL_NAV_ITEMS : NAV_ITEMS.filter(canSee);
  if(!isCreatorPortalUser() && CURRENT_USER && CURRENT_USER.client_portal) items.push({key:'client_portal',icon:'◎'});
  items.forEach(item=>{
    const div = document.createElement('div');
    div.className = 'nav-item' + (currentPage===item.key ? ' active':'');
    div.innerHTML = `<span class="nav-icon">${esc(item.icon)}</span><span>${t(item.key.startsWith('portal-') ? 'nav_'+item.key.replace('portal-','portal_') : 'nav_'+item.key)}</span>`;
    div.onclick = ()=> loadPage(item.key);
    nav.appendChild(div);
  });
}

async function enterApp(){
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('appShell').classList.add('visible');
  document.getElementById('userName').textContent = CURRENT_USER.name;
  document.getElementById('userRole').textContent = CURRENT_USER.role;
  document.getElementById('userAvatar').textContent = CURRENT_USER.name.slice(0,1).toUpperCase();
  applyStaticTranslations();
  try { CURRENT_USER.client_portal = !!(await api('/client/me')); } catch(e) { CURRENT_USER.client_portal = false; }
  renderNav();
  if(isCreatorPortalUser()){
    document.querySelector('.sidebar-logo .subline').textContent = t('creatorPortal');
    loadPage('portal-tasks');
  } else {
    checkAiStatus();
    loadPage('dashboard');
  }
}

async function checkAiStatus(){
  try{
    const s = await api('/ai/status');
    document.getElementById('aiDot').classList.toggle('on', s.ai_enabled);
    document.getElementById('aiStatusText').textContent = 'AI ' + (s.ai_enabled ? (LANG==='ar'?'مفعّل':'Active') : (LANG==='ar'?'احتياطي':'Fallback'));
  }catch(e){}
}

/* ---------------- Page router ---------------- */
async function loadPage(page){
  currentPage = page;
  renderNav();
  document.getElementById('pageTitle').textContent = t('page_'+page.replace(/-/g,'_'));
  const content = document.getElementById('content');
  content.innerHTML = `<div class="empty-state">${t('loading')}</div>`;
  try{
    if(page==='dashboard') await renderDashboard();
    else if(page==='leads') await renderLeads();
    else if(page==='clients') await renderClients();
    else if(page==='deals') await renderDeals();
    else if(page==='projects') await renderProjects();
    else if(page==='people') await renderPeople();
    else if(page==='client_portal') await renderClientPortal();
    else if(page==='media') await renderMedia();
    else if(page==='finance') await renderFinance();
    else if(page==='requests') await renderRequests();
    else if(page==='hr') await renderHr();
    else if(page==='academy') await renderAcademy();
    else if(page==='sop') await renderSop();
    else if(page==='assets') await renderAssets();
    else if(page==='security') await renderSecurity();
    else if(page==='ops') await renderOps();
    else if(page==='creators') await renderCreators();
    else if(page==='portal-tasks') await renderPortalTasks();
    else if(page==='portal-content') await renderPortalContent();
    else if(page==='portal-submit') await renderPortalSubmit();
  }catch(e){
    content.textContent = e.message || t('errorOccurred'); content.className = 'empty-state';
  }
}

/* ---------------- Dashboard ---------------- */
async function renderDashboard(){
  const content = document.getElementById('content');
  const d = await api('/dashboard');
  content.innerHTML = `
    <div class="ai-box">
      <div class="ai-box-label"><span>${t('aiBriefing')}</span><button class="btn secondary btn-sm" data-onclick="loadAiBriefing()">${t('refresh')}</button></div>
      <div class="ai-box-text" id="aiBriefingText">${t('loading')}</div>
    </div>
    <div class="section-title">${t('sales')}</div>
    <div class="grid grid-4">
      ${ledger(t('totalLeads'), d.sales.total_leads, [[t('newLeads'), d.sales.new_leads],[t('qualified'), d.sales.qualified_leads]])}
      ${ledger(t('dealsWon'), d.sales.deals_won, [[t('conversion'), d.sales.conversion_rate_pct+'%']])}
      ${ledger(t('revenue'), fmtMoney(d.sales.revenue), [])}
      ${ledger(t('conversion'), d.sales.conversion_rate_pct+'%', [])}
    </div>
    <div class="section-title">${t('projectsKpi')} / ${t('media')}</div>
    <div class="grid grid-4">
      ${ledger(t('active'), d.projects.active, [[t('delayed'), d.projects.delayed],[t('completed'), d.projects.completed]])}
      ${ledger(t('totalContent'), d.media.total_content, [[t('published'), d.media.published]])}
      ${ledger(t('views'), fmtNum(d.media.total_views), [])}
      ${ledger(t('engagement'), fmtNum(d.media.total_engagement), [])}
    </div>
    <div class="section-title">${t('finance')}</div>
    <div class="grid grid-4">
      ${ledger(t('income'), fmtMoney(d.finance.revenue), [])}
      ${ledger(t('expenses'), fmtMoney(d.finance.expenses), [])}
      ${ledger(t('profit'), fmtMoney(d.finance.profit), [])}
      ${ledger(t('pendingSalaries'), d.finance.pending_salaries, [])}
    </div>
  `;
  loadAiBriefing();
}
function ledger(eyebrow, figure, rows){
  return `<div class="ledger">
    <div class="ledger-eyebrow">${eyebrow}</div>
    <div class="ledger-figure mono">${figure}</div>
    <div class="ledger-sub">${rows.map(r=>`<div class="ledger-row"><span>${r[0]}</span><b>${r[1]}</b></div>`).join('')}</div>
  </div>`;
}
function fmtMoney(n){ return (n||0).toLocaleString(LANG==='ar'?'ar-EG':'en-US'); }
function fmtNum(n){ return (n||0).toLocaleString(LANG==='ar'?'ar-EG':'en-US'); }

async function loadAiBriefing(){
  const el = document.getElementById('aiBriefingText');
  if(!el) return;
  el.innerHTML = `<span class="spin">◐</span> ${t('loading')}`;
  try{
    const r = await api('/ai/summary?language='+LANG);
    el.textContent = r.summary;
  }catch(e){ el.textContent = e.message; }
}

/* ---------------- Leads ---------------- */
async function renderLeads(){
  const content = document.getElementById('content');
  const statuses = ['new','contacted','qualified','meeting','proposal','negotiation','won','lost'];
  content.innerHTML = `
    <div class="toolbar">
      <div class="filters">
        <select id="leadStatusFilter" data-onchange="renderLeads()">
          <option value="">${t('status')}: ${t('all')}</option>
          ${statuses.map(s=>`<option value="${s}">${s}</option>`).join('')}
        </select>
      </div>
      <button class="btn" data-onclick="openLeadModal()">${t('addLead')}</button>
    </div>
    <div id="leadsTableWrap"></div>
  `;
  const filter = document.getElementById('leadStatusFilter');
  const status = filter ? filter.value : '';
  const leads = await api('/leads' + (status ? '?status='+status : ''));
  const wrap = document.getElementById('leadsTableWrap');
  if(!leads.length){ wrap.innerHTML = `<div class="empty-state">${t('noData')}</div>`; return; }
  wrap.innerHTML = `<table><thead><tr>
    <th>${t('name')}</th><th>${t('company')}</th><th>${t('status')}</th><th>${t('score')}</th><th>${t('budget')}</th><th>${t('actions')}</th>
  </tr></thead><tbody>
    ${leads.map(l=>`<tr>
      <td>${esc(l.name)}</td>
      <td>${esc(l.company||'—')}</td>
      <td><span class="badge status">${esc(l.status)}</span></td>
      <td><span class="badge ${esc(l.score_tier)}">${esc(l.score)} · ${t('tier_'+l.score_tier)}</span></td>
      <td class="mono">${l.budget ? fmtMoney(l.budget) : '—'}</td>
      <td>
        <button class="btn secondary btn-sm" data-onclick="aiRescoreLead(${esc(l.id)})">${t('aiRescore')}</button>
        <button class="btn secondary btn-sm" data-onclick="openLeadDetail(${esc(l.id)})">›</button>
      </td>
    </tr>`).join('')}
  </tbody></table>`;
}

async function aiRescoreLead(id){
  try{
    showToast(t('loading'));
    const r = await api(`/ai/leads/${id}/score`, {method:'POST'});
    showToast(`${esc(r.tier)} · ${esc(r.score)} — ${esc(r.rationale)}`);
    renderLeads();
  }catch(e){ showToast(e.message, true); }
}

function openLeadModal(){
  showModal(`
    <div class="modal-title">${t('addLead')}</div>
    <div class="field"><label>${t('name')}</label><input id="f_name"></div>
    <div class="field"><label>${t('company')}</label><input id="f_company"></div>
    <div class="field"><label>${t('phone')}</label><input id="f_phone"></div>
    <div class="field"><label>${t('industry')}</label><input id="f_industry"></div>
    <div class="field"><label>${t('budget')}</label><input id="f_budget" type="number"></div>
    <div class="field"><label>${t('source')}</label><input id="f_source" placeholder="referral / website / ..."></div>
    <div class="modal-actions">
      <button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button>
      <button class="btn" data-onclick="submitLead()">${t('save')}</button>
    </div>
  `);
}
async function submitLead(){
  try{
    await api('/leads', {method:'POST', body:{
      name: val('f_name'), company: val('f_company'), phone: val('f_phone'),
      industry: val('f_industry'), budget: parseFloat(val('f_budget'))||0, source: val('f_source'),
    }});
    closeModal(); showToast(t('saved')); renderLeads();
  }catch(e){ showToast(e.message, true); }
}

async function openLeadDetail(id){
  const lead = await api('/leads/'+id);
  showModal(`
    <div class="modal-title">${esc(lead.name)}</div>
    <div class="ledger-row"><span>${t('company')}</span><b>${esc(lead.company||'—')}</b></div>
    <div class="ledger-row"><span>${t('status')}</span><b>${esc(lead.status)}</b></div>
    <div class="ledger-row"><span>${t('score')}</span><b>${esc(lead.score)} (${esc(lead.score_tier)})</b></div>
    <div class="ledger-row"><span>${t('phone')}</span><b>${esc(lead.phone||'—')}</b></div>
    <div class="section-title">${t('addActivity')}</div>
    <div class="field"><select id="act_type">
      <option value="call">call</option><option value="message">message</option>
      <option value="meeting">meeting</option><option value="note">note</option><option value="followup">followup</option>
    </select></div>
    <div class="field"><textarea id="act_content" rows="2" placeholder="${t('content')}"></textarea></div>
    <div class="modal-actions">
      <button class="btn secondary btn-sm" data-onclick="draftAiMessage(${id})">${t('draftMsg')}</button>
      <button class="btn secondary btn-sm" data-onclick="startLeadFollowups(${id})">${uiText('بدء متابعة','Start follow-up')}</button>
      <button class="btn secondary btn-sm" data-onclick="convertLead(${id})">${t('convert')}</button>
      <button class="btn btn-sm" data-onclick="addActivity(${id})">${t('save')}</button>
    </div>
    <div id="aiMsgOut" style="margin-top:12px; font-size:13px; color:var(--text-dim);"></div>
  `);
}
async function startLeadFollowups(leadId){
  try{ await api(`/leads/${leadId}/followups/start`, {method:'POST', body:{}}); showToast(t('saved')); }
  catch(e){ showToast(e.message, true); }
}
async function addActivity(leadId){
  try{
    await api(`/leads/${leadId}/activities`, {method:'POST', body:{type: val('act_type'), content: val('act_content')}});
    showToast(t('saved')); closeModal(); renderLeads();
  }catch(e){ showToast(e.message, true); }
}
async function convertLead(leadId){
  try{ await api(`/leads/${leadId}/convert`, {method:'POST', body:{}}); showToast(t('saved')); closeModal(); renderLeads(); }
  catch(e){ showToast(e.message, true); }
}
async function draftAiMessage(leadId){
  const out = document.getElementById('aiMsgOut');
  out.textContent = t('loading');
  try{
    const r = await api(`/ai/leads/${leadId}/message`, {method:'POST', body:{language:LANG}});
    out.textContent = r.message;
  }catch(e){ out.textContent = e.message; }
}

/* ---------------- Clients ---------------- */
async function renderClients(){
  const content = document.getElementById('content');
  const clients = await api('/clients');
  content.innerHTML = `
    <div class="toolbar"><div class="item-meta">${clients.length} ${t('nav_clients')}</div><button class="btn btn-sm" data-onclick="openClientModal()">+ ${t('nav_clients')}</button></div>
    ${!clients.length ? `<div class="empty-state">${t('noData')}</div>` : `<table><thead><tr><th>${t('name')}</th><th>${t('company')}</th><th>${t('industry')}</th><th>${t('phone')}</th><th>${t('actions')}</th></tr></thead>
    <tbody>${clients.map(c=>`<tr>
      <td>${esc(c.name)}</td><td>${esc(c.company||'—')}</td><td>${esc(c.industry||'—')}</td><td>${esc(c.phone||'—')}</td>
      <td><button class="btn secondary btn-sm" data-onclick="openClientDomain(${esc(c.id)})">${t('nav_projects')} ›</button></td>
    </tr>`).join('')}</tbody></table>`}`;
}
function openClientModal(){
  showModal(`<div class="modal-title">${t('nav_clients')}</div>
    <div class="field"><label>${t('name')}</label><input id="cl_name"></div>
    <div class="field"><label>${t('company')}</label><input id="cl_company"></div>
    <div class="field"><label>${t('phone')}</label><input id="cl_phone"></div>
    <div class="field"><label>${t('email')}</label><input id="cl_email"></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitClient()">${t('save')}</button></div>`);
}
async function submitClient(){try{await api('/clients',{method:'POST',body:{name:val('cl_name'),company:val('cl_company'),phone:val('cl_phone'),email:val('cl_email')}});closeModal();showToast(t('saved'));renderClients();}catch(e){showToast(e.message,true);}}
async function openClientDomain(id){
  try{
    const [c, contacts, projects] = await Promise.all([api('/clients/'+id), api(`/clients/${id}/contacts`), api(`/projects?client_id=${id}`)]);
    showModal(`
      <div class="modal-title">${esc(c.name)}</div>
      <div class="item-meta">${esc(c.company||'')} · ${esc(c.email||c.phone||'')}</div>
      <div class="section-title">${t('contacts')}</div>
      <div class="card-list">${contacts.length ? contacts.map(x=>`<div class="item-card"><b>${esc(x.name)}</b><div class="item-meta">${esc(x.job_title||'')} · ${esc(x.email||x.phone||'')}</div></div>`).join('') : `<div class="empty-state">${t('noData')}</div>`}</div>
      <div class="section-title">${t('nav_projects')}</div>
      <div class="card-list">${projects.length ? projects.map(x=>`<div class="item-card"><div class="item-card-top"><div><b>${esc(x.name)}</b><div class="item-meta">${esc(x.description||'')}</div></div><span class="badge status">${esc(x.status)}</span></div><div style="margin-top:8px"><button class="btn secondary btn-sm" data-onclick="openProjectDetail(${esc(x.id)})">${t('nav_projects')} ›</button></div></div>`).join('') : `<div class="empty-state">${t('noData')}</div>`}</div>
      <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button></div>
    `);
  }catch(e){ showToast(e.message,true); }
}

async function renderPeople(){
  const content=document.getElementById('content');
  const [employees, departments, positions, workspaceUsers]=await Promise.all([api('/employees'),api('/departments'),api('/positions'),api('/workspace/users')]);
  content.innerHTML=`
    <div class="grid grid-4" style="margin-bottom:18px">
      ${ledger(t('employee'), employees.length, [[t('department'), departments.length]])}
    </div>
    <div class="toolbar"><div></div><button class="btn btn-sm" data-onclick="openNewEmployeeModal()">+ ${t('employee')}</button></div>
    <div class="section-title">${t('employee')}</div>
    ${employees.length ? `<table><thead><tr><th>${t('name')}</th><th>${t('email')}</th><th>${t('department')}</th><th>${t('position')}</th><th>${t('status')}</th><th></th></tr></thead><tbody>${employees.map(e=>`<tr><td>${esc(e.name)}</td><td>${esc(e.email)}</td><td>${esc(e.department_name||'—')}</td><td>${esc(e.position_title||'—')}</td><td><span class="badge status">${esc(e.employment_status||'active')}</span></td><td><button class="btn secondary btn-sm" data-onclick="openEmployeeDetail(${esc(e.id)})">${uiText('التفاصيل','Details')} ›</button></td></tr>`).join('')}</tbody></table>` : `<div class="empty-state">${t('noData')}</div>`}
    <div class="section-title">${t('department')}</div>
    <div class="card-list">${departments.map(d=>`<div class="item-card"><b>${esc(d.name)}</b><div class="item-meta">${esc(d.code||'')}</div></div>`).join('') || `<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="section-title">${t('position')} / ${t('user')}</div>
    <div class="card-list">${positions.map(p=>`<div class="item-card"><b>${esc(p.title)}</b><div class="item-meta">${esc(p.code||'')}</div></div>`).join('') || `<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="section-title">Workspace Users</div>
    <div class="card-list">${workspaceUsers.slice(0,20).map(u=>`<div class="item-card"><b>${esc(u.name)}</b><div class="item-meta">${esc(u.email)} · ${esc(u.role)}</div></div>`).join('') || `<div class="empty-state">${t('noData')}</div>`}</div>`;
}
async function openNewEmployeeModal(){
  const [workspaceUsers, employees, departments, positions] = await Promise.all([api('/workspace/users'), api('/employees'), api('/departments'), api('/positions')]);
  const existingIds = new Set(employees.map(e=>e.user_id));
  const available = workspaceUsers.filter(u=>!existingIds.has(u.id));
  showModal(`<div class="modal-title">${uiText('إضافة موظف جديد','Add new employee')}</div>
    ${!available.length ? `<div class="item-meta">${uiText('كل أعضاء الفريق أصبحوا موظفين بالفعل — عايز تضيف عضو جديد للفريق الأول من صفحة الأتمتة/الفريق (دعوة عضو).','Every workspace member is already an employee — invite a new team member first from the Team page.')}</div>` : `
    <div class="field"><label>${uiText('العضو','Team member')}</label><select id="ne_user">${available.map(u=>`<option value="${u.id}">${esc(u.name)} (${esc(u.email)})</option>`).join('')}</select></div>
    <div class="field"><label>${t('department')}</label><select id="ne_dept"><option value="">—</option>${departments.map(d=>`<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select></div>
    <div class="field"><label>${t('position')}</label><select id="ne_pos"><option value="">—</option>${positions.map(p=>`<option value="${p.id}">${esc(p.title)}</option>`).join('')}</select></div>
    <div class="field"><label>${uiText('تاريخ التعيين','Hire date')}</label><input id="ne_hire" type="date"></div>
    <div class="field"><label>${uiText('نوع التوظيف','Employment type')}</label><select id="ne_type"><option value="full_time">full_time</option><option value="part_time">part_time</option><option value="contractor">contractor</option></select></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitNewEmployee()">${t('save')}</button></div>`}`);
}
async function submitNewEmployee(){
  try{
    await api('/employees',{method:'POST',body:{
      user_id:Number(val('ne_user')),
      department_id:val('ne_dept')?Number(val('ne_dept')):null,
      position_id:val('ne_pos')?Number(val('ne_pos')):null,
      hire_date:val('ne_hire'),
      employment_type:val('ne_type')
    }});
    closeModal(); showToast(t('saved')); renderPeople();
  }catch(e){ showToast(e.message, true); }
}

async function openEmployeeDetail(eid){
  const e=await api('/employees/'+eid);
  showModal(`<div class="modal-title">${esc(e.name)} — ${esc(e.position_title||'')}</div>
    <div class="item-meta">${esc(e.department_name||'')} · ${uiText('الحالة','Status')}: ${esc(e.employment_status||'active')}</div>
    <div class="section-title">${uiText('العقود','Contracts')}</div>
    <div class="card-list">${(e.contracts||[]).length?e.contracts.map(c=>`<div class="item-card"><b>${esc(c.contract_type)}</b><div class="item-meta">${esc(c.start_date)} → ${esc(c.end_date||uiText('مستمر','ongoing'))} · ${fmtMoney(c.salary||0)} <span class="badge status">${esc(c.status)}</span></div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="item-card" style="margin-top:10px"><div class="field"><label>${uiText('نوع العقد','Contract type')}</label><input id="ec_type" value="employment"></div><div class="field"><label>${uiText('تاريخ البدء','Start date')}</label><input id="ec_start" type="date"></div><div class="field"><label>${uiText('الراتب','Salary')}</label><input id="ec_salary" type="number"></div><button class="btn secondary btn-sm" data-onclick="submitEmployeeContract(${esc(eid)})">${uiText('إضافة عقد','Add contract')}</button></div>
    <div class="section-title">${uiText('المستندات','Documents')}</div>
    <div class="card-list">${(e.documents||[]).length?e.documents.map(d=>`<div class="item-card"><b>${esc(d.title)}</b><div class="item-meta">${esc(d.document_type)} <span class="badge status">${esc(d.status)}</span></div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="item-card" style="margin-top:10px"><div class="field"><label>${t('title')}</label><input id="ed_title"></div><div class="field"><label>${uiText('نوع المستند','Document type')}</label><input id="ed_type" value="id_card"></div><button class="btn secondary btn-sm" data-onclick="submitEmployeeDocument(${esc(eid)})">${uiText('إضافة مستند','Add document')}</button></div>`);
}
async function submitEmployeeContract(eid){try{await api(`/employees/${eid}/contracts`,{method:'POST',body:{contract_type:val('ec_type'),start_date:val('ec_start'),salary:parseFloat(val('ec_salary'))||0}});showToast(t('saved'));openEmployeeDetail(eid);}catch(e){showToast(e.message,true);}}
async function submitEmployeeDocument(eid){try{await api(`/employees/${eid}/documents`,{method:'POST',body:{title:val('ed_title'),document_type:val('ed_type')}});showToast(t('saved'));openEmployeeDetail(eid);}catch(e){showToast(e.message,true);}}

let CLIENT_PORTAL_TAB='projects';
function setClientPortalTab(tab){CLIENT_PORTAL_TAB=tab;renderClientPortal();}
async function renderClientPortal(){
  const content=document.getElementById('content');
  const me=await api('/client/me');
  const projects=await api('/client/projects');
  const tabs=[['projects',uiText('المشاريع','Projects')],['dashboard',uiText('لوحة العميل','Dashboard')],['deliverables',uiText('التسليمات','Deliverables')],['invoices',uiText('الفواتير','Invoices')],['messages',uiText('الرسائل','Messages')]];
  content.innerHTML=`
    <div class="grid grid-4">
      ${ledger(t('company'), me.company||me.name, [[t('nav_projects'),projects.length]])}
    </div>
    <div class="toolbar"><div class="filters">${tabs.map(([k,l])=>`<button class="btn ${CLIENT_PORTAL_TAB===k?'':'secondary'} btn-sm" data-onclick="setClientPortalTab('${k}')">${esc(l)}</button>`).join('')}</div><div></div></div>
    <div id="clientPortalTabBody"></div>`;
  const body=document.getElementById('clientPortalTabBody');
  if(CLIENT_PORTAL_TAB==='projects'){
    body.innerHTML=`<div class="section-title">${t('nav_projects')}</div>
    <div class="card-list">${projects.length ? projects.map(p=>`<div class="item-card"><div class="item-card-top"><div><div class="item-title">${esc(p.name)}</div><div class="item-meta">${esc(p.description||'')}</div></div><span class="badge status">${esc(p.status)}</span></div><div style="margin-top:10px"><button class="btn secondary btn-sm" data-onclick="openClientProject(${esc(p.id)})">${t('nav_projects')} ›</button></div></div>`).join('') : `<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="section-title">${t('createRequest')}</div>
    <div class="item-card"><div class="field"><input id="cp_title" placeholder="${t('title')}"></div><div class="field"><select id="cp_project"><option value="">— ${t('project')} —</option>${projects.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></div><div class="field"><textarea id="cp_desc" rows="3" placeholder="${t('description')}"></textarea></div><div class="modal-actions"><button class="btn" data-onclick="submitClientPortalRequest()">${t('save')}</button></div></div>`;
  } else if(CLIENT_PORTAL_TAB==='dashboard') await renderClientDashboard(body);
  else if(CLIENT_PORTAL_TAB==='deliverables') await renderClientDeliverables(body);
  else if(CLIENT_PORTAL_TAB==='invoices') await renderClientInvoices(body);
  else if(CLIENT_PORTAL_TAB==='messages') await renderClientMessages(body);
}
async function renderClientDashboard(body){
  try{
    const d=await api('/client/dashboard');
    body.innerHTML=`<div class="grid grid-4">
      ${ledger(uiText('المشاريع','Projects'),d.projects.length,[])}
      ${ledger(uiText('المهام','Tasks'),d.tasks.total||0,[[uiText('منجزة','Done'),d.tasks.done||0]])}
      ${ledger(uiText('الفواتير','Invoices'),d.invoices.total||0,[[uiText('المدفوع','Paid'),fmtMoney(d.invoices.paid||0)]])}
      ${ledger(uiText('الطلبات','Requests'),d.requests||0,[])}
    </div>`;
  }catch(e){ body.innerHTML=`<div class="empty-state">${esc(e.message||'')}</div>`; }
}
async function renderClientDeliverables(body){
  try{
    const rows=await api('/client/deliverables');
    body.innerHTML=rows.length?`<div class="card-list">${rows.map(x=>`<div class="item-card"><div class="item-card-top"><div><div class="item-title">${esc(x.name)}</div><div class="item-meta">${esc(x.project_name||'')}</div></div><span class="badge status">${esc(x.status)}</span></div>${x.status==='submitted'?`<div class="modal-actions" style="justify-content:flex-start;margin-top:8px"><button class="btn secondary btn-sm" data-onclick="submitClientDeliverableApproval(${esc(x.id)},'approved')">${t('approve')}</button><button class="btn danger btn-sm" data-onclick="submitClientDeliverableApproval(${esc(x.id)},'changes_requested')">${t('changesRequested')}</button></div>`:''}</div>`).join('')}</div>`:`<div class="empty-state">${t('noData')}</div>`;
  }catch(e){ body.innerHTML=`<div class="empty-state">${esc(e.message||'')}</div>`; }
}
async function submitClientDeliverableApproval(id,status){try{await api(`/client/deliverables/${id}/approval`,{method:'POST',body:{status}});showToast(t('saved'));renderClientDeliverables(document.getElementById('clientPortalTabBody'));}catch(e){showToast(e.message,true);}}
async function renderClientInvoices(body){
  try{
    const rows=await api('/client/invoices');
    body.innerHTML=rows.length?`<table><thead><tr><th>${t('invoice')}</th><th>${uiText('الإجمالي','Total')}</th><th>${t('status')}</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${esc(x.invoice_number||('#'+x.id))}</td><td class="mono">${fmtMoney(x.total)}</td><td><span class="badge status">${esc(x.status)}</span></td></tr>`).join('')}</tbody></table>`:`<div class="empty-state">${t('noData')}</div>`;
  }catch(e){ body.innerHTML=`<div class="empty-state">${esc(e.message||'')}</div>`; }
}
async function renderClientMessages(body){
  try{
    const rows=await api('/client/messages');
    body.innerHTML=`<div class="card-list">${(rows.length?rows.map(x=>`<div class="item-card"><div class="item-title">${esc(x.body||x.message||'')}</div><div class="item-meta">${esc(x.created_at||'')}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`)}</div>
    <div class="item-card" style="margin-top:12px"><div class="field"><textarea id="cm_body" rows="2" placeholder="${uiText('اكتب رسالة...','Write a message...')}"></textarea></div><button class="btn btn-sm" data-onclick="submitClientMessage()">${uiText('إرسال','Send')}</button></div>`;
  }catch(e){ body.innerHTML=`<div class="empty-state">${esc(e.message||'')}</div>`; }
}
async function submitClientMessage(){try{await api('/client/messages',{method:'POST',body:{body:val('cm_body')}});showToast(t('saved'));renderClientMessages(document.getElementById('clientPortalTabBody'));}catch(e){showToast(e.message,true);}}
async function submitClientPortalRequest(){
  try{ await api('/client/requests',{method:'POST',body:{title:val('cp_title'),project_id:val('cp_project')?Number(val('cp_project')):null,description:val('cp_desc')}}); showToast(t('saved')); renderClientPortal(); }
  catch(e){ showToast(e.message,true); }
}
async function openClientProject(id){
  const p=await api('/projects/'+id);
  const [members,milestones,deliverables,financials]=await Promise.all([
    api(`/projects/${id}/members`),api(`/projects/${id}/milestones`),api(`/projects/${id}/deliverables`),api(`/projects/${id}/financials`)
  ]);
  showModal(`<div class="modal-title">${esc(p.name)}</div>
    <div class="grid grid-2">
      ${ledger(t('projectMembers'),members.length,[])}
      ${ledger(t('milestones'),milestones.length,[])}
      ${ledger(t('deliverables'),deliverables.length,[])}
      ${ledger(t('profit'),fmtMoney(financials.profit||0),[[t('revenue'),fmtMoney(financials.revenue||0)],[t('expenses'),fmtMoney((financials.expenses||0)+(financials.labor_cost||0))]])}
    </div>
    <div class="section-title">${t('deliverables')}</div>
    <div class="card-list">${deliverables.length ? deliverables.map(d=>`<div class="item-card"><div class="item-card-top"><b>${esc(d.name)}</b><span class="badge status">${esc(d.status)}</span></div></div>`).join('') : `<div class="empty-state">${t('noData')}</div>`}</div>`);
}

/* ---------------- Deals ---------------- */
async function renderDeals(){
  const content = document.getElementById('content');
  content.innerHTML = `<div class="toolbar"><div></div><button class="btn btn-sm" data-onclick="openDealModal()">+ ${t('title')}</button></div><div id="dealsWrap"></div>`;
  const deals = await api('/deals');
  const wrap = document.getElementById('dealsWrap');
  if(!deals.length){ wrap.innerHTML = `<div class="empty-state">${t('noData')}</div>`; return; }
  wrap.innerHTML = `<table><thead><tr><th>${t('title')}</th><th>${t('amount')}</th><th>${t('status')}</th><th>${t('actions')}</th></tr></thead>
  <tbody>${deals.map(d=>`<tr>
    <td>${esc(d.title)}</td><td class="mono">${fmtMoney(d.value)}</td>
    <td><span class="badge ${d.status==='won'?'won':d.status==='lost'?'lost':'status'}">${esc(d.status)}</span></td>
    <td>${d.status==='open' ? `<button class="btn secondary btn-sm" data-onclick="closeDeal(${esc(d.id)},'won')">Won</button> <button class="btn secondary btn-sm" data-onclick="closeDeal(${esc(d.id)},'lost')">Lost</button>` : '—'}</td>
  </tr>`).join('')}</tbody></table>`;
}
function openDealModal(){
  showModal(`<div class="modal-title">${t('title')}</div>
    <div class="field"><label>${t('title')}</label><input id="dl_title"></div>
    <div class="field"><label>${t('amount')}</label><input id="dl_value" type="number"></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitDeal()">${t('save')}</button></div>`);
}
async function submitDeal(){try{await api('/deals',{method:'POST',body:{title:val('dl_title'),value:parseFloat(val('dl_value'))||0}});closeModal();showToast(t('saved'));renderDeals();}catch(e){showToast(e.message,true);}}
async function closeDeal(id, status){
  try{ await api(`/deals/${id}`, {method:'PATCH', body:{status}}); showToast(t('saved')); renderDeals(); }
  catch(e){ showToast(e.message, true); }
}

/* ---------------- Projects ---------------- */
let PROJECT_VIEW = 'list';
async function renderProjects(){
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="toolbar">
      <div class="filters">
        <button class="btn secondary btn-sm" data-onclick="setProjectView('list')" id="pvList">${t('listView')}</button>
        <button class="btn secondary btn-sm" data-onclick="setProjectView('kanban')" id="pvKanban">${t('kanbanView')}</button>
      </div>
      <button class="btn" data-onclick="openProjectModal()">${t('addProject')}</button>
    </div>
    <div id="projectsWrap"></div>
  `;
  updateProjectViewButtons();
  if(PROJECT_VIEW === 'kanban') await renderKanban();
  else await renderProjectsList();
}
function setProjectView(v){ PROJECT_VIEW = v; renderProjects(); }
function updateProjectViewButtons(){
  const listBtn = document.getElementById('pvList'), kanbanBtn = document.getElementById('pvKanban');
  if(!listBtn) return;
  listBtn.style.borderColor = PROJECT_VIEW==='list' ? 'var(--gold)' : 'var(--line)';
  listBtn.style.color = PROJECT_VIEW==='list' ? 'var(--gold)' : 'var(--text)';
  kanbanBtn.style.borderColor = PROJECT_VIEW==='kanban' ? 'var(--gold)' : 'var(--line)';
  kanbanBtn.style.color = PROJECT_VIEW==='kanban' ? 'var(--gold)' : 'var(--text)';
}
async function renderProjectsList(){
  const projects = await api('/projects');
  const wrap = document.getElementById('projectsWrap');
  wrap.className = 'card-list';
  if(!projects.length){ wrap.innerHTML = `<div class="empty-state">${t('noData')}</div>`; return; }
  wrap.innerHTML = projects.map(p=>`
    <div class="item-card">
      <div class="item-card-top">
        <div><div class="item-title">${esc(p.name)}</div><div class="item-meta">${esc(p.description||'')}</div></div>
        <span class="badge status">${esc(p.status)}</span>
      </div>
      <div style="margin-top:10px;"><button class="btn secondary btn-sm" data-onclick="openProjectDetail(${esc(p.id)})">${t('nav_projects')} ›</button></div>
    </div>
  `).join('');
}

const KANBAN_COLUMNS = ['todo','in_progress','review','approved','done'];
async function renderKanban(){
  const tasks = await api('/tasks');
  const wrap = document.getElementById('projectsWrap');
  wrap.className = '';
  wrap.innerHTML = `<div style="display:grid; grid-template-columns:repeat(5,1fr); gap:10px; align-items:start;">
    ${KANBAN_COLUMNS.map(col => `
      <div class="kanban-col" data-status="${col}" data-ondragover="event.preventDefault()" data-ondrop="onKanbanDrop(event,'${col}')"
           style="background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:10px; min-height:200px;">
        <div class="ledger-eyebrow" style="margin-bottom:10px;">${col} (${tasks.filter(x=>x.status===col).length})</div>
        <div style="display:flex; flex-direction:column; gap:8px;">
          ${tasks.filter(x=>x.status===col).map(tk => `
            <div class="item-card" draggable="true" data-ondragstart="onKanbanDragStart(event, ${esc(tk.id)})" style="cursor:grab; padding:10px 12px;">
              <div class="item-title" style="font-size:13px;">${esc(tk.title)}</div>
              <div class="item-meta">${t('priority')}: ${esc(tk.priority)}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('')}
  </div>`;
}
let kanbanDraggedTaskId = null;
function onKanbanDragStart(ev, taskId){ kanbanDraggedTaskId = taskId; ev.dataTransfer.effectAllowed = 'move'; }
async function onKanbanDrop(ev, newStatus){
  ev.preventDefault();
  if(kanbanDraggedTaskId == null) return;
  try{
    await api('/tasks/reorder', {method:'POST', body:{updates:[{id: kanbanDraggedTaskId, status: newStatus, order_index: 0}]}});
    showToast(t('saved'));
    renderKanban();
  }catch(e){ showToast(e.message, true); }
  kanbanDraggedTaskId = null;
}

function openProjectModal(){
  showModal(`
    <div class="modal-title">${t('addProject')}</div>
    <div class="field"><label>${t('name')}</label><input id="p_name"></div>
    <div class="field"><label>${t('description')}</label><textarea id="p_desc" rows="2"></textarea></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitProject()">${t('save')}</button></div>
  `);
}
async function submitProject(){
  try{ await api('/projects', {method:'POST', body:{name:val('p_name'), description:val('p_desc')}});
    closeModal(); showToast(t('saved')); renderProjects(); }
  catch(e){ showToast(e.message, true); }
}
async function openProjectDetail(id){
  try{
    const w=await api(`/projects/${id}/workspace`);
    const employees=await api('/employees');
    const clientId=w.client_id;
    const accountant=['accountant','founder','admin'].includes(CURRENT_USER.role);
    showModal(`<div class="modal-title">${esc(w.name)}</div>
      <div class="item-meta">${esc(w.client_name||'—')} · <span class="badge status">${esc(w.status)}</span></div>
      <div class="grid grid-4" style="margin-top:12px">
        ${ledger(t('projectMembers'),w.members.length,[])}
        ${ledger(t('milestones'),w.milestones.length,[])}
        ${ledger(t('deliverables'),w.deliverables.length,[])}
        ${ledger(t('profit'),fmtMoney(w.financials?.profit||0),[[t('revenue'),fmtMoney(w.financials?.revenue||0)],[t('expenses'),fmtMoney(w.financials?.total_cost||0)]])}
      </div>
      <div class="toolbar" style="margin-top:14px;flex-wrap:wrap">
        <button class="btn secondary btn-sm" data-onclick="openProjectMemberModal(${id})">${t('addMember')}</button>
        <button class="btn secondary btn-sm" data-onclick="openMilestoneModal(${id})">${t('addMilestone')}</button>
        <button class="btn secondary btn-sm" data-onclick="openDeliverableModal(${id})">${t('addDeliverable')}</button>
        <button class="btn secondary btn-sm" data-onclick="openBudgetModal(${id},${jsArg(w.financials?.budget?.budget_amount||0)})">${t('setBudget')}</button>
        <button class="btn secondary btn-sm" data-onclick="openExpenseModal(${id})">${t('addExpense')}</button>
        ${accountant && clientId ? `<button class="btn secondary btn-sm" data-onclick="openProjectInvoiceModal(${id},${clientId})">${t('createInvoice')}</button>`:''}
      </div>
      <div class="section-title">${t('projectMembers')}</div>
      <div class="card-list">${w.members.map(m=>`<div class="item-card"><div class="item-card-top"><b>${esc(m.name)}</b><span class="badge status">${esc(m.role)}</span></div><div class="item-meta">${esc(m.email||'')}</div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
      <div class="section-title">${t('milestones')}</div>
      <div class="card-list">${w.milestones.map(m=>`<div class="item-card"><div class="item-card-top"><b>${esc(m.name)}</b><span class="badge status">${esc(m.status)}</span></div><div class="item-meta">${esc(m.due_date||'')}</div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
      <div class="section-title">${t('deliverables')}</div>
      <div class="card-list">${w.deliverables.map(d=>`<div class="item-card"><div class="item-card-top"><b>${esc(d.name)}</b><span class="badge status">${esc(d.status)}</span></div><div class="item-meta">${esc(d.description||'')}</div><div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">${d.status==='submitted'?`<button class="btn secondary btn-sm" data-onclick="openApprovalDecision(${d.id})">${t('approve')}</button>`:''}<button class="btn secondary btn-sm" data-onclick="openDeliverableVersionModal(${d.id},${id})">${uiText('رفع نسخة','Upload version')}</button></div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
      <div class="section-title">${t('nav_projects')} — Tasks</div>
      <div class="card-list">${w.tasks.map(tk=>`<div class="item-card"><div class="item-card-top"><div><div class="item-title">${esc(tk.title)}</div><div class="item-meta">${t('priority')}: ${esc(tk.priority||'')} ${tk.deadline?'· '+t('deadline')+': '+esc(tk.deadline):''}</div></div><span class="badge status">${esc(tk.status)}</span></div><div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap"><button class="btn secondary btn-sm" data-onclick="openTaskWorkflowModal(${tk.id},${id})">${t('assign')} / ${t('logTime')}</button><button class="btn secondary btn-sm" data-onclick="openTaskDetail(${tk.id},${id})">${uiText('التفاصيل والتعليقات','Details & comments')}</button></div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
      <div class="item-card" style="margin-top:10px"><div class="field"><input id="nt_title_${id}" placeholder="${t('title')}"></div><button class="btn secondary btn-sm" data-onclick="submitNewTask(${id})">${uiText('إضافة مهمة','Add task')}</button></div>
      <div class="section-title">${t('requests')}</div>
      <div class="card-list">${w.requests.map(r=>`<div class="item-card"><div class="item-card-top"><b>${esc(r.title)}</b><span class="badge status">${esc(r.status)}</span></div><div class="item-meta">${esc(r.requester_name||'')} · ${esc(r.priority||'')}</div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
      <div class="section-title">${t('financials')}</div>
      <div class="grid grid-4">${ledger(t('revenue'),fmtMoney(w.financials?.revenue||0),[])}${ledger(t('expenses'),fmtMoney(w.financials?.total_cost||0),[])}${ledger(t('profit'),fmtMoney(w.financials?.profit||0),[])}${ledger(t('budget'),fmtMoney(w.financials?.budget?.budget_amount||0),[])}</div>`);
  }catch(e){ showToast(e.message,true); }
}

async function openProjectMemberModal(projectId){
  const employees=await api('/employees');
  showModal(`<div class="modal-title">${t('addMember')}</div><div class="field"><label>${t('employee')}</label><select id="pm_employee">${employees.map(e=>`<option value="${e.id}">${esc(e.name)} — ${esc(e.position_title||e.role||'')}</option>`).join('')}</select></div><div class="field"><label>Role</label><select id="pm_role"><option value="member">member</option><option value="project_manager">project_manager</option><option value="designer">designer</option><option value="developer">developer</option><option value="content">content</option></select></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitProjectMember(${projectId})">${t('save')}</button></div>`);
}
async function submitProjectMember(projectId){try{await api(`/projects/${projectId}/members`,{method:'POST',body:{employee_id:Number(val('pm_employee')),role:val('pm_role')}});closeModal();showToast(t('saved'));openProjectDetail(projectId);}catch(e){showToast(e.message,true);}}
async function openMilestoneModal(projectId){showModal(`<div class="modal-title">${t('addMilestone')}</div><div class="field"><input id="ms_name" placeholder="${t('title')}"></div><div class="field"><textarea id="ms_desc" placeholder="${t('description')}"></textarea></div><div class="field"><input id="ms_due" type="date"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitMilestone(${projectId})">${t('save')}</button></div>`);}
async function submitMilestone(projectId){try{await api(`/projects/${projectId}/milestones`,{method:'POST',body:{name:val('ms_name'),description:val('ms_desc'),due_date:val('ms_due')}});closeModal();showToast(t('saved'));openProjectDetail(projectId);}catch(e){showToast(e.message,true);}}
async function openDeliverableModal(projectId){const ms=await api(`/projects/${projectId}/milestones`);showModal(`<div class="modal-title">${t('addDeliverable')}</div><div class="field"><input id="dv_name" placeholder="${t('title')}"></div><div class="field"><textarea id="dv_desc" placeholder="${t('description')}"></textarea></div><div class="field"><select id="dv_ms"><option value="">—</option>${ms.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('')}</select></div><div class="field"><input id="dv_due" type="date"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitDeliverable(${projectId})">${t('save')}</button></div>`);}
async function submitDeliverable(projectId){try{await api(`/projects/${projectId}/deliverables`,{method:'POST',body:{name:val('dv_name'),description:val('dv_desc'),milestone_id:val('dv_ms')?Number(val('dv_ms')):null,due_date:val('dv_due')}});closeModal();showToast(t('saved'));openProjectDetail(projectId);}catch(e){showToast(e.message,true);}}
async function openApprovalDecision(deliverableId){showModal(`<div class="modal-title">${t('approvals')}</div><div class="field"><textarea id="ap_feedback" placeholder="${t('description')}"></textarea></div><div class="modal-actions"><button class="btn secondary" data-onclick="decideLatestApproval(${deliverableId},'rejected')">${t('reject')}</button><button class="btn secondary" data-onclick="decideLatestApproval(${deliverableId},'changes_requested')">${t('changesRequested')}</button><button class="btn" data-onclick="decideLatestApproval(${deliverableId},'approved')">${t('approve')}</button></div>`);}
async function decideLatestApproval(deliverableId,status){try{const r=await api(`/deliverables/${deliverableId}/approval`); const approval=r.id?r:null; if(approval){await api(`/approvals/${approval.id}`,{method:'PATCH',body:{status,feedback:val('ap_feedback')}});} closeModal();showToast(t('saved'));renderProjects();}catch(e){showToast(e.message,true);}}
async function openBudgetModal(projectId,current){showModal(`<div class="modal-title">${t('setBudget')}</div><div class="field"><input id="budget_amount" type="number" step="0.01" value="${esc(current)}"></div><div class="field"><input id="budget_currency" value="USD"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitBudget(${projectId})">${t('save')}</button></div>`);}
async function submitBudget(projectId){try{await api(`/projects/${projectId}/budget`,{method:'PUT',body:{budget_amount:Number(val('budget_amount')),currency:val('budget_currency')}});closeModal();showToast(t('saved'));openProjectDetail(projectId);}catch(e){showToast(e.message,true);}}
async function openExpenseModal(projectId){showModal(`<div class="modal-title">${t('addExpense')}</div><div class="field"><input id="ex_amount" type="number" step="0.01" placeholder="${t('amount')}"></div><div class="field"><input id="ex_category" placeholder="${t('category')}"></div><div class="field"><textarea id="ex_desc" placeholder="${t('description')}"></textarea></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitExpense(${projectId})">${t('save')}</button></div>`);}
async function submitExpense(projectId){try{await api(`/projects/${projectId}/expenses`,{method:'POST',body:{amount:Number(val('ex_amount')),category:val('ex_category'),description:val('ex_desc')}});closeModal();showToast(t('saved'));openProjectDetail(projectId);}catch(e){showToast(e.message,true);}}
async function openTaskWorkflowModal(taskId,projectId){const employees=await api('/employees');const task=await api(`/tasks/${taskId}`);showModal(`<div class="modal-title">${esc(task.title)}</div><div class="field"><label>${t('employee')}</label><select id="tw_employee"><option value="">—</option>${employees.map(e=>`<option value="${e.user_id}">${esc(e.name)}</option>`).join('')}</select></div><div class="field"><label>${t('status')}</label><select id="tw_status">${['todo','in_progress','review','approved','done'].map(x=>`<option ${task.status===x?'selected':''} value="${x}">${x}</option>`).join('')}</select></div><div class="field"><label>${t('hours')}</label><input id="tw_hours" type="number" step="0.25"></div><div class="field"><label>${t('workDate')}</label><input id="tw_date" type="date" value="${new Date().toISOString().slice(0,10)}"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitTaskWorkflow(${taskId},${projectId})">${t('save')}</button></div>`);}
async function submitNewTask(projectId){try{const el=document.getElementById('nt_title_'+projectId);await api('/tasks',{method:'POST',body:{title:el.value,project_id:projectId}});showToast(t('saved'));openProjectDetail(projectId);}catch(e){showToast(e.message,true);}}
async function submitTaskWorkflow(taskId,projectId){try{const uid=val('tw_employee');const body={status:val('tw_status')};if(uid)body.assignee_id=Number(uid);await api(`/tasks/${taskId}`,{method:'PATCH',body});const hours=Number(val('tw_hours')||0);if(hours>0)await api(`/tasks/${taskId}/time`,{method:'POST',body:{hours,work_date:val('tw_date')}});closeModal();showToast(t('saved'));openProjectDetail(projectId);}catch(e){showToast(e.message,true);}}
async function openTaskDetail(taskId,projectId){
  const [events,comments]=await Promise.all([api(`/tasks/${taskId}/events`),api(`/tasks/${taskId}/comments`)]);
  showModal(`<div class="modal-title">${uiText('تفاصيل المهمة','Task details')}</div>
    <div class="section-title">${uiText('الحالة السريعة','Quick status')}</div>
    <div class="modal-actions" style="justify-content:flex-start">${['todo','in_progress','review','approved','done'].map(s=>`<button class="btn secondary btn-sm" data-onclick="quickTaskStatus(${taskId},${projectId},'${s}')">${s}</button>`).join('')}</div>
    <div class="section-title">${uiText('سجل الأحداث','Event timeline')}</div>
    <div class="card-list">${events.length?events.map(e=>`<div class="item-card"><b>${esc(e.event_type)}</b><div class="item-meta">${esc(e.user_name||'')} · ${esc(e.created_at||'')} ${e.from_status?('· '+esc(e.from_status)+' → '+esc(e.to_status||'')):''}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="section-title">${uiText('التعليقات','Comments')}</div>
    <div class="card-list">${comments.length?comments.map(c=>`<div class="item-card"><div class="item-meta">${esc(c.created_at||'')}</div>${esc(c.comment)}</div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="field" style="margin-top:10px"><textarea id="tc_comment" rows="2" placeholder="${uiText('أضف تعليق...','Add a comment...')}"></textarea></div>
    <div class="modal-actions"><button class="btn" data-onclick="submitTaskComment(${taskId},${projectId})">${t('save')}</button></div>`);
}
async function quickTaskStatus(taskId,projectId,status){try{await api(`/tasks/${taskId}/status`,{method:'POST',body:{status}});showToast(t('saved'));openTaskDetail(taskId,projectId);}catch(e){showToast(e.message,true);}}
async function submitTaskComment(taskId,projectId){try{await api(`/tasks/${taskId}/comments`,{method:'POST',body:{comment:val('tc_comment')}});showToast(t('saved'));openTaskDetail(taskId,projectId);}catch(e){showToast(e.message,true);}}
async function openDeliverableVersionModal(deliverableId,projectId){
  const files=await api('/files');
  showModal(`<div class="modal-title">${uiText('رفع نسخة جديدة','Upload new version')}</div>
    <div class="field"><label>${uiText('الملف','File')}</label><select id="dvv_file"><option value="">—</option>${files.map(f=>`<option value="${f.id}">${esc(f.filename||f.name||('#'+f.id))}</option>`).join('')}</select></div>
    <div class="field"><label>${uiText('ملاحظات','Notes')}</label><textarea id="dvv_notes" rows="2"></textarea></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitDeliverableVersion(${deliverableId},${projectId})">${t('save')}</button></div>`);
}
async function submitDeliverableVersion(deliverableId,projectId){try{await api(`/deliverables/${deliverableId}/versions`,{method:'POST',body:{file_id:val('dvv_file')?Number(val('dvv_file')):null,notes:val('dvv_notes')}});closeModal();showToast(t('saved'));openProjectDetail(projectId);}catch(e){showToast(e.message,true);}}
async function openProjectInvoiceModal(projectId,clientId){showModal(`<div class="modal-title">${t('createInvoice')}</div><div class="field"><input id="inv_desc" placeholder="${t('description')}"></div><div class="field"><input id="inv_qty" type="number" value="1"></div><div class="field"><input id="inv_price" type="number" step="0.01" placeholder="${t('amount')}"></div><div class="field"><input id="inv_due" type="date"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitProjectInvoice(${projectId},${clientId})">${t('save')}</button></div>`);}
async function submitProjectInvoice(projectId,clientId){try{const r=await api('/invoices',{method:'POST',body:{client_id:clientId,project_id:projectId,due_date:val('inv_due'),items:[{description:val('inv_desc'),quantity:Number(val('inv_qty')||1),unit_price:Number(val('inv_price')||0)}]}});closeModal();showToast(`${t('saved')} #${esc(r.invoice_number||r.id)}`);openProjectDetail(projectId);}catch(e){showToast(e.message,true);}}

/* ---------------- Media ---------------- */
let MEDIA_VIEW = 'list';
async function renderMedia(){
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="toolbar">
      <div class="filters">
        <button class="btn secondary btn-sm" data-onclick="setMediaView('list')" id="mvList">${t('listView')}</button>
        <button class="btn secondary btn-sm" data-onclick="setMediaView('calendar')" id="mvCal">${t('calendarView')}</button>
      </div>
      <div>
        <button class="btn secondary btn-sm" data-onclick="openAiIdeasModal()">${t('aiGenerate')}</button>
        <button class="btn btn-sm" data-onclick="openContentModal()">${t('addContent')}</button>
      </div>
    </div>
    <div id="mediaMainWrap"></div>
  `;
  updateMediaViewButtons();
  if(MEDIA_VIEW === 'calendar') await renderMediaCalendar();
  else await renderMediaList();
}
function setMediaView(v){ MEDIA_VIEW = v; renderMedia(); }
function updateMediaViewButtons(){
  const l = document.getElementById('mvList'), c = document.getElementById('mvCal');
  if(!l) return;
  l.style.borderColor = MEDIA_VIEW==='list' ? 'var(--gold)' : 'var(--line)';
  l.style.color = MEDIA_VIEW==='list' ? 'var(--gold)' : 'var(--text)';
  c.style.borderColor = MEDIA_VIEW==='calendar' ? 'var(--gold)' : 'var(--line)';
  c.style.color = MEDIA_VIEW==='calendar' ? 'var(--gold)' : 'var(--text)';
}

async function renderMediaList(){
  const mainWrap = document.getElementById('mediaMainWrap');
  mainWrap.innerHTML = `
    <div class="section-title">${t('nav_media')}</div>
    <div id="contentWrap"></div>
    <div class="section-title">${t('bestContent')}</div>
    <div id="bestWrap"></div>
    <div class="section-title">${t('publishLog')}</div>
    <div id="publishLogWrap"></div>
  `;
  const items = await api('/content');
  const wrap = document.getElementById('contentWrap');
  wrap.innerHTML = !items.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<table><thead><tr><th>${t('title')}</th><th>${t('platform')}</th><th>${t('status')}</th><th>${t('actions')}</th></tr></thead>
    <tbody>${items.map(c=>`<tr>
      <td>${esc(c.title)}</td><td>${esc(c.platform||'—')}</td><td><span class="badge status">${esc(c.status)}</span></td>
      <td><button class="btn secondary btn-sm" data-onclick="openPublishModal(${esc(c.id)}, ${jsArg(c.platform||'tiktok')})">${t('publish')}</button>
      <button class="btn secondary btn-sm" data-onclick="openContentDetail(${esc(c.id)},${esc(c.creator_id||'null')})">${uiText('التفاصيل','Details')}</button></td>
    </tr>`).join('')}</tbody></table>`;

  const best = await api('/content/best');
  const bestWrap = document.getElementById('bestWrap');
  bestWrap.innerHTML = !best.length ? `<div class="empty-state">${t('noData')}</div>` : `<div class="card-list">
    ${best.map(b=>`<div class="item-card"><div class="item-card-top">
      <div><div class="item-title">${esc(b.tier)} ${esc(b.title)}</div><div class="item-meta">${esc(b.platform)}</div></div>
      <div class="mono">${fmtNum(b.total_views)} ${t('views')}</div>
    </div></div>`).join('')}</div>`;

  const log = await api('/publish/log');
  const logWrap = document.getElementById('publishLogWrap');
  logWrap.innerHTML = !log.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<table><thead><tr><th>${t('title')}</th><th>${t('platform')}</th><th>${t('status')}</th><th>mode</th></tr></thead>
    <tbody>${log.map(l=>`<tr><td>${esc(l.title)}</td><td>${esc(l.platform)}</td>
      <td><span class="badge ${l.status==='published'?'won':'lost'}">${esc(l.status)}</span></td>
      <td class="mono">${esc(l.mode)}</td></tr>`).join('')}</tbody></table>`;
}

function openPublishModal(contentId, defaultPlatform){
  showModal(`
    <div class="modal-title">${t('publish')}</div>
    <div class="ai-box" style="border-color:var(--line); border-inline-start-color:var(--cold);">
      <div class="ai-box-text" style="font-size:12.5px; color:var(--text-dim);">${t('mockModeNote')}</div>
    </div>
    <div class="field"><label>${t('platform')}</label>
      <select id="pub_platform">
        ${['tiktok','instagram','youtube','facebook'].map(p=>`<option value="${p}" ${p===defaultPlatform?'selected':''}>${p}</option>`).join('')}
      </select>
    </div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="doPublish(${contentId})">${t('publishNow')}</button></div>
    <div id="publishResultOut" style="margin-top:12px; font-size:13px; color:var(--text-dim);"></div>
  `);
}
async function doPublish(contentId){
  const out = document.getElementById('publishResultOut');
  out.textContent = t('loading');
  try{
    const r = await api(`/publish/content/${contentId}`, {method:'POST', body:{platform: val('pub_platform')}});
    out.textContent = `${esc(r.status)} (${esc(r.mode)}) — ${esc(r.external_post_id || r.error_message || '')}`;
    showToast(t('saved'));
    setTimeout(()=>{ closeModal(); renderMedia(); }, 900);
  }catch(e){ out.textContent = e.message; }
}

/* ---------------- Media: Calendar view (drag content between day columns) ---------------- */
async function renderMediaCalendar(){
  const mainWrap = document.getElementById('mediaMainWrap');
  const entries = await api('/calendar');
  const today = new Date();
  const days = [];
  for(let i=0;i<7;i++){ const d = new Date(today); d.setDate(d.getDate()+i); days.push(d); }
  const dateKey = (d)=> d.toISOString().slice(0,10);

  const unscheduled = entries.filter(e=>!e.publish_date);
  mainWrap.innerHTML = `<div style="display:grid; grid-template-columns: repeat(8, 1fr); gap:10px; align-items:start;">
    <div class="kanban-col" data-date="" data-ondragover="event.preventDefault()" data-ondrop="onCalDrop(event,null)"
         style="background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:10px; min-height:220px;">
      <div class="ledger-eyebrow" style="margin-bottom:10px;">${LANG==='ar'?'غير مجدول':'Unscheduled'}</div>
      ${calCards(unscheduled)}
    </div>
    ${days.map(d=>{
      const key = dateKey(d);
      const dayEntries = entries.filter(e=> e.publish_date && e.publish_date.slice(0,10)===key);
      return `<div class="kanban-col" data-date="${key}" data-ondragover="event.preventDefault()" data-ondrop="onCalDrop(event,'${key}')"
           style="background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:10px; min-height:220px;">
        <div class="ledger-eyebrow mono" style="margin-bottom:10px;">${d.toLocaleDateString(LANG==='ar'?'ar-EG':'en-US',{month:'short',day:'numeric'})}</div>
        ${calCards(dayEntries)}
      </div>`;
    }).join('')}
  </div>`;
}
function calCards(entries){
  if(!entries.length) return '';
  return `<div style="display:flex; flex-direction:column; gap:8px;">
    ${entries.map(e=>`<div class="item-card" draggable="true" data-ondragstart="onCalDragStart(event, ${esc(e.id)})" style="cursor:grab; padding:8px 10px;">
      <div class="item-title" style="font-size:12.5px;">${esc(e.title)}</div>
      <div class="item-meta">${esc(e.platform||e.content_platform||'')}</div>
    </div>`).join('')}
  </div>`;
}
let calDraggedEntryId = null;
function onCalDragStart(ev, entryId){ calDraggedEntryId = entryId; ev.dataTransfer.effectAllowed = 'move'; }
async function onCalDrop(ev, dateKey){
  ev.preventDefault();
  if(calDraggedEntryId == null) return;
  try{
    await api(`/calendar/${calDraggedEntryId}`, {method:'PATCH', body:{publish_date: dateKey}});
    showToast(t('saved'));
    renderMediaCalendar();
  }catch(e){ showToast(e.message, true); }
  calDraggedEntryId = null;
}

function openContentModal(){
  showModal(`
    <div class="modal-title">${t('addContent')}</div>
    <div class="field"><label>${t('title')}</label><input id="c_title"></div>
    <div class="field"><label>${t('platform')}</label><input id="c_platform" placeholder="tiktok / instagram / youtube"></div>
    <div class="field"><label>${t('hook')}</label><input id="c_hook"></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitContent()">${t('save')}</button></div>
  `);
}
async function submitContent(){
  try{ await api('/content', {method:'POST', body:{title:val('c_title'), platform:val('c_platform'), hook:val('c_hook')}});
    closeModal(); showToast(t('saved')); renderMedia(); }
  catch(e){ showToast(e.message, true); }
}
async function openContentDetail(contentId,creatorId){
  const versions=await api(`/content/${contentId}/versions`);
  showModal(`<div class="modal-title">${uiText('نسخ المحتوى','Content versions')}</div>
    <div class="card-list">${versions.length?versions.map(v=>`<div class="item-card"><div class="item-card-top"><b>v${esc(v.version)}</b><span class="badge status">${esc(v.status||'pending')}</span></div><div class="item-meta">${esc(v.body||'')}</div><div class="modal-actions" style="justify-content:flex-start;margin-top:6px"><button class="btn secondary btn-sm" data-onclick="submitContentApproval(${esc(v.id)},${contentId},'approved')">${t('approve')}</button><button class="btn danger btn-sm" data-onclick="submitContentApproval(${esc(v.id)},${contentId},'changes_requested')">${t('changesRequested')}</button></div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="item-card" style="margin-top:10px"><div class="field"><textarea id="cvs_body" rows="2" placeholder="${uiText('نص النسخة الجديدة','New version body')}"></textarea></div><button class="btn secondary btn-sm" data-onclick="submitContentVersion(${contentId})">${uiText('نسخة جديدة','New version')}</button></div>
    <div class="section-title">${uiText('الأداء','Analytics')}</div>
    <div class="item-card"><div class="field"><input id="ca_views" type="number" placeholder="${t('views')}"></div><div class="field"><input id="ca_likes" type="number" placeholder="likes"></div><button class="btn secondary btn-sm" data-onclick="submitContentAnalytics(${contentId})">${t('save')}</button></div>
    ${creatorId!=='null'&&creatorId?`<div class="section-title">${uiText('أداء الصانع','Creator performance')}</div><div id="creatorPerfWrap"></div>`:''}`);
  if(creatorId && creatorId!=='null'){
    try{ const perf=await api(`/creators/${creatorId}/performance`);
      const el=document.getElementById('creatorPerfWrap');
      if(el) el.innerHTML=perf.length?`<div class="card-list">${perf.map(p=>`<div class="item-card"><b>${esc(p.title)}</b><div class="item-meta">${esc(p.platform)} · ${fmtNum(p.views||0)} ${t('views')}</div></div>`).join('')}</div>`:`<div class="empty-state">${t('noData')}</div>`;
    }catch(e){}
  }
}
async function submitContentVersion(contentId){try{await api(`/content/${contentId}/versions`,{method:'POST',body:{body:val('cvs_body')}});showToast(t('saved'));openContentDetail(contentId,null);}catch(e){showToast(e.message,true);}}
async function submitContentApproval(versionId,contentId,status){try{await api(`/content/versions/${versionId}/approval`,{method:'POST',body:{status}});showToast(t('saved'));openContentDetail(contentId,null);}catch(e){showToast(e.message,true);}}
async function submitContentAnalytics(contentId){try{await api(`/content/${contentId}/analytics`,{method:'POST',body:{views:Number(val('ca_views'))||0,likes:Number(val('ca_likes'))||0}});showToast(t('saved'));}catch(e){showToast(e.message,true);}}
function openAiIdeasModal(){
  showModal(`
    <div class="modal-title">${t('aiGenerate')}</div>
    <div class="field"><label>${t('niche')}</label><input id="ai_niche" placeholder="e.g. dental clinic"></div>
    <div class="field"><label>${t('platform')}</label><input id="ai_platform" value="tiktok"></div>
    <div class="modal-actions"><button class="btn" data-onclick="generateAiIdeas()">${t('aiGenerate')}</button></div>
    <div id="aiIdeasOut" class="card-list" style="margin-top:14px;"></div>
  `);
}
async function generateAiIdeas(){
  const out = document.getElementById('aiIdeasOut');
  out.innerHTML = t('loading');
  try{
    const r = await api('/ai/content/ideas', {method:'POST', body:{niche:val('ai_niche'), platform:val('ai_platform'), language:LANG}});
    out.innerHTML = r.ideas.map(i=>`<div class="item-card"><div class="item-title">${esc(i.title)}</div><div class="item-meta">${esc(i.hook)}</div></div>`).join('');
  }catch(e){ out.textContent = e.message; }
}

/* ---------------- Finance ---------------- */
async function renderFinance(){
  const content = document.getElementById('content');
  if(!['accountant','sales_manager','founder','admin'].includes(CURRENT_USER.role)){
    content.innerHTML = `<div class="empty-state">${t('noAccess')}</div>`; return;
  }
  content.innerHTML = `<div id="financeSummary" class="grid grid-4" style="margin-bottom:20px;"></div>
    <div class="toolbar"><div></div><button class="btn" data-onclick="openTransactionModal()">${t('addTransaction')}</button></div>
    <div id="transactionsWrap"></div>
    <div class="section-title">${t('invoice')}</div>
    <div id="financeInvoicesWrap"></div>
    <div class="section-title">${uiText('عروض الأسعار','Quotes')}</div>
    <div id="financeQuotesWrap"></div>`;
  try{
    const summary = await api('/summary');
    document.getElementById('financeSummary').innerHTML =
      ledger(t('income'), fmtMoney(summary.income), []) +
      ledger(t('expenses'), fmtMoney(summary.expenses), []) +
      ledger(t('profit'), fmtMoney(summary.gross_profit), []);
    const tx = await api('/transactions');
    const wrap = document.getElementById('transactionsWrap');
    wrap.innerHTML = !tx.length ? `<div class="empty-state">${t('noData')}</div>` :
      `<table><thead><tr><th>${t('type')}</th><th>${t('category')}</th><th>${t('amount')}</th><th>${t('description')}</th></tr></thead>
      <tbody>${tx.map(x=>`<tr><td><span class="badge ${x.type==='income'?'won':'lost'}">${esc(x.type)}</span></td><td>${esc(x.category)}</td><td class="mono">${fmtMoney(x.amount)}</td><td>${esc(x.description||'—')}</td></tr>`).join('')}</tbody></table>`;
    const invoices = await api('/invoices');
    document.getElementById('financeInvoicesWrap').innerHTML = !invoices.length ? `<div class="empty-state">${t('noData')}</div>` :
      `<table><thead><tr><th>${t('invoice')}</th><th>${uiText('الإجمالي','Total')}</th><th>${t('status')}</th><th></th></tr></thead><tbody>${invoices.map(x=>`<tr><td>${esc(x.invoice_number||('#'+x.id))}</td><td class="mono">${fmtMoney(x.total)}</td><td><span class="badge status">${esc(x.status)}</span></td><td><button class="btn secondary btn-sm" data-onclick="openInvoiceDetail(${esc(x.id)})">›</button></td></tr>`).join('')}</tbody></table>`;
    const quotes = await api('/quotes');
    document.getElementById('financeQuotesWrap').innerHTML = !quotes.length ? `<div class="empty-state">${t('noData')}</div>` :
      `<table><thead><tr><th>${t('title')}</th><th>${uiText('الإجمالي','Total')}</th><th>${t('status')}</th><th></th></tr></thead><tbody>${quotes.map(x=>`<tr><td>${esc(x.title||('#'+x.id))}</td><td class="mono">${fmtMoney(x.total||0)}</td><td><span class="badge status">${esc(x.status)}</span></td><td><button class="btn secondary btn-sm" data-onclick="openQuoteDetail(${esc(x.id)})">›</button></td></tr>`).join('')}</tbody></table>`;
  }catch(e){ content.textContent = e.message || t('errorOccurred'); content.className = 'empty-state'; }
}
async function openInvoiceDetail(id){
  const inv=await api('/invoices/'+id);
  showModal(`<div class="modal-title">${esc(inv.invoice_number||('#'+inv.id))}</div>
    <div class="ledger-row"><span>${uiText('الإجمالي','Total')}</span><b>${fmtMoney(inv.total)}</b></div>
    <div class="ledger-row"><span>${uiText('المدفوع','Paid')}</span><b>${fmtMoney(inv.amount_paid||0)}</b></div>
    <div class="ledger-row"><span>${t('status')}</span><b>${esc(inv.status)}</b></div>
    <div class="section-title">${uiText('البنود','Items')}</div>
    <div class="card-list">${(inv.items||[]).map(it=>`<div class="item-card"><b>${esc(it.description)}</b><div class="item-meta">${esc(it.quantity)} × ${fmtMoney(it.unit_price)}</div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="section-title">${uiText('المدفوعات','Payments')}</div>
    <div class="card-list">${(inv.payments||[]).map(p=>`<div class="item-card"><div class="item-card-top"><b>${fmtMoney(p.amount)}</b><span class="item-meta">${esc(p.method||'')}</span></div><div class="modal-actions" style="justify-content:flex-start;margin-top:6px"><input id="pa_amt_${p.id}" type="number" step="0.01" placeholder="${uiText('مبلغ للتخصيص','Amount to allocate')}" style="width:140px"><button class="btn secondary btn-sm" data-onclick="submitPaymentAllocation(${p.id},${id})">${uiText('تخصيص للفاتورة','Allocate to invoice')}</button></div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="section-title">${uiText('تسجيل دفعة','Record payment')}</div>
    <div class="item-card"><div class="field"><input id="ip_amount" type="number" step="0.01" placeholder="${t('amount')}"></div><div class="field"><input id="ip_method" placeholder="${uiText('طريقة الدفع','Method')}"></div><button class="btn secondary btn-sm" data-onclick="submitInvoicePayment(${id})">${t('save')}</button></div>
    <div class="section-title">${uiText('سجل النشاط','Activity log')} <button class="btn secondary btn-sm" data-onclick="loadInvoiceActivity(${id})">↻</button></div>
    <div id="invActivity" class="card-list"></div>
    <div class="modal-actions">${inv.status!=='paid'?`<button class="btn secondary btn-sm" data-onclick="updateInvoiceStatus(${id},'sent')">${uiText('إرسال','Mark sent')}</button><button class="btn secondary btn-sm" data-onclick="updateInvoiceStatus(${id},'cancelled')">${t('cancel')}</button>`:''}</div>`);
}
async function submitPaymentAllocation(paymentId,invoiceId){try{const amt=document.getElementById('pa_amt_'+paymentId).value;await api(`/payments/${paymentId}/allocate`,{method:'POST',body:{invoice_id:invoiceId,amount:parseFloat(amt)||0}});showToast(t('saved'));openInvoiceDetail(invoiceId);}catch(e){showToast(e.message,true);}}
async function loadInvoiceActivity(invoiceId){try{const rows=await api(`/activity/invoice/${invoiceId}`);const el=document.getElementById('invActivity');if(el)el.innerHTML=rows.length?rows.map(a=>`<div class="item-card"><b>${esc(a.action||a.event_type||'')}</b><div class="item-meta">${esc(a.user_name||'')} · ${esc(a.created_at||'')}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`;}catch(e){}}
async function submitInvoicePayment(id){try{await api(`/invoices/${id}/payments`,{method:'POST',body:{amount:parseFloat(val('ip_amount'))||0,method:val('ip_method')}});showToast(t('saved'));openInvoiceDetail(id);renderFinance();}catch(e){showToast(e.message,true);}}
async function updateInvoiceStatus(id,status){try{await api(`/invoices/${id}`,{method:'PATCH',body:{status}});showToast(t('saved'));closeModal();renderFinance();}catch(e){showToast(e.message,true);}}
async function openQuoteDetail(id){
  const q=await api('/quotes/'+id);
  showModal(`<div class="modal-title">${esc(q.title||('#'+q.id))}</div>
    <div class="ledger-row"><span>${uiText('الإجمالي','Total')}</span><b>${fmtMoney(q.total||0)}</b></div>
    <div class="ledger-row"><span>${t('status')}</span><b>${esc(q.status)}</b></div>
    <div class="section-title">${uiText('البنود','Items')}</div>
    <div class="card-list">${(q.items||[]).map(it=>`<div class="item-card"><b>${esc(it.description||'')}</b></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="section-title">${uiText('السجل','History')}</div>
    <div class="card-list">${(q.events||[]).map(ev=>`<div class="item-card"><div class="item-meta">${esc(ev.from_status||'')} → ${esc(ev.to_status||'')} · ${esc(ev.created_at||'')}</div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="modal-actions">${['sent','approved','rejected','converted'].map(s=>`<button class="btn secondary btn-sm" data-onclick="updateQuoteStatus(${id},'${s}')">${s}</button>`).join('')}</div>`);
}
async function updateQuoteStatus(id,status){try{await api(`/quotes/${id}`,{method:'PATCH',body:{status}});showToast(t('saved'));openQuoteDetail(id);}catch(e){showToast(e.message,true);}}
function openTransactionModal(){
  showModal(`
    <div class="modal-title">${t('addTransaction')}</div>
    <div class="field"><label>${t('type')}</label><select id="tx_type"><option value="income">income</option><option value="expense">expense</option></select></div>
    <div class="field"><label>${t('category')}</label><input id="tx_category"></div>
    <div class="field"><label>${t('amount')}</label><input id="tx_amount" type="number"></div>
    <div class="field"><label>${t('description')}</label><input id="tx_desc"></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitTransaction()">${t('save')}</button></div>
  `);
}
async function submitTransaction(){
  try{
    await api('/transactions', {method:'POST', body:{type:val('tx_type'), category:val('tx_category'), amount:parseFloat(val('tx_amount'))||0, description:val('tx_desc')}});
    closeModal(); showToast(t('saved')); renderFinance();
  }catch(e){ showToast(e.message, true); }
}

/* ---------------- Requests (auto -> Task) ---------------- */
async function renderRequests(){
  const content=document.getElementById('content');
  content.innerHTML=`<div class="toolbar"><div></div><button class="btn" data-onclick="openRequestModal()">${t('addRequest')}</button></div><div id="requestsWrap"></div>`;
  const reqs=await api('/requests'); const wrap=document.getElementById('requestsWrap');
  wrap.innerHTML=!reqs.length?`<div class="empty-state">${t('noData')}</div>`:`<table><thead><tr><th>${t('title')}</th><th>${t('requesterName')}</th><th>${t('nav_clients')}</th><th>${t('nav_projects')}</th><th>${t('priority')}</th><th>${t('status')}</th><th>${t('actions')}</th></tr></thead><tbody>${reqs.map(r=>`<tr>
    <td>${esc(r.title)}</td><td>${esc(r.requester_name||'—')}</td><td>${esc(r.client_id||'—')}</td><td>${esc(r.project_id||'—')}</td><td><span class="badge status">${esc(r.priority)}</span></td>
    <td><span class="badge status">${esc(r.status)}</span></td>
    <td>${r.status!=='resolved'?`<button class="btn secondary btn-sm" data-onclick="resolveDomainRequest(${esc(r.id)})">${t('save')}</button>`:'✓'}</td></tr>`).join('')}</tbody></table>`;
}
function openRequestModal(){
  showModal(`<div class="modal-title">${t('addRequest')}</div>
    <div class="field"><label>${t('title')}</label><input id="rqn_title"></div>
    <div class="field"><label>${t('requesterName')}</label><input id="rqn_requester"></div>
    <div class="field"><label>${t('description')}</label><textarea id="rqn_desc" rows="3"></textarea></div>
    <div class="field"><label>${t('priority')}</label><select id="rqn_priority"><option value="low">low</option><option value="medium" selected>medium</option><option value="high">high</option><option value="urgent">urgent</option></select></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitRequest()">${t('save')}</button></div>`);
}
async function submitRequest(){
  try{
    await api('/requests',{method:'POST',body:{title:val('rqn_title'),requester_name:val('rqn_requester'),description:val('rqn_desc'),priority:val('rqn_priority')}});
    closeModal(); showToast(t('saved')); renderRequests();
  }catch(e){ showToast(e.message,true); }
}
async function openRequestAssignment(id){
  const [req,projects,employees]=await Promise.all([api(`/requests/${id}`),api('/projects'),api('/employees')]);
  showModal(`<div class="modal-title">${t('requestAssignment')}</div><div class="field"><label>${t('project')}</label><select id="rq_project"><option value="">—</option>${projects.filter(p=>!req.client_id||p.client_id===req.client_id).map(p=>`<option value="${p.id}" ${Number(req.project_id)===Number(p.id)?'selected':''}>${esc(p.name)}</option>`).join('')}</select></div><div class="field"><label>${t('employee')}</label><select id="rq_user"><option value="">—</option>${employees.map(e=>`<option value="${e.user_id}" ${Number(req.assigned_to)===Number(e.user_id)?'selected':''}>${esc(e.name)}</option>`).join('')}</select></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitRequestAssignment(${id})">${t('assign')}</button></div>`);
}
async function submitRequestAssignment(id){try{await api(`/requests/${id}/assign`,{method:'POST',body:{project_id:val('rq_project')?Number(val('rq_project')):null,assigned_to:val('rq_user')?Number(val('rq_user')):null}});closeModal();showToast(t('saved'));renderRequests();}catch(e){showToast(e.message,true);}}

async function resolveDomainRequest(id){
  const resolution=prompt(LANG==='ar'?'اكتب الحل':'Enter resolution','Resolved');
  if(resolution===null) return;
  try{ await api(`/requests/${id}/resolve`,{method:'POST',body:{resolution}}); showToast(t('saved')); renderRequests(); }
  catch(e){ showToast(e.message,true); }
}

/* ---------------- HR: Attendance ---------------- */
const MANAGER_ROLES = ['founder','admin','sales_manager','project_manager','content_manager'];
let ATTENDANCE_VIEW = 'mine';
async function renderHr(){
  const isManager = MANAGER_ROLES.includes(CURRENT_USER.role);
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="toolbar">
      <div class="filters">
        ${isManager ? `
          <button class="btn secondary btn-sm" data-onclick="setAttendanceView('mine')" id="avMine">${t('myAttendance')}</button>
          <button class="btn secondary btn-sm" data-onclick="setAttendanceView('team')" id="avTeam">${t('teamAttendance')}</button>
        ` : ''}
      </div>
      <div>
        ${isManager ? `<button class="btn secondary btn-sm" data-onclick="openOfficeSettingsModal()">${t('officeLocation')}</button>` : ''}
        <button class="btn secondary btn-sm" data-onclick="doCheckIn()">${t('checkIn')}</button>
        <button class="btn btn-sm" data-onclick="doCheckOut()">${t('checkOut')}</button>
      </div>
    </div>
    <div id="attendanceGeoNote" class="item-meta" style="margin-bottom:14px;"></div>
    <div id="attendanceWrap"></div>
  `;
  updateAttendanceViewButtons();
  if(ATTENDANCE_VIEW === 'team' && isManager) await renderTeamAttendance();
  else await renderMyAttendance();
}
function setAttendanceView(v){ ATTENDANCE_VIEW = v; renderHr(); }
function updateAttendanceViewButtons(){
  const m = document.getElementById('avMine'), tm = document.getElementById('avTeam');
  if(!m) return;
  m.style.borderColor = ATTENDANCE_VIEW==='mine' ? 'var(--gold)' : 'var(--line)';
  m.style.color = ATTENDANCE_VIEW==='mine' ? 'var(--gold)' : 'var(--text)';
  tm.style.borderColor = ATTENDANCE_VIEW==='team' ? 'var(--gold)' : 'var(--line)';
  tm.style.color = ATTENDANCE_VIEW==='team' ? 'var(--gold)' : 'var(--text)';
}
async function renderMyAttendance(){
  const rows = await api('/attendance');
  const wrap = document.getElementById('attendanceWrap');
  wrap.innerHTML = !rows.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<table><thead><tr><th>${t('date')}</th><th>${t('checkIn')}</th><th>${t('checkOut')}</th><th>${t('status')}</th></tr></thead>
    <tbody>${rows.map(r=>`<tr><td class="mono">${esc(r.date)}</td><td class="mono">${esc(r.check_in||'—')}</td><td class="mono">${esc(r.check_out||'—')}</td>
      <td><span class="badge status">${esc(r.status)}</span> ${r.is_flagged?`<span class="badge lost" title="${esc(r.flag_reason||'')}">⚑ ${t('flagged')}</span>`:''}</td></tr>`).join('')}</tbody></table>`;
}
async function renderTeamAttendance(){
  const rows = await api('/attendance/team');
  const wrap = document.getElementById('attendanceWrap');
  wrap.innerHTML = !rows.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<table><thead><tr><th>${t('name')}</th><th>${t('date')}</th><th>${t('checkIn')}</th><th>${t('checkOut')}</th><th>${t('status')}</th><th>${t('actions')}</th></tr></thead>
    <tbody>${rows.map(r=>`<tr>
      <td>${esc(r.user_name)}</td><td class="mono">${esc(r.date)}</td><td class="mono">${esc(r.check_in||'—')}</td><td class="mono">${esc(r.check_out||'—')}</td>
      <td>${r.is_flagged ? `<span class="badge lost" title="${esc(r.flag_reason||'')}">⚑ ${esc(r.flag_reason||t('flagged'))}</span>` : `<span class="badge won">${t('ok')}</span>`}</td>
      <td>${r.is_flagged ? `<button class="btn secondary btn-sm" data-onclick="clearFlag(${esc(r.id)})">${t('clearFlag')}</button>` : '—'}</td>
    </tr>`).join('')}</tbody></table>`;
}
async function clearFlag(id){
  try{ await api(`/attendance/${id}/clear-flag`, {method:'PATCH'}); showToast(t('saved')); renderTeamAttendance(); }
  catch(e){ showToast(e.message, true); }
}

function getGeolocation(){
  return new Promise((resolve)=>{
    if(!navigator.geolocation){ resolve(null); return; }
    navigator.geolocation.getCurrentPosition(
      pos => resolve({latitude: pos.coords.latitude, longitude: pos.coords.longitude}),
      () => resolve(null),
      {timeout: 6000}
    );
  });
}
async function doCheckIn(){
  const note = document.getElementById('attendanceGeoNote');
  if(note) note.textContent = t('locatingNote');
  const geo = await getGeolocation();
  if(note) note.textContent = geo ? '' : t('noLocationNote');
  try{ await api('/attendance/check-in', {method:'POST', body: geo||{}}); showToast(t('saved')); renderHr(); }
  catch(e){ showToast(e.message, true); }
}
async function doCheckOut(){
  const geo = await getGeolocation();
  try{ await api('/attendance/check-out', {method:'POST', body: geo||{}}); showToast(t('saved')); renderHr(); }
  catch(e){ showToast(e.message, true); }
}
async function openOfficeSettingsModal(){
  const s = await api('/company/settings');
  showModal(`
    <div class="modal-title">${t('officeLocation')}</div>
    <div class="item-meta" style="margin-bottom:14px;">${t('officeLocationNote')}</div>
    <div class="field"><label>${t('latitude')}</label><input id="off_lat" type="number" step="any" value="${esc(s.office_lat ?? '')}"></div>
    <div class="field"><label>${t('longitude')}</label><input id="off_lng" type="number" step="any" value="${esc(s.office_lng ?? '')}"></div>
    <div class="field"><label>${t('radiusMeters')}</label><input id="off_radius" type="number" value="${esc(s.office_radius_m ?? 200)}"></div>
    <button class="btn secondary btn-sm" data-onclick="useMyLocation()">${t('useMyLocation')}</button>
    <div class="modal-actions"><button class="btn" data-onclick="saveOfficeSettings()">${t('save')}</button></div>
  `);
}
async function useMyLocation(){
  const geo = await getGeolocation();
  if(geo){ document.getElementById('off_lat').value = geo.latitude; document.getElementById('off_lng').value = geo.longitude; }
  else showToast(t('noLocationNote'), true);
}
async function saveOfficeSettings(){
  try{
    await api('/company/settings', {method:'PATCH', body:{
      office_lat: parseFloat(val('off_lat'))||null, office_lng: parseFloat(val('off_lng'))||null,
      office_radius_m: parseInt(val('off_radius'))||200,
    }});
    showToast(t('saved')); closeModal();
  }catch(e){ showToast(e.message, true); }
}

/* ---------------- Academy ---------------- */
async function renderAcademy(){
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="toolbar"><div></div><button class="btn" data-onclick="openCourseModal()">${t('addCourse')}</button></div>
    <div class="section-title">${t('courses')}</div>
    <div class="card-list" id="coursesWrap"></div>
    <div class="section-title">${t('myCertificates')}</div>
    <div id="certsWrap"></div>
    <div class="toolbar"><div class="section-title" style="margin:0">${uiText('التقييمات','Assessments')}</div><button class="btn secondary btn-sm" data-onclick="openAssessmentModal()">+</button></div>
    <div class="card-list" id="assessmentsWrap"></div>
    <div class="toolbar"><div class="section-title" style="margin:0">${uiText('المدرّسين','Instructors')}</div><button class="btn secondary btn-sm" data-onclick="openInstructorModal()">+</button></div>
    <div class="card-list" id="instructorsWrap"></div>
  `;
  const courses = await api('/courses');
  document.getElementById('coursesWrap').innerHTML = !courses.length ? `<div class="empty-state">${t('noData')}</div>` :
    courses.map(c=>`<div class="item-card">
      <div class="item-card-top"><div><div class="item-title">${esc(c.title)}</div><div class="item-meta">${esc(c.description||'')} · ${esc(c.weeks)} ${t('weeks')}</div></div>
      <button class="btn secondary btn-sm" data-onclick="openCourseDetail(${esc(c.id)})">${t('lessons')} ›</button></div>
    </div>`).join('');

  const certs = await api('/certificates');
  document.getElementById('certsWrap').innerHTML = !certs.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<div class="card-list">${certs.map(c=>`<div class="item-card"><div class="item-title">🎓 ${esc(c.course_title)}</div><div class="item-meta mono">${esc(c.certificate_code)}</div></div>`).join('')}</div>`;

  const assessments = await api('/academy/assessments');
  document.getElementById('assessmentsWrap').innerHTML = !assessments.length ? `<div class="empty-state">${t('noData')}</div>` :
    assessments.map(a=>`<div class="item-card"><div class="item-card-top"><div><div class="item-title">${esc(a.title)}</div><div class="item-meta">${esc(a.course_title||'')} · ${uiText('حد النجاح','Pass')} ${esc(a.pass_score)}/${esc(a.max_score)}</div></div><button class="btn secondary btn-sm" data-onclick="openAssessmentAttemptModal(${esc(a.id)})">${uiText('تسجيل محاولة','Log attempt')}</button></div></div>`).join('');

  const instructors = await api('/academy/instructors');
  document.getElementById('instructorsWrap').innerHTML = !instructors.length ? `<div class="empty-state">${t('noData')}</div>` :
    instructors.map(i=>`<div class="item-card"><div class="item-title">${esc(i.name)}</div><div class="item-meta">${esc(i.bio||'')} <span class="badge status">${esc(i.status)}</span></div></div>`).join('');
}
function openInstructorModal(){
  showModal(`<div class="modal-title">${uiText('مدرّس جديد','New instructor')}</div><div class="field"><label>${t('name')}</label><input id="in_name"></div><div class="field"><label>${uiText('نبذة','Bio')}</label><textarea id="in_bio" rows="2"></textarea></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitInstructor()">${t('save')}</button></div>`);
}
async function submitInstructor(){try{await api('/academy/instructors',{method:'POST',body:{name:val('in_name'),bio:val('in_bio')}});closeModal();showToast(t('saved'));renderAcademy();}catch(e){showToast(e.message,true);}}
async function openAssessmentModal(){
  const courses = await api('/courses');
  showModal(`<div class="modal-title">${uiText('تقييم جديد','New assessment')}</div><div class="field"><label>${uiText('الكورس','Course')}</label><select id="as_course">${courses.map(c=>`<option value="${c.id}">${esc(c.title)}</option>`).join('')}</select></div><div class="field"><label>${t('title')}</label><input id="as_title"></div><div class="field"><label>${uiText('أقصى درجة','Max score')}</label><input id="as_max" type="number" value="100"></div><div class="field"><label>${uiText('درجة النجاح','Passing score')}</label><input id="as_pass" type="number" value="60"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitAssessment()">${t('save')}</button></div>`);
}
async function submitAssessment(){try{await api('/academy/assessments',{method:'POST',body:{course_id:Number(val('as_course')),title:val('as_title'),max_score:parseFloat(val('as_max'))||100,passing_score:parseFloat(val('as_pass'))||60}});closeModal();showToast(t('saved'));renderAcademy();}catch(e){showToast(e.message,true);}}
async function openAssessmentAttemptModal(assessmentId){
  const students = await api('/academy/students');
  showModal(`<div class="modal-title">${uiText('تسجيل محاولة','Log attempt')}</div><div class="field"><label>${uiText('الطالب','Student')}</label><select id="at_student">${students.map(s=>`<option value="${s.id}">${esc(s.name)} ${s.student_code?('('+esc(s.student_code)+')'):''}</option>`).join('')}</select></div><div class="field"><label>${uiText('الدرجة','Score')}</label><input id="at_score" type="number"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitAssessmentAttempt(${assessmentId})">${t('save')}</button></div>`);
}
async function submitAssessmentAttempt(assessmentId){try{await api(`/academy/assessments/${assessmentId}/attempts`,{method:'POST',body:{student_id:Number(val('at_student')),score:parseFloat(val('at_score'))||0}});closeModal();showToast(t('saved'));}catch(e){showToast(e.message,true);}}
function openCourseModal(){
  showModal(`
    <div class="modal-title">${t('addCourse')}</div>
    <div class="field"><label>${t('title')}</label><input id="co_title"></div>
    <div class="field"><label>${t('description')}</label><textarea id="co_desc" rows="2"></textarea></div>
    <div class="field"><label>${t('weeks')}</label><input id="co_weeks" type="number" value="4"></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitCourse()">${t('save')}</button></div>
  `);
}
async function submitCourse(){
  try{ await api('/courses', {method:'POST', body:{title:val('co_title'), description:val('co_desc'), weeks:parseInt(val('co_weeks'))||1}});
    closeModal(); showToast(t('saved')); renderAcademy(); }
  catch(e){ showToast(e.message, true); }
}
async function openCourseDetail(id){
  const c = await api('/courses/'+id);
  showModal(`
    <div class="modal-title">${esc(c.title)}</div>
    <div class="card-list">
      ${(c.lessons||[]).map(l=>`<div class="item-card"><div class="item-title">${esc(l.title)}</div></div>`).join('') || `<div class="empty-state">${t('noData')}</div>`}
    </div>
    <div class="item-card" style="margin-top:10px"><div class="field"><input id="ls_title" placeholder="${t('title')}"></div><button class="btn secondary btn-sm" data-onclick="submitLesson(${id})">${uiText('إضافة درس','Add lesson')}</button></div>
    <div class="modal-actions"><button class="btn secondary btn-sm" data-onclick="enrollInCourse(${id})">${t('enroll')}</button></div>
  `);
}
async function submitLesson(courseId){try{await api(`/courses/${courseId}/lessons`,{method:'POST',body:{title:val('ls_title')}});showToast(t('saved'));openCourseDetail(courseId);}catch(e){showToast(e.message,true);}}
async function enrollInCourse(courseId){
  try{
    const c = await api('/courses/'+courseId);
    const r = await api(`/courses/${courseId}/enroll`, {method:'POST', body:{}});
    showToast(t('saved'));
    showModal(`<div class="modal-title">${esc(c.title)}</div>
      <div class="section-title">${uiText('الدروس','Lessons')}</div>
      <div class="card-list">${(c.lessons||[]).map(l=>`<div class="item-card"><div class="item-card-top"><div class="item-title">${esc(l.title)}</div><button class="btn secondary btn-sm" data-onclick="completeLesson(${r.id},${l.id})">${uiText('إنجاز','Mark complete')}</button></div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>`);
  }
  catch(e){ showToast(e.message, true); }
}
async function completeLesson(enrollmentId,lessonId){try{await api(`/enrollments/${enrollmentId}/lessons/${lessonId}/complete`,{method:'POST',body:{}});showToast(t('saved'));}catch(e){showToast(e.message,true);}}

/* ---------------- SOP Center ---------------- */
function sopSearchEnter(e){ if(e && e.key==='Enter') renderSop(); }
async function renderSop(){
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="toolbar">
      <input id="sopSearch" placeholder="${t('searchSop')}" style="background:var(--surface-2); border:1px solid var(--line); border-radius:var(--radius); padding:8px 12px; min-width:220px;" data-onkeyup="sopSearchEnter(event)">
      <button class="btn" data-onclick="openSopModal()">${t('addSop')}</button>
    </div>
    <div class="card-list" id="sopWrap"></div>
  `;
  const q = document.getElementById('sopSearch') ? document.getElementById('sopSearch').value : '';
  const sops = await api('/sop' + (q ? '?q='+encodeURIComponent(q) : ''));
  const wrap = document.getElementById('sopWrap');
  wrap.innerHTML = !sops.length ? `<div class="empty-state">${t('noData')}</div>` :
    sops.map(s=>`<div class="item-card">
      <div class="item-card-top"><div class="item-title">${esc(s.title)}</div><span class="badge status">${esc(s.category_name||'—')}</span></div>
      <div class="item-meta" style="margin-top:8px; color:var(--text-dim); font-size:13px;">${esc(s.content)}</div>
      <div class="modal-actions" style="justify-content:flex-start;margin-top:8px"><button class="btn danger btn-sm" data-onclick="deleteSop(${esc(s.id)})">${t('delete')}</button></div>
    </div>`).join('');
}
async function deleteSop(id){try{await api(`/sop/${id}`,{method:'DELETE'});showToast(t('saved'));renderSop();}catch(e){showToast(e.message,true);}}
function openSopModal(){
  showModal(`
    <div class="modal-title">${t('addSop')}</div>
    <div class="field"><label>${t('title')}</label><input id="sop_title"></div>
    <div class="field"><label>${t('category')}</label><input id="sop_category" placeholder="e.g. Client Onboarding"></div>
    <div class="field"><label>${t('content')}</label><textarea id="sop_content" rows="5"></textarea></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitSop()">${t('save')}</button></div>
  `);
}
async function submitSop(){
  try{
    let categoryId = null;
    const catName = val('sop_category');
    if(catName){
      const cats = await api('/sop/categories');
      const existing = cats.find(c=>c.name.toLowerCase()===catName.toLowerCase());
      categoryId = existing ? existing.id : (await api('/sop/categories', {method:'POST', body:{name:catName}})).id;
    }
    await api('/sop', {method:'POST', body:{title:val('sop_title'), content:val('sop_content'), category_id:categoryId}});
    closeModal(); showToast(t('saved')); renderSop();
  }catch(e){ showToast(e.message, true); }
}

/* ---------------- Assets & Equipment ---------------- */
async function renderAssets(){
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="toolbar"><div></div><button class="btn" data-onclick="openAssetModal()">${t('addAsset')}</button></div>
    <div id="assetsWrap"></div>
  `;
  const assets = await api('/assets');
  const wrap = document.getElementById('assetsWrap');
  wrap.innerHTML = !assets.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<table><thead><tr><th>${t('name')}</th><th>${t('category')}</th><th>${t('location')}</th><th>${t('status')}</th><th>${t('value')}</th><th>${t('actions')}</th></tr></thead>
    <tbody>${assets.map(a=>`<tr>
      <td>${esc(a.name)}</td><td>${esc(a.category||'—')}</td><td>${esc(a.location||'—')}</td>
      <td><span class="badge status">${esc(a.status)}</span></td><td class="mono">${a.value?fmtMoney(a.value):'—'}</td>
      <td><button class="btn secondary btn-sm" data-onclick="openMaintenanceModal(${esc(a.id)})">${t('logMaintenance')}</button></td>
    </tr>`).join('')}</tbody></table>`;
}
function openAssetModal(){
  showModal(`
    <div class="modal-title">${t('addAsset')}</div>
    <div class="field"><label>${t('name')}</label><input id="as_name"></div>
    <div class="field"><label>${t('category')}</label><input id="as_category" placeholder="camera / laptop / ..."></div>
    <div class="field"><label>${t('location')}</label><input id="as_location"></div>
    <div class="field"><label>${t('value')}</label><input id="as_value" type="number"></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitAsset()">${t('save')}</button></div>
  `);
}
async function submitAsset(){
  try{ await api('/assets', {method:'POST', body:{name:val('as_name'), category:val('as_category'), location:val('as_location'), value:parseFloat(val('as_value'))||null}});
    closeModal(); showToast(t('saved')); renderAssets(); }
  catch(e){ showToast(e.message, true); }
}
function openMaintenanceModal(assetId){
  showModal(`
    <div class="modal-title">${t('logMaintenance')}</div>
    <div class="field"><label>${t('content')}</label><textarea id="m_notes" rows="2"></textarea></div>
    <div class="field"><label>${t('amount')}</label><input id="m_cost" type="number"></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitMaintenance(${assetId})">${t('save')}</button></div>
  `);
}
async function submitMaintenance(assetId){
  try{ await api(`/assets/${assetId}/maintenance`, {method:'POST', body:{notes:val('m_notes'), cost:parseFloat(val('m_cost'))||0}});
    closeModal(); showToast(t('saved')); renderAssets(); }
  catch(e){ showToast(e.message, true); }
}

/* ---------------- Creators (staff management) ---------------- */
async function renderCreators(){
  const content = document.getElementById('content');
  content.innerHTML = `<div class="toolbar"><div></div><button class="btn" data-onclick="openCreatorModal()">+ ${t('nav_creators')}</button></div><div id="creatorsWrap"></div>`;
  const creators = await api('/creators');
  const wrap = document.getElementById('creatorsWrap');
  wrap.innerHTML = !creators.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<table><thead><tr><th>${t('name')}</th><th>${t('niche')}</th><th>${t('loginCode')}</th></tr></thead>
    <tbody>${creators.map(c=>`<tr><td>${esc(c.stage_name)}</td><td>${esc(c.niche||'—')}</td><td class="mono">${esc(c.login_code||'—')}</td></tr>`).join('')}</tbody></table>`;
}
function openCreatorModal(){
  showModal(`
    <div class="modal-title">${t('nav_creators')}</div>
    <div class="field"><label>${t('name')}</label><input id="cr_name"></div>
    <div class="field"><label>${t('niche')}</label><input id="cr_niche"></div>
    <div class="field" style="display:flex; align-items:center; gap:8px;">
      <input type="checkbox" id="cr_create_login" style="width:auto;" checked>
      <label style="margin:0;">${t('createLogin')}</label>
    </div>
    <div class="modal-actions"><button class="btn" data-onclick="submitCreator()">${t('save')}</button></div>
  `);
}
async function submitCreator(){
  try{
    const r = await api('/creators', {method:'POST', body:{
      stage_name: val('cr_name'), niche: val('cr_niche'), create_login: document.getElementById('cr_create_login').checked,
    }});
    if(r.portal_login_code){
      showModal(`
        <div class="modal-title">✅ ${t('saved')}</div>
        <div class="item-meta" style="margin-bottom:14px;">${t('portalCredentialsNote')}</div>
        <div class="ledger" style="margin-bottom:10px;">
          <div class="ledger-row"><span>${t('loginCode')}</span><b class="mono">${esc(r.portal_login_code)}</b></div>
          <div class="ledger-row"><span>${t('tempPassword')}</span><b class="mono">${esc(r.portal_temp_password)}</b></div>
        </div>
        <div class="modal-actions"><button class="btn" data-onclick="closeModal(); renderCreators();">${t('save')}</button></div>
      `);
    } else {
      closeModal(); showToast(t('saved')); renderCreators();
    }
  }catch(e){ showToast(e.message, true); }
}

/* ---------------- Creator Portal (restricted 'model' role view) ---------------- */
async function renderPortalTasks(){
  const content = document.getElementById('content');
  const tasks = await api('/creator-portal/my-tasks');
  let profileHtml='';
  try{ const me=await api('/creator-portal/me'); profileHtml=`<div class="grid grid-3" style="margin-bottom:16px">${ledger(t('name'),me.stage_name||'—',[])}${ledger(t('niche'),me.niche||'—',[])}${ledger(uiText('كود الدخول','Login code'),me.login_code||'—',[])}</div>`; }catch(e){}
  content.innerHTML = profileHtml + (!tasks.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<div class="card-list">${tasks.map(tk=>`<div class="item-card">
      <div class="item-card-top"><div class="item-title">${esc(tk.title)}</div><span class="badge status">${esc(tk.status)}</span></div>
      <div class="item-meta">${t('priority')}: ${esc(tk.priority)} ${tk.deadline?('· '+t('deadline')+': '+esc(tk.deadline)):''}</div>
    </div>`).join('')}</div>`);
}
async function renderPortalContent(){
  const content = document.getElementById('content');
  const items = await api('/creator-portal/my-content');
  content.innerHTML = !items.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<div class="card-list">${items.map(c=>`<div class="item-card">
      <div class="item-card-top"><div class="item-title">${esc(c.title)}</div><span class="badge status">${esc(c.status)}</span></div>
      <div class="item-meta">${esc(c.platform||'')} ${safeUrl(c.video_url)?`· <a href="${esc(safeUrl(c.video_url))}" target="_blank" rel="noopener noreferrer">${t('videoUrl')}</a>`:''}</div>
    </div>`).join('')}</div>`;
}
async function renderPortalSubmit(){
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="field"><label>${t('title')}</label><input id="ps_title"></div>
    <div class="field"><label>${t('platform')}</label><input id="ps_platform" placeholder="tiktok / instagram / youtube"></div>
    <div class="field"><label>${t('hook')}</label><input id="ps_hook"></div>
    <div class="field"><label>${t('videoUrl')}</label><input id="ps_video" placeholder="https://..."></div>
    <button class="btn" data-onclick="submitPortalContent()">${t('submitContent')}</button>
    <div id="portalSubmitOut" style="margin-top:14px;"></div>
  `;
}
async function submitPortalContent(){
  try{
    await api('/creator-portal/submit', {method:'POST', body:{
      title: val('ps_title'), platform: val('ps_platform'), hook: val('ps_hook'), video_url: val('ps_video'),
    }});
    showToast(t('saved'));
    document.getElementById('portalSubmitOut').innerHTML = `<div class="item-card">✅ ${t('saved')}</div>`;
    ['ps_title','ps_platform','ps_hook','ps_video'].forEach(id => document.getElementById(id).value = '');
  }catch(e){ showToast(e.message, true); }
}

/* ---------------- Security (2FA + Sessions) ---------------- */
async function renderSecurity(){
  const content = document.getElementById('content');
  const me = await api('/auth/me');
  content.innerHTML = `
    <div class="section-title">${t('twoFaStatus')}</div>
    <div class="item-card" style="margin-bottom:20px;">
      <div class="item-card-top">
        <div class="item-title">${me.totp_enabled ? '🔒 ' + t('enabled') : '🔓 ' + t('notEnabled')}</div>
        ${me.totp_enabled
          ? `<button class="btn secondary btn-sm" data-onclick="openDisable2faModal()">${t('disable2fa')}</button>`
          : `<button class="btn btn-sm" data-onclick="start2faSetup()">${t('enable2fa')}</button>`}
      </div>
    </div>
    <div id="twoFaSetupWrap"></div>

    <div class="section-title">${t('activeSessions')}</div>
    <div class="toolbar"><div></div><button class="btn secondary btn-sm" data-onclick="logoutAllSessions()">${t('logoutAllSessions')}</button></div>
    <div id="sessionsWrap"></div>
  `;
  const sessions = await api('/auth/sessions');
  document.getElementById('sessionsWrap').innerHTML = !sessions.length ? `<div class="empty-state">${t('noData')}</div>` :
    `<table><thead><tr><th>${t('device')}</th><th>${t('lastActive')}</th><th>${t('actions')}</th></tr></thead>
    <tbody>${sessions.filter(s=>!s.is_revoked).map(s=>`<tr>
      <td style="font-size:12px; color:var(--text-dim);">${(s.user_agent||'—').slice(0,50)}</td>
      <td class="mono">${esc(s.last_used_at)}</td>
      <td><button class="btn secondary btn-sm" data-onclick="revokeSession(${esc(s.id)})">${t('revoke')}</button></td>
    </tr>`).join('')}</tbody></table>`;
}
async function start2faSetup(){
  const password = window.prompt(t('password'));
  if(!password) return;
  const code = window.prompt(t('twoFaCode') + ' (required if 2FA is already enabled)') || '';
  const wrap = document.getElementById('twoFaSetupWrap');
  wrap.innerHTML = t('loading');
  try{
    const r = await api('/auth/2fa/setup', {method:'POST', body:{password, code}});
    wrap.innerHTML = `
      <div class="item-card">
        <div class="item-meta" style="margin-bottom:10px;">${t('scanQr')}</div>
        <div id="qrHolder" style="background:#fff; padding:12px; width:fit-content; border-radius:4px; margin-bottom:12px;"></div>
        <div class="mono" style="font-size:12px; color:var(--text-dim); margin-bottom:12px; word-break:break-all;">${esc(r.secret)}</div>
        <div class="field"><label>${t('confirmCode')}</label><input id="tfa_confirm_code" maxlength="6" inputmode="numeric"></div>
        <button class="btn btn-sm" data-onclick="confirm2fa()">${t('verify')}</button>
      </div>
    `;
    // Keep the frontend self-contained: show the provisioning URI instead of
    // loading third-party executable JavaScript at runtime.
    const uri = document.createElement('div');
    uri.className = 'mono';
    uri.style.cssText = 'font-size:12px;color:var(--text-dim);word-break:break-all;margin-bottom:12px;';
    uri.textContent = r.provisioning_uri;
    document.getElementById('qrHolder').replaceWith(uri);
  }catch(e){ wrap.innerHTML = e.message; }
}
async function confirm2fa(){
  try{
    await api('/auth/2fa/confirm', {method:'POST', body:{code: val('tfa_confirm_code')}});
    showToast(t('saved')); renderSecurity();
  }catch(e){ showToast(e.message, true); }
}
function openDisable2faModal(){
  showModal(`
    <div class="modal-title">${t('disable2fa')}</div>
    <div class="field"><label>${t('password')}</label><input id="disable2faPassword" type="password" autocomplete="current-password"></div>
    <div class="field"><label>${t('twoFaCode')}</label><input id="disable2faCode" inputmode="numeric" maxlength="6" autocomplete="one-time-code"></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="disable2fa()">${t('verify')}</button></div>
  `);
}
async function disable2fa(){
  const password = val('disable2faPassword');
  const code = val('disable2faCode').trim();
  try{
    await api('/auth/2fa/disable', {method:'POST', body:{password, code}});
    showToast(t('saved')); closeModal(); renderSecurity();
  }catch(e){ showToast(e.message, true); }
}
async function revokeSession(id){
  try{ await api(`/auth/sessions/${id}/revoke`, {method:'POST'}); showToast(t('saved')); renderSecurity(); }
  catch(e){ showToast(e.message, true); }
}
async function logoutAllSessions(){
  try{ await api('/auth/logout-all', {method:'POST'}); showToast(t('saved')); logout(); }
  catch(e){ showToast(e.message, true); }
}

/* ---------------- Modal helpers ---------------- */
function showModal(html){
  document.getElementById('modalBody').innerHTML = `<span class="modal-close-x" data-onclick="closeModal()" title="${t('cancel')}">✕</span>${html}`;
  document.getElementById('overlay').classList.add('visible');
}
function closeModal(){ document.getElementById('overlay').classList.remove('visible'); }
document.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') closeModal(); });
document.getElementById('overlay').addEventListener('click', (e)=>{ if(e.target.id==='overlay') closeModal(); });
function val(id){ const el = document.getElementById(id); return el ? el.value : ''; }

/* ---------------- Boot ---------------- */
async function bootstrapSession(){
  applyStaticTranslations();
  try{
    const r = await apiRaw('/auth/refresh', {method:'POST'});
    if(r.res.ok && r.data && r.data.access_token){
      ACCESS_TOKEN = r.data.access_token;
      const me = await api('/auth/me');
      CURRENT_USER = me;
        enterApp();
      return;
    }
  }catch(e){}
  if(CURRENT_USER) applyStaticTranslations();
}
bootstrapSession();



/* ---------------- Complete Operations Control Center ---------------- */
function uiText(ar,en){ return LANG==='ar' ? ar : en; }
async function renderOps(){
  const c=document.getElementById('content');
  c.innerHTML=`
    <div class="toolbar"><div style="flex:1;display:flex;gap:8px;max-width:680px"><input id="globalSearchInput" placeholder="${uiText('بحث شامل في العملاء والمشاريع والمهام والطلبات والفواتير...','Search clients, projects, tasks, requests, invoices...')}" style="flex:1;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:10px 12px" data-onkeyup="globalSearchEnter(event)"><button class="btn" data-onclick="runGlobalSearch()">${uiText('بحث','Search')}</button></div><button class="btn secondary" data-onclick="loadOpsReports()">${uiText('تحديث التقارير','Refresh reports')}</button></div>
    <div id="opsSearchResults"></div>
    <div class="grid grid-4" id="opsKpis"></div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="ledger"><div class="ledger-eyebrow">${uiText('إدارة الشركة','Company')}</div><div id="opsSettings"></div></section>
      <section class="ledger"><div class="ledger-eyebrow">${uiText('تفضيلات الإشعارات','Notifications')}</div><div id="opsNotifications"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('الإجازات','Leave requests')} <button class="btn btn-sm" data-onclick="openLeaveModal()">+</button></div><div id="opsLeave"></div></section>
      <section class="card"><div class="section-title">${uiText('الرواتب','Payroll')} <button class="btn btn-sm" data-onclick="createPayrollRun()">${uiText('إنشاء كشف','Create run')}</button></div><div id="opsPayroll"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('الأكاديمية','Academy')} <button class="btn btn-sm" data-onclick="openStudentModal()">+</button></div><div id="opsAcademy"></div></section>
      <section class="card"><div class="section-title">${uiText('الإنتاج والمحتوى','Content production')}</div><div id="opsContent"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('المحادثات','Conversations')} <button class="btn btn-sm" data-onclick="openConversationModal()">+</button></div><div id="opsConversations"></div></section>
      <section class="card"><div class="section-title">${uiText('الملفات','Files')}</div><div id="opsFiles"></div></section>
    </div>
    <div class="grid grid-3" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('عروض الأسعار','Quotes')} <button class="btn btn-sm" data-onclick="loadOpsQuotes()">↻</button></div><div id="opsQuotes"></div></section>
      <section class="card"><div class="section-title">${uiText('التنبيهات','Notifications')} <button class="btn btn-sm" data-onclick="loadOpsUserNotifications()">↻</button></div><div id="opsUserNotifications"></div></section>
      <section class="card"><div class="section-title">${uiText('صحة النظام','System health')} <button class="btn btn-sm" data-onclick="loadOpsHealth()">↻</button></div><div id="opsHealth"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('الأتمتة','Automation rules')} <button class="btn btn-sm" data-onclick="openAutomationRuleModal()">+</button></div><div id="opsAutomation"></div></section>
      <section class="card"><div class="section-title">${uiText('سجل تشغيل الأتمتة','Automation runs')} <button class="btn secondary btn-sm" data-onclick="scanOverdueTasks()">${uiText('فحص المهام المتأخرة','Scan overdue tasks')}</button> <button class="btn secondary btn-sm" data-onclick="scanOverdueFollowupsAuto()">${uiText('فحص المتابعات','Scan followups')}</button></div><div id="opsAutomationRuns"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('الاشتراك والفوترة','Billing & subscription')}</div><div id="opsBilling"></div></section>
      <section class="card"><div class="section-title">${uiText('فواتير الاشتراك','Billing invoices')}</div><div id="opsBillingInvoices"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('قوالب التواصل','Message templates')} <button class="btn btn-sm" data-onclick="openTemplateModal()">+</button></div><div id="opsTemplates"></div></section>
      <section class="card"><div class="section-title">${uiText('إرسال رسالة','Send message')} <button class="btn secondary btn-sm" data-onclick="loadOpsCommLog()">${uiText('عرض السجل','View log')}</button></div><div id="opsCommSend"></div><div id="opsCommLog"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('متتابعات المتابعة','Follow-up sequences')} <button class="btn btn-sm" data-onclick="openFollowupSeqModal()">+</button></div><div id="opsFollowupSeqs"></div></section>
      <section class="card"><div class="section-title">${uiText('المتابعات المتأخرة','Overdue follow-ups')} <button class="btn secondary btn-sm" data-onclick="scanFollowupsNow()">${uiText('فحص الآن','Scan now')}</button></div><div id="opsFollowupsOverdue"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('قنوات النشر','Publish connections')} <button class="btn btn-sm" data-onclick="openPublishConnModal()">+</button></div><div id="opsPublishConn"></div></section>
      <section class="card"><div class="section-title">${uiText('الوظائف الخلفية','Background jobs')} <button class="btn btn-sm" data-onclick="loadOpsJobs()">↻</button></div><div id="opsJobs"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('النسخ الاحتياطي','Backups')} <button class="btn secondary btn-sm" data-onclick="triggerBackup()">${uiText('تشغيل نسخة','Run backup')}</button></div><div id="opsBackups"></div></section>
      <section class="card"><div class="section-title">${uiText('قواعد العمولة','Commission rules')} <button class="btn btn-sm" data-onclick="openCommissionRuleModal()">+</button></div><div id="opsCommissionRules"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('الرواتب','Salaries')} <button class="btn btn-sm" data-onclick="openSalaryModal()">+</button></div><div id="opsSalaries"></div></section>
      <section class="card"><div class="section-title">${uiText('المستحقات (ذمم مدينة)','Accounts receivable')} <button class="btn btn-sm" data-onclick="loadOpsArSummary()">↻</button></div><div id="opsArSummary"></div></section>
    <div class="grid grid-3" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('الأدوار','Roles')} <button class="btn btn-sm" data-onclick="openRoleModal()">+</button></div><div id="opsRoles"></div></section>
      <section class="card"><div class="section-title">${uiText('الصلاحيات','Permissions')}</div><div id="opsPermissions"></div></section>
      <section class="card"><div class="section-title">${uiText('مسارات العمل','Workflows')} <button class="btn btn-sm" data-onclick="openWorkflowModal()">+</button></div><div id="opsWorkflows"></div></section>
    </div>
    <div class="grid grid-1" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('فريق العمل — تعيين أدوار','Team — role assignment')} <button class="btn btn-sm" data-onclick="loadOpsTeamRoles()">↻</button></div><div id="opsTeamRoles"></div></section>
    </div>
    <div class="grid grid-2" style="margin-top:18px">
      <section class="card"><div class="section-title">${uiText('مرتجع / إشعار دائن','Refund / credit note')}</div>
        <div class="item-card"><div class="field"><input id="rf_invoice" type="number" placeholder="${uiText('رقم الفاتورة','Invoice ID')}"></div><div class="field"><input id="rf_amount" type="number" step="0.01" placeholder="${uiText('المبلغ','Amount')}"></div><div class="field"><input id="rf_reason" placeholder="${uiText('السبب','Reason')}"></div><div class="modal-actions" style="justify-content:flex-start"><button class="btn secondary btn-sm" data-onclick="submitRefund()">${uiText('إنشاء مرتجع','Create refund')}</button><button class="btn secondary btn-sm" data-onclick="submitCreditNote()">${uiText('إنشاء إشعار دائن','Create credit note')}</button></div><div id="opsRefundResult" class="item-meta" style="margin-top:8px"></div></div>
      </section>
      <section class="card"><div class="section-title">${uiText('دعوة عضو جديد','Invite teammate')}</div>
        <div class="item-card"><div class="field"><input id="inv_name" placeholder="${t('name')}"></div><div class="field"><input id="inv_email" placeholder="Email"></div><div class="field"><select id="inv_role"><option value="sales_manager">sales_manager</option><option value="project_manager">project_manager</option><option value="content_manager">content_manager</option><option value="accountant">accountant</option><option value="admin">admin</option><option value="sales">sales</option></select></div><button class="btn btn-sm" data-onclick="submitInvite()">${uiText('إرسال دعوة','Send invite')}</button></div>
      </section>
    </div>`;
  await Promise.all([loadOpsReports(),loadOpsSettings(),loadOpsNotifications(),loadOpsLeave(),loadOpsPayroll(),loadOpsAcademy(),loadOpsContent(),loadOpsConversations(),loadOpsFiles(),loadOpsQuotes(),loadOpsUserNotifications(),loadOpsHealth(),
    loadOpsAutomation(),loadOpsAutomationRuns(),loadOpsBilling(),loadOpsBillingInvoices(),loadOpsTemplates(),loadOpsCommSend(),loadOpsFollowupSeqs(),loadOpsFollowupsOverdue(),loadOpsPublishConn(),loadOpsJobs(),loadOpsBackups(),loadOpsCommissionRules(),loadOpsSalaries(),loadOpsArSummary(),loadOpsRoles(),loadOpsPermissions(),loadOpsWorkflows(),loadOpsTeamRoles()]);
}
async function loadOpsReports(){
  try{const [r,p]=await Promise.all([api('/reports/overview'),api('/reports/projects')]);
    const f=r.finance,o=r.operations,pe=r.people,s=r.sales;
    document.getElementById('opsKpis').innerHTML=[ledger(uiText('المتحصل','Collected'),fmtMoney(f.cash_collected),[[uiText('المفوتر','Invoiced'),fmtMoney(f.invoiced)]]),ledger(uiText('الربح النقدي','Cash profit'),fmtMoney(f.profit),[[uiText('تكلفة العمل','Labor'),fmtMoney(f.labor_cost)]]),ledger(uiText('المشاريع النشطة','Active projects'),o.active_projects,[[uiText('متأخرة','Overdue'),o.overdue_tasks]]),ledger(uiText('Pipeline','Pipeline'),fmtMoney(s.open_pipeline),[[uiText('العملاء','Clients'),pe.clients]])].join('');
    const wrap=document.getElementById('opsSearchResults'); if(wrap) wrap.innerHTML=`<div class="section-title">${uiText('ربحية المشاريع','Project profitability')}</div><table><thead><tr><th>${uiText('المشروع','Project')}</th><th>${uiText('العميل','Client')}</th><th>${uiText('التقدم','Progress')}</th><th>${uiText('المتحصل','Collected')}</th><th>${uiText('التكلفة','Cost')}</th><th>${uiText('الربح','Profit')}</th></tr></thead><tbody>${p.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.client_name||'—')}</td><td>${x.progress_pct}%</td><td class="mono">${fmtMoney(x.collected)}</td><td class="mono">${fmtMoney(x.costs)}</td><td class="mono">${fmtMoney(x.profit)}</td></tr>`).join('')}</tbody></table>`;
  }catch(e){showToast(e.message,true)}
}
function globalSearchEnter(e){ if(e && e.key==='Enter') runGlobalSearch(); }
async function runGlobalSearch(){const q=val('globalSearchInput'); if(!q)return; try{const rows=await api('/search?q='+encodeURIComponent(q)); const el=document.getElementById('opsSearchResults'); el.innerHTML=`<div class="section-title">${uiText('نتائج البحث','Search results')}</div>${rows.length?`<div class="card-list">${rows.map(x=>`<div class="item-card"><div class="item-card-top"><div><div class="item-title">${esc(x.label)}</div><div class="item-meta">${esc(x.type)} · ${esc(x.status||'')}</div></div><button class="btn secondary btn-sm" data-onclick="loadPage('${x.url.replace('/','')}')">${uiText('فتح','Open')}</button></div></div>`).join('')}</div>`:`<div class="empty-state">${t('noData')}</div>`}`;}catch(e){showToast(e.message,true)}}
async function loadOpsSettings(){try{const s=await api('/settings');document.getElementById('opsSettings').innerHTML=`<div class="field"><label>${uiText('اسم العلامة','Brand name')}</label><input id="set_brand" value="${esc(s.brand_name||'')}"></div><div class="field"><label>${uiText('العملة','Currency')}</label><input id="set_currency" value="${esc(s.default_currency||'EGP')}"></div><div class="field"><label>${uiText('المنطقة الزمنية','Timezone')}</label><input id="set_tz" value="${esc(s.timezone||'Africa/Cairo')}"></div><button class="btn btn-sm" data-onclick="saveTenantSettings()">${t('save')}</button>`}catch(e){}}
async function saveTenantSettings(){try{await api('/settings',{method:'PATCH',body:{brand_name:val('set_brand'),default_currency:val('set_currency'),timezone:val('set_tz')}});showToast(t('saved'))}catch(e){showToast(e.message,true)}}
async function loadOpsNotifications(){try{const n=await api('/notification-preferences');document.getElementById('opsNotifications').innerHTML=`<div class="grid grid-2">${['in_app','email','task_assignments','approvals','requests','finance','hr','academy','content'].map(k=>`<label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="np_${k}" ${n[k]?'checked':''} onchange="void 0">${esc(k)}</label>`).join('')}</div><button class="btn btn-sm" style="margin-top:12px" data-onclick="saveNotificationPrefs()">${t('save')}</button>`}catch(e){}}
async function saveNotificationPrefs(){const keys=['in_app','email','task_assignments','approvals','requests','finance','hr','academy','content'];const body={};keys.forEach(k=>body[k]=document.getElementById('np_'+k)?.checked);try{await api('/notification-preferences',{method:'PATCH',body});showToast(t('saved'))}catch(e){showToast(e.message,true)}}
async function loadOpsLeave(){try{const rows=await api('/leave-requests');document.getElementById('opsLeave').innerHTML=rows.length?`<table><thead><tr><th>${uiText('الموظف','Employee')}</th><th>${uiText('الفترة','Period')}</th><th>${t('status')}</th><th></th></tr></thead><tbody>${rows.slice(0,8).map(x=>`<tr><td>${esc(x.employee_name||'')}</td><td class="mono">${esc(x.start_date)} → ${esc(x.end_date)}</td><td>${esc(x.status)}</td><td>${x.status==='pending'&&['founder','admin'].includes(CURRENT_USER.role)?`<button class="btn secondary btn-sm" data-onclick="decideLeave(${x.id},'approved')">✓</button><button class="btn danger btn-sm" data-onclick="decideLeave(${x.id},'rejected')">×</button>`:''}</td></tr>`).join('')}</tbody></table>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){}}
function openLeaveModal(){showModal(`<div class="modal-title">${uiText('طلب إجازة','Leave request')}</div><div class="field"><label>${uiText('من','From')}</label><input id="lv_start" type="date"></div><div class="field"><label>${uiText('إلى','To')}</label><input id="lv_end" type="date"></div><div class="field"><label>${uiText('النوع','Type')}</label><select id="lv_type"><option value="annual">Annual</option><option value="sick">Sick</option><option value="unpaid">Unpaid</option></select></div><div class="field"><label>${t('description')}</label><textarea id="lv_reason"></textarea></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitLeave()">${t('save')}</button></div>`)}
async function submitLeave(){try{await api('/leave-requests',{method:'POST',body:{start_date:val('lv_start'),end_date:val('lv_end'),leave_type:val('lv_type'),reason:val('lv_reason')}});closeModal();showToast(t('saved'));loadOpsLeave()}catch(e){showToast(e.message,true)}}
async function decideLeave(id,status){try{await api('/leave-requests/'+id,{method:'PATCH',body:{status}});loadOpsLeave()}catch(e){showToast(e.message,true)}}
async function loadOpsPayroll(){try{const rows=await api('/payroll/runs');document.getElementById('opsPayroll').innerHTML=rows.length?`<table><thead><tr><th>Month</th><th>Status</th><th>Employees</th><th>Net</th><th></th></tr></thead><tbody>${rows.slice(0,8).map(x=>`<tr><td>${esc(x.month)}</td><td>${esc(x.status)}</td><td>${x.employee_count}</td><td class="mono">${fmtMoney(x.total_net)}</td><td><button class="btn secondary btn-sm" data-onclick="openPayrollRunDetail(${esc(x.id)})">›</button></td></tr>`).join('')}</tbody></table>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){}}
async function openPayrollRunDetail(id){
  const run=await api('/payroll/runs/'+id);
  showModal(`<div class="modal-title">${uiText('دفعة رواتب','Payroll run')} — ${esc(run.month)}</div>
    <div class="ledger-row"><span>${t('status')}</span><b>${esc(run.status)}</b></div>
    <div class="card-list">${(run.items||[]).map(i=>`<div class="item-card"><b>${esc(i.employee_name)}</b><div class="item-meta">${fmtMoney(i.net_amount||0)}</div></div>`).join('')||`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="modal-actions">${['approved','paid','cancelled'].map(s=>`<button class="btn secondary btn-sm" data-onclick="updatePayrollRunStatus(${id},'${s}')">${s}</button>`).join('')}</div>`);
}
async function updatePayrollRunStatus(id,status){try{await api(`/payroll/runs/${id}`,{method:'PATCH',body:{status}});showToast(t('saved'));openPayrollRunDetail(id);loadOpsPayroll();}catch(e){showToast(e.message,true);}}
async function createPayrollRun(){const month=new Date().toISOString().slice(0,7);try{await api('/payroll/runs',{method:'POST',body:{month}});showToast(t('saved'));loadOpsPayroll()}catch(e){showToast(e.message,true)}}
async function loadOpsAcademy(){try{const [s,e]=await Promise.all([api('/academy/students'),api('/academy/enrollments')]);document.getElementById('opsAcademy').innerHTML=`<div class="item-meta">${uiText('طلاب','Students')}: <b>${s.length}</b> · ${uiText('التحاقات','Enrollments')}: <b>${e.length}</b></div><div class="card-list" style="margin-top:10px">${s.slice(0,6).map(x=>`<div class="item-card"><div class="item-title">${esc(x.name)}</div><div class="item-meta">${esc(x.student_code||'')}</div></div>`).join('')}</div>`}catch(e){}}
function openStudentModal(){showModal(`<div class="modal-title">${uiText('إضافة طالب','Add student')}</div><div class="field"><label>User ID</label><input id="st_uid" type="number"></div><div class="field"><label>${uiText('كود الطالب','Student code')}</label><input id="st_code"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitStudent()">${t('save')}</button></div>`)}
async function submitStudent(){try{await api('/academy/students',{method:'POST',body:{user_id:Number(val('st_uid')),student_code:val('st_code')}});closeModal();showToast(t('saved'));loadOpsAcademy()}catch(e){showToast(e.message,true)}}
async function loadOpsContent(){try{const b=await api('/content/briefs');document.getElementById('opsContent').innerHTML=b.length?`<div class="card-list">${b.slice(0,8).map(x=>`<div class="item-card"><div class="item-title">${esc(x.objective||'Content brief')}</div><div class="item-meta">${esc(x.audience||'')} · #${x.content_id}</div></div>`).join('')}</div>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){}}
async function loadOpsConversations(){try{const rows=await api('/conversations');document.getElementById('opsConversations').innerHTML=rows.length?rows.slice(0,8).map(x=>`<div class="item-card" data-onclick="openConversationDetail(${x.id})" style="cursor:pointer"><div class="item-title">${esc(x.subject||uiText('محادثة','Conversation'))}</div><div class="item-meta">${esc(x.context_type||'internal')} · #${x.id}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){}}
async function openConversationDetail(cid){
  const msgs=await api(`/conversations/${cid}/messages`);
  showModal(`<div class="modal-title">${uiText('محادثة','Conversation')} #${cid}</div>
    <div class="card-list">${msgs.length?msgs.map(m=>`<div class="item-card"><b>${esc(m.user_name||'')}</b><div class="item-meta">${esc(m.created_at||'')}</div>${esc(m.body)}</div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="field" style="margin-top:10px"><textarea id="cvm_body" rows="2" placeholder="${uiText('اكتب رسالة...','Write a message...')}"></textarea></div>
    <div class="modal-actions"><button class="btn" data-onclick="submitConversationMessage(${cid})">${uiText('إرسال','Send')}</button></div>`);
}
async function submitConversationMessage(cid){try{await api(`/conversations/${cid}/messages`,{method:'POST',body:{body:val('cvm_body')}});showToast(t('saved'));openConversationDetail(cid);}catch(e){showToast(e.message,true);}}
function openConversationModal(){showModal(`<div class="modal-title">${uiText('محادثة جديدة','New conversation')}</div><div class="field"><label>${t('title')}</label><input id="cv_title"></div><div class="field"><label>${uiText('نوع السياق','Context type')}</label><select id="cv_type"><option value="internal">Internal</option><option value="project">Project</option><option value="client">Client</option></select></div><div class="field"><label>${uiText('رقم السياق','Context ID')}</label><input id="cv_id" type="number"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitConversation()">${t('save')}</button></div>`)}
async function submitConversation(){try{await api('/conversations',{method:'POST',body:{title:val('cv_title'),context_type:val('cv_type'),context_id:Number(val('cv_id'))||null}});closeModal();loadOpsConversations()}catch(e){showToast(e.message,true)}}
async function loadOpsFiles(){try{const rows=await api('/files');document.getElementById('opsFiles').innerHTML=rows.length?rows.slice(0,10).map(x=>`<div class="item-card"><div class="item-card-top"><div><div class="item-title">${esc(x.original_name)}</div><div class="item-meta">${esc(x.mime_type||'')} · ${fmtNum(x.size_bytes)} bytes</div></div></div><div class="modal-actions" style="justify-content:flex-start;margin-top:6px"><button class="btn secondary btn-sm" data-onclick="logFileAccess(${esc(x.id)})">${uiText('تسجيل وصول','Log access')}</button><button class="btn secondary btn-sm" data-onclick="openFileVersions(${esc(x.id)})">${uiText('النسخ','Versions')}</button></div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){}}
async function logFileAccess(fileId){try{await api(`/files/${fileId}/access`,{method:'POST',body:{action:'download'}});showToast(t('saved'));}catch(e){showToast(e.message,true);}}
async function openFileVersions(fileId){
  const rows=await api(`/files/${fileId}/versions`);
  showModal(`<div class="modal-title">${uiText('نسخ الملف','File versions')}</div>
    <div class="card-list">${rows.length?rows.map(v=>`<div class="item-card"><b>v${esc(v.version)}</b><div class="item-meta">${esc(v.storage_key||'')} · ${fmtNum(v.size_bytes||0)} bytes</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}</div>
    <div class="item-card" style="margin-top:10px"><div class="field"><input id="fv_key" placeholder="${uiText('مسار التخزين','Storage key')}"></div><button class="btn secondary btn-sm" data-onclick="submitFileVersion(${fileId})">${uiText('رفع نسخة','Upload version')}</button></div>`);
}
async function submitFileVersion(fileId){try{await api(`/files/${fileId}/versions`,{method:'POST',body:{storage_key:val('fv_key')}});showToast(t('saved'));openFileVersions(fileId);}catch(e){showToast(e.message,true);}}


async function loadOpsQuotes(){try{const rows=await api('/quotes');document.getElementById('opsQuotes').innerHTML=rows.length?rows.slice(0,8).map(x=>`<div class="item-card"><div class="item-title">${esc(x.quote_number)} · ${esc(x.client_name||'')}</div><div class="item-meta">${esc(x.status)} · ${fmtMoney(x.total||0)}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsQuotes').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
async function loadOpsUserNotifications(){try{const rows=await api('/notifications');document.getElementById('opsUserNotifications').innerHTML=rows.length?rows.slice(0,8).map(x=>`<div class="item-card" data-onclick="markOpsNotification(${x.id})"><div class="item-title">${esc(x.message)}</div><div class="item-meta">${esc(x.type)} · ${esc(x.created_at||'')}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){}}
async function markOpsNotification(id){try{await api('/notifications/'+id+'/read',{method:'POST'});loadOpsUserNotifications()}catch(e){showToast(e.message,true)}}
async function loadOpsHealth(){try{const rows=await api('/health/components');document.getElementById('opsHealth').innerHTML=rows.map(x=>`<div class="item-card"><div class="item-title">${esc(x.component)} <span class="status-dot ${x.status==='ok'?'positive':'danger'}"></span></div><div class="item-meta">${esc(x.status)} · ${fmtNum(x.latency_ms||0)} ms</div></div>`).join('')}catch(e){document.getElementById('opsHealth').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}

/* ---------------- Automation ---------------- */
async function loadOpsAutomation(){try{const rows=await api('/automation/rules');document.getElementById('opsAutomation').innerHTML=rows.length?rows.map(x=>`<div class="item-card"><div class="item-card-top"><div><div class="item-title">${esc(x.name)}</div><div class="item-meta">${esc(x.trigger_event)}</div></div><span class="badge ${x.is_active?'won':'status'}">${x.is_active?uiText('مفعّل','active'):uiText('معطل','inactive')}</span></div><div class="modal-actions" style="justify-content:flex-start;margin-top:8px"><button class="btn secondary btn-sm" data-onclick="testAutomationRule(${esc(x.id)})">${uiText('اختبار','Test')}</button><button class="btn danger btn-sm" data-onclick="deleteAutomationRule(${esc(x.id)})">${t('delete')}</button></div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsAutomation').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
async function testAutomationRule(id){try{const r=await api(`/automation/rules/${id}/test`,{method:'POST',body:{}});showToast(uiText('نتيجة الاختبار: ','Test result: ')+JSON.stringify(r).slice(0,120));}catch(e){showToast(e.message,true);}}
async function deleteAutomationRule(id){try{await api(`/automation/rules/${id}`,{method:'DELETE'});showToast(t('saved'));loadOpsAutomation();}catch(e){showToast(e.message,true);}}
async function loadOpsAutomationRuns(){try{const rows=await api('/automation/runs');document.getElementById('opsAutomationRuns').innerHTML=rows.length?`<table><thead><tr><th>${uiText('الحدث','Event')}</th><th>${t('status')}</th><th>${uiText('الوقت','Time')}</th></tr></thead><tbody>${rows.slice(0,10).map(x=>`<tr><td>${esc(x.trigger_event||'')}</td><td><span class="badge status">${esc(x.status)}</span></td><td class="mono">${esc(x.created_at||'')}</td></tr>`).join('')}</tbody></table>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsAutomationRuns').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
async function openAutomationRuleModal(){
  let meta={trigger_events:[],action_types:[]};
  try{meta=await api('/automation/meta');}catch(e){}
  showModal(`<div class="modal-title">${uiText('قاعدة أتمتة جديدة','New automation rule')}</div>
    <div class="field"><label>${t('name')}</label><input id="ar_name"></div>
    <div class="field"><label>${uiText('الحدث','Trigger event')}</label><select id="ar_event">${meta.trigger_events.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('')}</select></div>
    <div class="field"><label>${uiText('نوع الإجراء','Action type')}</label><select id="ar_action">${meta.action_types.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('')}</select></div>
    <div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitAutomationRule()">${t('save')}</button></div>`);
}
async function submitAutomationRule(){try{await api('/automation/rules',{method:'POST',body:{name:val('ar_name'),trigger_event:val('ar_event'),actions:[{type:val('ar_action')}]}});closeModal();showToast(t('saved'));loadOpsAutomation();}catch(e){showToast(e.message,true);}}
async function scanOverdueTasks(){try{await api('/automation/scan/overdue-tasks',{method:'POST'});showToast(t('saved'));loadOpsAutomationRuns();}catch(e){showToast(e.message,true);}}
async function scanOverdueFollowupsAuto(){try{await api('/automation/scan/overdue-followups',{method:'POST'});showToast(t('saved'));loadOpsAutomationRuns();}catch(e){showToast(e.message,true);}}

/* ---------------- Billing ---------------- */
async function loadOpsBilling(){try{const s=await api('/billing/subscription');const plans=await api('/billing/plans');document.getElementById('opsBilling').innerHTML=`<div class="item-meta">${uiText('الخطة الحالية','Current plan')}: <b>${esc(s.plan||'—')}</b> · ${esc(s.status||'')}</div><div class="field" style="margin-top:10px"><select id="bl_plan">${plans.map(p=>`<option value="${esc(p.code)}" ${p.code===s.plan?'selected':''}>${esc(p.name||p.code)}</option>`).join('')}</select></div><div class="modal-actions" style="justify-content:flex-start"><button class="btn secondary btn-sm" data-onclick="submitSubscribe()">${uiText('ترقية/تغيير الخطة','Upgrade / change plan')}</button><button class="btn danger btn-sm" data-onclick="submitCancelSubscription()">${uiText('إلغاء الاشتراك','Cancel')}</button><button class="btn secondary btn-sm" data-onclick="runBillingTrialCheck()">${uiText('فحص التجارب','Check trials')}</button></div>`;}catch(e){document.getElementById('opsBilling').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
async function submitSubscribe(){try{await api('/billing/subscribe',{method:'POST',body:{plan_code:val('bl_plan'),idempotency_key:'ui-'+Date.now()}});showToast(t('saved'));loadOpsBilling();loadOpsBillingInvoices();}catch(e){showToast(e.message,true);}}
async function submitCancelSubscription(){try{await api('/billing/cancel',{method:'POST'});showToast(t('saved'));loadOpsBilling();}catch(e){showToast(e.message,true);}}
async function runBillingTrialCheck(){try{await api('/billing/check-trials',{method:'POST'});showToast(t('saved'));loadOpsBilling();}catch(e){showToast(e.message,true);}}
async function loadOpsBillingInvoices(){try{const rows=await api('/billing/invoices');document.getElementById('opsBillingInvoices').innerHTML=rows.length?`<table><thead><tr><th>${uiText('المبلغ','Amount')}</th><th>${t('status')}</th><th>${uiText('التاريخ','Date')}</th></tr></thead><tbody>${rows.slice(0,8).map(x=>`<tr><td class="mono">${fmtMoney(x.amount)}</td><td><span class="badge status">${esc(x.status)}</span></td><td class="mono">${esc(x.created_at||'')}</td></tr>`).join('')}</tbody></table>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsBillingInvoices').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}

/* ---------------- Communication ---------------- */
async function loadOpsTemplates(){try{const rows=await api('/communication/templates');document.getElementById('opsTemplates').innerHTML=rows.length?rows.map(x=>`<div class="item-card"><b>${esc(x.name)}</b><div class="item-meta">${esc(x.channel)}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`;window.__opsTemplates=rows;}catch(e){document.getElementById('opsTemplates').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
function openTemplateModal(){showModal(`<div class="modal-title">${uiText('قالب رسالة جديد','New message template')}</div><div class="field"><label>${t('name')}</label><input id="tp_name"></div><div class="field"><label>${uiText('القناة','Channel')}</label><select id="tp_channel"><option value="whatsapp">whatsapp</option><option value="email">email</option><option value="sms">sms</option></select></div><div class="field"><label>${uiText('النص','Body')}</label><textarea id="tp_body" rows="3"></textarea></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitTemplate()">${t('save')}</button></div>`);}
async function submitTemplate(){try{await api('/communication/templates',{method:'POST',body:{name:val('tp_name'),channel:val('tp_channel'),body:val('tp_body')}});closeModal();showToast(t('saved'));loadOpsTemplates();}catch(e){showToast(e.message,true);}}
async function loadOpsCommSend(){document.getElementById('opsCommSend').innerHTML=`<div class="field"><select id="cs_channel"><option value="whatsapp">whatsapp</option><option value="email">email</option><option value="sms">sms</option></select></div><div class="field"><input id="cs_to" placeholder="${uiText('المستلم','To')}"></div><div class="field"><textarea id="cs_body" rows="2" placeholder="${uiText('النص','Message')}"></textarea></div><button class="btn secondary btn-sm" data-onclick="submitCommSend()">${uiText('إرسال','Send')}</button>`;}
async function submitCommSend(){try{await api('/communication/send',{method:'POST',body:{channel:val('cs_channel'),to:val('cs_to'),body:val('cs_body')}});showToast(t('saved'));document.getElementById('cs_body').value='';loadOpsCommLog();}catch(e){showToast(e.message,true);}}
async function loadOpsCommLog(){try{const rows=await api('/communication/log');document.getElementById('opsCommLog').innerHTML=rows.length?`<table><thead><tr><th>${uiText('القناة','Channel')}</th><th>${uiText('المستلم','To')}</th><th>${t('status')}</th></tr></thead><tbody>${rows.slice(0,8).map(x=>`<tr><td>${esc(x.channel)}</td><td>${esc(x.to_address||'')}</td><td><span class="badge status">${esc(x.status)}</span></td></tr>`).join('')}</tbody></table>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsCommLog').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}

/* ---------------- Follow-up sequences / Publish connections ---------------- */
async function loadOpsFollowupSeqs(){try{const rows=await api('/followups/sequences');document.getElementById('opsFollowupSeqs').innerHTML=rows.length?rows.map(x=>`<div class="item-card"><b>${esc(x.name)}</b><div class="item-meta">${esc(x.applies_to||'lead')} ${x.is_default?'· '+uiText('افتراضي','default'):''}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsFollowupSeqs').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
function openFollowupSeqModal(){showModal(`<div class="modal-title">${uiText('متتابعة متابعة جديدة','New follow-up sequence')}</div><div class="field"><label>${t('name')}</label><input id="fs_name"></div><div class="field"><label>${uiText('يطبق على','Applies to')}</label><select id="fs_applies"><option value="lead">lead</option><option value="client">client</option></select></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitFollowupSeq()">${t('save')}</button></div>`);}
async function submitFollowupSeq(){try{await api('/followups/sequences',{method:'POST',body:{name:val('fs_name'),applies_to:val('fs_applies')}});closeModal();showToast(t('saved'));loadOpsFollowupSeqs();}catch(e){showToast(e.message,true);}}
async function loadOpsFollowupsOverdue(){try{const rows=await api('/followups/overdue');document.getElementById('opsFollowupsOverdue').innerHTML=rows.length?rows.map(x=>`<div class="item-card"><div class="item-card-top"><div><div class="item-title">${esc(x.lead_name||'')}</div><div class="item-meta">${esc(x.title||x.channel||'')} · ${esc(x.due_at||'')}</div></div><span class="badge status">${esc(x.status)}</span></div><div class="modal-actions" style="justify-content:flex-start;margin-top:8px"><button class="btn secondary btn-sm" data-onclick="completeFollowup(${esc(x.id)})">${uiText('إنجاز','Complete')}</button><button class="btn danger btn-sm" data-onclick="skipFollowup(${esc(x.id)})">${uiText('تخطي','Skip')}</button></div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsFollowupsOverdue').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
async function scanFollowupsNow(){try{await api('/followups/scan',{method:'POST'});showToast(t('saved'));loadOpsFollowupsOverdue();}catch(e){showToast(e.message,true);}}
async function completeFollowup(id){try{await api(`/followups/${id}/complete`,{method:'POST',body:{}});showToast(t('saved'));loadOpsFollowupsOverdue();}catch(e){showToast(e.message,true);}}
async function skipFollowup(id){try{await api(`/followups/${id}/skip`,{method:'POST'});showToast(t('saved'));loadOpsFollowupsOverdue();}catch(e){showToast(e.message,true);}}
async function loadOpsPublishConn(){try{const rows=await api('/publish/connections');document.getElementById('opsPublishConn').innerHTML=rows.length?rows.map(x=>`<div class="item-card"><b>${esc(x.platform)}</b><div class="item-meta">${esc(x.account_name||'')} · ${x.is_active?uiText('نشط','active'):uiText('غير نشط','inactive')}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsPublishConn').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
function openPublishConnModal(){showModal(`<div class="modal-title">${uiText('ربط قناة نشر','Connect publish channel')}</div><div class="field"><label>${uiText('المنصة','Platform')}</label><select id="pc_platform"><option value="instagram">instagram</option><option value="tiktok">tiktok</option><option value="facebook">facebook</option><option value="youtube">youtube</option></select></div><div class="field"><label>${uiText('اسم الحساب','Account name')}</label><input id="pc_account"></div><div class="field"><label>Access token</label><input id="pc_token" type="password"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitPublishConn()">${t('save')}</button></div>`);}
async function submitPublishConn(){try{await api('/publish/connections',{method:'POST',body:{platform:val('pc_platform'),account_name:val('pc_account'),access_token:val('pc_token')}});closeModal();showToast(t('saved'));loadOpsPublishConn();}catch(e){showToast(e.message,true);}}
async function loadOpsJobs(){try{const rows=await api('/jobs');document.getElementById('opsJobs').innerHTML=rows.length?`<table><thead><tr><th>${uiText('النوع','Type')}</th><th>${t('status')}</th><th>${uiText('المحاولات','Attempts')}</th></tr></thead><tbody>${rows.slice(0,10).map(x=>`<tr><td>${esc(x.job_type)}</td><td><span class="badge status">${esc(x.status)}</span></td><td class="mono">${esc(x.attempts)}/${esc(x.max_attempts)}</td></tr>`).join('')}</tbody></table>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsJobs').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}

/* ---------------- Backups / commission / salaries / AR ---------------- */
async function loadOpsBackups(){try{const rows=await api('/backups/runs');document.getElementById('opsBackups').innerHTML=rows.length?`<table><thead><tr><th>${uiText('النوع','Type')}</th><th>${t('status')}</th><th>${uiText('البدء','Started')}</th></tr></thead><tbody>${rows.slice(0,8).map(x=>`<tr><td>${esc(x.backup_type)}</td><td><span class="badge status">${esc(x.status)}</span></td><td class="mono">${esc(x.started_at||'')}</td></tr>`).join('')}</tbody></table>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsBackups').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
async function triggerBackup(){try{await api('/backups/runs',{method:'POST',body:{backup_type:'database'}});showToast(t('saved'));loadOpsBackups();}catch(e){showToast(e.message,true);}}
async function loadOpsCommissionRules(){try{const rows=await api('/commission-rules');document.getElementById('opsCommissionRules').innerHTML=rows.length?rows.map(x=>`<div class="item-card"><div class="item-card-top"><div><b>${esc(x.name)}</b><div class="item-meta">${esc(x.role||uiText('كل الأدوار','any role'))} · ${x.rule_type==='flat'?fmtMoney(x.flat_amount):(x.rate+'%')}</div></div><button class="btn secondary btn-sm" data-onclick="editCommissionRuleRate(${esc(x.id)})">${uiText('تعديل النسبة','Edit rate')}</button></div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsCommissionRules').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
async function editCommissionRuleRate(id){const rate=prompt(uiText('النسبة الجديدة %','New rate %'));if(rate===null)return;try{await api(`/commission-rules/${id}`,{method:'PATCH',body:{rate:parseFloat(rate)||0}});showToast(t('saved'));loadOpsCommissionRules();}catch(e){showToast(e.message,true);}}
function openCommissionRuleModal(){showModal(`<div class="modal-title">${uiText('قاعدة عمولة جديدة','New commission rule')}</div><div class="field"><label>${t('name')}</label><input id="cr_name"></div><div class="field"><label>${uiText('نوع القاعدة','Rule type')}</label><select id="cr_type"><option value="percent_of_deal">percent_of_deal</option><option value="flat">flat</option></select></div><div class="field"><label>${uiText('النسبة %','Rate %')}</label><input id="cr_rate" type="number"></div><div class="field"><label>${uiText('مبلغ ثابت','Flat amount')}</label><input id="cr_flat" type="number"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitCommissionRule()">${t('save')}</button></div>`);}
async function submitCommissionRule(){try{await api('/commission-rules',{method:'POST',body:{name:val('cr_name'),rule_type:val('cr_type'),rate:parseFloat(val('cr_rate'))||0,flat_amount:parseFloat(val('cr_flat'))||0}});closeModal();showToast(t('saved'));loadOpsCommissionRules();}catch(e){showToast(e.message,true);}}
async function loadOpsSalaries(){try{const rows=await api('/salaries');document.getElementById('opsSalaries').innerHTML=rows.length?rows.map(x=>`<div class="item-card"><div class="item-card-top"><div><div class="item-title">${uiText('الشهر','Month')} ${esc(x.month)}</div><div class="item-meta">${fmtMoney((x.base_salary||0)+(x.commission||0)+(x.bonus||0)-(x.deductions||0))}</div></div><span class="badge status">${esc(x.status)}</span></div>${x.status!=='paid'?`<div class="modal-actions" style="justify-content:flex-start;margin-top:8px"><button class="btn secondary btn-sm" data-onclick="paySalary(${esc(x.id)})">${uiText('صرف','Pay')}</button></div>`:''}</div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsSalaries').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
function openSalaryModal(){showModal(`<div class="modal-title">${uiText('راتب جديد','New salary record')}</div><div class="field"><label>${uiText('رقم الموظف (يوزر)','User ID')}</label><input id="sl_user" type="number"></div><div class="field"><label>${uiText('الشهر','Month')}</label><input id="sl_month" placeholder="2026-08"></div><div class="field"><label>${uiText('الراتب الأساسي','Base salary')}</label><input id="sl_base" type="number"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitSalary()">${t('save')}</button></div>`);}
async function submitSalary(){try{await api('/salaries',{method:'POST',body:{user_id:Number(val('sl_user')),month:val('sl_month'),base_salary:parseFloat(val('sl_base'))||0}});closeModal();showToast(t('saved'));loadOpsSalaries();}catch(e){showToast(e.message,true);}}
async function paySalary(id){try{await api(`/salaries/${id}/pay`,{method:'PATCH'});showToast(t('saved'));loadOpsSalaries();}catch(e){showToast(e.message,true);}}
async function loadOpsArSummary(){try{const rows=await api('/finance/ar-summary');document.getElementById('opsArSummary').innerHTML=rows.length?`<table><thead><tr><th>${t('invoice')}</th><th>${uiText('الإجمالي','Total')}</th><th>${uiText('المدفوع','Paid')}</th><th>${uiText('الاستحقاق','Due')}</th></tr></thead><tbody>${rows.slice(0,10).map(x=>`<tr><td>${esc(x.invoice_number||('#'+x.id))}</td><td class="mono">${fmtMoney(x.total)}</td><td class="mono">${fmtMoney(x.amount_paid||0)}</td><td class="mono">${esc(x.due_date||'—')}</td></tr>`).join('')}</tbody></table>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsArSummary').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}

/* ---------------- Roles / Permissions / Workflows ---------------- */
async function loadOpsRoles(){try{const rows=await api('/roles');document.getElementById('opsRoles').innerHTML=rows.length?rows.map(x=>`<div class="item-card"><b>${esc(x.name)}</b><div class="item-meta">${esc(x.description||'')}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsRoles').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
function openRoleModal(){showModal(`<div class="modal-title">${uiText('دور جديد','New role')}</div><div class="field"><label>${t('name')}</label><input id="rl_name"></div><div class="field"><label>${t('description')}</label><input id="rl_desc"></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitRole()">${t('save')}</button></div>`);}
async function submitRole(){try{await api('/roles',{method:'POST',body:{name:val('rl_name'),description:val('rl_desc')}});closeModal();showToast(t('saved'));loadOpsRoles();}catch(e){showToast(e.message,true);}}
async function loadOpsPermissions(){try{const rows=await api('/permissions');document.getElementById('opsPermissions').innerHTML=rows.length?`<div class="card-list">${rows.slice(0,20).map(x=>`<div class="item-card"><b class="mono" style="font-size:12px">${esc(x.code)}</b><div class="item-meta">${esc(x.description||'')}</div></div>`).join('')}</div>`:`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsPermissions').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
async function loadOpsWorkflows(){try{const rows=await api('/workflows');document.getElementById('opsWorkflows').innerHTML=rows.length?rows.map(x=>`<div class="item-card"><b>${esc(x.name)}</b><div class="item-meta">${esc(x.entity_type)} ${x.is_active?'· '+uiText('مفعّل','active'):''}</div></div>`).join(''):`<div class="empty-state">${t('noData')}</div>`}catch(e){document.getElementById('opsWorkflows').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
function openWorkflowModal(){showModal(`<div class="modal-title">${uiText('مسار عمل جديد','New workflow')}</div><div class="field"><label>${t('name')}</label><input id="wf_name"></div><div class="field"><label>${uiText('نوع الكيان','Entity type')}</label><select id="wf_entity"><option value="task">task</option><option value="deliverable">deliverable</option><option value="quote">quote</option><option value="request">request</option></select></div><div class="modal-actions"><button class="btn secondary" data-onclick="closeModal()">${t('cancel')}</button><button class="btn" data-onclick="submitWorkflow()">${t('save')}</button></div>`);}
async function submitWorkflow(){try{await api('/workflows',{method:'POST',body:{name:val('wf_name'),entity_type:val('wf_entity')}});closeModal();showToast(t('saved'));loadOpsWorkflows();}catch(e){showToast(e.message,true);}}
async function loadOpsTeamRoles(){try{const users=await api('/users');const roles=await api('/roles');
  document.getElementById('opsTeamRoles').innerHTML=users.length?`<div class="card-list">${users.map(u=>`<div class="item-card"><div class="item-card-top"><div><b>${esc(u.name)}</b><div class="item-meta">${esc(u.email)} · ${esc(u.role)} ${u.is_active?'':'· '+uiText('معطّل','deactivated')}</div></div></div><div class="modal-actions" style="justify-content:flex-start;margin-top:6px"><select id="tr_role_${u.id}">${roles.map(r=>`<option value="${r.id}">${esc(r.name)}</option>`).join('')}</select><button class="btn secondary btn-sm" data-onclick="assignUserRole(${u.id})">${uiText('تعيين','Assign')}</button><button class="btn secondary btn-sm" data-onclick="viewUserRoles(${u.id})">${uiText('عرض الأدوار','View roles')}</button>${u.is_active?`<button class="btn danger btn-sm" data-onclick="deactivateUser(${u.id})">${uiText('تعطيل','Deactivate')}</button>`:''}</div></div>`).join('')}</div>`:`<div class="empty-state">${t('noData')}</div>`;
}catch(e){document.getElementById('opsTeamRoles').innerHTML=`<div class="item-meta">${esc(e.message||'')}</div>`}}
async function assignUserRole(userId){try{const sel=document.getElementById('tr_role_'+userId);await api(`/users/${userId}/roles`,{method:'POST',body:{role_id:Number(sel.value)}});showToast(t('saved'));}catch(e){showToast(e.message,true);}}
async function viewUserRoles(userId){try{const rows=await api(`/users/${userId}/roles`);showToast(rows.length?rows.map(r=>r.name).join(', '):uiText('لا توجد أدوار','No roles'));}catch(e){showToast(e.message,true);}}
async function deactivateUser(userId){try{await api(`/users/${userId}`,{method:'DELETE'});showToast(t('saved'));loadOpsTeamRoles();}catch(e){showToast(e.message,true);}}

/* ---------------- Refunds / credit notes / invite ---------------- */
async function submitRefund(){try{const r=await api('/refunds',{method:'POST',body:{invoice_id:Number(val('rf_invoice'))||null,amount:parseFloat(val('rf_amount'))||0,reason:val('rf_reason')}});document.getElementById('opsRefundResult').textContent=uiText('تم إنشاء المرتجع #','Refund created #')+r.id;showToast(t('saved'));}catch(e){showToast(e.message,true);}}
async function submitCreditNote(){try{const r=await api('/credit-notes',{method:'POST',body:{invoice_id:Number(val('rf_invoice'))||null,amount:parseFloat(val('rf_amount'))||0,reason:val('rf_reason')}});document.getElementById('opsRefundResult').textContent=uiText('تم إنشاء إشعار الدائن ','Credit note created ')+r.note_number;showToast(t('saved'));}catch(e){showToast(e.message,true);}}
async function submitInvite(){try{const r=await api('/auth/invite',{method:'POST',body:{name:val('inv_name'),email:val('inv_email'),role:val('inv_role')}});document.getElementById('inv_name').value='';document.getElementById('inv_email').value='';showModal(`<div class="modal-title">${t('saved')}</div><div class="item-meta">${uiText('كلمة المرور المؤقتة — انسخها وابعتها للعضو الجديد، مش هتظهر تاني','Temporary password — copy and send it to the new member, it will not be shown again')}</div><div class="item-card mono" style="margin-top:10px;font-size:16px;text-align:center;user-select:all">${esc(r.temporary_password)}</div><div class="modal-actions"><button class="btn" data-onclick="closeModal()">${uiText('تم','Done')}</button></div>`);}catch(e){showToast(e.message,true);}}

/* ---------------- CSP-safe action bridge ----------------
   Legacy data-on* attributes are inert under CSP. The bridge uses a static
   action map of direct function references; it never evaluates DOM strings. */
(function installSafeActionBridge(){
  const ACTIONS = {
    switchAuthTab,doLogin,submitTwoFaLogin,doRegister,logout,loadAiBriefing,openLeadModal,aiRescoreLead,openLeadDetail,closeModal,submitLead,draftAiMessage,startLeadFollowups,convertLead,addActivity,openClientDomain,openClientModal,submitClient,openDealModal,submitDeal,closeDeal,setProjectView,openProjectModal,openProjectDetail,submitProject,submitNewTask,setMediaView,openAiIdeasModal,openContentModal,openPublishModal,doPublish,submitContent,openContentDetail,submitContentVersion,submitContentApproval,submitContentAnalytics,generateAiIdeas,openTransactionModal,submitTransaction,openInvoiceDetail,submitInvoicePayment,updateInvoiceStatus,submitPaymentAllocation,loadInvoiceActivity,openQuoteDetail,updateQuoteStatus,openRequestModal,submitRequest,openRequestAssignment,submitRequestAssignment,resolveDomainRequest,openTaskWorkflowModal,submitTaskWorkflow,openTaskDetail,quickTaskStatus,submitTaskComment,openDeliverableVersionModal,submitDeliverableVersion,setAttendanceView,openOfficeSettingsModal,doCheckIn,doCheckOut,clearFlag,useMyLocation,saveOfficeSettings,openCourseModal,openCourseDetail,submitCourse,enrollInCourse,submitLesson,completeLesson,openAssessmentModal,submitAssessment,openAssessmentAttemptModal,submitAssessmentAttempt,openInstructorModal,submitInstructor,openSopModal,renderSop,submitSop,deleteSop,openAssetModal,openMaintenanceModal,submitAsset,submitMaintenance,openCreatorModal,submitCreator,renderCreators,submitPortalContent,openDisable2faModal,start2faSetup,logoutAllSessions,revokeSession,confirm2fa,disable2fa,renderOps,runGlobalSearch,loadOpsReports,loadOpsSettings,saveTenantSettings,loadOpsNotifications,saveNotificationPrefs,loadOpsLeave,openLeaveModal,submitLeave,decideLeave,loadOpsPayroll,createPayrollRun,loadOpsAcademy,openStudentModal,submitStudent,loadOpsContent,loadOpsConversations,openConversationModal,submitConversation,openConversationDetail,submitConversationMessage,loadOpsFiles,logFileAccess,openFileVersions,submitFileVersion,loadOpsQuotes,loadOpsUserNotifications,markOpsNotification,loadOpsHealth,
    openAutomationRuleModal,submitAutomationRule,scanOverdueTasks,scanOverdueFollowupsAuto,testAutomationRule,deleteAutomationRule,
    submitSubscribe,submitCancelSubscription,runBillingTrialCheck,
    openTemplateModal,submitTemplate,submitCommSend,loadOpsCommLog,
    openFollowupSeqModal,submitFollowupSeq,scanFollowupsNow,completeFollowup,skipFollowup,
    openPublishConnModal,submitPublishConn,loadOpsJobs,
    triggerBackup,openCommissionRuleModal,submitCommissionRule,editCommissionRuleRate,openSalaryModal,submitSalary,paySalary,loadOpsArSummary,openPayrollRunDetail,updatePayrollRunStatus,
    openRoleModal,submitRole,openWorkflowModal,submitWorkflow,loadOpsTeamRoles,assignUserRole,viewUserRoles,deactivateUser,
    submitRefund,submitCreditNote,submitInvite,
    openEmployeeDetail,submitEmployeeContract,submitEmployeeDocument,openNewEmployeeModal,submitNewEmployee,
    renderClientDashboard,renderClientDeliverables,renderClientInvoices,renderClientMessages,submitClientDeliverableApproval,submitClientMessage,setClientPortalTab,
    sopSearchEnter,globalSearchEnter,
    decideLatestApproval,loadPage,onCalDragStart,onCalDrop,onKanbanDragStart,onKanbanDrop,openApprovalDecision,openBudgetModal,openClientDomain,openClientProject,
    openDeliverableModal,openExpenseModal,openMilestoneModal,openProjectInvoiceModal,openProjectMemberModal,renderLeads,submitBudget,submitClientPortalRequest,
    submitDeliverable,submitExpense,submitMilestone,submitProjectInvoice,submitProjectMember
  };
  const attrs=['click','change','keyup','dragover','drop','dragstart'];
  function parseLiteral(x,e,el){
    x=x.trim(); if(x==='event')return e; if(x==='this')return el; if(x==='this.value')return el.value;
    if(x==='this.checked')return el.checked; if(x==='event.key')return e.key; if(x==='event.target')return e.target;
    if(x==='null')return null; if(x==='true')return true; if(x==='false')return false;
    if(/^[-+]?\d+(?:\.\d+)?$/.test(x))return Number(x);
    if((x.startsWith("'")&&x.endsWith("'"))||(x.startsWith('"')&&x.endsWith('"')))return x.slice(1,-1);
    return undefined;
  }
  function invoke(code,e,el){
    code=code.trim(); if(!code)return;
    if(code==='event.preventDefault()'){e.preventDefault();return;}
    if(code==='event.stopPropagation()'){e.stopPropagation();return;}
    const m=code.match(/^([A-Za-z_$][\w$]*)\s*\((.*)\)$/s); if(!m)return;
    const fn=ACTIONS[m[1]]; if(typeof fn!=='function')return;
    const args=[]; let cur='',q=null,d=0;
    for(let i=0;i<m[2].length;i++){const ch=m[2][i]; if(q){cur+=ch;if(ch===q&&m[2][i-1]!=="\\")q=null;continue;} if(ch==='"'||ch==="'"){q=ch;cur+=ch;continue;} if('([{'.includes(ch))d++; if(')]}'.includes(ch))d--; if(ch===','&&d===0){args.push(cur);cur='';}else cur+=ch;}
    if(cur.trim())args.push(cur); const vals=args.map(x=>parseLiteral(x,e,el)); if(vals.some(v=>v===undefined))return; fn.apply(el,vals);
  }
  attrs.forEach(type=>document.addEventListener(type,e=>{let el=e.target;while(el&&el!==document){const code=el.getAttribute?.('data-on'+type);if(code){code.split(';').forEach(c=>invoke(c,e,el));if(type==='click')break;}el=el.parentElement;}},type==='dragover'?{capture:true}:false));
})();


