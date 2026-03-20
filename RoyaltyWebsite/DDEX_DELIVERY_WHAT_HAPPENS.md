# What happens when you click "DDEX delivery for Audiomack"

## What the button does (current behaviour)

1. **XML**  
   A DDEX ERN 4.3 XML file is built and:
   - **If your S3 is configured** (`AWS_STORAGE_BUCKET_NAME`): uploaded to your bucket at  
     `ddex/audiomack/<date>/<upc>.xml`  
     Example: `ddex/audiomack/20260218/8905285301465.xml`
   - **If no bucket**: saved on the server under  
     `RoyaltyWebsite/out_audiomack/<upc>.xml`

2. **Audio and poster (when XML goes to your S3)**  
   After uploading the XML, the system **copies** your existing assets into the same delivery folder:
   - **Cover art** from `release.cover_art_url` → `ddex/audiomack/<date>/resources/coverart.jpg`
   - **Track 1 audio** from `track.audio_track_url` → `ddex/audiomack/<date>/resources/1_1.flac`
   - **Track 2 audio** → `resources/1_2.flac`, and so on.

So when you use **your S3**, the release **is** fully sent as one package: **XML + poster + audio** in one folder in your bucket. The XML and the `resources/` subfolder are in the same `ddex/audiomack/<date>/` prefix.

## Is the release fully sent?

- **XML:** Yes – built and uploaded (or saved locally if no bucket).
- **Audio:** Yes – when XML is uploaded to your S3, each track’s audio is **copied** from its current S3 path into `resources/1_1.flac`, etc.
- **Poster:** Yes – when XML is uploaded to your S3, the release’s cover art is **copied** into `resources/coverart.jpg`.

If the copy step fails for a file (e.g. wrong URL format or missing object), the XML is still uploaded and the success message will mention how many files were copied and any warnings.

## First time you clicked (before this update)

Previously, **only the XML** was uploaded; audio and poster were **not** copied into the delivery folder. So for that run you had:

- **XML:** Yes, in your S3 at `ddex/audiomack/<date>/<upc>.xml`
- **Audio / poster:** Not in that folder; they stayed in their original S3 paths.

From the next click onward, the full package (XML + resources) will be created. For an already-delivered release you can click again to create a new delivery folder that includes the copied resources.
