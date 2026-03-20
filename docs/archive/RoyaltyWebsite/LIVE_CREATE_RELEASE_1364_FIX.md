# Live error 1364: `apple_music_commercial_model` (Create Release broken)

## What happened

The column `apple_music_commercial_model` exists on **`releases_release`** in MySQL as **NOT NULL** but **without a server DEFAULT**. The “Create release” API only sends `title` and `created_by`, so MySQL raises:

`(1364, "Field 'apple_music_commercial_model' doesn't have a default value")`

That usually means **migrations that add Apple Music fields were applied on the live database** (deploy, manual `migrate`, or DBA script)—even if you did not intend to ship Apple Music UI yet. The Django model has `default='both'`, but that only helps if the **database column** also has `DEFAULT 'both'`.

## Fix in under 2 minutes (production MySQL)

Run this against the **same database** the live site uses:

```bash
# From RoyaltyWebsite folder (path may differ on server):
mysql -h YOUR_HOST -u YOUR_USER -p YOUR_DB < HOTFIX_MYSQL_APPLE_MUSIC_COMMERCIAL_MODEL.sql
```

Or paste the SQL from `HOTFIX_MYSQL_APPLE_MUSIC_COMMERCIAL_MODEL.sql` into your SQL client.

No app restart required for the SQL fix; new rows will get `both` by default.

## Fix in application code (deploy when ready)

1. **`releases/views.py`** — `Release.objects.create(...)` now passes `apple_music_commercial_model=BOTH` so inserts are explicit even if DB has no default.
2. **Migration `0021_mysql_default_apple_music_commercial_model.py`** — on **MySQL** only, sets `DEFAULT 'both'` and backfills empty values. Run after `0020` is applied:
   `python3 manage.py migrate releases`

## Apple Music testing vs live website

Merlin Bridge / `deliver_apple_music` only run when someone executes that command or uses an admin button with the right env. **Create Release** fails for everyone if the column has no default—this fix restores normal behaviour; it does not turn on Apple Music delivery for all users.

## Prevent recurrence

- Do not run `migrate` on production unless you intend to ship those schema changes.
- Prefer staging first; keep production DB in sync with tagged releases.
