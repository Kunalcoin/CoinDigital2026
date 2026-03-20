# Draft Email — To Spotify Team (DDEX Feed Setup)

**Subject:** DDEX feed setup — information needed to complete delivery (Coin Digital)

---

**Dear Spotify team,**

We are setting up our DDEX feed to deliver release metadata (Insert, Update, and Takedown) to Spotify and would like to complete the technical setup on our side. We are generating **DDEX ERN 4.3** messages for Singles, EPs, and Albums and currently use **Spotify’s DDEX Party ID** `PADPIDA2011072101T` in our MessageRecipient.

To finalise configuration and start delivering feeds, we need the following from you:

1. **Confirmation of Party ID**  
   Please confirm that `PADPIDA2011072101T` is the correct DDEX Party ID for Spotify to receive feeds from labels/distributors. If a different Party ID or Party Name should be used, please share the correct details.

2. **Delivery method**  
   How should we send our DDEX packages to Spotify? (e.g. **SFTP**, FTP, API, or upload via a partner portal.) If you use SFTP/FTP, do you provide a dedicated drop for each partner?

3. **Delivery credentials and access**  
   For the chosen method, we need:
   - Host and port (for SFTP/FTP)
   - Username and authentication (password or SSH public key)
   - Any whitelisting requirements (e.g. our server’s **public IP** and/or **SSH public key** for SFTP)

4. **Folder structure and file naming**  
   Please share the required folder structure and file naming convention (e.g. `batch_id/upc/upc.xml` and naming for XML and asset files). We will align our output to your specifications.

5. **DDEX version and schema**  
   We currently generate **ERN 4.3**. Please confirm that you accept 4.3, or tell us the required ERN version and, if applicable, the XSD or schema URL for validation.

6. **Test and go-live process**  
   What are the steps for (a) submitting a **test** DDEX package, (b) receiving validation or feedback, and (c) moving to **production** (e.g. separate test vs production credentials or endpoints)?

7. **Technical requirements**  
   Are there any mandatory elements, validation rules, or format requirements (e.g. specific use types, territory codes, or file formats for audio/artwork) we must follow?

8. **Contact for feed onboarding and support**  
   Who should we contact for feed onboarding, delivery issues, and ongoing feed support?

We have our feed generation and packaging ready and will complete configuration as soon as we have the above details. Thank you for your help.

Best regards,  
[Your name]  
[Your title]  
Coin Digital  
[Contact email]  
[Optional: phone]
