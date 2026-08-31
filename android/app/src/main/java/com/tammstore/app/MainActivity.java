package com.tammstore.app;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Message;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import androidx.annotation.Nullable;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;

public class MainActivity extends BridgeActivity {

    // Domains that stay INSIDE the app's WebView (your store + Shopify checkout/CDN).
    // Must be kept in sync with allowedHosts in ios/App/App/MainViewController.swift.
    // Add your payment gateway's domain here too if checkout redirects off-site.
    private static final String[] ALLOWED_HOSTS = {
        "tammstore.com",
        "myshopify.com",
        "shopify.com",
        "shopifycs.com",
        "shopifysvc.com",
        "shop.app"
    };

    private static boolean isAllowedHost(String host) {
        if (host == null) return false;
        for (String allowed : ALLOWED_HOSTS) {
            if (host.equals(allowed) || host.endsWith("." + allowed)) {
                return true;
            }
        }
        return false;
    }

    // The slow-loading "مراجعة منتجاتنا" (product reviews) Vimeo video widget that shows up
    // as soon as the store's home page loads, sits blank for a long time, and — if tapped —
    // pops open a full video player. Matched by host so we can strip it out at the network
    // level (fixes both the ad-like popup AND the page-load slowdown it causes on every page
    // that embeds it, including the Profile tab).
    private static boolean isBlockedHost(String host) {
        if (host == null) return false;
        return host.contains("vimeo.com") || host.contains("vimeocdn.com");
    }

    // Small pull-to-refresh + offline-banner script injected into every page load.
    // Also hides the Vimeo "product reviews" video widget (see isBlockedHost above) wherever
    // it appears on the site, since blocking its network requests alone can still leave an
    // empty placeholder box behind.
    private static final String INJECTED_JS =
        "(function(){"
        + "if(window.__tammInjected)return; window.__tammInjected=true;"
        + "var startY=0, pulling=false;"
        + "document.addEventListener('touchstart',function(e){ if(window.scrollY===0){ startY=e.touches[0].clientY; pulling=true; } },{passive:true});"
        + "document.addEventListener('touchmove',function(e){ if(pulling && e.touches[0].clientY - startY > 90){ pulling=false; window.location.reload(); } },{passive:true});"
        + "document.addEventListener('touchend',function(){ pulling=false; },{passive:true});"
        + "window.addEventListener('offline',function(){ showBanner('You are offline'); });"
        + "window.addEventListener('online',function(){ hideBanner(); });"
        + "function showBanner(msg){ var b=document.getElementById('__tammOfflineBanner'); if(!b){ b=document.createElement('div'); b.id='__tammOfflineBanner'; b.style.cssText='position:fixed;top:0;left:0;right:0;z-index:99999;background:#111;color:#fff;text-align:center;padding:8px;font-size:13px;font-family:sans-serif;'; document.body.appendChild(b);} b.textContent=msg; }"
        + "function hideBanner(){ var b=document.getElementById('__tammOfflineBanner'); if(b) b.remove(); }"
        + "if(!navigator.onLine){ showBanner('You are offline'); }"
        + "function hideReviewsWidget(){"
        + "  try{"
        + "    document.querySelectorAll('iframe[src*=\"vimeo\"]').forEach(function(f){"
        + "      var el=f; for(var i=0;i<4 && el.parentElement;i++){ el=el.parentElement; }"
        + "      el.style.display='none';"
        + "    });"
        + "    document.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(function(h){"
        + "      var t=(h.textContent||'').trim();"
        + "      if(t==='مراجعة منتجاتنا'){"
        + "        h.style.display='none';"
        + "        if(h.nextElementSibling){ h.nextElementSibling.style.display='none'; }"
        + "        var sec=h.closest('section,div[class*=\"section\"]');"
        + "        if(sec){ sec.style.display='none'; }"
        + "      }"
        + "    });"
        + "  }catch(e){}"
        + "}"
        // A handful of cheap one-off passes instead of a permanently-attached MutationObserver
        // watching the whole document subtree: that observer was firing its (expensive,
        // document-wide) query on every single DOM change anywhere on the page for the rest of
        // the session — including on pages like Profile/Sign-in with lots of form/keyboard
        // churn — which is very likely why those pages started feeling sluggish.
        + "hideReviewsWidget();"
        + "[300,1000,2500,5000].forEach(function(ms){ setTimeout(hideReviewsWidget, ms); });"
        + "})();";

    @Override
    public void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        WebView webView = getBridge().getWebView();
        webView.getSettings().setSupportMultipleWindows(true);
        webView.getSettings().setJavaScriptCanOpenWindowsAutomatically(true);

        webView.setWebViewClient(new BridgeWebViewClient(getBridge()) {
            @Override
            public android.webkit.WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                if (isBlockedHost(request.getUrl().getHost())) {
                    // Empty response instead of null: null lets the request fall through and
                    // load normally, an empty response actually stops it.
                    return new android.webkit.WebResourceResponse("text/plain", "utf-8",
                        new java.io.ByteArrayInputStream(new byte[0]));
                }
                return super.shouldInterceptRequest(view, request);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String scheme = uri.getScheme();

                // tel:, mailto:, whatsapp:, https://wa.me deep links etc. -> hand off to native apps.
                if (scheme != null && !scheme.startsWith("http")) {
                    return openExternally(uri);
                }

                if (isAllowedHost(uri.getHost())) {
                    return false; // keep it inside the app's WebView
                }

                // Vimeo (the product-reviews video widget): swallow it quietly, never hand off
                // to an external browser/app — that hand-off is exactly the "ad-like popup".
                if (isBlockedHost(uri.getHost())) {
                    return true; // consume the navigation, do nothing
                }

                // Anything else (social links, external articles, third-party payment pages
                // not listed above) opens in the system browser instead of trapping the user.
                return openExternally(uri);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                view.evaluateJavascript(INJECTED_JS, null);
            }

            private boolean openExternally(Uri uri) {
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (ActivityNotFoundException e) {
                    // No app can handle this link (e.g. whatsapp: with WhatsApp not installed) — ignore.
                }
                return true;
            }
        });

        // Handles links / JS that try to open a NEW window (target="_blank", window.open —
        // this is how Shop Pay / customer-account sign-in normally tries to launch). Instead
        // of creating a second window, allowed URLs load right back in this same WebView, so
        // sign-in stays inside the app instead of bouncing out to the system browser.
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onCreateWindow(WebView view, boolean isDialog, boolean isUserGesture, Message resultMsg) {
                WebView.HitTestResult result = view.getHitTestResult();
                String targetUrl = result != null ? result.getExtra() : null;

                if (targetUrl != null) {
                    Uri uri = Uri.parse(targetUrl);
                    if (isAllowedHost(uri.getHost())) {
                        view.loadUrl(targetUrl);
                    } else if (isBlockedHost(uri.getHost())) {
                        // Vimeo: do nothing, no external hand-off, no popup.
                    } else {
                        try {
                            startActivity(new Intent(Intent.ACTION_VIEW, uri));
                        } catch (ActivityNotFoundException ignored) {
                        }
                    }
                }
                // We never actually create a second WebView/window.
                return false;
            }
        });
    }
}
