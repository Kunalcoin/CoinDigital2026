import os
import sys
import csv
import django
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

# Now we can import Django models
from main.models import CDUser

def update_passwords_from_csv(csv_file_path):
    """
    Update user passwords from a CSV file containing email and password pairs.
    CSV format should be:
    email,password
    user@example.com,newpassword123
    """
    print("[START] Beginning password update process...")
    
    if not os.path.exists(csv_file_path):
        print(f"[ERROR] CSV file not found at: {csv_file_path}")
        return
    
    success_count = 0
    error_count = 0
    
    try:
        with open(csv_file_path, 'r') as file:
            reader = csv.DictReader(file)
            
            # Validate CSV structure
            required_fields = {'username', 'password'}
            if not required_fields.issubset(set(reader.fieldnames)):
                print(f"[ERROR] CSV must contain 'username' and 'password' columns. Found: {reader.fieldnames}")
                return
            
            # Process each row
            for row in reader:
                email = row['username'].strip()
                password = row['password'].strip()
                
                try:
                    # Find the user
                    user = CDUser.objects.filter(email=email).first()
                    
                    if user:
                        # Update password
                        user.set_password(password)
                        user.save()
                        print(f"[SUCCESS] Updated password for user: {email}")
                        success_count += 1
                    else:
                        print(f"[WARNING] User not found: {email}")
                        error_count += 1
                        
                except Exception as e:
                    print(f"[ERROR] Failed to update password for {email}: {str(e)}")
                    error_count += 1
    
    except Exception as e:
        print(f"[ERROR] Failed to process CSV file: {str(e)}")
        return
    
    print("\nPassword Update Summary:")
    print(f"Successfully updated: {success_count}")
    print(f"Errors/Not found: {error_count}")
    print("[COMPLETE] Password update process finished")

if __name__ == "__main__":
    # Check if CSV file path is provided as command line argument
    if len(sys.argv) != 2:
        print("Usage: python 03_update_passwords.py <path_to_csv_file>")
        sys.exit(1)
    
    csv_file_path = sys.argv[1]
    update_passwords_from_csv(csv_file_path) 