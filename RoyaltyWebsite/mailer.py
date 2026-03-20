import os
import sys
import argparse
import time
import pandas as pd
from django.conf import settings
from django.core.mail import EmailMessage
import django

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

def send_password_email(user_email, new_password):
    """
    Sends an email to the user with their new password.
    """
    subject = "Coin Digital Password Reset"
    html_body = f"""
    <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
        <h2 style="color: #0056b3; text-align: center;">Your New Password for Coin Digital</h2>
        <p>Dear User,</p>
        <p>Your password for the Coin Digital platform has been reset due to our migration to a new, faster architecture.</p>
        <p style="background-color: #f0f0f0; padding: 15px; border-left: 5px solid #0056b3; margin: 20px 0;">
            Your new temporary password is: <strong style="color: #d9534f; font-size: 16px;">{new_password}</strong>
        </p>
        <p>Please log in as soon as possible and change your password to something memorable for security reasons.</p>
        <p>You can log in by clicking on the link below:</p>
        <p style="text-align: center;">
            <a href="{settings.DOMAIN_URL_}login_page" style="display: inline-block; padding: 10px 20px; background-color: #28a745; color: #ffffff; text-decoration: none; border-radius: 5px;">
                Log In to Coin Digital
            </a>
        </p>
        <p>If you did not request this password reset, please contact our support team immediately.</p>
        <p>Thank you,</p>
        <p><strong>The Coin Digital Team</strong></p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">
        <p style="font-size: 12px; color: #777; text-align: center;">
            This is an automated email, please do not reply.
        </p>
    </div>
    """
    try:
        email = EmailMessage(subject, html_body, settings.EMAIL_FROM, [user_email])
        email.content_subtype = "html"  # Set the content type to HTML
        email.send()
        print(f"--> Successfully sent password email to {user_email}")
        return True
    except Exception as e:
        print(f"--> Error sending email to {user_email}: {e}")
        return False

def process_password_csv(csv_filepath):
    """
    Reads a CSV file containing user emails and new passwords, then emails them.
    Assumes CSV has 'email' and 'password' columns.
    """
    if not os.path.exists(csv_filepath):
        print(f"Error: CSV file not found at {csv_filepath}")
        return

    print(f"--> Processing password CSV: {csv_filepath}")
    try:
        df = pd.read_csv(csv_filepath)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    if 'username' not in df.columns or 'password' not in df.columns:
        print("Error: CSV must contain 'username' and 'password' columns.")
        return
    
    df = df[df.role.str.strip() !='member']
    print(f"--> Found {len(df)} members in the CSV. Starting email process...")

    total_users = len(df)
    sent_count = 0
    failed_count = 0

    print(f"--> Found {total_users} users in the CSV. Starting email process...")

    for index, row in df.iterrows():
        user_email = row['username'].strip()
        new_password = row['password'].strip()

        if send_password_email(user_email, new_password):
            sent_count += 1
            time.sleep(0.1)
        else:
            failed_count += 1

    print("\n--> Email Sending Summary:")
    print(f"   --> Total users processed: {total_users}")
    print(f"   --> Successfully sent: {sent_count}")
    print(f"   --> Failed to send: {failed_count}")

if __name__ == "__main__":

    csv_file = "passwords_alphanumeric_unique.csv"
    process_password_csv(csv_file) 

    # send_password_email("mirzaahmerg@gmail.com", "temp_password_mirzaahmerg@gmail.com")