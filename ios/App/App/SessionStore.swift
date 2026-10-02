import Foundation

enum SessionStore {
    private static let tokenKey = "tammstore.session.token"
    private static let emailKey = "tammstore.session.email"

    static var token: String? {
        get { UserDefaults.standard.string(forKey: tokenKey) }
        set { UserDefaults.standard.set(newValue, forKey: tokenKey) }
    }

    static var email: String? {
        get { UserDefaults.standard.string(forKey: emailKey) }
        set { UserDefaults.standard.set(newValue, forKey: emailKey) }
    }

    static var isLoggedIn: Bool {
        token != nil
    }

    static func save(token: String, email: String) {
        self.token = token
        self.email = email
    }

    static func clear() {
        token = nil
        email = nil
    }
}

// NOTE: UserDefaults is fine for now, but isn't as secure as Keychain for
// storing a session token long-term. Consider swapping this for a Keychain
// wrapper (e.g. KeychainAccess or KeychainSwift) before shipping to
// production if the token grants access to sensitive account actions.
