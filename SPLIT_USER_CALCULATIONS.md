# Split User (Split Recipient) Calculation Logic

This document explains the logic and code for all calculations related to **Split Users** (users with role `split_recipient`). Split recipients are users who receive a percentage of royalties from tracks they don't own—they are added as recipients in the `SplitReleaseRoyalty` table by track owners.

---

## Key Concepts

- **Split Recipient**: A user who receives a share of royalties from tracks owned by others, based on `recipient_percentage` in `SplitReleaseRoyalty`.
- **Owner's Ratio**: Split recipients use the **track owner's** ratio (from `main_ratio`), not their own—they typically have no ratio record.
- **Formula**: `Net_Royalty = Gross × Owner_Ratio × Recipient_Percentage / 100`

---

## 1. Due Balance Calculation

**Location:** `main/processor.py` → `NormalProcessor.refresh_due_balance_for_split_recipient()` (lines 1973–2006)

**Called by:** `populate_due_amounts.py` → `update_split_recipient_users()`

### Logic (SQL CTEs)

1. **recipient_royalty_totals**  
   - Sum `releases_royalties.net_total_INR` per ISRC and channel type (stores vs youtube).  
   - Only tracks where `sr.recipient_email = username` and `m.user != username` (user is recipient, not owner).

2. **recipient_split_percentages**  
   - For each such track, get `recipient_percentage` and `owner_email` from `SplitReleaseRoyalty`.

3. **owner_ratios**  
   - Get active stores/youtube ratios for all owners from `main_ratio`.

4. **recipient_royalties_with_ratios**  
   - Apply split: `net_total_INR × recipient_percentage / 100` → `split_amount`.  
   - Join with owner ratios.

5. **net_totals**  
   - Apply owner’s ratio per channel type:
     - Stores: `split_amount × (owner_stores_ratio / 100)`
     - YouTube: `split_amount × (owner_youtube_ratio / 100)`

6. **aggregated_payments**  
   - Sum `amount_paid` and `tds` from `main_payment` for the user.

7. **Final Due Amount**  
   - `amount_due = net_total - amount_paid - tds`

### Formula

```
Net_Total = Σ (Gross × Recipient_Percentage / 100 × Owner_Ratio / 100)
Due_Balance = Net_Total - Payments - TDS
```

### Code excerpt

```python
# Lines 2039-2048
CASE 
    WHEN channel_type = 'stores' THEN split_amount * (owner_stores_ratio / 100)
    ELSE split_amount * (owner_youtube_ratio / 100)
END
```

---

## 2. Net Royalties – Channel Wise (Split User)

**Location:** `main/processor.py` → `NormalProcessor.get_royalty_stats()` (lines 1507–1532)

**Entry point:** `Processor.get_royalty_stats()` routes `split_recipient` to `normal.get_royalty_stats()`.

### SQL query (`top_channels_query`)

```sql
SELECT 
    r.channel,
    sum(r.units) as units,
    sum(r.net_total_INR) as gross_total,
    sum(r.net_total_INR * COALESCE(sr.recipient_percentage, 100) / 100) as net_total
FROM releases_royalties r 
LEFT JOIN releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
LEFT JOIN releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
LEFT JOIN releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
    AND t.release_id = sr.release_id_id 
    AND LOWER(sr.recipient_email) = '{username}'
WHERE 
    (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}')
    AND r.channel != 'Youtube Official Channel'
    {filter}
GROUP BY r.channel
```

### Logic

- For split recipients: `LOWER(sr.recipient_email) = username` gives recipient rows.
- `COALESCE(sr.recipient_percentage, 100)` → uses `recipient_percentage` for recipients, 100 for owners.
- SQL net: `gross_total × recipient_percentage / 100` (already split share).

### Python post-processing (lines 1671–1675)

```python
top_channels['net_total_INR'] = top_channels.apply(
    lambda x: round(x['net_total'] * (ratio/100), 2), axis=1)
```

- For split recipients, `ratio` comes from `get_user_info()` (often 0 if no Ratio).  
- Net is then: `SQL_net × ratio/100`.  
- If split recipients have no ratio, this effectively zeroes the channel totals.

### Formula (intended)

```
Net_Channel = Gross × Owner_Ratio × Recipient_Percentage / 100
```

- Owner ratio is not applied in the current SQL for split recipients; it is left to the Python layer via `ratio`, which is wrong for split recipients.

---

## 3. Net Royalties – Song Wise (Split User)

**Location:** `main/processor.py` → `NormalProcessor.get_royalty_stats()` (lines 1434–1479)

### SQL query (`top_tracks_query`)

```sql
-- owner_tracks CTE
SELECT 
    m.track,
    UPPER(m.isrc) as isrc,
    sum(r.units) as units,
    sum(r.net_total_INR) as gross_total,
    sum(r.net_total_INR * COALESCE(sr.recipient_percentage, 100) / 100) as net_total
FROM releases_royalties r 
LEFT JOIN releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
LEFT JOIN releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
LEFT JOIN releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
    AND t.release_id = sr.release_id_id 
    AND LOWER(sr.recipient_email) = '{username}'
WHERE 
    (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}')
    AND r.channel != 'Youtube Official Channel'
    {filter}
GROUP BY m.track, UPPER(m.isrc), t.id, t.release_id

-- top_isrc: For each track name, pick ISRC with highest gross_total
-- Final: Aggregate by track using top ISRC per track
```

### Logic

- Same WHERE and JOIN as channels: keeps owner tracks and recipient tracks.
- For recipients: `sr.recipient_percentage` is used.
- One ISRC per track is chosen (highest gross), then aggregated by track.

### Python post-processing (lines 1682–1684)

```python
top_tracks['net_total'] = top_tracks.apply(
    lambda x: round(x['net_total'] * (ratio/100), 2), axis=1)
```

- Again, `ratio` comes from the user’s own record and is typically 0 for split recipients.
- Same mismatch as channels: owner ratio should be applied instead.

### Formula (intended)

```
Net_Track = Gross × Owner_Ratio × Recipient_Percentage / 100
```

---

## 4. Net Royalties – Song Expanded → Channel Wise (per track)

**Location:** `main/processor.py` → `NormalProcessor.fetch_track_channels()` (lines 2105–2124)

**Triggered by:** Clicking a track row to open the channel breakdown.

### SQL query (`track_channels_query`)

```sql
-- owner_tracks: Find tracks/ISRCs for this user (owner or recipient)
WHERE (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}')
    AND m.track = '{track_name}'

-- top_isrc: ISRC with highest gross for this track

-- Final SELECT: Channel breakdown for that ISRC
SELECT 
    r.channel,
    sum(r.units) as units,
    sum(r.net_total_INR) as gross_total,
    sum(r.net_total_INR * COALESCE(sr.recipient_percentage, 100) / 100) as net_total
FROM releases_royalties r 
...
WHERE (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}') 
    AND m.track = '{track_name}' {filter}
GROUP BY r.channel
```

### Logic

- For specified track name, finds ISRCs where user is owner or recipient.
- Chooses one ISRC (highest gross).
- Aggregates by channel and applies `recipient_percentage` in SQL.

### Python post-processing (lines 2505–2511)

```python
tracks_channels_df['net_total'] = tracks_channels_df.apply(
    lambda x: round(
        x['net_total'] * (ratio/100)
        if x['channel'].lower() != 'youtube official channel' else 
        x['net_total'] * (yt_ratio/100), 2), 
    axis=1
)
```

- Same pattern: channel-type split (stores vs youtube) and user ratio.
- Split recipients usually have no ratio, so this again zeroes the breakdown.

### Formula (intended)

```
Net_Channel_for_Track = Gross × Owner_Ratio × Recipient_Percentage / 100
```

---

## Data Flow Summary

| Calculation                 | Entry Point                         | SQL Applies                          | Python Applies          | Split Recipient Uses |
|----------------------------|-------------------------------------|--------------------------------------|--------------------------|----------------------|
| Due Balance                | `refresh_due_balance_for_split_recipient` | Owner ratio + recipient %             | —                        | Owner ratio           |
| Channel-wise net           | `get_royalty_stats` → `top_channels_query` | Recipient % only                      | User ratio (often 0)     | Owner ratio (missing) |
| Song-wise net              | `get_royalty_stats` → `top_tracks_query`   | Recipient % only                     | User ratio (often 0)     | Owner ratio (missing) |
| Track → channel breakdown  | `fetch_track_channels`              | Recipient % only                     | User ratio (often 0)     | Owner ratio (missing) |

---

## Related Files

| File                     | Purpose                                                   |
|--------------------------|-----------------------------------------------------------|
| `main/processor.py`      | Core logic for all royalty calculations                  |
| `main/views.py`          | Routing for split recipients, dashboard, navigation       |
| `populate_due_amounts.py`| Batch refresh of due amounts (uses split-specific path)  |
| `releases/models.py`     | `SplitReleaseRoyalty` model                               |
| `main/models.py`         | `CDUser` (including `SPLIT_RECIPIENT` role)             |

---

## Tables

- **releases_royalties**: `net_total_INR` — platform gross per row
- **releases_metadata**: `user` — track owner
- **releases_splitreleaseroyalty**: `recipient_email`, `recipient_percentage`, `user_id` (owner)
- **main_ratio**: `stores`, `youtube` — owner’s share per channel type
- **main_payment**: `amount_paid`, `tds` — payments and TDS
- **main_dueamount**: Cached due balance per user

---

## Important Note

For split recipients, **Due Balance** is calculated correctly because `refresh_due_balance_for_split_recipient` applies the owner’s ratio in SQL.

By contrast, **channel-wise**, **song-wise**, and **track → channel** net royalties in `get_royalty_stats` and `fetch_track_channels` apply the user’s own `ratio` in Python. Split recipients usually have no ratio (0), so these views can show zero. To fix this, the owner’s ratio should be applied (as in the due balance logic) when the logged-in user is a split recipient.
