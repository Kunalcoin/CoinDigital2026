# Email draft: To Sonosuite team

**Subject:** API integration – metadata CSV upload endpoint & delivery flow (coin.sonosuite.com)

---

Hi,

We are integrating our royalty/release management system with your platform (coin.sonosuite.com) so that our users can distribute releases to stores via your API.

We have implemented the flow on our side (upload of release metadata CSV when the user clicks “Distribute”, then a separate delivery step when an admin approves). We are currently blocked because our request to **upload the metadata CSV** is returning a “Not Found” response, so we need the correct API details from your side.

Could you please provide the following:

**1. Metadata CSV upload (priority)**  
- The **exact URL** we should use to upload a release metadata CSV file (e.g. full URL or the path to use with base `https://coin.sonosuite.com`).  
- The **expected request format** (e.g. POST with multipart/form-data, and the exact form field name for the file – we are currently using `"file"`).  
- Confirmation that we should use the same **Bearer token** (from your login API) in the `Authorization` header for this upload endpoint.

**2. Login API (for confirmation)**  
- Is the login endpoint: `POST https://coin.sonosuite.com/distribution/api/login` with body `{"username": "<email>", "password": "<password>"}` and response `{"token": "<string>"}`? If not, please share the correct URL, request body, and response format.

**3. Delivery API (for confirmation)**  
- For sending a release to stores, should we: (a) call `GET {base}/distribution/api/dsp` to get the list of DSPs, then (b) for each DSP call `POST {base}/distribution/api/delivery` with `{"dsp_code": "...", "upcs": ["<UPC>"], "deliver_taken_down": false}`? If the endpoints or payload differ, please share the correct specification.

**4. CSV format**  
- Do you have a required template or list of columns for the metadata CSV? We can send a sample export from our system so you can confirm it matches what your upload API expects.

**5. Flow**  
- Can you confirm that the intended flow is: (1) upload metadata CSV to register the release in your catalog, then (2) a separate delivery API call (using the release UPC) to send that release to stores? Our implementation follows this two-step process.

We use **https://coin.sonosuite.com** as the base URL and the same admin credentials for login, upload, and delivery. Once we have the correct upload URL and format, we will be able to complete the integration.

Thank you for your help.

Best regards,  
[Your name]  
[Your role / company]
