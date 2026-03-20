# Deploy "Deliver to Apple Music only" button to live

The **Deliver to Apple Music only** button appears on **Preview & Distribute** only after the updated code is on the server. Hard refresh alone will not show it if the server is still serving the old template.

## Files that must be on the server

- `releases/templates/volt_preview_distribute_info.html` — contains the Apple Music block and `ddex_deliver_apple_music()` JS
- `releases/views.py` — contains `ddex_deliver_apple_music` view
- `releases/urls.py` — contains path `ddex-deliver-apple-music/`
- `releases/merlin_bridge_delivery.py` — Apple delivery logic
- `releases/apple_itunes_importer.py` — Apple XML builder

## Deploy steps (royalties.coindigital.in)

1. **From your machine** (in the project that has these changes):
   ```bash
   cd "RoyaltyWebsite"   # or your RoyaltyWebsite folder
   ./deploy_to_server.sh
   ```
   Or if you use rsync manually, sync the `RoyaltyWebsite` folder to the server (same path as your current deploy).

2. **On the server**, restart Django so it loads the new code and templates:
   ```bash
   # If using Docker (typical):
   cd /home/ubuntu/coin-digital-app   # or your DEPLOY_DOCKER_PATH
   docker-compose restart django_gunicorn

   # If using systemd:
   sudo systemctl restart gunicorn
   ```

3. **In the browser**: open  
   `https://royalties.coindigital.in/releases/preview_distribute_info/36848`  
   and hard refresh (Ctrl+Shift+R or Cmd+Shift+R). You should see:
   - **DDEX delivery for Audiomack, Gaana & TikTok**
   - **Deliver to Apple Music only** (new, purple-tinted block)

4. **Who sees it**: only **admin** (or staff). The block is inside `{% if can_use_ddex_delivery %}`. If you are admin and still don’t see it after deploy + restart, check that the server is actually using the synced files (e.g. `grep -l "Deliver to Apple Music only" releases/templates/volt_preview_distribute_info.html` on the server).
