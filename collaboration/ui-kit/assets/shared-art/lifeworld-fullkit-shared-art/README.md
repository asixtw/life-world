# Life World — shared artwork v1 (partial delivery)

**8 actual image-generated originals, not a completed full kit.** Built-in image generation produced original PNG artwork; technical resizing/canvas placement/crop previews are reproducible in `provenance/export_assets.py`. No paid service, credentials, film assets, repository modifications, upload, or publication was used.

## Delivered

| Stable asset ID | State / use | Exports |
|---|---|---|
| `lw-egg-rest-v1` | `rest` — unhatched egg | transparent 1024 / 512 / 256 |
| `lw-egg-softglow-v1` | `softglow` — closed, glowing egg | transparent 1024 / 512 / 256 |
| `lw-egg-initialcrack-v1` | `initialcrack` — first crack | transparent 1024 / 512 / 256 |
| `lw-egg-deepcrack-v1` | `deepcrack` — deeper branching cracks | transparent 1024 / 512 / 256 |
| `lw-lumi-companion-v1` | companion / welcome pose | transparent 1024 / 512 / 256 |
| `lw-lumi-quiet-v1` | peaceful eyes-closed quiet pose | transparent 1024 / 512 / 256 |
| `lw-app-icon-v1` | square App / representative image | opaque 1024 / 512 / 192 / 180 / 48 / 32 / 16 |
| `lw-share-illustration-v1` | text-free share illustration | opaque 1200×630 / 600×315 |

The raw generator outputs are preserved in `originals/`: seven are 1254×1254 and the share illustration is 1731×909. The standardized 1024 exports are **derived masters**, not falsely described as the generator's native size. Actual paths, byte counts, hashes and alt text are in `assets/manifest.json`; paths resolve relative to this package root.

## Still blocked / not delivered

The attempted four-job batch returned `moderation_blocked` at the output stage with category `other`; it did not identify which sub-job caused it. No usable output for any of those four appeared. Request ID: `ea16e21f-c111-411d-a2e6-856168730a92`. There was **no retry or attempt to bypass this**.

- `lw-egg-shellsplit-v1` / `shellsplit`: separated-shell state and independent shell pieces.
- `lw-lumi-completion-v1` / `lumi-completion`: dedicated completed-hatch still with shell fragments.
- `lw-effects-nourishment-v1`: independent compositable light/nourishment effect layer.
- `lw-world-base-v1`: empty compositable room/world base.

Full attempted prompts and reference roles are in `provenance/prompts-batch3.json`; details are in `provenance/generation-status.json`. Do not replace these missing entries with empty paths, count them as delivered, or call the whole six-state sequence complete. The existing companion image may be reused by the integration team as an explicitly labeled static fallback, not as proof that the dedicated completion illustration was delivered.

## Alignment and integration

- All transparent normalized exports have a **1024×1024 logical canvas**, nominal center/bottom anchor **(512, 820)**, normalized **(0.5, 0.80078125)**. At 512: **(256, 410)**; at 256: **(128, 205)**.
- Four eggs use the exact same uniform 0.66 scale and (98, 107) placement from 1254 sources. Underlying shell bottom varies by approximately ±2 pixels because generator edits are not pixel-locked. The soft glow extends beyond the shell, as intended.
- Both Lumi poses use identical 0.82 scale and (-2, -25) placement. Body bottom aligns with the same nominal baseline; sprout grows above the egg silhouette. Render full canvas, `object-fit: contain`, not auto-trimmed per state. Use common-size layers with transforms around `50% 80.078125%`.
- Use `@512` for typical UI and `@256` for small cards; `@1024` for large or high-DPI presentation. PNG is losslessly optimized, alpha preserved. No recoloring or alpha cleanup was performed. Very faint generated alpha speckles remain below 16/255 outside the main silhouette; they are documented rather than silently repainted.
- These are **flattened imagegen PNGs**. Each transparent whole asset can be composited, but individual features inside an egg or Lumi are not editable layers. No fake raster-in-SVG “editable source” is supplied. Separate shell/light layers remain missing.
- Welcome/error fallback may reuse the neutral companion image without implying death, punishment, damage or lost progress. Quiet uses the peaceful pose, no flashing effect. Static fallback must remain operable even if images fail to load.
- First Lumi appearance remains gated by confirmed first Bio/goal creation. Art files do not award points or change progress. Skip/replay/cancel must not alter ledger state. Later goal eggs do not automatically repeat first Lumi birth.
- App icon master is a full opaque square, not pre-rounded. Platform/UI may crop it. Circle and rounded previews are separate. 48/32/16 size exports are provided for actual small-size inspection. This is a Web/design output, not a native app-store submission.
- All assets are `product_candidate`, not approved production branding. No unrestricted commercial-use or legal-clearance claim is made. Sources are user-authorized current Life World visual identity plus original tool generation; formal product/visual approval remains Boyi/Jerry's.

## Verification scope

Actual files, dimensions, alpha channels, paths and SHA-256 are verified by local scripts. Previews cover day/Quiet backgrounds and App clipping/small sizes; these are image-level checks only. No child gallery, mobile browser, Safari, animation callback, keyboard interaction or runtime integration is claimed tested in this artwork package.

Originals, exports and technical previews are separated. `provenance/` includes exact prompts, source URLs/blob hashes, conversion steps, and the unresolved generation error. Final archive packaging is transport only; do not commit duplicate ZIPs into the child repository.
