// One-time, safe-to-repeat patch: installable-app metadata + iPhone safe-area CSS.
// Run from the app/ folder:  node scripts/add-mobile-support.mjs
// It only ADDS what is missing, so it will not undo a UI restyle. Prints what it did.
import { readFileSync, writeFileSync, existsSync } from "node:fs";

const log = (m) => console.log(m);

// 1) layout.tsx: manifest, icons, apple web app, viewport-fit cover
const layoutPath = "src/app/layout.tsx";
let layout = readFileSync(layoutPath, "utf8");
if (layout.includes("manifest.webmanifest")) {
  log("layout.tsx: already has the manifest, skipped");
} else {
  const before = layout;
  layout = layout.replace(
    /(export const metadata: Metadata = \{[\s\S]*?)(\n\};)/,
    `$1\n  manifest: "/manifest.webmanifest",\n  icons: { icon: "/icons/icon-192.png", apple: "/icons/apple-touch-icon.png" },\n  appleWebApp: { capable: true, title: "Dowser", statusBarStyle: "black-translucent" },$2`,
  );
  layout = layout.replace(
    /export const viewport: Viewport = \{[^}]*\};/,
    'export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#0f1215" };',
  );
  if (layout === before) log("layout.tsx: could not find metadata/viewport to patch. Add manifest, icons, appleWebApp and viewportFit by hand.");
  else {
    writeFileSync(layoutPath, layout);
    log("layout.tsx: patched");
  }
}

// 2) globals.css: safe areas for the iPhone notch and home indicator
const cssPath = "src/app/globals.css";
if (!existsSync(cssPath)) log("globals.css not found, skipped");
else {
  const css = readFileSync(cssPath, "utf8");
  if (css.includes("safe-area-inset-top")) log("globals.css: already has safe-area rules, skipped");
  else {
    writeFileSync(
      cssPath,
      css +
        `\n/* iPhone notch / home indicator (installed app and Add-to-Home-Screen) */\n.field { padding-top: calc(14px + env(safe-area-inset-top)); padding-bottom: calc(40px + env(safe-area-inset-bottom)); padding-left: calc(16px + env(safe-area-inset-left)); padding-right: calc(16px + env(safe-area-inset-right)); }\n@media (max-width: 800px) { .sidebar-head { padding-top: calc(16px + env(safe-area-inset-top)); } }\n`,
    );
    log("globals.css: safe-area rules added");
  }
}
