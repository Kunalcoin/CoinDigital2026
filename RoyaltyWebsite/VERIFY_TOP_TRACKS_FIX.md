# Verification: Top Tracks Net Total & Units Total Fix

## ISSUE 1: Left Net Total ≠ Right Total
**Fix:** Backend (Intermediate processor) now uses per-channel net (same logic as channel breakdown), then sums by track. Left panel Net Total = Right panel Total.

## ISSUE 2: Units Total concatenated (47614517581093)
**Fix:** Frontend uses `Number(...) || 0` for units, gross_total, net_total_INR when building the Total row. Units Total is now a numeric sum (e.g. 7657).

---

## Changes Made

### BACKEND (`main/processor.py` – Intermediate processor)
1. **New query** `top_tracks_by_channel_query`: returns `(user, track, channel, units, gross_total)` for **all channels** (including YouTube Official Channel), same filters as Top Tracks.
2. **Per-channel net:**
   - If `channel == "Youtube Official Channel"`: `net = gross_total * (intermediate_user_ytratio/100 - yt_ratios[user]/100)`
   - Else: `net = gross_total * (intermediate_user_ratio/100 - ratios[user]/100)`
3. **Track net:** `groupby track` → sum(units), sum(gross_total), sum(net_total_INR). This becomes the Top Tracks table (left panel).

### FRONTEND (`main/templates/volt_admin.html`)
1. **Track breakdown (right panel):**
   - `channel_units = Number(track_object[channel_ind]['units']) || 0`
   - `channel_revenue = Number(track_object[channel_ind]['gross_total']) || 0`
   - `net_revenue = Number(track_object[channel_ind]['net_total_INR']) || 0`
   - Totals: `total_units += channel_units`, etc.
2. **Channels table totals:** Same `Number(...) || 0` for `gross_total`, `units`, `net_total_INR`.
3. **Console verification:** `console.log('[Track breakdown] ... total_units, net_total')` and `console.log('[Channels total] ...')` so you can confirm types and sums in DevTools.

---

## How to Verify

### 1. Browser (after deploy)
- Open the royalties page (Intermediate view).
- Open DevTools → Console.
- In **Top Tracks** (left), note **Net Total (INR)** for one track (e.g. FACE OFF).
- Click that track to open the channel breakdown (right).
- In the right panel **Total** row check:
  - **Units Sold** = 7657 (or correct sum), not a long concatenated number.
  - **Net Total (INR)** = same as the left panel Net Total for that track (e.g. both 908.36).
- In the console you should see something like:
  - `[Track breakdown] track: FACE OFF | units type: number | total_units: 7657 | total_revenue: 1068.67 | net_total: 908.36`

### 2. Console snippet (run in DevTools on the royalties page)
```javascript
// After opening a track breakdown, run:
var tbody = document.querySelector('#data_table_track_channels tbody');
if (tbody) {
  var rows = tbody.querySelectorAll('tr');
  var sumUnits = 0, sumNet = 0;
  rows.forEach(function(r) {
    var cells = r.querySelectorAll('td');
    if (cells.length >= 4) {
      sumUnits += Number(cells[1].textContent) || 0;
      sumNet   += Number(cells[3].textContent) || 0;
    }
  });
  console.log('Verification: sumUnits=', sumUnits, 'sumNet=', sumNet.toFixed(2), 'typeof sumUnits=', typeof sumUnits);
}
```

### 3. Expected result
- Left **Net Total (INR)** for a track = Right **Total** Net Total (INR) for that track.
- Right **Total** Units = correct sum (e.g. 7657), not a concatenated string.
- Console shows `units type: number` and numeric totals.
