# DSP Registry — DDEX Party IDs

**File:** `ddex_dsps.json` (this folder)

This is the single source of truth for all DSPs we deliver DDEX (ERN 4.3) to. You **do not** need to share or configure all DSP deals at once. Update the registry **as you receive** Party IDs from each DSP.

---

## When a DSP sends their DDEX Party ID

1. Open **`releases/data/ddex_dsps.json`**.
2. Find the DSP by **`code`** (e.g. `apple_music`, `deezer`).
3. Replace **`party_id`** with the value they provided (usually like `PADPIDA2011072101T`; use the format they give, without hyphens if they send e.g. `PA-DPIDA-2011072101-T` → `PADPIDA2011072101T` unless they specify otherwise).
4. Optionally set **`is_active`** to **`true`** when you are ready to generate and deliver feeds to that DSP.
5. Save the file. No code change or deploy needed — the app reads the JSON at runtime. If the app caches the file, restart the app or call `releases.ddex_dsp_registry.reload_registry()` to pick up changes.

**Example:** Apple sends Party ID `PADPIDA2012010101A` and Party Name "Apple Inc.":

- Update that DSP’s `party_id` to `PADPIDA2012010101A` and `party_name` to `Apple Inc.` if different.
- Set `is_active` to `true` when you’re ready to build packages for Apple.

---

## Updating one DSP at a time

You can update **one DSP at a time**. There is no need to wait until you have all IDs or to “share all DSP deals at once.” Add or edit a single entry, save, and that DSP is ready (once `is_active` is true).

---

## Fields per DSP

| Field           | Description |
|----------------|-------------|
| **code**       | Unique slug (lowercase, no spaces). Used in CLI: `--store <code>`. |
| **party_id**   | DDEX Party ID from the DSP. Use placeholder (e.g. `PADPIDA_PLACEHOLDER_APPLE`) until received. |
| **party_name** | Official name for the DDEX MessageRecipient (e.g. "Spotify", "Saavn"). |
| **deal_profile** | `streaming` (most DSPs), `ugc` (TikTok), or `download` (download-only). Determines deal terms in the XML. See DEAL_PROFILES.md. |
| **is_active**  | `true` = include in “build for all DSPs” and allow `--store <code>`. `false` = skip until you’re ready. |

---

## Placeholders

Entries with **`party_id`** starting with **`PADPIDA_PLACEHOLDER_`** are waiting for the real Party ID from the DSP. Replace with the actual ID when they provide it.

---

## Adding a new DSP

Append a new object to the **`dsps`** array:

```json
{
  "code": "new_dsp",
  "party_id": "PADPIDA_PLACEHOLDER_NEWDSP",
  "party_name": "New DSP Name",
  "deal_profile": "streaming",
  "is_active": false
}
```

Use **`deal_profile`**: `streaming` (default), `ugc` (TikTok UGC/Library), or `download` (download-only). No code change required. See RoyaltyWebsite/DEAL_PROFILES.md.

---

## YouTube Music

The **`youtube_music`** DSP uses the streaming deal profile. Delivery is via **SFTP or Aspera** (set up by your YouTube partner representative). For full setup (Party ID, test batches, BatchComplete, delivery), see **RoyaltyWebsite/YOUTUBE_DDEX.md**.
