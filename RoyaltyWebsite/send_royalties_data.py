import os
import argparse
from zipfile import ZipFile
import django
import pandas as pd
from django.conf import settings
from django.core.mail import EmailMessage
from releases.models import Royalties, Metadata
from django.db.models.functions import Upper, Trim
from datetime import datetime
import calendar

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

def send_email(email_to, attachment_file):
    body = f"""Please find attached Royalty Report\n"""
    email = EmailMessage("Royalties Report", body, settings.EMAIL_FROM, [email_to])
    email.attach_file(attachment_file)
    email.send()
    return


def get_extracted_file_paths(structure):
    file_paths = []
    for root, directories, files in os.walk('./processed_royalties'):
        for filename in files:
            if structure in filename and filename.split('.')[-1] == 'csv':
                filepath = os.path.join(root, filename)
                file_paths.append(filepath)
    return list(set(file_paths))


def trigger(email, field_category, field, start_date, end_date):
    print(f"[INFO] Starting trigger function for email: {email}, category: {field_category}, field: {field}, start_date: {start_date}, end_date: {end_date}")
    # Construct date objects for filtering
    start_date_obj = datetime.strptime(f'{start_date}-01', '%Y-%m-%d').date()
    
    end_date_year = int(end_date.split('-')[0])
    end_date_month = int(end_date.split('-')[1])
    _, last_day = calendar.monthrange(end_date_year, end_date_month)
    end_date_obj = datetime.strptime(f'{end_date}-{last_day}', '%Y-%m-%d').date()
    print(f"[INFO] Date objects constructed: start_date_obj={start_date_obj}, end_date_obj={end_date_obj}")

    # Get all metadata ISRC values for the user, ensuring they are uppercase.
    metadata_isrcs = list(Metadata.objects.filter(user__iexact=email).values_list('isrc', flat=True))
    upper_metadata_isrcs = [isrc.upper().strip() for isrc in metadata_isrcs]
    print(f"[INFO] Fetched {len(metadata_isrcs)} metadata ISRCs.")

    # Filter Royalties based on the user's ISRCs and date range.
    # The join is case-insensitive on `isrc`.
    royalties_qs = Royalties.objects.annotate(upper_isrc=Upper(Trim('isrc'))).filter(
        upper_isrc__in=upper_metadata_isrcs,
        confirmed_date__gte=start_date_obj,
        confirmed_date__lte=end_date_obj
    )
    print(f"[INFO] Filtered royalties queryset. Count: {royalties_qs.count()}")

    # Get the corresponding metadata for the filtered royalties.
    royalty_isrcs_upper = list(royalties_qs.values_list('upper_isrc', flat=True).distinct())
    metadata_qs = Metadata.objects.filter(isrc__in=royalty_isrcs_upper)

    # Convert querysets to DataFrames for processing.
    royalties_df = pd.DataFrame(list(royalties_qs.values()))
    metadata_df = pd.DataFrame(list(metadata_qs.values()))
    print(f"[INFO] Converted querysets to DataFrames. Royalties DF rows: {len(royalties_df)}, Metadata DF rows: {len(metadata_df)}")

    # If there are royalties, merge them with metadata.
    if not royalties_df.empty and not metadata_df.empty:
        royalties_df['join_key'] = royalties_df['isrc'].str.upper()
        metadata_df['join_key'] = metadata_df['isrc'].str.upper()
        
        # Merge dataframes to replicate the SQL JOIN.
        df = pd.merge(
            royalties_df,
            metadata_df,
            on='join_key',
            how='inner',
            suffixes=('_royalty', '')
        )
        print(f"[INFO] Merging DataFrames. Royalties DF shape: {royalties_df.shape}, Metadata DF shape: {metadata_df.shape}")
        df.drop(columns=['join_key', 'upper_isrc', 'isrc_royalty'], inplace=True, errors='ignore')
        print(f"[INFO] DataFrames merged successfully. Final DF shape: {df.shape}")
    else:
        df = pd.DataFrame()

    if df.empty:
        print("[INFO] No data found for the given criteria. Exiting trigger function.")
        return

    if field_category.lower() == 'multiple':
        for unique_field in set(df[field].tolist()):
            filename = unique_field.replace(" ", '_').lower()
            print(f"[INFO] Attempting to create CSV for multiple categories: {filename}")
            try:
                df[df[field] == unique_field].to_csv(f'./processed_royalties/{email}_{field}_{filename}.csv', index=False)
                print(f"[INFO] Successfully created CSV: ./processed_royalties/{email}_{field}_{filename}.csv")
            except Exception as e:
                print(f"[ERROR] Failed to create CSV for {filename}: {e}")
                pass
    else:
        print(f"[INFO] Attempting to create single CSV for {email}_{field}")
        directory_path = './processed_royalties/'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            print(f"[INFO] Created directory: {directory_path}")
        df.to_csv(F"./processed_royalties/{email}_{field}.csv", index=False)
        print(f"[INFO] Successfully created CSV: ./processed_royalties/{email}_{field}.csv")

    file_paths = get_extracted_file_paths(f"{email}_{field}")
    print(f"[INFO] Found {len(file_paths)} files to zip.")
    zip_file_name = f'./processed_royalties/{email}_{field}.zip'
    with ZipFile(zip_file_name,'w') as zip:
        for file in file_paths:
            zip.write(file)
    print(f"[INFO] Files zipped successfully to {zip_file_name}")

    print(f"[INFO] Sending email to {email} with attachment {zip_file_name}")
    send_email(email, zip_file_name)
    print(f"[INFO] Email sent successfully.")

    print(f"[INFO] Removing temporary CSV files.")
    for file_path in file_paths:
        os.remove(file_path)
        print(f"[INFO] Removed {file_path}")
    os.remove(f'./processed_royalties/{email}_{field}.zip')
    print(f"[INFO] Removed zip file: ./processed_royalties/{email}_{field}.zip")
    print(f"[INFO] Trigger function finished.")
    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("field_category")
    parser.add_argument("field")
    parser.add_argument("start_date")
    parser.add_argument("end_date")
    args = parser.parse_args()

    trigger(args.email, args.field_category, args.field, args.start_date, args.end_date)