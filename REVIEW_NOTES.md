# Tamm Store iOS — Resubmission Pack (App Review rejection of Oct 13, 2026)

Submission ID: `e4e8d276-1062-411a-b53a-70f7ed25a3f3` · Version 1.0 · Review device: iPad Air 11" (M3), iPadOS 27.0.1

Everything below marked **[CODE]** is already done in this project. Everything marked **[YOU]** must be done by you in
App Store Connect / Shopify — code can't do it for you.

---

## 1) Guideline 5.1.2(i) — Privacy: Data Use and Sharing (App Tracking Transparency)

**[CODE] done**
- `Info.plist` → added `NSUserTrackingUsageDescription` (Arabic + English).
- `MainViewController.swift` → the ATT system prompt is requested once on first launch
  (`requestTrackingPermissionIfNeeded()` from `viewDidAppear`).
- Until the user taps **Allow**, all known third-party tracking/ads domains (Meta, TikTok, Google Ads/Analytics, Snap,
  Pinterest, LinkedIn, Bing, Hotjar, Clarity, Criteo, …) are blocked in the WebView with a `WKContentRuleList`, and
  Shopify's Customer Privacy API is set to "no consent" (analytics / marketing / sale of data = false).
- If the user taps **Allow** → blocklist removed, page reloads. If **Ask App Not to Track** → blocklist stays forever.

**[YOU] required**
1. App Store Connect → **App Privacy** → answer that you **do track** users (Identifiers / Usage Data / Purchases →
   "Used for Tracking") **if your store's pixels (Meta/TikTok/Google…) are active**. Needs Account Holder/Admin.
2. Paste this in **App Review Information → Notes**:

```
App Tracking Transparency: the system permission prompt ("Allow “Tamm Store” to track your activity across other
companies’ apps and websites?") is shown automatically on the first launch of the app, a moment after the home screen
appears (implemented in MainViewController.viewDidAppear). If the user does not allow tracking, all third-party
tracking/advertising domains are blocked inside the app's web view and Shopify's Customer Privacy API is set to
"no consent", so no cookies are used for tracking.
```

---

## 2) Guideline 2.1(a) — App Completeness (could not sign in: no OTP received)
## 2b) Guideline 2.1(a) — Information Needed (demo account)

Your store uses Shopify's passwordless sign-in: a one-time code is e-mailed to whatever address is typed. App Review
can't read an inbox they don't own, so they never got the code.

**[CODE] done**
- Sub-frames (hCaptcha / Cloudflare / Shop sign-in / widgets) on hosts that were not in `allowedHosts` used to be
  **cancelled** and replaced by a pop-up Safari sheet. That can silently break the "send code" step, especially on
  iPad. Sub-frames now always load inline (`decidePolicyFor`: `if !isMainFrame { allow }`); `cloudflare.com` added to the
  allowed hosts. Tracker domains stay blocked separately.
- `UIRequiredDeviceCapabilities` changed from obsolete `armv7` to `arm64`.

**[YOU] required — create a demo mailbox the reviewer can open (this is the standard fix for OTP-only apps)**
1. Create a mailbox such as `appreview@tammstore.com` (own-domain webmail or Zoho/Outlook) with **no 2-step
   verification** and a simple password. Make sure Shopify can e-mail it (test it once yourself, on an iPad if possible).
2. In Shopify, create a customer with that email (optionally with a test order so "Orders" has content).
3. App Store Connect → **App Review Information** → tick **Sign-in required**, and fill:
   - User name: `appreview@tammstore.com`
   - Password: *(the mailbox password)*
4. Paste this in the **Notes** box (below the ATT note above):

```
Sign-in is OPTIONAL: browsing, search, cart and checkout work as a guest.
To test the account area (Profile tab → Sign in): enter the demo e-mail above. Shopify then e-mails a 6-digit code
to that same address — open the mailbox at <WEBMAIL URL> with the user name/password above, copy the code
(arrives within seconds; check Junk if needed) and enter it in the app.
```

5. Click **Reply to App Review** in the rejection message and send:

```
Hello, thank you for the review. We fixed all issues in the new build: (1) App Tracking Transparency prompt added and
tracking domains are blocked unless the user allows tracking; (2) sign-in verification frames now load inside the app,
and we added a demo mailbox in App Review Information (the one-time code is delivered to that mailbox); (3) removed
references to other platforms from the app and metadata. Please review the new build.
```

---

## 3) Guideline 2.3.10 — Accurate Metadata (non-Apple platforms / devices)

**[CODE] done** (iOS WebView only — Android build unaffected)
- Injected script `applePlatformFocusJS` hides store badges / links / mentions of other mobile platforms
  (Google Play, AppGallery, Android …) and hides product cards for non-Apple device brands (Samsung, Xiaomi, Huawei,
  OPPO, Pixel …); a product page of such a brand sent directly redirects to the store home.
- ⚠️ I could not open tammstore.com from here, so the brand/platform lists are **educated defaults**. Edit
  `platformTerms` and `nonAppleProductTerms` in `MainViewController.swift` to match your real catalog.

**[YOU] required — Apple explicitly said metadata too**
In App Store Connect remove every mention of other platforms/devices from: **description, promotional text,
What's New, keywords, app preview videos, and ALL screenshots** (re-take screenshots that show Android phones,
Samsung/Xiaomi products, Google Play badges, or Android names). Don't write "also on Android / Google Play".
For the strongest fix, also hide non-Apple products on the Shopify side for the app (e.g. serve the app an
Apple-only collection) — in-app hiding is a safety net, not a guarantee.

---

## Before you upload the new build
- Bump nothing manually: `codemagic.yaml` sets a unique build number automatically.
- Push to `main` → Codemagic builds → TestFlight → select the build in the version page → **Resubmit to App Review**.
- Test on a real iPad once: ATT prompt appears, Profile → email → code arrives, no popup sheets during sign-in.
