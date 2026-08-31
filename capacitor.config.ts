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
      '*.shop.app'
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

  android: {
    allowMixedContent: false
  }
};

export default config;
