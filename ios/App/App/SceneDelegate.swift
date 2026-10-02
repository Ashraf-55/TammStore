import UIKit
import Capacitor

class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = scene as? UIWindowScene else { return }

        window = UIWindow(windowScene: windowScene)
        // Go straight to the webview. Login now happens inside the site itself
        // (the email+code option on the Shopify account screen) — the "Continue
        // with shop" button is hidden there by MainViewController's injected JS.
        window?.rootViewController = MainViewController()
        window?.makeKeyAndVisible()
    }

    // Forwards deep links (universal links / custom URL schemes) to Capacitor's
    // bridge, same mechanism Capacitor's own default SceneDelegate template uses.
    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        guard let url = URLContexts.first?.url else { return }
        NotificationCenter.default.post(name: .capacitorOpenURL, object: url)
    }

    func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
        NotificationCenter.default.post(name: .capacitorContinueActivity, object: userActivity)
    }
}
