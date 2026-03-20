import os
import django
import sys
import traceback

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RoyaltyWebsite.settings")
django.setup()

from main.models import CDUser, DueAmount, Ratio
from main.processor import admin as admin_processor
from main.processor import intermediate as intermediate_processor
from main.processor import normal as normal_processor


def truncate_aggregate_relation():
    # return
    DueAmount.objects.all().delete()
    print("DueAmount table truncated!")


def update_admin_users():
    # return
    admin_users = CDUser.objects.filter(role=CDUser.ROLES.ADMIN)
    total_admin = admin_users.count()
    print(f"Processing {total_admin} admin users...")
    
    success_count = 0
    error_count = 0
    
    for i, user in enumerate(admin_users, 1):
        try:
            admin_processor.refresh_due_balance(user.email, 100, 100)
            success_count += 1
        except Exception as e:
            error_count += 1
            print(f"  ERROR processing admin user {user.email}: {str(e)}")
            traceback.print_exc()
            # Continue processing other users even if this one fails
        
        if i % 10 == 0 or i == total_admin:
            print(f"  Processed {i}/{total_admin} admin users (Success: {success_count}, Errors: {error_count})")
    
    print(f"Admin Users Updated! Success: {success_count}, Errors: {error_count}")


def update_intermediate_users():
    intermediate_users = CDUser.objects.filter(
        role=CDUser.ROLES.INTERMEDIATE)

    total_intermediate = intermediate_users.count()
    print(f"Processing {total_intermediate} intermediate users...")

    success_count = 0
    error_count = 0

    for i, user in enumerate(intermediate_users, 1):
        try:
            # Try to get active ratio first
            ratio = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
            
            # If no active ratio, try to get the most recent ratio (regardless of status) as fallback
            if not ratio:
                ratio = Ratio.objects.filter(user=user).order_by('-created_at').first()
            
            # If still no ratio, use default values (0, 0)
            if ratio:
                stores_ratio = ratio.stores
                youtube_ratio = ratio.youtube
            else:
                stores_ratio = 0
                youtube_ratio = 0
                print(f"  No ratio found for user {user.email}, using default values (0, 0)")
            
            # Process all users, even if they don't have ratios
            intermediate_processor.refresh_due_balance(
                username=user.email,
                ratio=stores_ratio,
                yt_ratio=youtube_ratio,
            )
            success_count += 1
        except Exception as e:
            error_count += 1
            print(f"  ERROR processing intermediate user {user.email}: {str(e)}")
            traceback.print_exc()
            # Continue processing other users even if this one fails
        
        if i % 10 == 0 or i == total_intermediate:
            print(f"  Processed {i}/{total_intermediate} intermediate users (Success: {success_count}, Errors: {error_count})")
    
    print(f"Intermediate Users Updated! Success: {success_count}, Errors: {error_count}")


def update_normal_users():
    normal_users = CDUser.objects.filter(
        role=CDUser.ROLES.NORMAL,
    )

    total_normal = normal_users.count()
    print(f"Processing {total_normal} normal users...")

    success_count = 0
    error_count = 0

    for i, user in enumerate(normal_users, 1):
        try:
            # Try to get active ratio first
            ratio = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
            
            # If no active ratio, try to get the most recent ratio (regardless of status) as fallback
            if not ratio:
                ratio = Ratio.objects.filter(user=user).order_by('-created_at').first()
            
            # If still no ratio, use default values (0, 0)
            if ratio:
                stores_ratio = ratio.stores
                youtube_ratio = ratio.youtube
            else:
                stores_ratio = 0
                youtube_ratio = 0
                print(f"  No ratio found for user {user.email}, using default values (0, 0)")
            
            # Process all users, even if they don't have ratios
            normal_processor.refresh_due_balance(
                username=user.email,
                ratio=stores_ratio,
                yt_ratio=youtube_ratio,
            )
            success_count += 1
        except Exception as e:
            error_count += 1
            print(f"  ERROR processing normal user {user.email}: {str(e)}")
            traceback.print_exc()
            # Continue processing other users even if this one fails
        
        if i % 10 == 0 or i == total_normal:
            print(f"  Processed {i}/{total_normal} normal users (Success: {success_count}, Errors: {error_count})")
    
    print(f"Normal Users Updated! Success: {success_count}, Errors: {error_count}")


def update_split_recipient_users():
    split_recipient_users = CDUser.objects.filter(
        role=CDUser.ROLES.SPLIT_RECIPIENT,
    )

    total_split_recipients = split_recipient_users.count()
    print(f"Processing {total_split_recipients} split recipient users...")

    success_count = 0
    error_count = 0

    for i, user in enumerate(split_recipient_users, 1):
        try:
            # Split recipients use owner's ratio, calculated in the function
            normal_processor.refresh_due_balance_for_split_recipient(
                username=user.email,
            )
            success_count += 1
        except Exception as e:
            error_count += 1
            print(f"  ERROR processing split recipient user {user.email}: {str(e)}")
            traceback.print_exc()
            # Continue processing other users even if this one fails
        
        if i % 10 == 0 or i == total_split_recipients:
            print(f"  Processed {i}/{total_split_recipients} split recipient users (Success: {success_count}, Errors: {error_count})")
    
    print(f"Split Recipient Users Updated! Success: {success_count}, Errors: {error_count}")


def trigger():
    try:
        print("=" * 60)
        print("Starting Due Amount Refresh Process")
        print("=" * 60)
        
        truncate_aggregate_relation()
        update_admin_users()
        update_intermediate_users()
        update_normal_users()
        update_split_recipient_users()
        
        print("=" * 60)
        print("Due Amount Refresh Process Completed!")
        print("=" * 60)
    except Exception as e:
        print(f"FATAL ERROR in trigger(): {str(e)}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    try:
        trigger()
    except Exception as e:
        print(f"Script failed with error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
