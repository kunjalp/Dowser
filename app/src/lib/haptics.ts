/**
 * Haptics for the iPhone app (Capacitor). Every call is a safe no-op in a plain browser, on
 * desktop, and in an older app build that does not contain the native plugin yet.
 */
import { Capacitor } from "@capacitor/core";

type Mod = typeof import("@capacitor/haptics");

let loaded: Promise<Mod | null> | null = null;

function load(): Promise<Mod | null> {
  if (loaded) return loaded;
  loaded = (async () => {
    try {
      if (typeof window === "undefined" || !Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("Haptics")) {
        return null;
      }
      return await import("@capacitor/haptics");
    } catch {
      return null;
    }
  })();
  return loaded;
}

const last: Record<string, number> = {};

/** Runs fn at most once per 60 ms per kind, so one action never buzzes twice. */
function fire(kind: string, fn: (m: Mod) => Promise<void>) {
  const now = Date.now();
  if (now - (last[kind] ?? 0) < 60) return;
  last[kind] = now;
  void load().then((m) => (m ? fn(m).catch(() => {}) : undefined));
}

export const haptics = {
  /** Light impact: decision buttons, Sort tab, Undo. */
  light: () => fire("light", (m) => m.Haptics.impact({ style: m.ImpactStyle.Light })),
  /** Selection tick: sort options, list/map toggle. */
  tick: () =>
    fire("tick", async (m) => {
      await m.Haptics.selectionStart();
      await m.Haptics.selectionChanged();
      await m.Haptics.selectionEnd();
    }),
  success: () => fire("notify", (m) => m.Haptics.notification({ type: m.NotificationType.Success })),
  warning: () => fire("notify", (m) => m.Haptics.notification({ type: m.NotificationType.Warning })),
  error: () => fire("notify", (m) => m.Haptics.notification({ type: m.NotificationType.Error })),
};
