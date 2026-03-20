# Draft Email to Merlin Bridge Support

**Subject:** Apple Music delivery – file extension (.itmsp vs .zip) and metadata.xml location; need clarification

---

Hi Merlin Bridge team,

We deliver Apple Music packages to your Bridge SFTP (path: **apple/regular/**) and are getting two recurring validation messages. We’d like to align with your requirements and need your confirmation on the following.

**1. File extension (.itmsp vs .zip)**  
Your validation asks us to “add .itmsp as the file extension.”  
We do upload a package with the **.itmsp** extension (e.g. **apple/regular/8905285306132.itmsp**). We also upload the same package as **.zip** (e.g. **apple/regular/8905285306132.zip**) because when we upload **only** .itmsp, the delivery does not appear in the Bridge dashboard at all; it only appears when the .zip is present.  
**Question:** Can you confirm that Bridge is set up to ingest and list packages that are **only** .itmsp in apple/regular/? If yes, we will stop uploading .zip. If the dashboard only triggers on .zip, can you advise how we should deliver so that (a) the package appears in Bridge and (b) it passes the “use .itmsp extension” check?

**2. XML file name and location (metadata.xml)**  
Your validation asks us to “ensure the XML file is named metadata.xml.”  
We name the XML file exactly **metadata.xml**. We have tried two package layouts:

- **Set A – metadata.xml at zip root**  
  Unzipped contents: **metadata.xml**, **{upc}.jpg**, **{upc}_01_001.wav** (and other tracks) all at the top level of the package.

- **Set B – metadata.xml inside a folder**  
  Unzipped contents: a single folder **{upc}/** containing **metadata.xml**, **{upc}.jpg**, **{upc}_01_001.wav**, etc. (per Apple’s “package is a directory” wording).

In both cases the XML file name is **metadata.xml** (no path prefix in the name).  
**Question:** Which of these does Bridge expect—metadata.xml at the **root** of the package (Set A), or metadata.xml **inside** a folder named with the UPC (Set B)? If you have a different layout (e.g. a specific folder name or path), please describe it so we can match it.

**3. Sample package on SFTP**  
For your reference, we have delivered the following to **apple/regular/** for UPC **8905285306132**:

| File on SFTP | Description |
|--------------|-------------|
| **apple/regular/8905285306132.itmsp** | Package with .itmsp extension (zip format; currently contains Set A layout). |
| **apple/regular/8905285306132.zip** | Same content as above, .zip extension (uploaded so the delivery appears in the Bridge UI). |

You can log in to our Bridge SFTP (same credentials as our Content Delivery setup) and inspect these files. The **metadata.xml** inside each package contains a valid **&lt;upc&gt;** element with the 13-digit UPC.

**4. What we need from you**  
To avoid further “incorrect file extension” and “incorrect file name for the XML” errors, please confirm:

1. The **exact file extension(s)** we should upload (only .itmsp, or something else) so that the package both **appears** in the Bridge dashboard and **passes** validation.  
2. The **exact location** of **metadata.xml** inside the package (zip root vs. inside a folder, and if so, which folder name).  
3. If possible, a **short specification or example** of the expected package structure (e.g. “.itmsp file that unzips to a single folder {UPC}/ containing metadata.xml and assets”) so we can match it exactly.

We’re happy to switch to a single, correct format and re-deliver once we have this guidance.

Thank you,  
[Your name]  
[Label name – e.g. Coin Digital]  
[Contact email]
