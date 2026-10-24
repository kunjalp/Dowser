# Local integrated preview

Started 2026-10-24 at http://127.0.0.1:3000.
Field View: http://127.0.0.1:3000/field.

New read-only reference mode: http://127.0.0.1:3000/reviewed. It has 62 actual
human-annotated rings plus two labelled errors, each with coherent source data;
see [reviewed reference preview](ml/REVIEWED_REFERENCE_PREVIEW.md). It does not
replace the existing shared production candidate set or change model metrics.

Runtime checkout: `/Users/emirtg/Desktop/dowser-preview`, branch
`preview/integration`. This is a separate clone, not a branch switch in the
original or Claude's checkout. Main `cc315eff3ed801afbb042c07f0357c29f2b99eac`
and ML `019f880e65074cc773945e6722b573e28b0cf7e7` were combined there using
`git merge --no-commit --no-ff`. No remote PR merge or deployment was made.
The preview merge remains uncommitted; do not mistake it for a team merge.

Both root and app dependencies were installed with `npm ci --no-audit --no-fund`.
Ignored `app/.env.local` points at the existing shared production backend
`https://earnest-otter-112.convex.cloud`, discovered in the team's public site
and subsequently confirmed by the user. `/api/query` candidate reads and
`https://earnest-otter-112.convex.site/health` responded successfully.
No seeding, reload, Convex dev/deploy or sensor POST was run. The UI's existing
status/pairing/finding buttons still operate on that shared backend.

Run/restart from the preview checkout:

```sh
cd /Users/emirtg/Desktop/dowser-preview/app
npm run dev -- --hostname 127.0.0.1 --port 3000
```

The long-running Next process is left active. Initial HTTP checks passed for
`/`, `/field`, the MapLibre worker, ML comparison HTML and a referenced native
Val PNG. This is startup/HTTP verification, not browser end-to-end acceptance.

Three pinned GeoTIFFs were converted using the existing overlay converter into
preview-only `app/public/historical/`: Oil Center 1954, Oildale 1954 and Oil
Center 1992. The manifest/assets are local and not published to the team site.

Existing ML reports are linked read-only under preview `app/public/ml/`:

- http://127.0.0.1:3000/ml/runs/kern_repair_v2_mixed_s42/comparison_to_cursor_translate/comparison.html
- http://127.0.0.1:3000/ml/runs/kern_yolo11n_data_v2/comparison_to_baseline/comparison.html

These links use current source reports/images from `dowser-cursor/data/ml`.
No Test images were linked. Main map data comes from the existing team backend;
opening this preview does not promote a repair model or implement the proposed
95% quality plan. Changes in the source checkout are not automatically copied
to the preview clone; app edits made inside the preview use Next hot reload.
