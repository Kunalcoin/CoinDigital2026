# ALL CALCULATION INSTANCES IN ROYALTY SYSTEM

This document lists ALL places where `net_total` calculations are applied across the entire website for all user types.

---

## 1. ADMIN USERS (`AdminProcessor`)

### 1.1 Admin - Top Tracks Calculation
**Location:** `processor.py` lines 422-424  
**Function:** `AdminProcessor.get_royalty_stats()`

```python
top_tracks['net_total_INR'] = top_tracks.apply(
    lambda x: round(x['gross_total'] * (admin_ratio/100 - ratios.get(str(x["user"]).lower(), 0)/100), 2), axis=1)
```

**Formula:** `Gross × (Admin_Ratio - User_Ratio) / 100`
- Admin ratio = 100%
- User ratio = child user's ratio
- **Result:** Admin's share = Gross × (100% - User_Ratio%)

---

### 1.2 Admin - Top Channels Calculation
**Location:** `processor.py` lines 368-374  
**Function:** `AdminProcessor.get_royalty_stats()`

```python
top_channels['net_total_INR'] = top_channels['gross_total']
top_channels['net_total_INR'] = top_channels.apply(
    lambda x: round(x['gross_total'] *
                    (admin_ratio/100 -
                    ratios.get(str(x["user"]).lower(), 0)/100)
                    if x['channel'] != 'Youtube Official Channel' else x['gross_total']
                    * (admin_ytratio/100 - yt_ratios.get(str(x["user"]).lower(), 0)/100), 2), axis=1)
```

**Formula:** 
- For Stores: `Gross × (Admin_Ratio - User_Ratio) / 100`
- For YouTube: `Gross × (Admin_YT_Ratio - User_YT_Ratio) / 100`

---

### 1.3 Admin - YouTube Channels Calculation
**Location:** `processor.py` lines 324-326  
**Function:** `AdminProcessor.get_royalty_stats()`

```python
top_youtube_channels['net_total_INR'] = top_youtube_channels.apply(
    lambda x: round(x['gross_total'] * (admin_ytratio/100 - yt_ratios.get(str(x["user"]).lower(), 0)/100), 2), axis=1)
```

**Formula:** `Gross × (Admin_YT_Ratio - User_YT_Ratio) / 100`

---

### 1.4 Admin - Track Channels (fetch_track_channels)
**Location:** `processor.py` lines 640-645  
**Function:** `AdminProcessor.fetch_track_channels()`

```python
tracks_channels_df['net_total_INR'] = tracks_channels_df.apply(
    lambda x: round(x['gross_total'] *
                    (admin_ratio/100 -
                    ratios.get(str(x["user"]).lower(), 0)/100)
                    if x['channel'].lower() != 'youtube official channel' else x['gross_total']
                    * (admin_ytratio/100 - yt_ratios.get(str(x["user"]).lower(), 0)/100), 2), axis=1)
```

**Formula:** Same as 1.2 (Top Channels)

---

### 1.5 Admin - Due Balance Calculation (Direct to Admin)
**Location:** `processor.py` lines 694-696  
**Function:** `AdminProcessor.refresh_due_balance()`

**SQL Query:**
```sql
CASE 
    WHEN ADMIN1.channel_type LIKE 'stores' THEN 
        ADMIN1.net_total_INR * ((100 - ADMIN1.stores_ratio)/100)
    ELSE 
        ADMIN1.net_total_INR * ((100 - ADMIN1.youtube_ratio)/100) 
END AS calculated_net_total_INR
```

**Formula:** `Gross × (100% - User_Ratio%) / 100`
- This calculates Admin's share from Normal/Intermediate users directly under Admin

---

### 1.6 Admin - Due Balance Calculation (Through Intermediate)
**Location:** `processor.py` lines 735-737  
**Function:** `AdminProcessor.refresh_due_balance()`

**SQL Query:**
```sql
CASE 
    WHEN ADMIN3.channel_type LIKE 'stores' THEN 
        ADMIN3.net_total_INR * ((100 - ADMIN3.parent_stores_ratio)/100)
    ELSE 
        ADMIN3.net_total_INR * ((100 - ADMIN3.parent_youtube_ratio)/100) 
END AS calculated_net_total_INR
```

**Formula:** `Gross × (100% - Intermediate_Ratio%) / 100`
- This calculates Admin's share from Normal users under Intermediate users

---

## 2. INTERMEDIATE USERS (`IntermediateProcessor`)

### 2.1 Intermediate - Top Tracks Calculation
**Location:** `processor.py` lines 1025-1026  
**Function:** `IntermediateProcessor.get_royalty_stats()`

```python
top_tracks['net_total_INR'] = top_tracks.apply(
    lambda x: round(x['gross_total'] * (intermediate_user_ratio/100 - ratios.get(str(x["user"]).lower(), 0)/100), 2), axis=1)
```

**Formula:** `Gross × (Intermediate_Ratio - Child_User_Ratio) / 100`
- Intermediate ratio = Intermediate user's ratio (e.g., 95%)
- Child user ratio = Normal user's ratio (e.g., 80%)
- **Result:** Intermediate's share = Gross × (95% - 80%) = Gross × 15%

---

### 2.2 Intermediate - Top Channels Calculation
**Location:** `processor.py` lines 980-983  
**Function:** `IntermediateProcessor.get_royalty_stats()`

```python
top_channels['net_total_INR'] = top_channels['gross_total']
top_channels['net_total_INR'] = top_channels.apply(
    lambda x: round(x['gross_total'] *
                    (intermediate_user_ratio/100 -
                    ratios.get(str(x["user"]).lower(), 0)/100), 2), axis=1)
```

**Formula:** `Gross × (Intermediate_Ratio - Child_User_Ratio) / 100`
- Only for non-YouTube channels (YouTube handled separately)

---

### 2.3 Intermediate - YouTube Channels Calculation
**Location:** `processor.py` lines 936-937  
**Function:** `IntermediateProcessor.get_royalty_stats()`

```python
top_youtube_channels['net_total_INR'] = top_youtube_channels.apply(
    lambda x: round(x['gross_total'] * (intermediate_user_ytratio/100 - yt_ratios.get(str(x["user"]).lower(), 0)/100), 2), axis=1)
```

**Formula:** `Gross × (Intermediate_YT_Ratio - Child_User_YT_Ratio) / 100`

---

### 2.4 Intermediate - Track Channels (fetch_track_channels)
**Location:** `processor.py` lines 1202-1207  
**Function:** `IntermediateProcessor.fetch_track_channels()`

```python
tracks_channels_df['net_total_INR'] = tracks_channels_df.apply(
    lambda x: round(x['gross_total'] *
                    (intermediate_user_ratio/100 -
                    ratios.get(str(x["user"]).lower(), 0)/100)
                    if x['channel'].lower() != 'youtube official channel' else x['gross_total']
                    * (intermediate_user_ytratio/100 - yt_ratios.get(str(x["user"]).lower(), 0)/100), 2), axis=1)
```

**Formula:** Same as 2.1 and 2.3

---

### 2.5 Intermediate - Due Balance Calculation
**Location:** `processor.py` lines 1244-1246  
**Function:** `IntermediateProcessor.refresh_due_balance()`

**SQL Query:**
```sql
CASE 
    WHEN t1.channel_type LIKE 'stores' THEN 
        t1.net_total_INR * (({ratio}/100) - (rt.stores/100))
    ELSE 
        t1.net_total_INR * (({yt_ratio}/100) - (rt.youtube/100))
END AS calculated_net_total_INR
```

**Formula:** `Gross × (Intermediate_Ratio - Child_User_Ratio) / 100`

---

## 3. NORMAL USERS (`NormalProcessor`)

### 3.1 Normal - Top Tracks Calculation (SQL Query - Owner Tracks)
**Location:** `processor.py` lines 1480-1491  
**Function:** `NormalProcessor.get_royalty_stats()`

**SQL Query:**
```sql
ra.gross_total * ({ratio} / 100.0) * (
    (100.0 - COALESCE((
        SELECT SUM(sr2.recipient_percentage)
        FROM releases_splitreleaseroyalty sr2
        JOIN releases_track t2 ON sr2.track_id_id = t2.id AND sr2.release_id_id = t2.release_id
        JOIN releases_metadata m2 ON UPPER(t2.isrc) = UPPER(m2.isrc)
        WHERE UPPER(t2.isrc) = ra.isrc
            AND LOWER(m2.user) = '{username}'
            AND LOWER(sr2.recipient_email) != LOWER(m2.user)  -- Exclude owner's own split
            AND LOWER(sr2.recipient_email) != '{username}'    -- Double check
    ), 0.0)) / 100.0
) as net_total
```

**Formula:** 
- **Without splits:** `Gross × Ratio / 100`
- **With splits:** `Gross × Ratio / 100 × (100% - Total_Split_Percentage%) / 100`
- **CRITICAL:** This applies the user's ratio ONCE, then subtracts recipient splits

**Python Post-Processing:** Lines 1952-1983
- **NO ADDITIONAL RATIO APPLICATION** - Already calculated in SQL
- Only debug logging and formatting

---

### 3.2 Normal - Top Tracks Calculation (SQL Query - Recipient Tracks)
**Location:** `processor.py` lines 1505-1512  
**Function:** `NormalProcessor.get_royalty_stats()`

**SQL Query:**
```sql
ra.gross_total * (
    COALESCE(
        (SELECT r2.stores FROM main_ratio r2 
         JOIN main_cduser u2 ON r2.user_id = u2.id 
         WHERE LOWER(u2.email) = ra.owner_email AND r2.status = 'active' LIMIT 1),
        0
    ) / 100
) * (sr.recipient_percentage / 100) as net_total
```

**Formula:** `Gross × Owner_Ratio / 100 × Recipient_Percentage / 100`
- First applies owner's ratio, then applies recipient's split percentage

---

### 3.3 Normal - Top Channels Calculation (SQL Query - Owner)
**Location:** `processor.py` lines 1665-1676  
**Function:** `NormalProcessor.get_royalty_stats()`

**SQL Query:**
```sql
CASE 
    -- If user is recipient: Gross × Owner_Ratio × Recipient_Percentage
    WHEN sr.recipient_email IS NOT NULL THEN 
        CASE 
            WHEN r.channel = 'Youtube Official Channel' THEN
                r.net_total_INR * (Owner_YT_Ratio / 100) * (sr.recipient_percentage / 100)
            ELSE
                r.net_total_INR * (Owner_Stores_Ratio / 100) * (sr.recipient_percentage / 100)
        END
    -- If user is owner with splits: Gross × Owner_Ratio × (100% - sum_of_splits)
    WHEN COALESCE(ts.total_recipient_percentage, 0) > 0 THEN 
        CASE 
            WHEN r.channel = 'Youtube Official Channel' THEN
                r.net_total_INR * ({yt_ratio} / 100) * ((100 - ts.total_recipient_percentage) / 100)
            ELSE
                r.net_total_INR * ({ratio} / 100) * ((100 - ts.total_recipient_percentage) / 100)
        END
    -- If no splits: Gross × Owner_Ratio
    ELSE 
        CASE 
            WHEN r.channel = 'Youtube Official Channel' THEN
                r.net_total_INR * ({yt_ratio} / 100)
            ELSE
                r.net_total_INR * ({ratio} / 100)
        END
END
```

**Formula:**
- **Recipient:** `Gross × Owner_Ratio × Recipient_Percentage`
- **Owner with splits:** `Gross × Owner_Ratio × (100% - Total_Splits%)`
- **Owner without splits:** `Gross × Owner_Ratio`

**Python Post-Processing:** Lines 1908-1914
- **NO ADDITIONAL RATIO APPLICATION** - Already calculated in SQL
- Just column renaming: `top_channels['net_total_INR'] = top_channels['net_total']`

---

### 3.4 Normal - YouTube Channels Calculation (SQL Query)
**Location:** `processor.py` lines 1576-1589  
**Function:** `NormalProcessor.get_royalty_stats()`

**SQL Query:**
```sql
CASE 
    -- If user is recipient: Gross × Owner_YouTube_Ratio × Recipient_Percentage
    WHEN sr.recipient_email IS NOT NULL THEN 
        r.net_total_INR * (Owner_YT_Ratio / 100) * (sr.recipient_percentage / 100)
    -- If user is owner with splits: Gross × Owner_YouTube_Ratio × (100% - sum_of_splits)
    WHEN COALESCE(ts.total_recipient_percentage, 0) > 0 THEN 
        r.net_total_INR * ({yt_ratio} / 100) * ((100 - ts.total_recipient_percentage) / 100)
    -- If no splits: Gross × Owner_YouTube_Ratio
    ELSE 
        r.net_total_INR * ({yt_ratio} / 100)
END
```

**Formula:** Same as 3.3 but for YouTube channels

**Python Post-Processing:** Lines 1868-1874
- **FIXED:** Removed double ratio application
- Previously was applying ratio again (line 1871-1872), now removed
- **NO ADDITIONAL RATIO APPLICATION** - Already calculated in SQL

---

### 3.5 Normal - Track Channels (fetch_track_channels)
**Location:** `processor.py` lines 2532-2538  
**Function:** `NormalProcessor.fetch_track_channels()`

**SQL Query (lines 2500):**
```sql
sum(r.net_total_INR * COALESCE(sr.recipient_percentage, 100) / 100) as net_total
```

**Python Post-Processing (lines 2532-2538):**
```python
tracks_channels_df['net_total'] = tracks_channels_df.apply(
    lambda x: round(
        x['net_total'] * (ratio/100)
        if x['channel'].lower() != 'youtube official channel' else 
        x['net_total'] * (yt_ratio/100), 2), 
    axis=1
)
```

**⚠️ POTENTIAL ISSUE:** This applies the ratio AFTER the SQL query has already calculated net_total with recipient_percentage. This might be causing double application if the SQL query is already applying the user's ratio.

**Formula:** `SQL_Net_Total × User_Ratio / 100`
- SQL calculates: `Gross × Recipient_Percentage / 100` (if recipient) or `Gross` (if owner)
- Python then applies: `Result × User_Ratio / 100`

---

### 3.6 Normal - Due Balance Calculation
**Location:** `processor.py` lines 2107-2140  
**Function:** `NormalProcessor.refresh_due_balance()`

**SQL Query:**
```sql
-- For owner tracks with splits:
CASE 
    WHEN channel_type = 'stores' THEN 
        gross_total_INR * ({ratio}/100) * ((100 - COALESCE(total_recipient_percentage, 0)) / 100)
    ELSE 
        gross_total_INR * ({yt_ratio}/100) * ((100 - COALESCE(total_recipient_percentage, 0)) / 100)
END

-- For recipient tracks:
CASE 
    WHEN channel_type = 'stores' THEN 
        gross_total_INR * (Owner_Stores_Ratio / 100) * (recipient_percentage / 100)
    ELSE 
        gross_total_INR * (Owner_YT_Ratio / 100) * (recipient_percentage / 100)
END
```

**Formula:**
- **Owner with splits:** `Gross × User_Ratio × (100% - Total_Splits%)`
- **Recipient:** `Gross × Owner_Ratio × Recipient_Percentage`

---

## 4. SUMMARY OF POTENTIAL ISSUES

### ⚠️ Issue 1: Normal User - Track Channels (fetch_track_channels)
**Location:** Lines 2532-2538  
**Problem:** Applies user ratio AFTER SQL query that may already include ratio calculations.

**Current Flow:**
1. SQL calculates: `Gross × Recipient_Percentage / 100` (for recipients) or `Gross` (for owners)
2. Python applies: `Result × User_Ratio / 100`

**Expected Flow:**
- If user is owner: `Gross × User_Ratio × (100% - Splits%)`
- If user is recipient: `Gross × Owner_Ratio × Recipient_Percentage`

**Fix Needed:** Check if SQL query at line 2500 is correct, or if Python post-processing should be removed.

---

### ⚠️ Issue 2: Normal User - Top Tracks (SQL Query)
**Location:** Lines 1480-1491  
**Status:** ✅ CORRECT - Applies ratio once, then subtracts splits

**Formula:** `Gross × Ratio × (100% - Splits%)`

---

### ⚠️ Issue 3: Normal User - YouTube Channels
**Location:** Lines 1868-1874  
**Status:** ✅ FIXED - Removed double ratio application

**Previous Issue:** Python was applying ratio again after SQL already calculated it.
**Current Status:** No additional ratio application in Python.

---

## 5. CALCULATION FLOW DIAGRAM

### Normal User (Owner) - Track Without Splits:
```
Gross → × User_Ratio → Net_Total
```

### Normal User (Owner) - Track With Splits:
```
Gross → × User_Ratio → × (100% - Total_Splits%) → Net_Total
```

### Normal User (Recipient):
```
Gross → × Owner_Ratio → × Recipient_Percentage → Net_Total
```

### Intermediate User:
```
Gross → × (Intermediate_Ratio - Child_User_Ratio) → Net_Total
```

### Admin User:
```
Gross → × (100% - User_Ratio%) → Net_Total
```

---

## 6. FILES TO CHECK

1. **`processor.py`** - Main calculation file
   - AdminProcessor: Lines 205-821
   - IntermediateProcessor: Lines 824-1361
   - NormalProcessor: Lines 1363-2554

2. **Key Functions:**
   - `get_royalty_stats()` - Main dashboard calculations
   - `fetch_track_channels()` - Track breakdown calculations
   - `refresh_due_balance()` - Due balance calculations

---

## 7. DEBUGGING CHECKLIST

- [ ] Check if `fetch_track_channels` (line 2532) is applying ratio twice
- [ ] Verify SQL queries are not applying ratio multiple times
- [ ] Check if `net_total_INR` from `releases_royalties` table already has ratios applied
- [ ] Verify split percentage calculations exclude owner's own split
- [ ] Check if YouTube Official Channel calculations are consistent with regular channels

---

**Last Updated:** 2026-01-25  
**File:** `processor.py`  
**Total Calculation Instances:** 15+ locations
