-- EMERGENCY FIX for MySQL error 1364 on CREATE RELEASE:
-- Field 'apple_music_commercial_model' doesn't have a default value
--
-- Run on live MySQL (e.g. mysql client or RDS) as a user with ALTER on releases_release:
--
--   mysql -u ... -p your_database < HOTFIX_MYSQL_APPLE_MUSIC_COMMERCIAL_MODEL.sql
--
-- Then create release from the website should work even before the next app deploy.

UPDATE releases_release
SET apple_music_commercial_model = 'both'
WHERE apple_music_commercial_model IS NULL OR apple_music_commercial_model = '';

ALTER TABLE releases_release
MODIFY COLUMN apple_music_commercial_model VARCHAR(20) NOT NULL DEFAULT 'both';
