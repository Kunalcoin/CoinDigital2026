@echo off

echo Starting migration execution...
echo ==================================

REM Create output directory
if not exist migration_outputs mkdir migration_outputs

echo Running 01_migrate_users.py...
python data_migrations\01_migrate_users.py > migration_outputs\01_migrate_users_output.txt 2>&1

echo Running 02_migrate_teams.py...
python data_migrations\02_migrate_teams.py > migration_outputs\02_migrate_teams_output.txt 2>&1

echo Running 03_migrate_payments.py...
python data_migrations\03_migrate_payments.py > migration_outputs\03_migrate_payments_output.txt 2>&1

echo Running 04_migrate_due_amounts.py...
python data_migrations\04_migrate_due_amounts.py > migration_outputs\04_migrate_due_amounts_output.txt 2>&1

echo Running 05_migrate_announcements.py...
python data_migrations\05_migrate_announcements.py > migration_outputs\05_migrate_announcements_output.txt 2>&1

echo Running 06_migrate_user_requests.py...
python data_migrations\06_migrate_user_requests.py > migration_outputs\06_migrate_user_requests_output.txt 2>&1

echo Running 07_migrate_unique_codes.py...
python data_migrations\07_migrate_unique_codes.py > migration_outputs\07_migrate_unique_codes_output.txt 2>&1

echo Running 08_migrate_labels.py...
python data_migrations\08_migrate_labels.py > migration_outputs\08_migrate_labels_output.txt 2>&1

echo Running 09_migrate_artists.py...
python data_migrations\09_migrate_artists.py > migration_outputs\09_migrate_artists_output.txt 2>&1

echo Running 09_1_flatten_artists.py...
python data_migrations\09_1_flatten_artists.py > migration_outputs\09_1_flatten_artists_output.txt 2>&1

echo Running 10_migrate_releases.py...
python data_migrations\10_migrate_releases.py > migration_outputs\10_migrate_releases_output.txt 2>&1

echo Running 11_migrate_tracks.py...
python data_migrations\11_migrate_tracks.py > migration_outputs\11_migrate_tracks_output.txt 2>&1

echo Running 12_migrate_metadata.py...
python data_migrations\12_migrate_metadata.py > migration_outputs\12_migrate_metadata_output.txt 2>&1

echo Running 14_migrate_related_artists.py...
python data_migrations\14_migrate_related_artists.py > migration_outputs\14_migrate_related_artists_output.txt 2>&1

echo Running 15_create_split_release_royalties.py...
python data_migrations\15_create_split_release_royalties.py > migration_outputs\15_create_split_release_royalties_output.txt 2>&1

echo Running 13_migrate_royalties.py...
python data_migrations\13_migrate_royalties.py > migration_outputs\13_migrate_royalties_output.txt 2>&1

echo.
echo ==================================
echo Migration execution completed!
echo Check the 'migration_outputs' directory for detailed logs.
echo ==================================

pause 