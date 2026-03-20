# JioSaavn DDEX Delivery Requirements

We deliver to JioSaavn using **DDEX ERN 4.3** (our standard version). Their published list includes 3.x and 4.1.1; we use 4.3 and they have confirmed standard 4.3.

---

## 1. DDEX / Recipient

| Item | Value |
|------|--------|
| **DDEX Party ID** | `PA-DPIDA-2012073007-R` (in their docs); in XML we use `PADPIDA2012073007R` (no hyphens, standard DDEX format) |
| **DDEX Party Name** | **Saavn** |
| **Version** | ERN 4.3 (our standard) |

---

## 2. Assets

| Asset | Requirement |
|-------|-------------|
| **Audio** | 320 kbps MP3, WAV, or FLAC |
| **Album artwork** | JPEG, **min 1400×1400** preferred |

---

## 3. SFTP Delivery

- **Method:** Content deliveries to an **SFTP drop**.
- **Whitelisting:** Share your **SSH public key** and **public IP** with JioSaavn for whitelisting.
- **Folder structure:**
  ```
  <batch_id>/<upc>/<upc>.xml
  ```
  Example: `batch_20260128/8905285127614/8905285127614.xml` (and assets under the same `<upc>` folder as needed).

- Request a test SFTP drop from JioSaavn when you are ready to deliver a test package.

---

## 4. XML Requirements

### 4.1 Language of performance

- Use the **`<LanguageOfPerformance>`** tag to specify the language of the content.
- JioSaavn classifies albums by language; this is especially important for **non-English** content.
- Our builder already populates `LanguageOfPerformance` from track/release language (ISO 639-2 via `ddex_language_iso`).

### 4.2 MessageControlType (testing vs production)

- **During testing:** Use **`<MessageControlType>TestMessage</MessageControlType>`** in the `<MessageHeader>`.
- **After successful testing (production):** Use **`<MessageControlType>LiveMessage</MessageControlType>`**.

To generate test vs live XML:

- **Test package (for JioSaavn testing):**
  ```bash
  python manage.py build_ddex <release_id> --store jiosaavn --test
  ```
- **Production (go-live):**
  ```bash
  python manage.py build_ddex <release_id> --store jiosaavn
  ```
  (default is `LiveMessage` when `--test` is not used)

---

## 5. Summary Checklist

- [ ] Provide **SSH public key** and **server public IP** to JioSaavn for whitelisting.
- [ ] Request **SFTP drop** when ready for test delivery.
- [ ] Use folder structure: **`<batch_id>/<upc>/<upc>.xml`** (and assets under `<upc>/`).
- [ ] Audio: **320 kbps MP3**, WAV, or FLAC.
- [ ] Artwork: **JPEG, min 1400×1400** preferred.
- [ ] **`<LanguageOfPerformance>`** populated (already in our 4.3 builder).
- [ ] **Test phase:** `MessageControlType` = **TestMessage** (use `--test` flag).
- [ ] **Production:** `MessageControlType` = **LiveMessage** (default).

---

## 6. DSP Registry

JioSaavn is in the DSP registry as:

- **code:** `jiosaavn`
- **party_id:** `PADPIDA2012073007R`
- **party_name:** `Saavn`
- **deal_profile:** `streaming`
- **is_active:** `true`

Build for JioSaavn only: `python manage.py build_ddex <release_id> --store jiosaavn [--test]`  
Build for all active DSPs (including JioSaavn): `python manage.py build_ddex_all <release_id>`
