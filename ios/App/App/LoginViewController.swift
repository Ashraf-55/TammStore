import UIKit
import SwiftUI

class LoginViewController: UIViewController {

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .white

        let loginView = LoginView { [weak self] token, email in
            SessionStore.save(token: token, email: email)
            self?.goToApp()
        }

        let hosting = UIHostingController(rootView: loginView)
        addChild(hosting)
        hosting.view.frame = view.bounds
        hosting.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(hosting.view)
        hosting.didMove(toParent: self)
    }

    private func goToApp() {
        let mainVC = MainViewController()
        mainVC.modalPresentationStyle = .fullScreen
        mainVC.modalTransitionStyle = .crossDissolve
        present(mainVC, animated: true)
    }
}
