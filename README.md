# Tamm Store — Mobile App (Capacitor WebView wrapper)

This project wraps **https://tammstore.com** as a native Android/iOS app using
[Capacitor](https://capacitorjs.com). The app loads your live storefront directly, so
anything you change in Shopify (products, theme, prices) shows up instantly — no app
update needed.

## What's already done

- ✅ Capacitor project scaffolded, pointed at `https://tammstore.com`
- ✅ Android platform generated (`/android`)
- ✅ Navigation locked to your store + Shopify checkout/CDN domains; every other link
  (WhatsApp, Telegram, social icons, `tel:`, `mailto:`) opens in the phone's native
  app/browser instead of trapping the user inside the WebView
  (`android/app/src/main/java/com/tammstore/app/MainActivity.java`)
- ✅ Pull-to-refresh and an offline banner injected automatically
- ✅ App icon + splash screen generated for every Android density (placeholder design —
  see **Before you submit** below)
- ✅ RTL support enabled in the manifest (for the Arabic version of your store)
- ✅ INTERNET permission set

## ⚠️ Read this before you spend time building

**Apple is genuinely strict about plain WebView wrapper apps.** App Store Review
Guideline 4.2 ("Minimum Functionality") is the single most common rejection reason for
apps like this — Apple will bounce a submission that is "just a website in a box" with
no native functionality. Google Play is more lenient but has a similar quality bar.

To have a realistic shot at approval, budget time for **at least one or two** of:
- Push notifications (order updates, abandoned cart, promos)
- Native features: biometric login, Apple/Google Pay button, saved addresses, a native
  account/order-history screen, camera-based barcode/QR scanning for in-store pickup, etc.
- A genuinely app-like layer on top of the WebView (native tab bar, native product search
  with instant results, wishlist stored on-device)

If you want, I can help you scope and build one of these next — push notifications tied to
Shopify order webhooks is usually the highest-value, lowest-effort option.

## Before you submit to either store

1. **Replace the placeholder logo.** `assets/icon.png` (1024×1024) and
   `assets/splash.png` (2732×2732) are a generic placeholder I generated — swap in your
   real Tamm Store logo, then re-run:
   ```
   npx capacitor-assets generate --android
   npx cap sync android
   ```
2. **Privacy policy URL** — both stores require one at submission. You already have
   `https://tammstore.com/policies/privacy-policy` (or similar) — use that link.
3. **Screenshots** — take these from the running app (phone + tablet sizes for Android,
   6.7" and iPad sizes for iOS) once you can run it.
4. **App Store Connect "Sign in with Apple"** — if your store lets users log in with any
   third-party account (Google, Facebook), Apple requires you to also offer Sign in with
   Apple. Worth checking your Shopify customer-account settings.

---

## Before your first release build — generate your signing key

The project is already wired to sign release builds from `android/keystore.properties`,
but that file (and the actual `.jks` key) must never be committed, zipped, or shared —
it's the one secret that must live only on your machine.

1. Open a terminal in `android/app/` and run:
   ```
   keytool -genkey -v -keystore release-key.jks -alias tamm-release -keyalg RSA -keysize 2048 -validity 10000
   ```
   Use a long, random password when prompted (a password manager's generator is ideal) —
   not a word, name, or email address.
2. Copy `android/keystore.properties.example` to `android/keystore.properties` and fill in
   the real password(s) you just chose.
3. Back up `release-key.jks` and its password somewhere safe and private (password
   manager / encrypted note). **If you lose this file, you can never update this app on
   the same Play Store listing again** — you'd have to publish as a brand new app.
4. Both files are already git-ignored. Keep it that way.

## Building for Android (Google Play) — you can do this yourself now

**Requirements:** [Android Studio](https://developer.android.com/studio) (free), installed
on any Windows/Mac/Linux machine.

1. Unzip this project, open a terminal in it, run:
   ```
   npm install
   npx cap sync android
   ```
2. Open the `android` folder in Android Studio (File → Open).
3. Let Gradle sync finish (first time takes a few minutes).
4. **Build → Generate Signed Bundle / APK → Android App Bundle**. Create (or reuse) a
   signing key — Android Studio walks you through this. Keep the keystore file and its
   passwords somewhere safe; you'll need the *same* keystore for every future update.
5. This produces a `.aab` file — that's what you upload in
   [Google Play Console](https://play.console.google.com) under your company account:
   Create app → fill in store listing (uses your existing screenshots/description) →
   Production → Create release → upload the `.aab`.
6. Play Console will also ask for a **Data safety** form and **content rating**
   questionnaire — straightforward for an e-commerce app, no special data beyond normal
   account/order info.

## Building for iOS (App Store) — no Mac needed, use a cloud build

Since you don't have a Mac, use a cloud CI that builds and signs iOS apps on macOS
runners for you. Recommended: **[Codemagic](https://codemagic.io)** (free tier covers
occasional builds) or **Ionic Appflow**.

High-level flow with Codemagic:
1. Push this project to a GitHub/GitLab repo (private is fine).
2. Sign up at codemagic.io, connect the repo, choose "Capacitor" as the project type.
3. In your Apple Developer account (needed regardless — $99/year, required to publish on
   the App Store no matter who builds the app), generate an **App Store Connect API key**
   and add it to Codemagic under Team settings → Code signing. Codemagic then handles
   certificates/provisioning automatically ("automatic code signing").
4. Set the build to run `ios` platform:
   ```
   npx cap sync ios
   ```
   (Codemagic can run this step for you, or you add `npx cap add ios` locally before
   pushing so the `/ios` folder is committed.)
5. Codemagic builds the `.ipa` and can publish it straight to **TestFlight** or App Store
   Connect for review.
6. Finish the listing in [App Store Connect](https://appstoreconnect.apple.com):
   screenshots, description, privacy policy URL, privacy "nutrition label" (what data the
   app collects — for a Shopify store this is typically contact info, purchase history,
   identifiers for analytics if you use any).

If you'd rather not deal with CI configuration yourself, this is also a very cheap thing
to hand to a freelancer for a one-time setup — the hard part (the app itself) is already
built.

---

## Project structure

```
tamm-store-app/
├── android/                 # Native Android project (open in Android Studio)
├── assets/                  # Source icon.png / splash.png (replace with your real logo)
├── www/                     # Unused placeholder — app loads the live site directly
├── capacitor.config.ts      # Points the app at tammstore.com, allowed domains, plugins
└── package.json
```

## Common tweaks

- **Add/remove allowed domains** (e.g. a payment gateway that redirects off-domain during
  checkout): edit `allowNavigation` in `capacitor.config.ts` AND the `ALLOWED_HOSTS` array
  in `MainActivity.java`, then `npx cap sync android`.
- **Change app name/colors**: `capacitor.config.ts` (`appName`) and `assets/icon.svg` /
  `assets/splash.svg` if you want to tweak the placeholder design before generating a real
  logo.

# TammStore-AppStore
