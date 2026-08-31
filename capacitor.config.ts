import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.tammstorekw.app',
  appName: 'Tamm Store',
  webDir: 'www',

  // This makes the app load your LIVE Shopify store directly,
  // so any changes you make in Shopify show up instantly with no app update needed.
  server: {
    url: 'https://tammstore.com/ar',
    cleartext: false,
    // Domains the in-app WebView is allowed to navigate to without kicking out to the system browser.
    // Add any other domains your checkout / payment provider redirects through.
    allowNavigation: [
      'tammstore.com',
      '*.tammstore.com',
      '*.myshopify.com',
      '*.shopify.com',
      '*.shopifycs.com',
      '*.shopifysvc.com',
      'checkout.shopify.com',
      'shop.app',
      '*.shop.app',
      // Domains used by the "product reviews" widget (photo/video reviews,
      // pagination, "view all reviews") so it can load its content and any
      // full-screen/video expansion without getting blocked inside the app.
      '*.judge.me',
      'judge.me',
      '*.loox.io',
      'loox.io',
      '*.okendo.io',
      'okendo.io',
      '*.stamped.io',
      'stamped.io',
      '*.yotpo.com',
      'yotpo.com',
      '*.reviews.io',
      'reviews.io',
      '*.vidjet.io',
      'vidjet.io',
      '*.vimeo.com',
      'vimeo.com',
      '*.vimeocdn.com',
      'youtube.com',
      '*.youtube.com',
      'youtube-nocookie.com',
      '*.youtube-nocookie.com',
      '*.ytimg.com'
    ]
  },

  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#ffffff',
      androidSplashResourceName: 'splash',
      showSpinner: false
    },
    StatusBar: {
      style: 'LIGHT',
      backgroundColor: '#ffffff'
    }
  },

  // Fix for "مراجعة منتجاتنا" (product reviews) not loading in the app:
  // the reviews/video widget checks the browser's User-Agent, and Capacitor's
  // WKWebView UA is missing the trailing "Safari/..." token that Mobile Safari
  // always has. Some third-party widgets treat any UA without that token as an
  // unsupported/embedded browser and refuse to render their video/photo content,
  // even though the exact same page works fine when opened in real Safari.
  // Appending it here makes the in-app browser identify itself exactly like
  // Safari does, so the widget renders normally.
  ios: {
    appendUserAgent: 'Safari/604.1',
    allowsLinkPreview: false,
    contentInset: 'automatic'
  },

  android: {
    allowMixedContent: false
  }
};

export default config;
