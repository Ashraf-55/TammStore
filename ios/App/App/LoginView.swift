import SwiftUI

// Set this to your deployed backend URL (see backend/README.md).
let backendBaseURL = "https://YOUR-BACKEND.vercel.app"

enum LoginStep {
    case enterEmail
    case enterCode
}

struct LoginView: View {
    var onLoggedIn: (String, String) -> Void // (token, email)

    @State private var email: String = ""
    @State private var code: String = ""
    @State private var step: LoginStep = .enterEmail
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Text("تسجيل الدخول")
                .font(.system(size: 28, weight: .bold))

            Text(step == .enterEmail
                 ? "أدخل إيميلك وهنبعتلك كود دخول"
                 : "أدخل الكود اللي وصلك على \(email)")
                .font(.system(size: 15))
                .foregroundColor(.gray)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            if step == .enterEmail {
                TextField("الإيميل", text: $email)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
                    .padding()
                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(10)
                    .padding(.horizontal, 32)
            } else {
                TextField("الكود", text: $code)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.center)
                    .font(.system(size: 24, weight: .semibold, design: .monospaced))
                    .padding()
                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(10)
                    .padding(.horizontal, 32)
            }

            if let errorMessage {
                Text(errorMessage)
                    .foregroundColor(.red)
                    .font(.system(size: 13))
            }

            Button(action: primaryAction) {
                if isLoading {
                    ProgressView().tint(.white)
                } else {
                    Text(step == .enterEmail ? "إرسال الكود" : "تأكيد")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(.white)
                }
            }
            .frame(maxWidth: .infinity)
            .frame(height: 52)
            .background(isFormValid ? Color.black : Color.gray.opacity(0.4))
            .cornerRadius(10)
            .padding(.horizontal, 32)
            .disabled(!isFormValid || isLoading)

            if step == .enterCode {
                Button("رجوع") {
                    step = .enterEmail
                    code = ""
                    errorMessage = nil
                }
                .font(.system(size: 14))
                .foregroundColor(.gray)
            }

            Spacer()
            Spacer()
        }
    }

    private var isFormValid: Bool {
        switch step {
        case .enterEmail:
            return email.contains("@") && email.contains(".")
        case .enterCode:
            return code.count == 6
        }
    }

    private func primaryAction() {
        errorMessage = nil
        switch step {
        case .enterEmail:
            sendCode()
        case .enterCode:
            verifyCode()
        }
    }

    private func sendCode() {
        isLoading = true
        postJSON(path: "/api/send-code", body: ["email": email]) { result in
            isLoading = false
            switch result {
            case .success:
                step = .enterCode
            case .failure:
                errorMessage = "حصل خطأ، حاول تاني"
            }
        }
    }

    private func verifyCode() {
        isLoading = true
        postJSON(path: "/api/verify-code", body: ["email": email, "code": code]) { result in
            isLoading = false
            switch result {
            case .success(let json):
                if let token = json["token"] as? String {
                    onLoggedIn(token, email)
                } else {
                    errorMessage = "الكود غلط، حاول تاني"
                }
            case .failure:
                errorMessage = "الكود غلط أو انتهت صلاحيته"
            }
        }
    }

    private func postJSON(
        path: String,
        body: [String: String],
        completion: @escaping (Result<[String: Any], Error>) -> Void
    ) {
        guard let url = URL(string: backendBaseURL + path) else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error {
                    completion(.failure(error))
                    return
                }
                guard let data,
                      let httpResponse = response as? HTTPURLResponse,
                      (200...299).contains(httpResponse.statusCode),
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
                else {
                    completion(.failure(NSError(domain: "login", code: -1)))
                    return
                }
                completion(.success(json))
            }
        }.resume()
    }
}
