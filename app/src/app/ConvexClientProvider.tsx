"use client";

import { ConvexProvider, ConvexReactClient } from "convex/react";
import { ReactNode, useMemo } from "react";

export default function ConvexClientProvider({ children }: { children: ReactNode }) {
  const url = process.env.NEXT_PUBLIC_CONVEX_URL;
  const client = useMemo(() => (url ? new ConvexReactClient(url) : null), [url]);

  if (!client) {
    return (
      <div className="setup-error">
        <h1>Missing NEXT_PUBLIC_CONVEX_URL</h1>
        <p>
          Create <code>app/.env.local</code> with the line{" "}
          <code>NEXT_PUBLIC_CONVEX_URL=https://your-deployment.convex.cloud</code>, then restart{" "}
          <code>npm run dev</code>.
        </p>
      </div>
    );
  }
  return <ConvexProvider client={client}>{children}</ConvexProvider>;
}
