# Apple Music (Merlin Bridge) — What labels need to provide

This is a **client-facing summary** of metadata Coin Digital sends to **Merlin Bridge** for Apple Music (iTunes Importer `music5.3` XML). Technical operators should also read **`MERLIN_BRIDGE_APPLE_MUSIC.md`**.

---

## 1. Release-level (Django admin → Release)

| Topic | What to set | Notes |
|--------|-------------|--------|
| **Street / release date** | **Digital release date** (or **Original release date** if digital empty) | Drives `sales_start_date` / `stream_start_date` and what Merlin shows as release date. |
| **Pre-order** | **Apple Music pre-order sales start date** | Optional. Must be **before** street date. Emits `preorder_sales_start_date` on the **album** product only (not each track). **Cannot** be used together with **Retail / download only** — Apple returns ITMS-4020. |
| **Streaming vs download** | **Apple Music commercial model** | Default: both. Use **Streaming only** or **Retail / download only** only for Merlin checklist tests unless you intend that configuration live. Pre-order + instant grat need **not** retail-only. |

---

## 2. Track-level (Django admin → each Track on the release)

| Topic | What to set | Notes |
|--------|-------------|--------|
| **Instant grat (pre-order)** | **Apple Music instant gratification (pre-order)** checkbox | When a **pre-order date** is set, we send **`<preorder_type>` on each track** in `metadata.xml`: `instant-gratification` for checked tracks, `standard` for others (track-level — not inside `<product>`). **At most half** of the tracks may be IG. |

---

## 3. Delivery

- After metadata is correct and the release is **approved**, delivery uploads **`{UPC}.itmsp.zip`** to Merlin Bridge SFTP (e.g. `apple/regular/`).
- Operators run: `python3 manage.py deliver_apple_music --upc YOUR_UPC` (or use **Deliver to Apple Music only** in the admin UI where enabled).

---

## 4. What we validate automatically

Before upload, the app blocks delivery if:

- Pre-order date is set but **not** before street date.
- **Too many** tracks are marked instant grat (**more than 50%** of tracks on the release).
- *(Warning only, upload not blocked:)* pre-order is set but **no** track is marked IG — some Apple flows expect at least one IG track; check the Apple Music Spec / Merlin checklist.

---

## 5. Related docs (internal)

- **`MERLIN_BRIDGE_APPLE_MUSIC.md`** — SSH/SFTP env vars, preorder, instant grat, streaming/retail checklist.
- **`APPLE_MUSIC_VALIDATION_PLAN.md`** — Merlin Bridge checklist mapping.
