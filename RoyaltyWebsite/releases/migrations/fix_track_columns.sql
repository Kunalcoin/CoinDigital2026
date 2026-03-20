-- Add missing Track columns (migration 0015 was marked applied but columns don't exist).
-- Run against your local MySQL DB. If a column already exists, you'll get an error for that line only; run the rest.
-- Table: releases_track

ALTER TABLE releases_track ADD COLUMN audio_wav_url VARCHAR(1024) NOT NULL DEFAULT '';
ALTER TABLE releases_track ADD COLUMN audio_mp3_url VARCHAR(1024) NOT NULL DEFAULT '';
ALTER TABLE releases_track ADD COLUMN audio_flac_url VARCHAR(1024) NOT NULL DEFAULT '';
ALTER TABLE releases_track ADD COLUMN audio_uploaded_at DATETIME NULL;

-- If you get "Duplicate column" errors, that column already exists; skip that line.
