-- Move releases from Pending for Approval to Delivered
-- Run this against your live database (MySQL)
-- Usage: mysql -u USER -p DATABASE < sql_set_delivered.sql
-- Or run via Django: python manage.py dbshell < sql_set_delivered.sql

UPDATE releases_release
SET
  approval_status = 'approved',
  published = 1,
  published_at = COALESCE(published_at, NOW())
WHERE upc IN (
  '8905285300321',
  '8905285300673',
  '8905285300680',
  '8905285300628',
  '8905285300635',
  '8905285300642',
  '8905285300345',
  '8905285300314',
  '8905285300352',
  '8905285300369',
  '8905285300376',
  '8905285300383',
  '8905285300390',
  '8905285300604',
  '8905285300611',
  '8905285300451',
  '8905285300581',
  '8905285300574',
  '8905285300567',
  '8905285300550',
  '8905285300420',
  '8905285300413',
  '8905285300406',
  '8905285300468',
  '8905285300598',
  '8905285300475',
  '8905285300482',
  '8905285300499',
  '8905285300505',
  '8905285300512',
  '8905285300529',
  '8905285300536',
  '8905285300543'
);
