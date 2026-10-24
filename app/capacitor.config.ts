import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Live-URL wrapper: the native app loads the deployed site, so UI changes shipped to Vercel
 * show up in the app with no rebuild. Rebuild (Codemagic) only for native changes.
 * Change appId to the bundle identifier registered in your Apple Developer account.
 */
const config: CapacitorConfig = {
  appId: "com.kunjalp.dowser",
  appName: "Dowser",
  webDir: "capacitor-www", // required by Capacitor; only shown if the live URL is unreachable
  server: {
    url: "https://dowser-ten.vercel.app/field",
    cleartext: false,
    allowNavigation: ["dowser-ten.vercel.app", "*.convex.cloud", "*.convex.site", "server.arcgisonline.com"],
  },
  ios: {
    contentInset: "never",
    backgroundColor: "#0f1215",
    limitsNavigationsToAppBoundDomains: false,
  },
};

export default config;
