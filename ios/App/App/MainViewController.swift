import UIKit
import WebKit
import Capacitor
import SafariServices
import AppTrackingTransparency
import os.log

private let navLog = OSLog(subsystem: "com.tammstorekw.app", category: "Navigation")

/// Custom bridge controller that keeps the whole shopping + sign-in journey inside the app.
///
/// Mirrors android/app/src/main/java/com/tammstore/app/MainActivity.java — keep the
/// `allowedHosts` list in sync between the two platforms.
///
/// - Links to an allowed host (your store + Shopify/Shop Pay domains) load right inside
///   the app's single WebView — this is what makes Shop Pay sign-in (the "Profile" tab)
///   stay inside the app instead of kicking the user out to Safari.
/// - tel:, mailto:, whatsapp: etc. hand off to the matching native app (not a browser).
/// - Anything genuinely external opens as an in-app Safari sheet (SFSafariViewController)
///   that sits on top of the app, so the user never actually leaves the app.
class MainViewController: CAPBridgeViewController, WKNavigationDelegate, WKUIDelegate {

    private let allowedHosts: [String] = [
        "tammstore.com",
        "myshopify.com",
        "shopify.com",
        "shopifycs.com",
        "shopifysvc.com",
        "shopifysvc.net",
        "shop.app",
        // The "Manage account" / delete-account page (Shopify's new Customer Account
        // UI extension) is served from extensions.shopifycdn.com. It wasn't in this
        // list, so tapping it fell through to presentInAppBrowser() and opened a
        // brand-new, signed-out SFSafariViewController — blank page, no delete-account
        // option, because that sheet doesn't share the app WebView's login session.
        // Allowing it keeps it inside the same authenticated WebView instead.
        "shopifycdn.com",
        // Shop Pay's sign-in "Verify" step (the hCaptcha challenge shown right after
        // tapping Continue on the Shop sign-in screen) opens via window.open() to
        // hcaptcha.com. Not being in this list meant it fell into presentInAppBrowser()
        // too — a blank pop-up Safari sheet on top of the sign-in screen that looked
        // like an ad. Allowing it lets it load back into the same WebView instead,
        // exactly like the rest of the Shop Pay sign-in flow already does.
        "hcaptcha.com",
        // Bot-protection challenge frames used during sign-in / checkout.
        "cloudflare.com"
    ]

    private func isAllowed(_ host: String?) -> Bool {
        guard let host = host?.lowercased(), !host.isEmpty else { return false }
        return allowedHosts.contains { host == $0 || host.hasSuffix("." + $0) }
    }

    // The "مراجعة منتجاتنا" (product reviews) Vimeo video widget: a tap on it used to
    // navigate to a vimeo.com URL as a *new window/tab*, which — since vimeo isn't an
    // allowedHost — fell into presentInAppBrowser() below and popped a full-screen in-app
    // Safari sheet on top of the app. That's the "ad-like play thing" popup that needed to
    // go away. The widget itself, though, is just a normal <iframe src="https://vimeo.com/...">
    // sitting inline in the page (same as it is in Safari) — so isBlockedHost is only ever
    // consulted for *new-window* requests (createWebViewWith) and *main-frame* navigations
    // below. Ordinary iframe loads are left alone entirely and never even reach this check,
    // so the video loads and plays inline exactly like it does in Safari.
    private func isBlockedHost(_ host: String?) -> Bool {
        guard let host = host?.lowercased(), !host.isEmpty else { return false }
        return host.contains("vimeo.com") || host.contains("vimeocdn.com")
    }

    // MARK: - Hook into Capacitor's bridge once it's ready, so our navigation/UI
    // delegate methods below actually get called by the WebView.

    // iOS-only: visually hides the Shopify "Continue with shop" sign-in button
    // (plus the "or" divider and "create account" subtitle) inside the WebView (App Store Guideline 4.8 — the app's own email+code
    // option on the Shopify account screen is the login method now).
    //
    // Why the first version didn't work (button stayed visible):
    //  1. It matched only on the element's text ("continue with shop"). On Shopify's
    //     login page the "shop" part is usually a logo (SVG/img), not text, so the text
    //     is just "Continue with" and the match silently failed.
    //  2. It ran once at DOMContentLoaded + a MutationObserver attached at document
    //     start, when <html> may not exist yet (the observer then throws and the
    //     try/catch swallows it). The login form is rendered later by JS, so a single
    //     early pass never sees the button.
    //
    // This version: matches on text OR aria-label / alt / svg <title> / href, looks inside
    // open shadow roots, waits for <html>, re-scans on DOM changes + on a short timer,
    // and hides through a CSS rule on a marker attribute so a re-render can't undo it.
    // NOTE: this is a Swift *raw* string (#"""..."""#) so JS backslashes like \s stay literal.
    private static let hideShopButtonJS: String = #"""
    (function () {
      if (window.__tammHideShop) return;
      window.__tammHideShop = true;

      var MARK = 'data-tamm-hidden';
      var TEXT_RE = /continue\s*with\s*shop|(?:متابعة|المتابعة|تابع|استمر|الاستمرار)\s*(?:مع|ب|باستخدام|بواسطة)?\s*shop/i;
      var CONTINUE_RE = /continue\s*with|متابعة|المتابعة/i;
      var SHOP_RE = /(^|[^a-z])shop([^a-z]|$)/i;
      var BADGE_RE = /آخر\s*استخدام|last\s*used/gi;

      // Shopify's login widget may use a *closed* shadow root, which querySelectorAll can't
      // see into. Force new shadow roots to be open so the scan below can reach them.
      try {
        var _attach = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function (init) {
          return _attach.call(this, Object.assign({}, init, { mode: 'open' }));
        };
      } catch (e) {}

      function addStyle() {
        try {
          if (document.getElementById('tamm-hide-shop-style')) return;
          var st = document.createElement('style');
          st.id = 'tamm-hide-shop-style';
          st.textContent = '[' + MARK + ']{display:none !important;visibility:hidden !important;}';
          (document.head || document.documentElement).appendChild(st);
        } catch (e) {}
      }

      function collectLabel(el) {
        var parts = [el.innerText, el.textContent,
                     el.getAttribute('aria-label'), el.getAttribute('title'),
                     el.getAttribute('value')];
        try {
          var inner = el.querySelectorAll('img[alt], svg[aria-label], [aria-label], svg title');
          for (var i = 0; i < inner.length; i++) {
            parts.push(inner[i].getAttribute('alt'), inner[i].getAttribute('aria-label'), inner[i].textContent);
          }
        } catch (e) {}
        return parts.join(' ').replace(/\s+/g, ' ').trim();
      }

      function isShopButton(el) {
        var label = collectLabel(el);
        if (!label) return false;
        if (TEXT_RE.test(label)) return true;
        // The button carries a small "last used" badge (آخر استخدام) and the word "shop" is
        // a logo with no text, so after removing the badge the label is just "Continue with".
        var bare = label.replace(BADGE_RE, '').replace(/\s+/g, ' ').trim();
        if (bare.length < 40 && /^(continue with|متابعة مع|المتابعة مع|تابع مع|المتابعة باستخدام|متابعة باستخدام)$/i.test(bare)) return true;
        // "Continue with" + a "shop" logo (svg/img/aria-label) — short labels only,
        // so a big container that merely contains both words is never matched.
        return label.length < 60 && CONTINUE_RE.test(label) && SHOP_RE.test(label);
      }

      function hide(el) {
        el.setAttribute(MARK, '1');
        el.setAttribute('aria-hidden', 'true');
        el.setAttribute('tabindex', '-1');
        el.style.setProperty('display', 'none', 'important');
      }

      // Login-page cleanup (only on a page that has an email field, so the rest of the
      // store is never touched): hide the "Sign in or create account" subtitle and the
      // "or" divider that separated the removed Shop button from the email field.
      var SUBTITLE_RE = /^(تسجيل الدخول\s*أو\s*(إنشاء|انشاء)\s*حساب|sign in or create (an )?account|log in or create (an )?account)$/i;
      var OR_RE = /^(أو|او|or)$/i;
      var EMAIL_SEL = 'input[type="email"], input[autocomplete*="email" i], input[name*="email" i], ' +
                      'input[placeholder*="email" i], input[placeholder*="بريد"], input[aria-label*="بريد"], input[aria-label*="email" i]';

      function hideLoginExtras(root) {
        try {
          if (!root.querySelector(EMAIL_SEL)) return;
          var nodes = root.querySelectorAll('*');
          for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            if (el.children.length !== 0 || el.hasAttribute(MARK)) continue;
            var t = (el.textContent || '').replace(/\s+/g, ' ').trim();
            if (!t || t.length > 40) continue;
            if (SUBTITLE_RE.test(t)) {
              hide(el);
            } else if (OR_RE.test(t)) {
              var par = el.parentElement;
              var pt = par ? (par.textContent || '').replace(/\s+/g, ' ').trim() : '';
              hide(par && OR_RE.test(pt) ? par : el);
            }
          }
        } catch (e) {}
      }

      var SELECTOR = 'button, a, [role="button"], [tabindex], input[type="submit"], input[type="button"]';

      function scan(root) {
        hideLoginExtras(root);
        try {
          var nodes = root.querySelectorAll('*');
          for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            if (el.shadowRoot) scan(el.shadowRoot);
            if (el.hasAttribute && el.hasAttribute(MARK)) continue;
            if (el.matches && el.matches(SELECTOR) && isShopButton(el)) hide(el);
          }
        } catch (e) {}
      }

      var pending = false;
      function schedule() {
        if (pending) return;
        pending = true;
        setTimeout(function () { pending = false; addStyle(); scan(document); }, 50);
      }

      function observe() {
        try {
          if (!document.documentElement) { setTimeout(observe, 20); return; }
          new MutationObserver(schedule).observe(document.documentElement,
            { childList: true, subtree: true });
        } catch (e) {}
      }

      observe();
      schedule();
      document.addEventListener('DOMContentLoaded', schedule);
      window.addEventListener('load', schedule);
      window.addEventListener('pageshow', schedule);
      // Safety net: the login form is rendered by JS a moment after load.
      var ticks = 0;
      var timer = setInterval(function () { schedule(); if (++ticks > 60) clearInterval(timer); }, 500);
    })();
    """#

    private static let hideShopButtonScript: WKUserScript =
        WKUserScript(source: hideShopButtonJS, injectionTime: .atDocumentStart, forMainFrameOnly: false)


    // MARK: - Guideline 5.1.2(i) — App Tracking Transparency
    //
    // Apple's finding: the WebView loads a site that sets tracking cookies/pixels, but the
    // app never asked for ATT permission. What we do now:
    //   1. Until the user explicitly taps "Allow" on the system ATT prompt, every known
    //      third-party tracking / advertising domain is blocked inside the WebView
    //      (WKContentRuleList) and Shopify's Customer Privacy API is told "no consent".
    //   2. The ATT prompt itself is shown once, right after the first screen appears
    //      (MainViewController.viewDidAppear -> requestTrackingPermissionIfNeeded()).
    //   3. If the user taps "Allow", the blocklist is removed and the page reloads. If they
    //      deny (or tracking is restricted), the blocklist stays in place permanently.
    // Review Notes text for App Store Connect lives in REVIEW_NOTES.md.

    private static let trackerRulesID = "tamm.tracker.blocklist.v1"

    /// Third-party tracking / ad-tech hosts blocked unless the user allowed tracking.
    private static let trackerHostPatterns: [String] = [
        #"connect\.facebook\.net"#,
        #"facebook\.com/tr"#,
        #"analytics\.tiktok\.com"#,
        #"analytics-sg\.tiktok\.com"#,
        #"business-api\.tiktok\.com"#,
        #"google-analytics\.com"#,
        #"analytics\.google\.com"#,
        #"googleadservices\.com"#,
        #"googlesyndication\.com"#,
        #"doubleclick\.net"#,
        #"googletagmanager\.com/(gtm|gtag)"#,
        #"snap\.licdn\.com"#,
        #"px\.ads\.linkedin\.com"#,
        #"ct\.pinterest\.com"#,
        #"s\.pinimg\.com/ct"#,
        #"sc-static\.net"#,
        #"tr\.snapchat\.com"#,
        #"bat\.bing\.com"#,
        #"clarity\.ms"#,
        #"static\.hotjar\.com"#,
        #"script\.hotjar\.com"#,
        #"analytics\.twitter\.com"#,
        #"static\.ads-twitter\.com"#,
        #"criteo\.(com|net)"#,
        #"taboola\.com"#,
        #"outbrain\.com"#,
        #"adsrvr\.org"#,
        #"appsflyer\.com"#,
        #"adjust\.com"#
    ]

    private var trackingAuthorized: Bool {
        ATTrackingManager.trackingAuthorizationStatus == .authorized
    }

    private var trackerRulesList: WKContentRuleList?
    private var privacyScriptInstalled = false
    private var attRequestScheduled = false

    private static var trackerRulesJSON: String {
        let rules: [[String: Any]] = trackerHostPatterns.map { host in
            [
                "trigger": ["url-filter": "^https?://([^/]+\\.)?" + host],
                "action": ["type": "block"]
            ]
        }
        guard let data = try? JSONSerialization.data(withJSONObject: rules),
              let json = String(data: data, encoding: .utf8) else { return "[]" }
        return json
    }

    /// Runs inside the page when tracking is NOT authorized: tells Shopify's Customer Privacy
    /// API that analytics/marketing/sale-of-data consent is denied. Everything happens inside
    /// timers and checks window.__tammTrackingAllowed, which is set by a second script that
    /// is added after the user taps "Allow" (user scripts can't be removed individually).
    private static let denyTrackingJS: String = #"""
    (function () {
      if (window.__tammDenyTracking) return;
      window.__tammDenyTracking = true;
      var tries = 0;
      function apply() {
        if (window.__tammTrackingAllowed === true) return true;
        try {
          var cp = window.Shopify && window.Shopify.customerPrivacy;
          if (cp && typeof cp.setTrackingConsent === 'function') {
            cp.setTrackingConsent({ analytics: false, marketing: false, preferences: false, sale_of_data: false }, function () {});
            return true;
          }
          if (window.Shopify && typeof window.Shopify.loadFeatures === 'function' && !window.__tammLoadingPrivacy) {
            window.__tammLoadingPrivacy = true;
            window.Shopify.loadFeatures([{ name: 'consent-tracking-api', version: '0.1' }], function () { window.__tammLoadingPrivacy = false; });
          }
        } catch (e) {}
        return false;
      }
      var t = setInterval(function () { if (apply() || ++tries > 40) clearInterval(t); }, 500);
    })();
    """#

    private static let allowTrackingJS = "window.__tammTrackingAllowed = true;"

    /// Applies the correct tracking policy for the current ATT status. Safe to call repeatedly.
    private func applyTrackingPolicy(reloadIfChanged: Bool) {
        guard let webView = bridge?.webView else { return }
        let ucc = webView.configuration.userContentController

        if trackingAuthorized {
            if let list = trackerRulesList {
                ucc.remove(list)
                trackerRulesList = nil
            }
            if privacyScriptInstalled {
                // Order matters only loosely: the deny script re-checks the flag inside timers.
                ucc.addUserScript(WKUserScript(source: Self.allowTrackingJS, injectionTime: .atDocumentStart, forMainFrameOnly: false))
                privacyScriptInstalled = false
            }
            if reloadIfChanged { webView.reload() }
            return
        }

        // Not authorized (not determined yet, denied or restricted): block trackers.
        if !privacyScriptInstalled {
            ucc.addUserScript(WKUserScript(source: Self.denyTrackingJS, injectionTime: .atDocumentStart, forMainFrameOnly: false))
            privacyScriptInstalled = true
        }
        if trackerRulesList == nil {
            WKContentRuleListStore.default().compileContentRuleList(forIdentifier: Self.trackerRulesID, encodedContentRuleList: Self.trackerRulesJSON) { [weak self] list, error in
                DispatchQueue.main.async {
                    guard let self = self, let list = list, self.trackerRulesList == nil, !self.trackingAuthorized else {
                        if let error = error { os_log("tracker rules failed: %{public}@", log: navLog, type: .error, String(describing: error)) }
                        return
                    }
                    self.trackerRulesList = list
                    self.bridge?.webView?.configuration.userContentController.add(list)
                    // Pages that began loading before the rules compiled may already have fired
                    // a pixel — reload once so the first paint is tracker-free.
                    if reloadIfChanged { self.bridge?.webView?.reload() }
                }
            }
        }
    }

    /// Shows the system ATT prompt exactly once (status .notDetermined), only while the app is
    /// active — iOS silently ignores the request otherwise.
    private func requestTrackingPermissionIfNeeded() {
        guard ATTrackingManager.trackingAuthorizationStatus == .notDetermined, !attRequestScheduled else { return }
        attRequestScheduled = true

        let present = { [weak self] in
            // Small delay so the prompt appears over a fully drawn first screen.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                ATTrackingManager.requestTrackingAuthorization { _ in
                    DispatchQueue.main.async { self?.applyTrackingPolicy(reloadIfChanged: true) }
                }
            }
        }

        if UIApplication.shared.applicationState == .active {
            present()
        } else {
            var token: NSObjectProtocol?
            token = NotificationCenter.default.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { _ in
                if let token = token { NotificationCenter.default.removeObserver(token) }
                present()
            }
        }
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        requestTrackingPermissionIfNeeded()
    }

    // MARK: - Guideline 2.3.10 — keep the iOS app focused on Apple's platform
    //
    // Apple's finding: the app (a) shows content/products for non-Apple platforms and
    // (b) the metadata mentions third-party platforms. The metadata part must be fixed in
    // App Store Connect (see REVIEW_NOTES.md). For what the WebView itself displays, this
    // script — iOS only — removes store badges / links / mentions of other mobile platforms
    // and hides product cards whose name matches a non-Apple device brand.
    // EDIT the two lists below to match your catalog.
    /// MASTER SWITCH for product hiding.
    ///  true  = hide product cards of non-Apple device brands (safest for Guideline 2.3.10, fewer sales in the iOS app)
    ///  false = show ALL products (full catalog). Other-platform badges/mentions (Android / Google Play) are still hidden.
    private static let hideNonAppleProducts = false

    private static let platformTerms: [String] = [
        "google play", "play store", "play.google.com", "appgallery", "app gallery",
        "android", "اندرويد", "أندرويد", "جوجل بلاي", "متجر بلاي", "هواوي جاليري"
    ]

    private static let nonAppleProductTerms: [String] = [
        "samsung", "galaxy", "xiaomi", "redmi", "poco phone", "huawei", "honor", "oppo", "realme",
        "oneplus", "google pixel", "nokia", "infinix", "tecno", "motorola", "sony xperia",
        "سامسونج", "سامسونغ", "جالكسي", "شاومي", "هواوي", "اوبو", "أوبو", "ريلمي", "ون بلس", "ونبلس", "جوجل بيكسل"
    ]

    private static var applePlatformFocusJS: String {
        func jsArray(_ a: [String]) -> String {
            let data = (try? JSONSerialization.data(withJSONObject: a)) ?? Data("[]".utf8)
            return String(data: data, encoding: .utf8) ?? "[]"
        }
        return #"""
        (function () {
          if (window.__tammApplePlatformFocus) return;
          window.__tammApplePlatformFocus = true;
          var MARK = 'data-tamm-platform-hidden';
          var PLATFORM = \#(jsArray(platformTerms));
          var PRODUCTS = \#(jsArray(hideNonAppleProducts ? nonAppleProductTerms : []));
          function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
          var PLATFORM_RE = new RegExp(PLATFORM.map(esc).join('|'), 'i');
          var PRODUCT_RE = PRODUCTS.length ? new RegExp(PRODUCTS.map(esc).join('|'), 'i') : null;
          var CARD_SEL = 'li, article, .grid__item, [class*="product-card"], [class*="card-wrapper"], [class*="product-item"], [class*="productitem"]';

          function hide(el) {
            if (!el || el.hasAttribute(MARK)) return;
            el.setAttribute(MARK, '1');
            el.style.setProperty('display', 'none', 'important');
          }

          function cardFor(a) {
            var el = a.closest(CARD_SEL);
            if (!el) return null;
            // Safety: never hide a big container that holds many different products.
            var hrefs = {};
            var links = el.querySelectorAll('a[href*="/products/"]');
            for (var i = 0; i < links.length; i++) hrefs[links[i].getAttribute('href').split('?')[0]] = 1;
            return Object.keys(hrefs).length <= 2 ? el : null;
          }

          function scan() {
            try {
              // 1) other platforms' store badges / links / short mentions
              var badges = document.querySelectorAll('a[href*="play.google.com"], a[href*="appgallery"], a[href*="apps.microsoft.com"], img[alt], svg[aria-label], a[aria-label]');
              for (var i = 0; i < badges.length; i++) {
                var b = badges[i];
                var label = (b.getAttribute('alt') || b.getAttribute('aria-label') || b.getAttribute('href') || '');
                if (PLATFORM_RE.test(label) && label.length < 80) hide(b.closest('a') || b);
              }
              var leaves = document.querySelectorAll('a, button, li, span, p');
              for (var j = 0; j < leaves.length; j++) {
                var el = leaves[j];
                if (el.hasAttribute(MARK) || el.children.length > 3) continue;
                var t = (el.textContent || '').replace(/\s+/g, ' ').trim();
                if (t && t.length < 50 && PLATFORM_RE.test(t) && !el.closest('a[href*="/products/"]')) hide(el);
              }
              // 2) product cards for non-Apple device brands
              var prodLinks = PRODUCT_RE ? document.querySelectorAll('a[href*="/products/"]') : [];
              for (var k = 0; k < prodLinks.length; k++) {
                var a = prodLinks[k];
                var name = (a.textContent || '') + ' ' + (a.getAttribute('aria-label') || '') + ' ' + (a.getAttribute('href') || '');
                var img = a.querySelector('img[alt]');
                if (img) name += ' ' + img.getAttribute('alt');
                if (PRODUCT_RE && PRODUCT_RE.test(name)) { var card = cardFor(a); if (card) hide(card); }
              }
              // 3) product page of a non-Apple device opened directly -> back to the store home
              if (/\/products\//.test(location.pathname)) {
                var h1 = document.querySelector('h1');
                if (PRODUCT_RE && h1 && PRODUCT_RE.test(h1.textContent || '')) location.replace('/');
              }
            } catch (e) {}
          }

          var pending = false;
          function schedule() { if (pending) return; pending = true; setTimeout(function () { pending = false; scan(); }, 80); }
          function observe() {
            try {
              if (!document.documentElement) { setTimeout(observe, 20); return; }
              new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
            } catch (e) {}
          }
          observe(); schedule();
          document.addEventListener('DOMContentLoaded', schedule);
          window.addEventListener('load', schedule);
          var ticks = 0, timer = setInterval(function () { schedule(); if (++ticks > 40) clearInterval(timer); }, 750);
        })();
        """#
    }

    private static var applePlatformFocusScript: WKUserScript {
        WKUserScript(source: applePlatformFocusJS, injectionTime: .atDocumentStart, forMainFrameOnly: false)
    }

    override func capacitorDidLoad() {
        super.capacitorDidLoad()
        bridge?.webView?.navigationDelegate = self
        bridge?.webView?.uiDelegate = self
        bridge?.webView?.configuration.userContentController.addUserScript(Self.hideShopButtonScript)
        // 2.3.10: keep the in-app content focused on Apple's platform.
        bridge?.webView?.configuration.userContentController.addUserScript(Self.applePlatformFocusScript)
        // 5.1.2(i): block trackers until the user allows tracking via the ATT prompt.
        applyTrackingPolicy(reloadIfChanged: true)

        // Fix #1: Kill the brief black flash between the Launch Screen and the
        // site's content finishing its load. WKWebView (and its internal
        // scrollView) default to a black/system background, which is invisible
        // while the Launch Screen image is on top, but flashes black for a
        // frame or two right after the Launch Screen is dismissed and before
        // the live page has painted anything. Forcing white here (matching the
        // Launch Screen's own white background and the site's own background
        // color) makes that transition invisible instead of a black flash.
        view.backgroundColor = .white
        bridge?.webView?.backgroundColor = .white
        bridge?.webView?.isOpaque = true
        bridge?.webView?.scrollView.backgroundColor = .white

        // Fix #2: Stop the site's top bar (language/currency selector) from
        // rendering underneath the notch / Dynamic Island. Main.storyboard uses
        // `<adaptation id="fullscreen"/>`, which lets the WebView draw edge-to-edge,
        // and the live site does not reserve safe-area space for that top cutout
        // on its own. Insetting the WebView's scrollView by the top safe area
        // pushes all page content down below the notch/Dynamic Island, mirroring
        // the padding-so-content-never-hides-behind-system-bars fix already
        // applied on the Android side.
        if let webView = bridge?.webView {
            let topInset = view.safeAreaInsets.top
            webView.scrollView.contentInset = UIEdgeInsets(top: topInset, left: 0, bottom: 0, right: 0)
            webView.scrollView.scrollIndicatorInsets = webView.scrollView.contentInset
        }

        // Parity fix for the "Profile" tab not navigating reliably:
        // Android's MainActivity.java explicitly turns on
        // setJavaScriptCanOpenWindowsAutomatically(true), but WKWebView on iOS
        // defaults javaScriptCanOpenWindowsAutomatically to NO. When the site's
        // account/sign-in button opens its destination via an async window.open()
        // (e.g. after a tracking call or a promise resolves) rather than a
        // same-tick call, WebKit's stricter "must be a direct, synchronous
        // continuation of the user gesture" rule silently drops the call —
        // the tap still shows its CSS press state, but createWebViewWith(...)
        // below never fires. Enabling this brings iOS behavior in line with
        // Android's explicit opt-in and lets the WKUIDelegate methods below
        // actually receive the request.
        bridge?.webView?.configuration.preferences.javaScriptCanOpenWindowsAutomatically = true
    }

    // Re-apply the top inset if the safe area changes (e.g. rotation, or the
    // view being laid out again after the initial capacitorDidLoad() call
    // ran before safeAreaInsets had its final value).
    override func viewSafeAreaInsetsDidChange() {
        super.viewSafeAreaInsetsDidChange()
        if let webView = bridge?.webView {
            let topInset = view.safeAreaInsets.top
            webView.scrollView.contentInset = UIEdgeInsets(top: topInset, left: 0, bottom: 0, right: 0)
            webView.scrollView.scrollIndicatorInsets = webView.scrollView.contentInset
        }
    }

    // MARK: - Normal navigation (link taps, redirects, form posts, and iframe loads)

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.allow)
            return
        }

        let scheme = url.scheme?.lowercased() ?? ""
        let isMainFrame = navigationAction.targetFrame?.isMainFrame ?? true
        os_log("decidePolicyFor: %{public}@ (host=%{public}@, mainFrame=%{public}@)", log: navLog, type: .debug, url.absoluteString, url.host ?? "nil", String(isMainFrame))

        // tel:, mailto:, whatsapp:, sms: etc. -> hand off to the native app that handles them.
        if !scheme.hasPrefix("http") {
            if UIApplication.shared.canOpenURL(url) {
                UIApplication.shared.open(url, options: [:], completionHandler: nil)
            }
            decisionHandler(.cancel)
            return
        }

        if isAllowed(url.host) {
            decisionHandler(.allow)
            return
        }

        // Embedded frames (hCaptcha / bot-check / Shop sign-in / review widgets) must load
        // inline. Previously a sub-frame on an unlisted host was cancelled and replaced by a
        // popup Safari sheet — which can silently break the sign-in "send code" step
        // (App Review 2.1(a): "we did not receive an OTP code"). Tracker hosts are still
        // blocked separately by the content rule list above.
        if !isMainFrame {
            decisionHandler(.allow)
            return
        }

        // Vimeo (the product-reviews video widget): only block it from hijacking the
        // *whole page* (a top-level navigation actually leaving the app's site). An
        // ordinary iframe load (isMainFrame == false) is the video widget rendering
        // inline exactly like it does in Safari — let it through.
        if isBlockedHost(url.host) {
            if isMainFrame {
                os_log("decidePolicyFor: silently blocking a full-page vimeo hijack: %{public}@", log: navLog, type: .debug, url.absoluteString)
                decisionHandler(.cancel)
            } else {
                decisionHandler(.allow)
            }
            return
        }

        // Anything else: open inside an in-app browser sheet so the user never leaves the app.
        decisionHandler(.cancel)
        presentInAppBrowser(url)
    }

    // Safety net: if the injected user script didn't run for some reason, run the same
    // (idempotent) script again once each page finishes loading.
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        webView.evaluateJavaScript(Self.hideShopButtonJS, completionHandler: nil)
    }

    // MARK: - New-window requests (target="_blank", window.open). This only fires for
    // requests that want a *separate* window/tab — never for iframe loads — so this is
    // exactly where the old "ad-like popup" came from, and exactly where Vimeo still
    // needs to be blocked. Allowed URLs load right back in this same WebView instead,
    // so sign-in stays in-app.

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        guard let url = navigationAction.request.url else {
            os_log("createWebViewWith: navigationAction had no URL", log: navLog, type: .debug)
            return nil
        }

        os_log("createWebViewWith (new-window request): %{public}@ (host=%{public}@)", log: navLog, type: .debug, url.absoluteString, url.host ?? "nil")

        if isAllowed(url.host) {
            webView.load(navigationAction.request)
        } else if isBlockedHost(url.host) {
            os_log("createWebViewWith: silently blocking a vimeo popup window: %{public}@", log: navLog, type: .debug, url.absoluteString)
        } else {
            presentInAppBrowser(url)
        }
        return nil
    }

    private func presentInAppBrowser(_ url: URL) {
        let safari = SFSafariViewController(url: url)
        safari.modalPresentationStyle = .pageSheet
        present(safari, animated: true, completion: nil)
    }
}
