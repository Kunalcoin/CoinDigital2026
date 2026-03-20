# Reply to Sonosuite – Request details for bulk CSV ingestion

**Subject:** Re: API integration – Bulk CSV ingestion details

---

Hi,

Thank you for clarifying that the Distribution API does not provide endpoints for content ingestion, and that we need to ingest releases first using one of the supported methods (bulk CSV, DDEX, or Platform UI) before delivery.

We have updated our flow accordingly: when a user submits a release for approval, we set it to pending and our admin will ingest the release using your platform, then trigger delivery through your Distribution API from our side.

We would like to use **bulk upload via CSV** for ingestion where possible. Could you please share additional details on this option:

1. **How do we perform the bulk CSV upload?**  
   Is it done only through the Platform UI (e.g. a specific page where we upload a CSV file), or is there a programmatic way to submit the CSV (e.g. a separate ingestion API, SFTP, or similar) that we could integrate with our system?

2. **If it is via the Platform UI:**  
   What is the exact URL or path where we upload the CSV (e.g. a dedicated “Bulk upload” or “Import” section)? Any step-by-step instructions would be helpful.

3. **CSV format:**  
   Do you have a required template or specification (column names, encoding, delimiter) for the bulk CSV so we can ensure our export matches it?

4. **Timing:**  
   After we upload the CSV, how long does it typically take before the release is available for delivery via the Distribution API? Is there a status we can check, or should we simply trigger delivery after a short delay?

Once we have these details, we can align our process (and any automation) with your bulk CSV workflow.

Thank you again for your help.

Best regards,  
[Your name]
