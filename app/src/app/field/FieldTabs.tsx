"use client";

import { haptics } from "../../lib/haptics";

type View = "list" | "map";

/** Rows: three bars, filled when the tab is active. */
function ListIcon({ on }: { on: boolean }) {
  return (
    <svg className="tab-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {[4, 10, 16].map((y) =>
        on ? (
          <rect key={y} x="3" y={y} width="18" height="4" fill="currentColor" />
        ) : (
          <rect key={y} x="3.75" y={y + 0.75} width="16.5" height="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        ),
      )}
    </svg>
  );
}

/** Map pin, solid with a punched-out center when active. */
function MapIcon({ on }: { on: boolean }) {
  const pin = "M12 2.5c-3.9 0-7 3-7 6.9 0 5 7 12.1 7 12.1s7-7.1 7-12.1c0-3.9-3.1-6.9-7-6.9z";
  return (
    <svg className="tab-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {on ? (
        <path d={`${pin}M12 7a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z`} fill="currentColor" fillRule="evenodd" />
      ) : (
        <>
          <path d={pin} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          <circle cx="12" cy="9.5" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </>
      )}
    </svg>
  );
}

/** Sliders. Sort opens a sheet and is never the active tab, so it only has an outline form. */
function SortIcon() {
  return (
    <svg className="tab-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M3 7h18M3 17h18" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="9" cy="7" r="2.5" fill="var(--panel)" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="15" cy="17" r="2.5" fill="var(--panel)" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

/** Field View bottom tab bar: List / Map, plus Sort (opens the sort sheet) in list view. */
export default function FieldTabs({
  view,
  onView,
  onSort,
}: {
  view: View;
  onView: (v: View) => void;
  onSort: () => void;
}) {
  const tab = (v: View, label: string, Icon: typeof ListIcon) => (
    <button
      type="button"
      role="tab"
      aria-selected={view === v}
      className={`tab ${view === v ? "on" : ""}`}
      onClick={() => {
        if (view !== v) haptics.tick();
        onView(v);
      }}
    >
      <span className="tab-inner">
        <Icon on={view === v} />
        <span className="tab-label">{label}</span>
      </span>
    </button>
  );

  return (
    <nav className="field-tabs" aria-label="Field View" role="tablist">
      {tab("list", "List", ListIcon)}
      {tab("map", "Map", MapIcon)}
      {view === "list" && (
        <button
          type="button"
          className="tab sort"
          aria-haspopup="dialog"
          onClick={() => {
            haptics.light();
            onSort();
          }}
        >
          <span className="tab-inner">
            <SortIcon />
            <span className="tab-label">Sort</span>
          </span>
        </button>
      )}
    </nav>
  );
}
