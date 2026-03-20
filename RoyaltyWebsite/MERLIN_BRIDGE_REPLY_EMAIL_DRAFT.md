# Draft Reply Email to Merlin Bridge

**Subject:** Apple Music Bridge packages – final format `[UPC].itmsp.zip` + metadata.xml + Sonosuite (Udio)

Hi Merlin Bridge team,

Thanks for the detailed breakdown — super helpful.

## Sonosuite / Udio account
Regarding the Sonosuite request: please confirm whether you want me to proceed with setting up the Udio account on your behalf (expected/approved), or if you need me to take a different action.  
([Reply with YES/NO once you confirm.])

## Apple Music delivery – confirmation of final package format
For Apple Music, we understand now that all packages should be:
- Named: **`[UPC].itmsp`**, then **compressed** so the final file delivered to Bridge SFTP is **`[UPC].itmsp.zip`**
- With XML: **`metadata.xml`** inside the package folder: **`[UPC].itmsp/metadata.xml`**
- And the rest of the assets in that same **`[UPC].itmsp/`** folder.

### Packages on our Bridge SFTP for review (UPC 8905285306132)
We uploaded/are re-uploading the following to **`apple/regular/`**:

| File on SFTP | What it represents |
|---|---|
| `apple/regular/8905285306132.itmsp` | Earlier attempt (we were experimenting with layout) |
| `apple/regular/8905285306132.zip` | Earlier attempt (Bridge UI listing trigger) |
| `apple/regular/8905285306132.itmsp.zip` | **New attempt (final state)** matching your instructions |

If you prefer, we can also provide checksum/md5 of each file after the upload finishes.

## Next step
We will re-deliver using the exact final format **`[UPC].itmsp.zip`** and stop sending non-final filenames once you confirm ingestion.

Thanks again,  
Kunal

