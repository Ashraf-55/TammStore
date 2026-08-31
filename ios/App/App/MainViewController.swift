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
        "shop.app"
    ]

    private func isAllowed(_ host: String?) -> Bool {
        guard let host = host?.lowercased(), !host.isEmpty else { return false }
        return allowedHosts.contains { host == $0 || host.hasSuffix("." + $0) }
    }

    // The "مراجعة منتجاتنا" (product reviews) Vimeo video widget: wherever it shows up on the
    // site (home page, product cards, etc.), a tap on it used to navigate to a vimeo.com URL,
    // which — since vimeo isn't an allowedHost — fell into presentInAppBrowser() below and
    // popped a full-screen in-app Safari sheet. That popup is exactly the "ad-like play thing"
    // that needs to disappear, so vimeo hosts get a dedicated silent-cancel path instead of
    // ever reaching presentInAppBrowser(), no matter which UI element on the page triggered it.
    private func isBlockedHost(_ host: String?) -> Bool {
        guard let host = host?.lowercased(), !host.isEmpty else { return false }
        return host.contains("vimeo.com") || host.contains("vimeocdn.com")
    }

    // MARK: - Hook into Capacitor's bridge once it's ready, so our navigation/UI
    // delegate methods below actually get called by the WebView.

    override func capacitorDidLoad() {
        super.capacitorDidLoad()
        bridge?.webView?.navigationDelegate = self
        bridge?.webView?.uiDelegate = self

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

        // Fix #3: the "مراجعة منتجاتنا" (product reviews) Vimeo video widget. Blocks its
        // requests at the network level, silently cancels any navigation to it (see
        // isBlockedHost usage in decidePolicyFor / createWebViewWith below — this is what
        // actually stops the popup, network-blocking alone did not), and hides any leftover
        // placeholder box via a few cheap injected JS passes.
        installVimeoReviewWidgetBlock()
    }

    // MARK: - Vimeo "product reviews" widget removal

    private func installVimeoReviewWidgetBlock() {
        guard let controller = bridge?.webView?.configuration.userContentController else { return }

        let hideWidgetJS = """
        (function(){
          function hideReviewsWidget(){
            try{
              document.querySelectorAll('iframe[src*="vimeo"]').forEach(function(f){
                var el=f; for(var i=0;i<4 && el.parentElement;i++){ el=el.parentElement; }
                el.style.display='none';
              });
              document.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(function(h){
                var t=(h.textContent||'').trim();
                if(t==='مراجعة منتجاتنا'){
                  h.style.display='none';
                  if(h.nextElementSibling){ h.nextElementSibling.style.display='none'; }
                  var sec=h.closest('section,div[class*="section"]');
                  if(sec){ sec.style.display='none'; }
                }
              });
            }catch(e){}
          }
          // A handful of cheap one-off passes instead of a permanently-attached
          // MutationObserver watching the whole document subtree: that observer was firing
          // its (expensive, document-wide) query on every single DOM change anywhere on the
          // page for the rest of the session — including on pages like Profile/Sign-in with
          // lots of form/keyboard churn — which is very likely why those pages started
          // feeling sluggish.
          hideReviewsWidget();
          document.addEventListener('DOMContentLoaded', hideReviewsWidget);
          [300, 1000, 2500, 5000].forEach(function(ms){ setTimeout(hideReviewsWidget, ms); });
        })();
        """
        let script = WKUserScript(source: hideWidgetJS, injectionTime: .atDocumentStart, forMainFrameOnly: false)
        controller.addUserScript(script)

        let blockRuleJSON = """
        [{ "trigger": { "url-filter": ".*vimeo.*" }, "action": { "type": "block" } }]
        """
        WKContentRuleListStore.default().compileContentRuleList(
            forIdentifier: "TammBlockVimeoReviewsWidget",
            encodedContentRuleList: blockRuleJSON
        ) { ruleList, error in
            guard let ruleList = ruleList, error == nil else {
                os_log("Vimeo content-rule compile failed: %{public}@", log: navLog, type: .error, error?.localizedDescription ?? "unknown")
                return
            }
            controller.add(ruleList)
        }
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

    // MARK: - Normal navigation (link taps, redirects, form posts)

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.allow)
            return
        }

        let scheme = url.scheme?.lowercased() ?? ""
        os_log("decidePolicyFor: %{public}@ (host=%{public}@)", log: navLog, type: .debug, url.absoluteString, url.host ?? "nil")

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

        // Vimeo (the product-reviews video widget): cancel quietly, never pop the Safari sheet.
        if isBlockedHost(url.host) {
            os_log("decidePolicyFor: silently blocking vimeo navigation: %{public}@", log: navLog, type: .debug, url.absoluteString)
            decisionHandler(.cancel)
            return
        }

        // Anything else: open inside an in-app browser sheet so the user never leaves the app.
        decisionHandler(.cancel)
        presentInAppBrowser(url)
    }

    // MARK: - New-window requests (target="_blank", window.open — this is how Shop Pay /
    // customer-account sign-in normally tries to launch). We never create a second window;
    // allowed URLs load right back in this same WebView instead, so sign-in stays in-app.

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        guard let url = navigationAction.request.url else {
            os_log("createWebViewWith: navigationAction had no URL", log: navLog, type: .debug)
            return nil
        }

        os_log("createWebViewWith (new-window request): %{public}@ (host=%{public}@)", log: navLog, type: .debug, url.absoluteString, url.host ?? "nil")

        if isAllowed(url.host) {
            webView.load(navigationAction.request)
        } else if isBlockedHost(url.host) {
            os_log("createWebViewWith: silently blocking vimeo new-window request: %{public}@", log: navLog, type: .debug, url.absoluteString)
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
