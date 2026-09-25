import UIKit
import WebKit
import Capacitor
import SafariServices
import AuthenticationServices
import os.log

private let navLog = OSLog(subsystem: "com.tammstorekw.app", category: "Navigation")

// TODO: replace with your real Vercel deployment URL once it's live, e.g.
// "https://tamm-store-apple-signin.vercel.app/api/apple-signin"
private let appleSignInBackendURL = URL(string: "https://tamm-store-login-9lva.vercel.app/api/apple-signin")!

// Hosts where the Shop sign-in screen actually lives — this is where we
// surface the native "Sign in with Apple" button as the equivalent option
// Apple's Guideline 4.8 asks for, sitting alongside the existing Shop login.
private let signInHosts: Set<String> = ["shop.app"]

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

    // MARK: - Sign in with Apple (Guideline 4.8)
    //
    // A real, native alternative to the existing Shop login — not a
    // decoration. Tapping it runs Apple's native auth flow, then calls our
    // backend to find-or-create the matching Shopify customer using only
    // the name/email Apple provides.
    //
    // Sits as a floating overlay above the WebView (not inside it), so it
    // can never interfere with the site's own layout or the navigation
    // logic below. Hidden by default; only shown while the WebView is on
    // the Shop sign-in screen (see webView(_:didFinish:) further down).

    private lazy var appleSignInButton: ASAuthorizationAppleIDButton = {
        let button = ASAuthorizationAppleIDButton(type: .signIn, style: .black)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.addTarget(self, action: #selector(handleAppleSignInTap), for: .touchUpInside)
        button.isHidden = true
        return button
    }()

    private func installAppleSignInButtonIfNeeded() {
        guard appleSignInButton.superview == nil else { return }
        view.addSubview(appleSignInButton)
        NSLayoutConstraint.activate([
            appleSignInButton.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            appleSignInButton.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24),
            appleSignInButton.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -24),
            appleSignInButton.heightAnchor.constraint(equalToConstant: 50)
        ])
    }

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

        installAppleSignInButtonIfNeeded()
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

    // MARK: - Show the Apple button only on the actual sign-in screen, so it
    // never floats over normal shopping pages.

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let host = webView.url?.host?.lowercased() ?? ""
        let onSignInScreen = signInHosts.contains { host == $0 || host.hasSuffix("." + $0) }
        appleSignInButton.isHidden = !onSignInScreen
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

    @objc private func handleAppleSignInTap() {
        let request = ASAuthorizationAppleIDProvider().createRequest()
        request.requestedScopes = [.fullName, .email]
        let controller = ASAuthorizationController(authorizationRequests: [request])
        controller.delegate = self
        controller.presentationContextProvider = self
        controller.performRequests()
    }

    private func showAppleSignInAlert(title: String, message: String) {
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

// MARK: - Apple Sign-In result handling + talking to our backend

extension MainViewController: ASAuthorizationControllerDelegate, ASAuthorizationControllerPresentationContextProviding {

    func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
        return view.window ?? UIWindow()
    }

    func authorizationController(controller: ASAuthorizationController, didCompleteWithAuthorization authorization: ASAuthorization) {
        guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
              let tokenData = credential.identityToken,
              let identityToken = String(data: tokenData, encoding: .utf8) else {
            showAppleSignInAlert(title: "حصل خطأ", message: "معرفناش نكمل تسجيل الدخول بـ Apple. حاول تاني.")
            return
        }

        // Apple only sends the email/name on the very first authorization for
        // this app. Cache it locally (keyed by Apple's stable user id) so
        // later sign-ins on this device still have it to send to the backend.
        let userId = credential.user
        let defaultsKey = "appleSignIn.email.\(userId)"
        let emailFromApple = credential.email
        if let emailFromApple = emailFromApple {
            UserDefaults.standard.set(emailFromApple, forKey: defaultsKey)
        }
        let email = emailFromApple ?? UserDefaults.standard.string(forKey: defaultsKey)

        sendToBackend(
            identityToken: identityToken,
            email: email,
            firstName: credential.fullName?.givenName,
            lastName: credential.fullName?.familyName
        )
    }

    func authorizationController(controller: ASAuthorizationController, didCompleteWithError error: Error) {
        // .canceled just means the user dismissed the Apple sheet — not a real error.
        if let authError = error as? ASAuthorizationError, authError.code == .canceled {
            return
        }
        showAppleSignInAlert(title: "حصل خطأ", message: "تسجيل الدخول بـ Apple ماكملش. حاول تاني.")
    }

    private func sendToBackend(identityToken: String, email: String?, firstName: String?, lastName: String?) {
        var body: [String: Any] = ["identityToken": identityToken]
        if let email = email { body["email"] = email }
        if let firstName = firstName { body["firstName"] = firstName }
        if let lastName = lastName { body["lastName"] = lastName }

        var request = URLRequest(url: appleSignInBackendURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                guard let self = self else { return }
                guard error == nil, let data = data,
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      (json["success"] as? Bool) == true else {
                    self.showAppleSignInAlert(title: "حصل خطأ", message: "معرفناش نجهز حسابك دلوقتي. حاول تاني بعد شوية.")
                    return
                }

                self.showAppleSignInAlert(
                    title: "تمام!",
                    message: "حسابك جاهز على نفس الإيميل بتاع Apple ID بتاعك. أكمل تسجيل الدخول بنفس الإيميل ده في الشاشة اللي فتحت."
                )
            }
        }.resume()
    }
}
