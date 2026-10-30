# LifeWorld · Three Kingdoms demo art · v1.0.0

## Delivered

Five actual imagegen portraits — 曹操、劉備、諸葛亮、孫權、周瑜 — and one peaceful riverside council cover. These are **demo assets, not production-approved assets**. All six originals were generated with OpenAI's built-in `image_gen.imagegen` tool on 2026-10-28. Model and tool version were not exposed; no invented model/version claims are made.

| Logical asset ID | Subject | Master | Display / preview |
| --- | --- | --- | --- |
| portrait-three-kingdoms-caocao | 曹操 | 1024 × 1024 PNG | 256 square + 256 transparent circle |
| portrait-three-kingdoms-liubei | 劉備 | 1024 × 1024 PNG | 256 square + 256 transparent circle |
| portrait-three-kingdoms-zhugeliang | 諸葛亮 | 1024 × 1024 PNG | 256 square + 256 transparent circle |
| portrait-three-kingdoms-sunquan | 孫權 | 1024 × 1024 PNG | 256 square + 256 transparent circle |
| portrait-three-kingdoms-zhouyu | 周瑜 | 1024 × 1024 PNG | 256 square + 256 transparent circle |
| cover-three-kingdoms | 三國策略 | 1600 × 900 PNG | 800 × 450 PNG |

`assets/manifest.json` is the integration authority for IDs, relative paths, dimensions, SHA-256, byte sizes, alt text, source/tool/version/status and usage restrictions. All paths resolve relative to this package root after the six natural archive parts are extracted into the same directory.

## Layout

- `assets/originals/`: unmodified native generator outputs (portraits 1254 × 1254; cover 1672 × 941), byte-identical to the source files.
- `assets/masters/`: exact required dimensions, technical resampling only.
- `assets/display/`: required smaller square portraits and cover.
- `assets/previews/`: transparent, antialiased 256 × 256 circular portrait crops.
- `qa/`: contact sheet, technical verification and visual inspection notes. Contact-sheet labels are review-only; runtime images contain no baked-in UI text.
- `provenance/`: exact prompts, generation records, export script/records and pinned repository specification snapshots.

## Sources and limitations

1. **Historical artistic interpretations, not verified authentic likenesses.** Facial features, clothes, headwear, setting and composition are interpretive. These images are not source evidence for historical claims.
2. The five-person council is a **fictional illustrative composition**, not an assertion that these people met together at this location or at a documented event. Historical and literary claims belong in the demo's separately sourced persona/scenario data.
3. Source requirements: `asixtw/life-world`, commit `1c9d502f32688bcc3c73e4b99a2cc3724c179047`, `docs/team/ART_DELIVERY_SPEC.md` and `PROMPT_SIMULATION_001.md`. Exact fetched text and blob SHAs are preserved in `provenance/`.
4. User authorization: LifeWorld full-kit art, with fifteen-person list A confirmed 2026-10-28. `usage_scope=demo`; permitted intended channels are test / POC / closed-beta demo. Formal/production retention remains unapproved and subject to owner review. No unrestricted commercial clearance is claimed.
5. All artwork is newly generated from text prompts. No external photo, film image, actor likeness reference, previously blocked Lumi art, or《空山問獅會》material was used.
6. The tool returned flattened raster PNG files. **No editable painting layers, PSD, genuine vector source, or pixel-independent original exists.** Python/Pillow was used only for expressly authorized technical resizing, a 16:9 cover crop, circular alpha previews, review-sheet assembly and validation; not for illustration synthesis or retouching.
7. Six logical assets / 23 PNG files. All native outputs are preserved; no output was discarded or regenerated. No generation failures occurred for these six requests.

## Integration

Keep all assets in the `three-kingdoms` demo namespace. Suggested destination is `collaboration/ui-kit/assets/` with paths adjusted consistently; this delivery does not modify any repository, desktop files, routes, production database or live UI. Use the supplied alt text or a context-appropriate equivalent, and render names/labels as accessible UI text outside the raster. The provided persona keys are `caocao`, `liubei`, `zhugeliang`, `sunquan`, `zhouyu`; map them explicitly to the consuming content schema rather than guessing final persona IDs.

Review `qa/contact-sheet.png` before acceptance. Technical checks cover dimensions, decodability, SHA-256, path resolution, source preservation and circle alpha. App integration, mobile/desktop browser rendering, Safari, physical devices and rights clearance are not tested by this image-only package. Boyi/Jerry review is still required.

## Reproduce technical exports

`python provenance/export_assets.py` uses the source paths recorded in `provenance/generation-records.json`, which refer to this execution workspace. For a relocated package, point those records at the preserved native files in `assets/originals/` first. The generation prompts are preserved for provenance, not a promise of deterministic regeneration.

Archive parts are bounded below 8,000,000 bytes each; `PACKAGE_INDEX.json` lists contents, sizes and checksums. This is an art handoff only, not the complete playable simulation or evidence of a production launch.
