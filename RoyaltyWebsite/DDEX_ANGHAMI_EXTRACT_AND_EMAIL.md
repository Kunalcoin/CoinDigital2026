# Anghami – PDF Extract (ERN 4.3) + Email Draft

**Source:** Anghami - Guidelines for Labels and Content Distributors (PDF)

We use **ERN 4.3 only**; the PDF specifies **ERN 3.8.2**. Below: what we can reuse for 4.3, what’s missing, and a ready-to-send email to request 4.3 specs.

---

## 1. Useful information extracted from PDF (for ERN 4.3)

| Item | From PDF | Use for ERN 4.3 |
|------|----------|------------------|
| **Contact – operations** | contentoperations@anghami.com | Primary contact for delivery/DDEX |
| **Contact – metadata/updates** | contentupdate@anghami.com | Metadata and content update requests |
| **Delivery method** | SFTP | Keep; confirm for 4.3 if needed |
| **SFTP auth** | Username/password, Public key | Keep |
| **Drop-off path** | /content | Keep |
| **Resources path** | /resources | Keep |
| **Directory structure** | /content/batchid/ICPN/ICPN.xml or /content/timestamp/ICPN/… | Keep; confirm for 4.3 |
| **Commercial models** | AdvertisementSupportedModel, SubscriptionModel | Same in 4.3 |
| **Use type** | Stream | Map to 4.3 UseType (e.g. OnDemandStream / NonInteractiveStream) once confirmed |
| **Audio** | FLAC, MP3 320, or WAV | Keep |
| **Image** | JPG/JPEG, 1000×1000 – 3072×3072 | Keep |
| **Video** | MP4, MOV, HD 1920×1080 | Keep |
| **Arabic content** | Composer, Lyricist, Producer; Genre/Subgenre; Arabic + Latin titles | Metadata rules for 4.3 |
| **International content** | Specific subgenres; Latin titles for non-Latin (e.g. J-Pop, K-Pop) | Metadata rules for 4.3 |

**Not in PDF (needed for ERN 4.3 build):**

- Anghami **DDEX Party ID** (DPID) for MessageRecipient
- Confirmation that they accept **ERN 4.3** (and schema/namespace if different)
- **Update** and **Takedown** message type (NewReleaseMessage with UpdateIndicator vs PurgeReleaseMessage, etc.)
- Exact **UseType** values for 4.3 (Stream → OnDemandStream / NonInteractiveStream?)
- Any 4.3-specific required elements or naming (e.g. UpdateIndicator, ReleaseProfileVersionId)

---

## 2. Email to Anghami – request ERN 4.3 requirements

**To:** contentoperations@anghami.com  
**CC (optional):** contentupdate@anghami.com (if you want metadata/update requests aligned)  
**Subject:** DDEX ERN 4.3 delivery requirements – Coin Digital (Merlin member)

---

**Body:**

Dear Anghami Content Operations,

We are **Coin Digital Private Limited**, a Merlin member (Merlin ID: 202000047). Our content is currently distributed to Anghami via our distributor Sonosuite. We are now moving to deliver our content via **in-house DDEX** and intend to follow your “Guidelines for Labels and Content Distributors” for content and delivery rules.

To achieve the same (in-house DDEX delivery to Anghami), we need the following information from your side. We deliver only **DDEX ERN 4.3** (we do not use ERN 3.8.2). Your guidelines state a preferred ERN version of 3.8.2, so we request your official specifications for **ERN 4.3**. Please provide or confirm the following:

1. **ERN version**  
   - Do you accept **ERN 4.3** for ingestion (and if yes, is there a specific schema/namespace we should use)?

2. **Message recipient**  
   - Your **DDEX Party ID (DPID)** for the MessageRecipient element when sending to Anghami.  
   - The exact **Party Name** you want us to use (e.g. “Anghami”).

3. **Delivery (SFTP)**  
   - Confirm that delivery remains **SFTP** for ERN 4.3.  
   - Confirm directory structure: e.g. `/content/<batchid_or_timestamp>/<ICPN>/<ICPN>.xml` and resources under `/resources`.  
   - Any 4.3-specific file naming or folder rules.

4. **Deal terms (ERN 4.3)**  
   - CommercialModelType: please confirm we should use **AdvertisementSupportedModel** and **SubscriptionModel**.  
   - UseType: your guidelines mention “Stream”; for ERN 4.3 we use values such as **OnDemandStream** and **NonInteractiveStream**. Which UseType values do you require or accept for 4.3?

5. **Update and takedown**  
   - For **metadata/territory updates**: do you accept **NewReleaseMessage** with an update indicator (e.g. UpdateMessage), or another message type?  
   - For **takedowns**: do you accept **PurgeReleaseMessage** in ERN 4.3, or only **NewReleaseMessage** with a validity end date (or another format)?  
   - Any required elements (e.g. reason codes, dates) for updates and takedowns.

6. **Optional**  
   - A sample ERN 4.3 NewReleaseMessage (or a link to schema/docs) so we can align our generator with your validation.

We will use your Guidelines PDF for content rules (audio/image/video specs, Arabic and international metadata, disallowed content). The above technical details for ERN 4.3 are what we need from your side to build our in-house DDEX feed correctly.

Thank you for your help.

Best regards,  
[Your Name]  
[Your Title]  
Coin Digital Private Limited (Merlin ID: 202000047)  
[Your Email]

---

## 3. Next steps

- Send the email above (and add your company name, contact name, title, email).
- When Anghami replies, share their response (or the relevant parts) and we can:
  - Add Anghami to the DDEX config and DSP registry for ERN 4.3.
  - Implement build_ddex for `--store anghami` and any update/takedown flows they specify.
  - Update this doc with their 4.3 requirements.

---

**Reusable rule:** For any DSP PDF you share, we will (1) extract only what’s useful for building DDEX ERN 4.3, and (2) if information is missing (e.g. they only support an older ERN), draft an email to the DSP with their contact and a short requirement list. Once they reply, you can share that and we’ll implement.
