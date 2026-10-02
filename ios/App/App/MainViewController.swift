import UIKit
import WebKit
import Capacitor
import SafariServices
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
        "hcaptcha.com"
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

    override func capacitorDidLoad() {
        super.capacitorDidLoad()
        bridge?.webView?.navigationDelegate = self
        bridge?.webView?.uiDelegate = self
        bridge?.webView?.configuration.userContentController.addUserScript(Self.hideShopButtonScript)

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
