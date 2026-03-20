import ast
import base64
import os
import threading
import time
import traceback
import wave
from collections import defaultdict
from datetime import datetime
from django.utils import timezone
import secrets
import string

import pandas as pd
from django.core.mail import send_mail
from releases.models import (
    Artist,
    CDUser,
    Label,
    RelatedArtists,
    Release,
    Track,
    UniqueCode,
    Metadata,
    Royalties,
    SplitReleaseRoyalty,
    DistributionJob,
    ARTIST_ROLES,
)
from commons.sql_client import sql_client
from constants import *
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection
from django.db import close_old_connections
from django.db.models import Q, Sum, Max
from django.db.models.functions import Upper
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from handlers import DataValidator, FileHandler
from django.views.decorators.http import require_POST, require_GET
import json
from django.contrib.auth.decorators import login_required

from .processor import processor


def create_user_if_not_exists(recipient_email, sharing_user):
    """
    Create a new CDUser if the recipient_email doesn't exist.
    Returns the user object (existing or newly created).
    For split royalty recipients, creates user with SPLIT_RECIPIENT role and password #Coin7474.
    Split recipients always belong to admin@admin.com by default.
    """
    recipient_email_lower = recipient_email.lower().strip()
    
    # Get admin user as parent
    try:
        admin_user = CDUser.objects.get(email__iexact='admin@admin.com')
    except CDUser.DoesNotExist:
        admin_user = None
        print("Warning: admin@admin.com not found, split recipient will have no parent")
    
    try:
        # Try to get existing user (case-insensitive search)
        user = CDUser.objects.get(email__iexact=recipient_email_lower)
        # If user already exists, DON'T change their role
        # They can receive splits regardless of their role (admin/normal/intermediate)
        # Only set parent to admin if they are a split recipient
        if user.role == CDUser.ROLES.SPLIT_RECIPIENT:
            # For existing split recipients, ensure parent is set to admin
            if admin_user and user.parent != admin_user:
                user.parent = admin_user
                user.save()
                print(f"Updated parent for {recipient_email_lower} to admin@admin.com")
        else:
            # User exists with a different role (admin/normal/intermediate)
            # Keep their original role - they can still receive splits
            print(f"User {recipient_email_lower} already exists with role {user.role}, keeping original role")
        return user
    except CDUser.DoesNotExist:
        # Create new user with SPLIT_RECIPIENT role and default password
        user = CDUser.objects.create(
            email=recipient_email_lower,
            first_name="",
            last_name="",
            role=CDUser.ROLES.SPLIT_RECIPIENT,
            contact_phone="",
            company_contact_phone="",
            pan="",
            parent=admin_user  # Set parent to admin@admin.com
        )
        user.set_password("#Coin7474")
        user.save()
        print(f"Created new user {recipient_email_lower} with SPLIT_RECIPIENT role, parent: admin@admin.com")
        
        # Send welcome email
        try:
            login_url = f"https://royalties.coindigital.in/login/"
            
            subject = f"You've Received a Split Royalty from {sharing_user.email}"
            message = f"""
Hello,

You've received a split royalty from {sharing_user.email}.

To access your royalties dashboard:
1. Login at: {login_url}
2. Email: {recipient_email}
3. Password: #Coin7474
4. You can change your password after logging in.

You will be able to see:
- Dashboard with your royalty overview
- Royalties from tracks where you are a recipient
- Analytics and payment information

Best regards,
The Royalty Team
            """
            
            send_mail(
                subject=subject,
                message=message.strip(),
                from_email=settings.EMAIL_FROM,
                recipient_list=[recipient_email],
                fail_silently=False
            )
        except Exception as e:
            # Log email error but don't fail user creation
            print(f"Email sending failed for {recipient_email}: {str(e)}")
        
        return user


def delete_s3_folder(bucket_name, folder_prefix):
    s3client = processor.get_s3_client()
    objects_to_delete = s3client.list_objects_v2(
        Bucket=bucket_name, Prefix=folder_prefix
    )
    try:
        if "Contents" in objects_to_delete:
            for obj in objects_to_delete["Contents"]:
                s3client.delete_object(Bucket=bucket_name, Key=obj["Key"])
    except Exception as e:
        print(e)
    return


def delete_release(primary_uuid):
    delete_success = True
    release = Release.objects.get(pk=primary_uuid)
    try:
        try:
            if not release.published:
                delete_s3_folder(
                    settings.AWS_STORAGE_BUCKET_NAME, f"unassigned/{primary_uuid}/"
                )
            else:
                if release.upc:
                    delete_s3_folder(
                        settings.AWS_STORAGE_BUCKET_NAME, f"{release.upc}/"
                    )
        except:
            pass
        for track in Track.objects.filter(release=release):
            RelatedArtists.objects.filter(relation_key="track", track=track).delete()
            track.delete()
        RelatedArtists.objects.filter(relation_key="release", release=release).delete()
        release.delete()
    except:
        delete_success = False
    return delete_success


def has_release_access(user, release_uuid):
    if user.role == CDUser.ROLES.NORMAL:
        return Release.objects.filter(created_by=user, id=release_uuid).exists()
    elif user.role == CDUser.ROLES.INTERMEDIATE:
        children = CDUser.objects.filter(parent=user)
        children = list(children.values_list("id", flat=True))
        children.append(user)
        return Release.objects.filter(created_by__in=children, id=release_uuid).exists()
    elif user.role == CDUser.ROLES.MEMBER:
        leader = get_leader(user)
        return Release.objects.filter(created_by=leader, id=release_uuid).exists()
    else:
        return True


def unpublish_release_view(
    request, unpublish_primary_uuid, unpublish_upc, unpublish_requester
):
    if (
        request.user.is_authenticated
        and request.user.is_active
        and has_release_access(request.user, unpublish_primary_uuid)
    ):
        if request.method == "GET":
            # Set is_published = False, published_at_time = Null, reset approval_status so it can be re-submitted
            release = Release.objects.get(pk=unpublish_primary_uuid)
            release.published_at = None
            release.published = False
            release.approval_status = "draft"
            release.save(update_fields=["published", "published_at", "approval_status"])

            return JsonResponse({"message": "Release has been unpublished!"})
        else:
            return JsonResponse({"message": "Invalid Request!"})
    else:
        return JsonResponse({"message": "Authentication Failed!"})


def get_leader(user):
    leader = CDUser.objects.get(id=user.pk).parent
    return leader


# ================= ORIGINAL FUNCTION (FOR REFERENCE) ===================
# def is_active(username):
#     try:
#         df = sql_client.read_sql(
#             f"select status from user_login where username = '{username}';"
#         )
#         if df["status"].tolist()[0]:
#             return True
#     except Exception as e:
#         print(e)
#         df = sql_client.read_sql(
#             f"select * from teams where member_username like '{username}'"
#         )
#         if len(df):
#             return True
#         return False
# ===================================================================

# New ORM-based implementation
def is_active(username):
    try:
        user = CDUser.objects.get(email=username)
        return user.is_active
    except CDUser.DoesNotExist:
        print(f"User {username} does not exist")
        return None


def delivered_releases(request):
    if request.user.is_authenticated and request.user.is_active:
        if request.method == "GET":
            return render(
                request,
                "volt_releases.html",
                context={
                    "username": request.user,
                    "requesting_user_role": request.user.role,
                    "request_type": "delivered",
                },
            )
        else:
            return HttpResponseNotFound("Invalid request!")
    else:
        return HttpResponseNotFound("Authentication Failed!")


def pending_approval_releases(request):
    """Admin/staff list of releases pending approval (for Approve & send to Sonosuite)."""
    if not request.user.is_authenticated or not request.user.is_active:
        return HttpResponseNotFound("Authentication Failed!")
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return HttpResponseNotFound("Only admin or staff can view pending approval.")
    if request.method != "GET":
        return HttpResponseNotFound("Invalid request!")
    return render(
        request,
        "volt_releases.html",
        context={
            "username": request.user,
            "requesting_user_role": request.user.role,
            "request_type": "pending_approval",
        },
    )


def fetch_unique_codes(request, code_type):
    if (
        request.user.is_authenticated
        and request.user.is_active
        and request.user.role == CDUser.ROLES.ADMIN
    ):
        codes = UniqueCode.objects.filter(assigned=False, type=code_type)
        rows = ""
        for _code in codes:
            rows += f"<tr><td>{_code.code}</td></tr>"

        table = f"""
            <table class="table table-hover" id="remaining_{code_type}_datatable">
                <thead>
                    <tr>
                        <th>{code_type.upper()} Code<th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        """
        return JsonResponse({"table": table})
    else:
        return HttpResponseNotFound("<h2>Authentication Failed!</h2>")


@csrf_exempt
def release_codes_upload(request):
    if (
        request.user.is_authenticated
        and request.user.is_active
        and request.user.role == CDUser.ROLES.ADMIN
    ):
        codes_file = request.FILES["codes_file"].file
        file_handler = FileHandler(codes_file, "codes", "excel")
        validator = DataValidator(
            file_handler.data, [codes_validations], file_handler.file_type
        )
        status, validator_response = validator.validate()
        if status:
            status, validator_response = validator.process()
            if status:
                try:
                    for index, row in validator.data.iterrows():
                        code_instance = UniqueCode.objects.create(
                            code=row["code"], type=row["type"], assigned=False
                        )
                        code_instance.save()
                    message = f"Assignable Codes updated!"
                except:
                    message = "All checks passed, but there was still an error and file could not be uploaded. \nPlease check if there is any code in this file, which is already in the system."
            else:
                message = validator_response
        else:
            message = validator_response

        return JsonResponse({"message": message})
    else:
        return JsonResponse({"message": "Authentication Failed!"})


@csrf_exempt
def releases_paginated(request, request_type):
    if request.user.is_authenticated and request.user.is_active:
        if request.method == "GET":
            # Initialize base queryset
            releases = Release.objects.all()
            
            # Apply request type filtering
            if request_type == "delivered":
                releases = releases.filter(published=True).order_by("-published_at")
            elif request_type == "pending_approval":
                releases = releases.filter(
                    approval_status__iexact="pending_approval"
                ).order_by("-submitted_for_approval_at", "-updated_at", "-original_release_date")
            else:
                releases = releases.filter(published=False).order_by(
                    "-original_release_date"
                )

            # Apply role-based filtering
            if request.user.role == CDUser.ROLES.NORMAL:
                releases = releases.filter(created_by=request.user)
            elif request.user.role == CDUser.ROLES.INTERMEDIATE:
                children = list(
                    CDUser.objects.filter(parent=request.user).values_list(
                        "id", flat=True
                    )
                )
                children.append(request.user.id)
                releases = releases.filter(created_by__in=children)
            elif request.user.role == CDUser.ROLES.MEMBER:
                leader = get_leader(request.user)
                releases = releases.filter(created_by=leader)
            elif request.user.role == CDUser.ROLES.ADMIN:
                # For admin, we already have all releases, no need to reassign
                pass
            else:
                pass

            # Get pagination parameters
            items_per_page = int(request.GET.get("length", 10))
            start = int(request.GET.get("start", 0))
            search_term = request.GET.get("search[value]", "")

            # Calculate total count before search filtering
            total_count = releases.count()

            # Apply search filtering if search term exists
            if search_term:
                releases = releases.filter(
                    Q(title__icontains=search_term)
                    | Q(label__label__icontains=search_term)
                    | Q(upc__icontains=search_term)
                )

            # Calculate filtered count after search
            filtered_count = releases.count()

            # Apply database-level pagination
            filtered_releases = releases[start : start + items_per_page]

            data = []
            for filtered_release in filtered_releases:
                if (
                    request_type != "delivered"
                    and filtered_release.original_release_date
                ):
                    release_date = filtered_release.original_release_date.strftime(
                        "%Y-%m-%d"
                    )
                elif request_type == "delivered" and filtered_release.published_at:
                    release_date = filtered_release.published_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                else:
                    release_date = ""

                submitted_date = ""
                if request_type == "pending_approval" and filtered_release.submitted_for_approval_at:
                    submitted_date = filtered_release.submitted_for_approval_at.strftime("%Y-%m-%d %H:%M")
                elif request_type == "pending_approval" and filtered_release.updated_at:
                    submitted_date = filtered_release.updated_at.strftime("%Y-%m-%d %H:%M")

                row = {
                    "Download": filtered_release.pk,
                    "Cover Art": (
                        filtered_release.cover_art_url
                        if filtered_release.cover_art_url
                        else f"/static/img/{settings.LOGO['light']}"
                    ),
                    "Title": filtered_release.title,
                    "Label": (
                        filtered_release.label.label
                        if filtered_release.label
                        else ""
                    ),
                    "Genre": filtered_release.primary_genre,
                    "UPC": filtered_release.upc,
                    "Format": filtered_release.album_format,
                    "ReleaseDate": release_date,
                    "Edit": filtered_release.pk,
                    "Status": (
                        "Pending approval"
                        if request_type == "pending_approval"
                        else ("Delivered" if request_type == "delivered" else "Draft")
                    ),
                }
                if request_type == "pending_approval":
                    row["Submitted"] = submitted_date
                data.append(row)
            return JsonResponse(
                {
                    "data": data,
                    "recordsTotal": total_count,
                    "recordsFiltered": filtered_count,
                    "request_type": request_type,
                }
            )
        else:
            return HttpResponseNotFound("Invalid request!")
    else:
        return HttpResponseNotFound("Authentication Failed!")


@csrf_exempt
def releases(request):
    if request.user.is_authenticated and request.user.is_active:
        if request.method == "GET":
            return render(
                request,
                "volt_releases.html",
                context={
                    "username": request.user,
                    "request_type": "all",
                    "requesting_user_role": request.user.role,
                },
            )
        if request.method == "POST":
            try:
                new_release_name = request.POST.get("new_release_name", None)

                if new_release_name == "" or new_release_name is None:
                    return JsonResponse({"message": "Provide a Release Name"}, status=400)
                creator = request.user
                if request.user.role == CDUser.ROLES.MEMBER:
                    try:
                        creator = get_leader(request.user)
                    except Exception:
                        creator = None
                    if creator is None:
                        return JsonResponse(
                            {"message": "Your account is not properly linked to a team. Please contact support."},
                            status=400,
                        )

                release = Release.objects.create(
                    title=new_release_name.strip(),
                    created_by=creator,
                    apple_music_commercial_model=Release.APPLE_MUSIC_COMMERCIAL_MODEL.BOTH,
                )
                return JsonResponse({"primary_uuid": str(release.pk)})
            except Exception as e:
                return JsonResponse(
                    {"message": str(e) if str(e) else "Release could not be created. Please try again."},
                    status=500,
                )
    else:
        return HttpResponseNotFound("Authentication Failed!")


@csrf_exempt
def release_info(request, primary_uuid):
    if (
        request.user.is_authenticated
        and request.user.is_active
        and has_release_access(request.user, primary_uuid)
    ):
        PAGE_NAME = "release_info"
        TABLE_NAME = "rl_release"
        if request.method == "GET":
            creator = request.user
            if request.user.role == CDUser.ROLES.MEMBER:
                creator = get_leader(request.user)
            labels = Label.objects.filter(user=creator)
            artists = Artist.objects.filter(user=creator)
            artists_context = []
            for artist in artists:
                artists_context.append({"name": artist.name, "id": artist.pk})
            release = Release.objects.get(id=primary_uuid)
            rl_data = processor.context_generator(release, TABLE_NAME)
            # Add Copyright Holder and Phonogram Rights Holder data
            rl_data["copyright_holder_year"] = release.license_holder_year or "2026"
            rl_data["copyright_holder_name"] = release.license_holder_name or ""
            rl_data["phonogram_rights_holder_year"] = release.copyright_recording_year or "2026"
            rl_data["phonogram_rights_holder_name"] = release.copyright_recording_text or ""
            rl_info = processor.get_release_name(primary_uuid)
            if not rl_info:
                rl_info = ["", 0]
            labels_list = list(labels.values_list("label", flat=True))
            if rl_data["labels"]:
                labels_list.append(rl_data["labels"])
            release_created_by_email = release.created_by.email if release.created_by else ""
            return render(
                request,
                "volt_releases_info.html",
                context={
                    "username": request.user,
                    "primary_uuid": primary_uuid,
                    "labels": labels_list,
                    "artists": artists_context,
                    "is_published": rl_info[1],
                    "rl_data": rl_data,
                    "page_name": PAGE_NAME,
                    "release_title": rl_info[0],
                    "requesting_user_role": request.user.role,
                    "release_created_by_email": release_created_by_email,
                },
            )
        if request.method == "POST":
            try:
                data = {
                    "release_title": request.POST.get("release_title"),
                    "remix_version": request.POST.get("remix_version"),
                    "label": request.POST.get("labels"),
                    "primary_genre": request.POST.get("primary_genere"),
                    "secondary_genre": request.POST.get("secondary_genere"),
                    "language": request.POST.get("language"),
                    "album_format": request.POST.get("album_format"),
                    "upc_code": request.POST.get("upc_code"),
                    "reference_number": request.POST.get("reference_number"),
                    "gr_id": request.POST.get("gr_id"),
                    "release_description": request.POST.get("release_description"),
                    "created_by": request.POST.get("created_by"),
                    "copyright_holder_year": request.POST.get("copyright_holder_year", ""),
                    "copyright_holder_name": request.POST.get("copyright_holder_name", ""),
                    "phonogram_rights_holder_year": request.POST.get("phonogram_rights_holder_year", ""),
                    "phonogram_rights_holder_name": request.POST.get("phonogram_rights_holder_name", ""),
                }
                from releases.upc_utils import normalize_upc_to_13
                # Check if provided upc code already exists
                current_release = Release.objects.get(pk=primary_uuid)
                
                # Update release title if provided
                if data["release_title"]:
                    current_release.title = data["release_title"]
                if data["upc_code"]:
                    provided_upc = normalize_upc_to_13(data["upc_code"])
                    if str(current_release.upc).strip() == str(provided_upc).strip():
                        pass
                    else:
                        if Release.objects.filter(upc=provided_upc).exists():
                            return JsonResponse(
                                {
                                    "message": "Provided UPC already exists in the system. Please use a new UPC and try again!"
                                },
                                status=400,
                            )
                release_artists = defaultdict(list)
                for key in dict(request.POST):
                    if key.startswith("artist_release_"):
                        raw_value = request.POST.get(key)
                        if not raw_value:
                            continue
                        try:
                            value = ast.literal_eval(raw_value)
                            role = value[0]
                            artist_id = int(value[1]) if isinstance(value[1], (int, str)) else value[1]
                            release_artists[role].append(artist_id)
                        except (ValueError, SyntaxError, TypeError, IndexError):
                            continue

                if (
                    "Primary Artist" in release_artists.keys()
                    and "Performer" in release_artists.keys()
                ):
                    if len(
                        set(release_artists["Primary Artist"]).intersection(
                            set(release_artists["Performer"])
                        )
                    ):
                        return JsonResponse(
                            {
                                "message": "The values for Primary Artist and Performer can not be same!"
                            },
                            status=400,
                        )

                # Primary Artist and Featuring/Featured Artist cannot be the same artist
                primary_artist_ids = set(release_artists.get("Primary Artist", []))
                featuring_roles = ("Featuring", "Featured Artist")
                for role in featuring_roles:
                    if role in release_artists:
                        overlap = primary_artist_ids.intersection(set(release_artists[role]))
                        if overlap:
                            return JsonResponse(
                                {"message": "An artist cannot be both Primary Artist and Featuring on the same release."},
                                status=400,
                            )

                RelatedArtists.objects.filter(release=current_release).delete()
                for related_role in release_artists.keys():
                    role_artist_ids = release_artists[related_role]
                    for role_artist_id in role_artist_ids:
                        artist = Artist.objects.filter(pk=role_artist_id).first()
                        if not artist:
                            continue
                        instance = RelatedArtists.objects.create(
                            relation_key="release",
                            release=current_release,
                            artist=artist,
                            role=related_role,
                        )
                        instance.save()
                path = "media/"
                try:
                    dir_list = os.listdir(path) if os.path.isdir(path) else []
                except OSError:
                    dir_list = []
                files = [
                    i
                    for i in dir_list
                    if os.path.isfile(os.path.join(path, i)) and primary_uuid in i
                ]
                if files:
                    # Since there is a case where we don't have upc if user wants it to be assigned as new,
                    # so we will have to set primary_uuid for the time being
                    cover_art = ContentFile(open("media/" + files[0], "rb").read())
                    extension = files[0].split(".")[-1]
                    default_storage.save(
                        f"unassigned/{primary_uuid}/{primary_uuid}.{extension}", cover_art
                    )
                    stored_cover_art_url = default_storage.url(
                        f"unassigned/{primary_uuid}/{primary_uuid}.{extension}"
                    )
                    current_release.cover_art_url = stored_cover_art_url
                    try:
                        os.remove(f"media/{files[0]}")
                    except OSError:
                        pass

                current_release.remix_version = data["remix_version"] or ""

                creator = current_release.created_by
                if request.user.role == CDUser.ROLES.MEMBER:
                    creator = get_leader(request.user)
                labels = Label.objects.filter(user=creator, label=data["label"])
                if len(labels):
                    current_release.label = labels.first()

                current_release.primary_genre = data["primary_genre"] or current_release.primary_genre
                current_release.secondary_genre = (
                    data["secondary_genre"] if data["secondary_genre"] else ""
                )
                current_release.language = data["language"] or current_release.language
                # Normalize album_format to model choice value (single, ep, album)
                raw_album = (data["album_format"] or "").strip().lower()
                if raw_album in [Release.ALBUM_FORMAT.SINGLE, Release.ALBUM_FORMAT.EP, Release.ALBUM_FORMAT.ALBUM]:
                    current_release.album_format = raw_album
                elif raw_album in ("single", "ep", "album"):
                    current_release.album_format = raw_album
                # else keep existing value
                current_release.reference_number = data["reference_number"] or ""
                current_release.grid = data["gr_id"] or ""
                current_release.upc = normalize_upc_to_13(data["upc_code"] or "")
                current_release.description = data["release_description"] or ""

                # Map Copyright Holder and Phonogram Rights Holder to existing model fields
                if data["copyright_holder_year"]:
                    current_release.license_holder_year = data["copyright_holder_year"]
                if data["copyright_holder_name"]:
                    current_release.license_holder_name = data["copyright_holder_name"]
                if data["phonogram_rights_holder_year"]:
                    current_release.copyright_recording_year = data["phonogram_rights_holder_year"]
                if data["phonogram_rights_holder_name"]:
                    current_release.copyright_recording_text = data["phonogram_rights_holder_name"]

                current_release.save()
                return JsonResponse(
                    {"success": "success", "message": "Release draft saved successfully!"}
                )
            except Exception as e:
                return JsonResponse(
                    {"message": str(e) if str(e) else "Request failed. Please try again."},
                    status=500,
                )
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


@csrf_exempt
def licenses_info(request, primary_uuid):
    if (
        request.user.is_authenticated
        and request.user.is_active
        and has_release_access(request.user, primary_uuid)
    ):
        PAGE_NAME = "licenses_info"
        release = Release.objects.get(pk=primary_uuid)

        if request.method == "GET":
            print(release.digital_release_date)
            print(release.original_release_date)
            rl_data = {
                "price_category": release.price_category,
                "digital_release_date": (
                    release.digital_release_date.strftime("%m/%d/%Y")
                    if release.digital_release_date
                    else ""
                ),
                "original_release_date": (
                    release.original_release_date.strftime("%m/%d/%Y")
                    if release.original_release_date
                    else ""
                ),
                "license_type_format_toggle": release.license_type,
                "license_holder_year": release.license_holder_year,
                "license_holder_name": release.license_holder_name,
                "copyright_recording_year": release.copyright_recording_year,
                "copyright_recording_name": release.copyright_recording_text,
                "territories": release.territories,
            }
            return render(
                request,
                "volt_licenses_info.html",
                context={
                    "username": request.user,
                    "primary_uuid": primary_uuid,
                    "rl_data": rl_data,
                    "page_name": PAGE_NAME,
                    "release_title": release.title,
                    "is_published": release.published,
                    "requesting_user_role": request.user.role,
                },
            )
        if request.method == "POST":
            release.price_category = request.POST.get("price_category")
            print(request.POST.get("digital_release_date"))
            print(request.POST.get("original_release_date"))
            dig_release_date = (
                request.POST.get("digital_release_date")
                if request.POST.get("digital_release_date") != ""
                else None
            )
            if dig_release_date:
                dig_release_date = dig_release_date.split("/")
                release.digital_release_date = (
                    f"{dig_release_date[2]}-{dig_release_date[0]}-{dig_release_date[1]}"
                )

            orig_release_date = (
                request.POST.get("original_release_date")
                if request.POST.get("original_release_date") != ""
                else None
            )
            if orig_release_date:
                orig_release_date = orig_release_date.split("/")
                release.original_release_date = f"{orig_release_date[2]}-{orig_release_date[0]}-{orig_release_date[1]}"

            release.license_type = request.POST.get("license_type_format_toggle")
            release.license_holder_year = request.POST.get("license_holder_year")
            release.license_holder_name = request.POST.get("license_holder_name")
            release.copyright_recording_year = request.POST.get(
                "copyright_recording_year"
            )
            release.copyright_recording_text = request.POST.get(
                "copyright_recording_name"
            )
            release.save()
            return JsonResponse(
                {"success": "success", "message": "License draft saved successfully!"}
            )
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


@csrf_exempt
def tracks_info(request, primary_uuid):
    print(request)
    if (
        request.user.is_authenticated
        and request.user.is_active
        and has_release_access(request.user, primary_uuid)
    ):
        PAGE_NAME = "tracks_info"
        release = Release.objects.get(pk=primary_uuid)
        try:
            tracks = Track.objects.filter(release=release).order_by("sequence", "id")
        except Exception:
            tracks = Track.objects.filter(release=release).order_by("id")
        if request.method == "GET":
            can_create = True
            is_single_track = False
            if release.album_format.lower() == release.ALBUM_FORMAT.SINGLE:
                is_single_track = True
                if (
                    len(tracks) > 0
                    and release.album_format.lower() == release.ALBUM_FORMAT.SINGLE
                ):
                    can_create = False
            rl_data = {"all_tracks": []}
            for _track in tracks:
                rl_data["all_tracks"].append(
                    {
                        "title": _track.title,
                        "primary_track_uuid": _track.pk,
                        "track_link": f"/releases/tracks_info/{release.pk}/track/{_track.pk}",
                        "audio_path": _track.audio_track_url,
                    }
                )
            print({
                    "username": request.user,
                    "primary_uuid": primary_uuid,
                    "rl_data": rl_data,
                    "page_name": PAGE_NAME,
                    "can_create": can_create,
                    "is_published": release.published,
                    "is_single_track": is_single_track,
                    "release_title": release.title,
                    "requesting_user_role": request.user.role,
                })
            return render(
                request,
                "volt_tracks_info.html",
                context={
                    "username": request.user,
                    "primary_uuid": primary_uuid,
                    "rl_data": rl_data,
                    "page_name": PAGE_NAME,
                    "can_create": can_create,
                    "is_published": release.published,
                    "is_single_track": is_single_track,
                    "release_title": release.title,
                    "requesting_user_role": request.user.role,
                },
            )
        if request.method == "POST":
            new_track_title = request.POST.get("new_track_title", None)
            if new_track_title == "" or new_track_title is None:
                return JsonResponse({"error_message": "Provide a Track Name"}, status=400)

            creator = request.user
            if request.user.role == CDUser.ROLES.MEMBER:
                try:
                    creator = get_leader(request.user)
                except Exception:
                    creator = None
                if creator is None:
                    return JsonResponse(
                        {"error_message": "Your account is not properly linked to a team. Please contact support."},
                        status=400,
                    )

            max_seq = Track.objects.filter(release=release).aggregate(m=Max("sequence"))["m"] or 0
            _track = Track.objects.create(
                release=release,
                title=new_track_title.strip(),
                created_by=creator,
                primary_genre=release.primary_genre,
                language=release.language,
                publishing_rights_owner=release.license_holder_name,
                publishing_rights_year=release.license_holder_year,
                sequence=max_seq + 1,
            )
            _track.save()

            # Add SplitReleaseRoyalty for the creator if split royalties are enabled
            if creator.split_royalties_enabled:
                # Check if a split already exists for this user and track
                existing_split = SplitReleaseRoyalty.objects.filter(
                    user_id=creator,
                    release_id=release,
                    track_id=_track,
                    recipient_email=creator.email
                ).exists()
                if not existing_split:
                    SplitReleaseRoyalty.objects.create(
                        user_id=creator,
                        release_id=release,
                        track_id=_track,
                        recipient_name=f"{creator.first_name} {creator.last_name}".strip() or creator.email,
                        recipient_email=creator.email,
                        recipient_role="Primary Artist",
                        recipient_percentage=100.0
                    )

            related_release_artists = RelatedArtists.objects.filter(
                relation_key="release", release=release
            )
            for _related_release_artist in related_release_artists:
                related_artist_instance = RelatedArtists.objects.create(
                    relation_key="track",
                    track=_track,
                    artist=_related_release_artist.artist,
                    role=_related_release_artist.role,
                )
                related_artist_instance.save()

            return JsonResponse(
                {
                    "release_primary_uuid": primary_uuid,
                    "primary_track_uuid": _track.pk,
                }
            )
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


def _tracks_owner_user(request):
    """User whose 'catalog' we show: leader for MEMBER, else request.user."""
    if request.user.role == CDUser.ROLES.MEMBER:
        return get_leader(request.user)
    return request.user


@csrf_exempt
def catalog_tracks(request, primary_uuid):
    """GET: List tracks from releases created by this user (excluding current release). For 'From Catalog' picker."""
    if not (request.user.is_authenticated and request.user.is_active and has_release_access(request.user, primary_uuid)):
        return JsonResponse({"error": "Not authorized"}, status=403)
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"error": "Release not found"}, status=404)
    owner = _tracks_owner_user(request)
    # Tracks from releases created by this user, excluding current release; only with audio and ISRC (delivery rule: every delivered track has ISRC)
    qs = (
        Track.objects.filter(release__created_by=owner)
        .exclude(release=release)
        .exclude(audio_track_url="")
        .exclude(isrc="")
        .filter(audio_track_url__isnull=False)
        .select_related("release")
        .order_by("release__title", "sequence", "id")
    )
    out = []
    for t in qs:
        out.append({
            "id": t.pk,
            "title": t.title,
            "release_title": getattr(t.release, "title", ""),
            "audio_track_url": t.audio_track_url or "",
            "isrc": (t.isrc or "").strip(),
        })
    return JsonResponse({"tracks": out})


@csrf_exempt
def add_from_catalog(request, primary_uuid):
    """POST: Add a track from catalog (catalog_track_id) to current release. Copies metadata and audio reference."""
    if not (request.user.is_authenticated and request.user.is_active and has_release_access(request.user, primary_uuid)):
        return JsonResponse({"error": "Not authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        release = Release.objects.get(pk=primary_uuid)
        catalog_track_id = request.POST.get("catalog_track_id")
        if not catalog_track_id:
            return JsonResponse({"error": "catalog_track_id required"}, status=400)
        catalog_track = Track.objects.get(pk=catalog_track_id)
    except Release.DoesNotExist:
        return JsonResponse({"error": "Release not found"}, status=404)
    except Track.DoesNotExist:
        return JsonResponse({"error": "Track not found"}, status=404)
    owner = _tracks_owner_user(request)
    if catalog_track.release.created_by_id != owner.pk:
        return JsonResponse({"error": "You can only add tracks from your own catalog"}, status=403)
    if catalog_track.release_id == release.pk:
        return JsonResponse({"error": "Track already belongs to this release"}, status=400)
    creator = request.user if request.user.role != CDUser.ROLES.MEMBER else get_leader(request.user)
    max_seq = Track.objects.filter(release=release).aggregate(m=Max("sequence"))["m"] or 0
    new_track = Track.objects.create(
        release=release,
        title=catalog_track.title,
        created_by=creator,
        primary_genre=catalog_track.primary_genre,
        language=catalog_track.language,
        publishing_rights_owner=catalog_track.publishing_rights_owner or release.license_holder_name,
        publishing_rights_year=catalog_track.publishing_rights_year or release.license_holder_year,
        remix_version=getattr(catalog_track, "remix_version", "") or "",
        audio_track_url=catalog_track.audio_track_url or "",
        audio_wav_url=getattr(catalog_track, "audio_wav_url", "") or "",
        audio_mp3_url=getattr(catalog_track, "audio_mp3_url", "") or "",
        audio_flac_url=getattr(catalog_track, "audio_flac_url", "") or "",
        audio_uploaded_at=getattr(catalog_track, "audio_uploaded_at", None),
        isrc=getattr(catalog_track, "isrc", "") or "",
        secondary_genre=getattr(catalog_track, "secondary_genre", "") or "",
        explicit_lyrics=getattr(catalog_track, "explicit_lyrics", Track.EXPLICIT_LYRICS.NOT_EXPLICIT) or Track.EXPLICIT_LYRICS.NOT_EXPLICIT,
        sequence=max_seq + 1,
        start_point=getattr(catalog_track, "start_point", "") or "",
        notes=getattr(catalog_track, "notes", "") or "",
    )
    related_release_artists = RelatedArtists.objects.filter(relation_key="release", release=release)
    for ra in related_release_artists:
        RelatedArtists.objects.create(relation_key="track", track=new_track, artist=ra.artist, role=ra.role)
    if creator.split_royalties_enabled and not SplitReleaseRoyalty.objects.filter(user_id=creator, release_id=release, track_id=new_track).exists():
        SplitReleaseRoyalty.objects.create(
            user_id=creator,
            release_id=release,
            track_id=new_track,
            recipient_name=f"{creator.first_name} {creator.last_name}".strip() or creator.email,
            recipient_email=creator.email,
            recipient_role="Primary Artist",
            recipient_percentage=100.0,
        )
    return JsonResponse({
        "release_primary_uuid": primary_uuid,
        "primary_track_uuid": new_track.pk,
        "title": new_track.title,
    })


@csrf_exempt
def reorder_tracks(request, primary_uuid):
    """POST: Save track order. Body: JSON { \"track_ids\": [id1, id2, ...] } or form track_ids=id1&track_ids=id2."""
    if not (request.user.is_authenticated and request.user.is_active and has_release_access(request.user, primary_uuid)):
        return JsonResponse({"error": "Not authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"error": "Release not found"}, status=404)
    try:
        if request.content_type and "application/json" in request.content_type:
            data = json.loads(request.body)
            track_ids = data.get("track_ids") or []
        else:
            track_ids = request.POST.getlist("track_ids")
        track_ids = [str(x).strip() for x in track_ids if str(x).strip()]
    except Exception:
        return JsonResponse({"error": "Invalid payload"}, status=400)
    tracks = list(Track.objects.filter(release=release, pk__in=track_ids))
    if len(tracks) != len(track_ids):
        return JsonResponse({"error": "Some track IDs do not belong to this release"}, status=400)
    for seq, tid in enumerate(track_ids, start=1):
        t = next((x for x in tracks if str(x.pk) == str(tid)), None)
        if t:
            t.sequence = seq
            t.save(update_fields=["sequence"])
    return JsonResponse({"success": True, "message": "Order saved"})


@csrf_exempt
def single_tracks_info(request, primary_uuid, primary_track_uuid):
    if (
        request.user.is_authenticated
        and request.user.is_active
        and has_release_access(request.user, primary_uuid)
    ):
        PAGE_NAME = "single_tracks_info"
        TABLE_NAME = "rl_tracks"
        try:
            _release = Release.objects.get(pk=primary_uuid)
            _track = Track.objects.get(pk=primary_track_uuid)
        except (Release.DoesNotExist, Track.DoesNotExist):
            return HttpResponseNotFound("<h1>Release or Track not found!</h1>")

        if request.method == "GET":
            rl_data = processor.context_generator(_track, TABLE_NAME)
            creator = request.user
            if request.user.role == CDUser.ROLES.MEMBER:
                creator = get_leader(request.user)

            artists_context = [
                {"name": artist.name, "id": artist.id}
                for artist in Artist.objects.filter(user=creator)
            ]
            editable = True
            if request.user.role == CDUser.ROLES.ADMIN:
                pass
            elif (
                _release.album_format
                and _release.album_format.lower() == _release.ALBUM_FORMAT.SINGLE
            ):
                editable = False
            if creator.split_royalties_enabled:
                track_splits = SplitReleaseRoyalty.objects.filter(track_id=_track).select_related('user_id')
                splits_data = []
                for split in track_splits:
                    splits_data.append({
                        'id': split.id,
                        'recipient_name': split.recipient_name,
                        'recipient_email': split.recipient_email,
                        'recipient_role': split.recipient_role,
                        'recipient_percentage': split.recipient_percentage,
                        'owner_email': split.user_id.email,
                    })
            else:
                splits_data = []
            

            return render(
                request,
                "volt_single_track_info.html",
                context={
                    "username": request.user,
                    "primary_uuid": primary_uuid,
                    "primary_track_uuid": primary_track_uuid,
                    "artists": artists_context,
                    "rl_data": rl_data,
                    "is_published": _release.published,
                    "page_name": PAGE_NAME,
                    "release_title": _release.title,
                    "requesting_user_role": request.user.role,
                    "name_editable": editable,
                    "track_splits": splits_data,
                    "show_split_royalty_section": creator.split_royalties_enabled,
                    "artist_roles_list": ARTIST_ROLES, # Pass ARTIST_ROLES to the template
                },
            )
        if request.method == "POST":
            # Check if provided isrc code already exists
            creator = request.user
            if request.POST.get("isrc_code_track"):
                provided_isrc_code = str(request.POST.get("isrc_code_track")).upper()
                if str(_track.isrc.upper()) == str(provided_isrc_code):
                    pass
                else:
                    if (
                        Track.objects.annotate(isrc_upper=Upper("isrc"))
                        .filter(isrc_upper=provided_isrc_code.upper())
                        .exists()
                    ):
                        return JsonResponse(
                            {
                                "message": "Provided ISRC already exists in the system. Please use a new ISRC and try again!"
                            }
                        )

            release_artists = defaultdict(list)
            print(request.POST)
            for key in dict(request.POST):
                if key.startswith("artist_track_"):
                    value = ast.literal_eval(request.POST.get(key))
                    release_artists[value[0]].append(int(value[1]))
            if (
                "Primary Artist" in release_artists.keys()
                and "Performer" in release_artists.keys()
            ):
                if len(
                    set(release_artists["Primary Artist"]).intersection(
                        set(release_artists["Performer"])
                    )
                ):
                    return JsonResponse(
                        {"message": "The values for Primary Artist and Performer can not be same!"},
                        status=400,
                    )

            # Primary Artist and Featuring/Featured Artist cannot be the same artist
            primary_artist_ids = set(release_artists.get("Primary Artist", []))
            for role in ("Featuring", "Featured Artist"):
                if role in release_artists:
                    overlap = primary_artist_ids.intersection(set(release_artists[role]))
                    if overlap:
                        return JsonResponse(
                            {"message": "An artist cannot be both Primary Artist and Featuring on the same track."},
                            status=400,
                        )

            RelatedArtists.objects.filter(relation_key="track", track=_track).delete()
            for artist_role in release_artists.keys():
                for _id in release_artists[artist_role]:
                    artist_instance = RelatedArtists.objects.create(
                        relation_key="track",
                        track=_track,
                        artist=Artist.objects.get(pk=_id),
                        role=artist_role,
                    )
                    artist_instance.save()
            path = "media/"
            # Staged stereo master: media/{release_id}.wav (NOT *_atmos.wav — that is Dolby upload)
            files = [
                i
                for i in os.listdir(path)
                if os.path.isfile(os.path.join(path, i))
                and primary_uuid in i
                and "_atmos." not in i
            ]
            if files:
                wav_local = os.path.join(path, files[0])
                base_key = f"unassigned/{primary_uuid}/{primary_uuid}_{primary_track_uuid}"
                # 1. Save WAV to S3
                with open(wav_local, "rb") as f:
                    default_storage.save(f"{base_key}.wav", ContentFile(f.read()))
                _track.audio_wav_url = default_storage.url(f"{base_key}.wav")
                # 2. Convert WAV → FLAC and WAV → MP3 (same quality: bitrate/sample rate from WAV)
                from releases.audio_converter import wav_to_flac, wav_to_mp3
                flac_local = wav_to_flac(wav_local)
                mp3_local = wav_to_mp3(wav_local)
                if flac_local and os.path.isfile(flac_local):
                    with open(flac_local, "rb") as f:
                        default_storage.save(f"{base_key}.flac", ContentFile(f.read()))
                    _track.audio_flac_url = default_storage.url(f"{base_key}.flac")
                    try:
                        os.remove(flac_local)
                    except Exception:
                        pass
                # Primary URL for delivery: prefer FLAC, else WAV
                _track.audio_track_url = _track.audio_flac_url or _track.audio_wav_url
                if mp3_local and os.path.isfile(mp3_local):
                    with open(mp3_local, "rb") as f:
                        default_storage.save(f"{base_key}.mp3", ContentFile(f.read()))
                    _track.audio_mp3_url = default_storage.url(f"{base_key}.mp3")
                    try:
                        os.remove(mp3_local)
                    except Exception:
                        pass
                _track.audio_uploaded_at = timezone.now()
                try:
                    os.remove(wav_local)
                except Exception:
                    pass

            _track.remix_version = request.POST.get("remix_version_track")
            _track.title = request.POST.get("title_track")
            _track.primary_genre = request.POST.get("primary_genere_track")
            _track.secondary_genre = request.POST.get("secondary_genere_track")
            _track.isrc = request.POST.get("isrc_code_track")
            _track.iswc = request.POST.get("iswc_code_track")
            _track.publishing_rights_year = request.POST.get("publishing_rights_year")
            _track.publishing_rights_owner = request.POST.get("publishing_rights_name")
            _track.lyrics = request.POST.get("lyrics_track")
            _track.explicit_lyrics = request.POST.get("explicit_lyrics_track")
            _track.language = request.POST.get("language_track")
            _track.available_separately = (
                True
                if request.POST.get("available_seperatly_check_track") == "on"
                else False
            )
            _track.start_point = request.POST.get("start_point_time_track")
            _track.notes = request.POST.get("notes_track")
            _track.apple_music_dolby_atmos_url = (
                request.POST.get("apple_music_dolby_atmos_url") or ""
            ).strip()
            _track.apple_music_dolby_atmos_isrc = (
                request.POST.get("apple_music_dolby_atmos_isrc") or ""
            ).strip().upper()

            # Staged Dolby Atmos BWF (after form fields — overwrites URL when user just uploaded)
            atmos_staged = os.path.join(
                path, f"{primary_uuid}_{primary_track_uuid}_atmos.wav"
            )
            if os.path.isfile(atmos_staged):
                base_key_atmos = (
                    f"unassigned/{primary_uuid}/{primary_uuid}_{primary_track_uuid}_atmos"
                )
                with open(atmos_staged, "rb") as f:
                    default_storage.save(f"{base_key_atmos}.wav", ContentFile(f.read()))
                _track.apple_music_dolby_atmos_url = default_storage.url(
                    f"{base_key_atmos}.wav"
                )
                try:
                    os.remove(atmos_staged)
                except Exception:
                    pass

            _track.save()

            # Add SplitReleaseRoyalty for the creator if split royalties are enabled
            if creator.split_royalties_enabled:
                # Check if a split already exists for this user and track
                existing_split = SplitReleaseRoyalty.objects.filter(
                    user_id=creator,
                    release_id=_release,
                    track_id=_track,
                    recipient_email=creator.email
                ).exists()
                if not existing_split:
                    SplitReleaseRoyalty.objects.create(
                        user_id=creator,
                        release_id=_release,
                        track_id=_track,
                        recipient_name=f"{creator.first_name} {creator.last_name}".strip() or creator.email,
                        recipient_email=creator.email,
                        recipient_role="Primary Artist",
                        recipient_percentage=100.0
                    )

            return JsonResponse(
                {"success": "success", "message": "Track draft saved successfully!"}
            )
        if request.method == "DELETE":
            RelatedArtists.objects.filter(relation_key="track", track=_track).delete()
            SplitReleaseRoyalty.objects.filter(track_id=_track).delete() # Delete associated splits
            _track.delete()
            s3client = processor.get_s3_client()
            message = "Track Removed Successfully"
            base_key = f"unassigned/{primary_uuid}/{primary_uuid}_{primary_track_uuid}"
            for ext in ("wav", "mp3", "flac"):
                try:
                    s3client.delete_object(
                        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                        Key=f"{base_key}.{ext}",
                    )
                except Exception:
                    pass
            return JsonResponse({"message": message})
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


@csrf_exempt
def preview_distribute_info(request, primary_uuid):
    PAGE_NAME = "preview_distribute_info"
    if (
        request.user.is_authenticated
        and request.user.is_active
        and has_release_access(request.user, primary_uuid)
    ):
        _release = Release.objects.get(pk=primary_uuid)
        _tracks = Track.objects.filter(release=_release)
        if request.method == "GET":
            # For pending releases without UPC/ISRC, assign them so they're visible on preview
            if (_release.approval_status or "").strip().lower() == "pending_approval":
                from releases.upc_utils import normalize_upc_to_13
                changed = False
                if not _release.upc:
                    upc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.UPC, assigned=False).first()
                    if upc_to_assign:
                        _release.upc = normalize_upc_to_13(upc_to_assign.code) or upc_to_assign.code
                        upc_to_assign.assigned = True
                        upc_to_assign.save()
                        _release.save(update_fields=["upc"])
                        changed = True
                for track in _tracks:
                    if not track.isrc:
                        isrc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.ISRC, assigned=False).first()
                        if isrc_to_assign:
                            track.isrc = isrc_to_assign.code
                            isrc_to_assign.assigned = True
                            track.save()
                            isrc_to_assign.save()
                            changed = True
                if changed:
                    _release.refresh_from_db()
                    _tracks = Track.objects.filter(release=_release)
            rl_data = processor.get_pd_context(_release)
            can_be_distributed = True
            validation_message = ""
            missing_fields = []
            
            # Check basic requirements
            if not len(_tracks):
                missing_fields.append("Release must have at least one track")
            if not _release.cover_art_url:
                missing_fields.append("Release Cover Art must be uploaded")
            for track in _tracks:
                if not track.audio_track_url:
                    missing_fields.append(f"Track '{track.title}': Audio file must be uploaded")
            
            # Album Format validation - accept model default (Single) if not set
            effective_album_format = (_release.album_format or "").strip() or Release.ALBUM_FORMAT.SINGLE
            if effective_album_format.lower() not in [Release.ALBUM_FORMAT.SINGLE, Release.ALBUM_FORMAT.EP, Release.ALBUM_FORMAT.ALBUM]:
                missing_fields.append("Album Format must be one of: Single, EP, or Album")
            
            # License Type validation - accept model default (Copyright) if not set
            effective_license_type = (_release.license_type or "").strip() or Release.LICENSE_TYPE.COPYRIGHT
            if effective_license_type.lower() != "copyright":
                missing_fields.append("License Type must be set to 'Copyright' (Creative Common is not allowed)")
            
            # Digital Release Date validation
            if not _release.digital_release_date:
                missing_fields.append("Digital Release Date is mandatory")
            
            # Original Release Date validation
            if not _release.original_release_date:
                missing_fields.append("Original Release Date is mandatory")
            
            # License Holder validation
            if not _release.license_holder_name or not _release.license_holder_name.strip():
                missing_fields.append("License Holder Name is mandatory")
            if not _release.license_holder_year or not _release.license_holder_year.strip():
                missing_fields.append("License Holder Year is mandatory")
            
            # (P) Copyright for sound recordings validation
            if not _release.copyright_recording_text or not _release.copyright_recording_text.strip():
                missing_fields.append("(P) Copyright for sound recordings: Copyright Text is mandatory")
            if not _release.copyright_recording_year or not _release.copyright_recording_year.strip():
                missing_fields.append("(P) Copyright for sound recordings: Copyright Year is mandatory")
            
            # Track-level validations
            for _track in _tracks:
                # Primary Genre in tracks
                if not _track.primary_genre or not _track.primary_genre.strip():
                    missing_fields.append(f"Track '{_track.title}': Primary Genre is mandatory")
                
                # Explicit Lyrics validation - accept model default (Not Explicit) if not set
                # Accept both DB value ("not_explicit") and UI label ("Not Explicit") so default selection passes
                effective_explicit = (_track.explicit_lyrics or "").strip() or Track.EXPLICIT_LYRICS.NOT_EXPLICIT
                normalized = effective_explicit.lower().replace(" ", "_")
                if normalized not in [Track.EXPLICIT_LYRICS.NOT_EXPLICIT, Track.EXPLICIT_LYRICS.EXPLICIT, Track.EXPLICIT_LYRICS.CLEANED]:
                    missing_fields.append(f"Track '{_track.title}': Explicit Lyrics must be selected")
                
                # (P) Publishing rights validation - must match license holder
                if not _track.publishing_rights_owner or not _track.publishing_rights_owner.strip():
                    missing_fields.append(f"Track '{_track.title}': (P) Publishing Rights Owner is mandatory")
                if not _track.publishing_rights_year or not _track.publishing_rights_year.strip():
                    missing_fields.append(f"Track '{_track.title}': (P) Publishing Rights Year is mandatory")
                
                # Publishing rights must match license holder information
                if (_track.publishing_rights_owner and _track.publishing_rights_owner.strip() and 
                    _release.license_holder_name and _release.license_holder_name.strip() and
                    _track.publishing_rights_owner.strip() != _release.license_holder_name.strip()):
                    missing_fields.append(f"Track '{_track.title}': (P) Publishing Rights Owner must match License Holder Name")
                
                if (_track.publishing_rights_year and _track.publishing_rights_year.strip() and 
                    _release.license_holder_year and _release.license_holder_year.strip() and
                    _track.publishing_rights_year.strip() != _release.license_holder_year.strip()):
                    missing_fields.append(f"Track '{_track.title}': (P) Publishing Rights Year must match License Holder Year")
            
            # First Name and Last Name are optional for Primary Artist, Lyricist, Composer (no longer validated)
            
            if missing_fields:
                can_be_distributed = False
                missing_list = "\n".join([f"- {field}" for field in missing_fields])
                validation_message = f"The following mandatory fields are missing or incorrect:\n\n{missing_list}\n\nPlease complete all mandatory fields before distributing."
            
            # Approval workflow: draft → user submits → pending_approval → admin approves → Sonosuite
            # If published=False, treat as draft (fixes inconsistency from unpublish or bad data)
            approval_status = (_release.approval_status or "").strip() or "draft"
            if approval_status == "pending":
                approval_status = "draft"
            if not _release.published and approval_status == APPROVED:
                approval_status = "draft"  # Unpublished release with "approved" is effectively draft
            can_trigger_sonosuite = (
                request.user.role == CDUser.ROLES.ADMIN or getattr(request.user, "is_staff", False)
            )
            can_use_ddex_delivery = can_trigger_sonosuite  # Admin only: DDEX delivery to Audiomack (and Gaana)
            sonosuite_operation_ids = getattr(_release, "sonosuite_operation_ids", "") or ""

            return render(
                request,
                "volt_preview_distribute_info.html",
                context={
                    "username": request.user,
                    "primary_uuid": primary_uuid,
                    "rl_data": rl_data,
                    "page_name": PAGE_NAME,
                    "release_title": _release.title,
                    "is_published": _release.published,
                    "requesting_user_role": request.user.role,
                    "can_be_distributed": can_be_distributed,
                    "validation_message": validation_message,
                    "approval_status": approval_status,
                    "can_trigger_sonosuite": can_trigger_sonosuite,
                    "can_use_ddex_delivery": can_use_ddex_delivery,
                    "sonosuite_operation_ids": sonosuite_operation_ids,
                },
            )
        if request.method == "POST":
            ## This portion is to check if the release has cover art and audio path, before publishing
            can_be_distributed = True
            missing_fields = []

            # Basic file requirements
            if not len(_tracks):
                missing_fields.append("Release must have at least one track")
            if not _release.cover_art_url:
                missing_fields.append("Release Cover Art must be uploaded")
            for track in _tracks:
                if not track.audio_track_url:
                    missing_fields.append(f"Track '{track.title}': Audio file must be uploaded")
            
            audio_bucket_name_check = [
                not settings.AWS_STORAGE_BUCKET_NAME in track.audio_track_url
                for track in _tracks
            ]
            image_bucket_name_check = (
                settings.AWS_STORAGE_BUCKET_NAME in _release.cover_art_url
            )
            if not image_bucket_name_check:
                missing_fields.append("Release Cover Art must be stored in the correct S3 bucket")
            for i, track in enumerate(_tracks):
                if audio_bucket_name_check[i]:
                    missing_fields.append(f"Track '{track.title}': Audio file must be stored in the correct S3 bucket")
            
            # Album Format validation - accept model default (Single) if not set
            effective_album_format = (_release.album_format or "").strip() or Release.ALBUM_FORMAT.SINGLE
            if effective_album_format.lower() not in [Release.ALBUM_FORMAT.SINGLE, Release.ALBUM_FORMAT.EP, Release.ALBUM_FORMAT.ALBUM]:
                missing_fields.append("Album Format must be one of: Single, EP, or Album")
            
            # License Type validation - accept model default (Copyright) if not set
            effective_license_type = (_release.license_type or "").strip() or Release.LICENSE_TYPE.COPYRIGHT
            if effective_license_type.lower() != "copyright":
                missing_fields.append("License Type must be set to 'Copyright' (Creative Common is not allowed)")
            
            # Digital Release Date validation
            if not _release.digital_release_date:
                missing_fields.append("Digital Release Date is mandatory")
            
            # Original Release Date validation
            if not _release.original_release_date:
                missing_fields.append("Original Release Date is mandatory")
            
            # License Holder validation
            if not _release.license_holder_name or not _release.license_holder_name.strip():
                missing_fields.append("License Holder Name is mandatory")
            if not _release.license_holder_year or not _release.license_holder_year.strip():
                missing_fields.append("License Holder Year is mandatory")
            
            # (P) Copyright for sound recordings validation
            if not _release.copyright_recording_text or not _release.copyright_recording_text.strip():
                missing_fields.append("(P) Copyright for sound recordings: Copyright Text is mandatory")
            if not _release.copyright_recording_year or not _release.copyright_recording_year.strip():
                missing_fields.append("(P) Copyright for sound recordings: Copyright Year is mandatory")
            
            # Track-level validations
            for _track in _tracks:
                # Primary Genre in tracks
                if not _track.primary_genre or not _track.primary_genre.strip():
                    missing_fields.append(f"Track '{_track.title}': Primary Genre is mandatory")
                
                # Explicit Lyrics validation - accept model default (Not Explicit) if not set
                # Accept both DB value ("not_explicit") and UI label ("Not Explicit") so default selection passes
                effective_explicit = (_track.explicit_lyrics or "").strip() or Track.EXPLICIT_LYRICS.NOT_EXPLICIT
                normalized = effective_explicit.lower().replace(" ", "_")
                if normalized not in [Track.EXPLICIT_LYRICS.NOT_EXPLICIT, Track.EXPLICIT_LYRICS.EXPLICIT, Track.EXPLICIT_LYRICS.CLEANED]:
                    missing_fields.append(f"Track '{_track.title}': Explicit Lyrics must be selected")
                
                # (P) Publishing rights validation - must match license holder
                if not _track.publishing_rights_owner or not _track.publishing_rights_owner.strip():
                    missing_fields.append(f"Track '{_track.title}': (P) Publishing Rights Owner is mandatory")
                if not _track.publishing_rights_year or not _track.publishing_rights_year.strip():
                    missing_fields.append(f"Track '{_track.title}': (P) Publishing Rights Year is mandatory")
                
                # Publishing rights must match license holder information
                if (_track.publishing_rights_owner and _track.publishing_rights_owner.strip() and 
                    _release.license_holder_name and _release.license_holder_name.strip() and
                    _track.publishing_rights_owner.strip() != _release.license_holder_name.strip()):
                    missing_fields.append(f"Track '{_track.title}': (P) Publishing Rights Owner must match License Holder Name")
                
                if (_track.publishing_rights_year and _track.publishing_rights_year.strip() and 
                    _release.license_holder_year and _release.license_holder_year.strip() and
                    _track.publishing_rights_year.strip() != _release.license_holder_year.strip()):
                    missing_fields.append(f"Track '{_track.title}': (P) Publishing Rights Year must match License Holder Year")
            
            # First Name and Last Name are optional for Primary Artist, Lyricist, Composer (no longer validated)
            
            # Return error with all missing fields
            if missing_fields:
                missing_list = "\n".join([f"- {field}" for field in missing_fields])
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"Release could not be submitted! The following mandatory fields are missing or incorrect:\n\n{missing_list}\n\nPlease complete all mandatory fields before distributing."
                    },
                    status=400,
                )

            # Distribute = upload Metadata.csv to Sonosuite only + send to admin for approval. Delivery happens only when admin clicks Approve.
            current_status = (_release.approval_status or "").strip() or DRAFT
            if current_status == "pending":
                current_status = DRAFT
            if current_status == REJECTED:
                current_status = DRAFT  # Rejected releases can be re-submitted (treated as draft)
            if not _release.published and current_status == APPROVED:
                current_status = DRAFT  # Unpublished with "approved" is inconsistent; treat as draft
            if current_status != DRAFT:
                return JsonResponse(
                    {"success": False, "message": f"Release is not in draft. Current status: {current_status}"},
                    status=400,
                )

            # No ingestion API: set pending_approval. Admin must ingest via platform's bulk CSV / Platform UI, then Approve here to trigger delivery.
            _release.approval_status = PENDING_APPROVAL
            _release.save(update_fields=["approval_status"])

            return JsonResponse({
                "success": True,
                "message": "Release submitted for approval. Ingest the release via the platform (bulk CSV upload or Platform UI). From Pending for Approval you can use Download Selected to get the metadata CSV. Once ingested, click Approve here to trigger delivery to stores.",
                "approval_status": _release.approval_status,
                "sonosuite": {
                    "success": True,
                    "message": "Sent to admin for approval. Ingest via platform (bulk CSV or UI), then Approve to deliver.",
                    "operation_ids": [],
                    "error": None,
                },
            })
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


# --- Approval workflow: user submits for delivery → admin approves and sends to Sonosuite ---
PENDING_APPROVAL = "pending_approval"
APPROVED = "approved"
REJECTED = "rejected"
DRAFT = "draft"


@csrf_exempt
@login_required
def submit_for_approval(request, primary_uuid):
    """User requests delivery: (1) set release to pending_approval, (2) upload metadata CSV to Sonosuite. Admin then approves to send to stores."""
    import logging
    log = logging.getLogger(__name__)
    log.info("submit_for_approval called: primary_uuid=%s user=%s", primary_uuid, getattr(request.user, "email", request.user))
    try:
        if not request.user.is_active or not has_release_access(request.user, primary_uuid):
            return JsonResponse({"success": False, "message": "Not authorized."}, status=403)
        try:
            release = Release.objects.get(pk=primary_uuid)
        except Release.DoesNotExist:
            return JsonResponse({"success": False, "message": "Release not found."}, status=404)
        current = (release.approval_status or "").strip() or DRAFT
        if current == "pending":
            current = DRAFT
        if current == REJECTED:
            current = DRAFT  # Rejected releases can be re-submitted (treated as draft)
        if not release.published and current == APPROVED:
            current = DRAFT  # Unpublished with "approved" is inconsistent; treat as draft
        if current != DRAFT:
            return JsonResponse(
                {"success": False, "message": f"Release is not in draft. Current status: {current}"},
                status=400,
            )

        # Assign UPC/ISRC when submitting so they're visible on Preview & Distribute before admin approves
        from releases.upc_utils import normalize_upc_to_13
        if not release.upc:
            upc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.UPC, assigned=False).first()
            if not upc_to_assign:
                return JsonResponse(
                    {"success": False, "message": "No UPC codes available. Contact admin to add UPC codes."},
                    status=400,
                )
            release.upc = normalize_upc_to_13(upc_to_assign.code) or upc_to_assign.code
            upc_to_assign.assigned = True
            upc_to_assign.save()
            release.save(update_fields=["upc"])
        tracks = Track.objects.filter(release=release)
        for track in tracks:
            if not track.isrc:
                isrc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.ISRC, assigned=False).first()
                if not isrc_to_assign:
                    return JsonResponse(
                        {"success": False, "message": f"Track '{track.title}' needs ISRC. No ISRC codes available. Contact admin."},
                        status=400,
                    )
                track.isrc = isrc_to_assign.code
                isrc_to_assign.assigned = True
                track.save()
                isrc_to_assign.save()

        # Rigid check: release must have cover and every track must have at least one audio (FLAC or audio_track_url) for package.
        if not (getattr(release, "cover_art_url", None) or "").strip():
            return JsonResponse(
                {"success": False, "message": "Release must have cover art before submitting for approval."},
                status=400,
            )
        tracks = Track.objects.filter(release=release)
        for t in tracks:
            has_audio = (
                (getattr(t, "audio_flac_url", None) or "").strip()
                or (getattr(t, "audio_track_url", None) or "").strip()
            )
            if not has_audio:
                return JsonResponse(
                    {"success": False, "message": f"Track '{t.title}' has no audio. Add WAV/FLAC/MP3 before submitting."},
                    status=400,
                )

        release.approval_status = PENDING_APPROVAL
        release.submitted_for_approval_at = datetime.now()
        release.save(update_fields=["approval_status", "submitted_for_approval_at"])

        # Package-first: build DDEX package (XML + poster + WAV + FLAC + MP3) and save to our S3 when user submits for approval.
        from releases.ddex_package import build_ddex_package_and_save_to_s3
        pkg_ok, pkg_err = build_ddex_package_and_save_to_s3(release)
        if not pkg_ok:
            log.warning("Submit for approval: DDEX package build failed (release will still be pending): %s", pkg_err)
            return JsonResponse({
                "success": False,
                "message": f"Release set to pending approval, but DDEX package could not be built: {pkg_err}. Contact admin or fix assets and try again.",
                "approval_status": release.approval_status,
            }, status=502)

        return JsonResponse({
            "success": True,
            "message": "Release submitted for approval. DDEX package (XML + cover + audio) has been saved. When admin approves, it will be distributed to all configured stores.",
            "approval_status": release.approval_status,
        })
    except Exception as e:
        log.exception("submit_for_approval error: %s", e)
        return JsonResponse({
            "success": False,
            "message": "Submit for approval failed: " + str(e),
        }, status=500)


def _approve_single_release(release):
    """
    Perform approval for one release: assign UPC/ISRC if needed, call delivery API, mark approved.
    Returns (True, None) on success, or (False, error_message) on failure.
    """
    current = (release.approval_status or "").strip() or DRAFT
    if current == "pending":
        current = DRAFT
    if current != PENDING_APPROVAL:
        return (False, f"Not pending approval (current: {current})")
    tracks = Track.objects.filter(release=release)
    if not release.upc:
        from releases.upc_utils import normalize_upc_to_13
        upc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.UPC, assigned=False).first()
        if not upc_to_assign:
            return (False, "No UPC codes available. Contact admin.")
        release.upc = normalize_upc_to_13(upc_to_assign.code) or upc_to_assign.code
        upc_to_assign.assigned = True
        upc_to_assign.save()
        release.save(update_fields=["upc"])
    for track in tracks:
        if not track.isrc:
            isrc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.ISRC, assigned=False).first()
            if not isrc_to_assign:
                return (False, f"Track '{track.title}' needs ISRC; no codes available.")
            track.isrc = isrc_to_assign.code
            isrc_to_assign.assigned = True
            track.save()
            isrc_to_assign.save()

    from releases.upc_utils import normalize_upc_to_13

    # Single-click: when DDEX delivery is configured, Approve = approve + deliver to all stores (Audiomack, Gaana, TikTok, Apple Music, etc.) using each store's method.
    from releases.store_delivery import use_ddex_delivery, deliver_release_to_all_stores
    if use_ddex_delivery():
        ok_deliver, err_deliver, detail = deliver_release_to_all_stores(release)
        if not ok_deliver:
            return (False, err_deliver or "Delivery to stores failed.")
        release.approval_status = APPROVED
        release.published = True
        release.published_at = datetime.now()
        op_ids_str = (detail.get("operation_ids_str") or "").strip()
        if op_ids_str and hasattr(release, "sonosuite_operation_ids"):
            release.sonosuite_operation_ids = op_ids_str
            release.save(update_fields=["approval_status", "published", "published_at", "sonosuite_operation_ids"])
        else:
            release.save(update_fields=["approval_status", "published", "published_at"])
        return (True, None)

    # Fallback: Sonosuite when DDEX delivery is not configured (no DELIVERY_STORES)
    from releases.sonosuite_client import send_release_to_sonosuite, is_sonosuite_configured
    if not is_sonosuite_configured():
        return (False, "Delivery is not configured. Set DELIVERY_STORES (e.g. audiomack,gaana,tiktok) or Sonosuite credentials in .env.")
    result = send_release_to_sonosuite(upc=normalize_upc_to_13(release.upc) or release.upc)
    if not result.get("success"):
        return (False, result.get("error", "Failed to send to delivery API."))
    operation_ids = result.get("operation_ids", [])
    release.approval_status = APPROVED
    release.published = True
    release.published_at = datetime.now()
    release.sonosuite_operation_ids = ",".join(operation_ids) if operation_ids else ""
    release.save(update_fields=["approval_status", "published", "published_at", "sonosuite_operation_ids"])
    return (True, None)


@csrf_exempt
@login_required
def approve_release(request, primary_uuid):
    """Admin approves release (status → approved). Delivery to stores is separate (DDEX delivery button) or via Sonosuite if not using DDEX."""
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"success": False, "message": "Only admin or staff can approve."}, status=403)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"success": False, "message": "Release not found."}, status=404)
    ok, err = _approve_single_release(release)
    if not ok:
        status = 502 if "delivery" in (err or "").lower() or "configured" in (err or "").lower() else 400
        return JsonResponse({"success": False, "message": err}, status=status)
    op_ids = (getattr(release, "sonosuite_operation_ids", "") or "").strip()
    upc = (release.upc or "").strip()
    from releases.store_delivery import use_ddex_delivery, get_delivery_stores
    stores = get_delivery_stores() if use_ddex_delivery() else []
    if use_ddex_delivery() and (op_ids or stores):
        msg = f"Release approved and delivered to all configured stores ({', '.join(stores)}). UPC: {upc or '(none)'}."
        if op_ids:
            msg += f" Ref: {op_ids[:200]}{'…' if len(op_ids) > 200 else ''}"
    elif "|" in op_ids or (op_ids and not op_ids.startswith("audiomack:") and "tiktok" in op_ids.lower()):
        msg = f"Release approved and delivered to all configured stores. UPC: {upc or '(none)'}."
        if op_ids:
            msg += f" Ref: {op_ids[:200]}{'…' if len(op_ids) > 200 else ''}"
    elif op_ids.startswith("audiomack:"):
        ref = op_ids.replace("audiomack:", "", 1)
        if ref and (ref.startswith("/") or "out_audiomack" in ref):
            msg = f"Release approved and delivered to Audiomack. UPC: {upc or '(none)'}. File saved to {ref}"
        else:
            msg = f"Release approved and delivered to Audiomack. UPC: {upc or '(none)'}. S3: {ref}"
    else:
        msg = f"Release approved. UPC: {upc or '(none)'}"
        if op_ids:
            msg += f". Operation IDs: {op_ids}"
        else:
            msg += ". (No operation IDs returned — check Sonosuite history tab or contact support.)"
    return JsonResponse({
        "success": True,
        "message": msg,
        "approval_status": release.approval_status,
        "published": True,
        "sonosuite_operation_ids": op_ids,
        "sonosuite_results": {"success": True, "operation_ids": op_ids.split(",") if op_ids else [], "upc": upc},
    })


@csrf_exempt
@login_required
def bulk_approve_releases(request):
    """Admin approves multiple pending releases in one request. POST selectedRows[] = list of release IDs."""
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"success": False, "message": "Only admin or staff can approve."}, status=403)
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST required."}, status=405)
    # jQuery sends selectedRows=id1&selectedRows=id2 (no brackets); some clients send selectedRows[]=id1
    selected = request.POST.getlist("selectedRows[]") or request.POST.getlist("selectedRows") or []
    selected = [s for s in selected if (s or "").strip()]
    if not selected:
        return JsonResponse({
            "success": False,
            "message": "No releases selected. Select one or more rows and click Approve Releases.",
            "approved": 0,
            "failed": 0,
            "errors": [],
        }, status=400)
    approved = 0
    errors = []
    for pk in selected:
        try:
            release = Release.objects.get(pk=pk)
        except Release.DoesNotExist:
            errors.append({"id": pk, "title": "?", "error": "Release not found."})
            continue
        title = (release.title or "")[:50]
        ok, err = _approve_single_release(release)
        if ok:
            approved += 1
        else:
            errors.append({"id": pk, "title": title, "error": err or "Unknown error."})
    failed = len(errors)
    total = approved + failed
    if total > 0:
        message = f"{approved} out of {total} delivered via API successfully."
        if failed:
            message += f" {failed} failed. "
            if errors:
                short_errors = [e.get("title", e.get("id", "?")) + ": " + (e.get("error", "")[:60] or "") for e in errors[:5]]
                message += " ".join(short_errors)
                if len(errors) > 5:
                    message += f" (+{len(errors) - 5} more)"
    else:
        message = "No releases were approved."
    return JsonResponse({
        "success": True,
        "message": message,
        "approved": approved,
        "failed": failed,
        "total": total,
        "errors": errors,
    })


@csrf_exempt
@login_required
def reject_release(request, primary_uuid):
    """Admin rejects a release: unpublish and set back to draft so it appears under Drafts and can be re-submitted."""
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"success": False, "message": "Only admin or staff can reject."}, status=403)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"success": False, "message": "Release not found."}, status=404)
    current = (release.approval_status or "").strip() or DRAFT
    if current == "pending":
        current = DRAFT
    if current != PENDING_APPROVAL:
        return JsonResponse(
            {"success": False, "message": f"Only releases pending approval can be rejected. Current: {current}"},
            status=400,
        )
    release.approval_status = DRAFT
    release.published = False
    update_fields = ["approval_status", "published"]
    if hasattr(release, "published_at"):
        release.published_at = None
        update_fields.append("published_at")
    release.save(update_fields=update_fields)
    return JsonResponse({
        "success": True,
        "message": "Release rejected and returned to drafts. You can edit and submit again.",
        "approval_status": release.approval_status,
    })


@login_required
def ddex_package_status(request, primary_uuid):
    """GET: Admin-only. Returns DDEX package status for a release: bucket, prefix, exists, list of S3 keys (for debugging)."""
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"error": "Admin only."}, status=403)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"error": "Release not found."}, status=404)
    from releases.ddex_package import (
        _get_our_bucket,
        get_package_s3_prefix,
        package_exists,
    )
    bucket = _get_our_bucket()
    prefix = get_package_s3_prefix(release).rstrip("/") + "/"
    exists = package_exists(release)
    upc = (getattr(release, "upc", None) or "").strip() or str(release.id)
    files = []
    list_error = None
    try:
        s3 = processor.get_s3_client()
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents") or []:
                k = obj.get("Key", "")
                short = k.replace(prefix, "", 1) if k.startswith(prefix) else k
                files.append({"key": short, "size": obj.get("Size", 0)})
    except Exception as e:
        list_error = str(e)
    return JsonResponse({
        "release_id": str(release.id),
        "title": release.title,
        "upc": upc,
        "approval_status": (release.approval_status or "").strip(),
        "bucket": bucket,
        "prefix": prefix,
        "package_exists": exists,
        "file_count": len(files),
        "files": files,
        "list_error": list_error,
        "s3_path": f"s3://{bucket}/{prefix}",
        "note": "Package is created when user submits for approval. If package_exists is false, this release was likely submitted before the package flow was deployed, or the build failed." if not exists else None,
    })


@csrf_exempt
@login_required
def ddex_deliver_audiomack(request, primary_uuid):
    """Send existing DDEX package to Audiomack, Gaana and TikTok. Release must be approved and package must exist (created on submit-for-approval)."""
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"success": False, "message": "Only admin or staff can use DDEX delivery."}, status=403)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"success": False, "message": "Release not found."}, status=404)
    from releases.ddex_package import package_exists
    if not package_exists(release):
        return JsonResponse({
            "success": False,
            "message": "DDEX package not found. The package is created when the user submits for approval. Ask the user to re-submit, or check S3 for ddex/packages/<release_id>/.",
        }, status=400)
    if (release.approval_status or "").strip() != APPROVED:
        return JsonResponse({
            "success": False,
            "message": "Release must be approved before DDEX delivery. Approve the release first, then click DDEX delivery.",
        }, status=400)
    import logging
    log = logging.getLogger(__name__)
    from releases.audiomack_delivery import deliver_release_to_audiomack
    from releases.gaana_delivery import deliver_release_to_gaana
    from releases.tiktok_delivery import deliver_release_to_tiktok

    upc = (getattr(release, "upc", None) or "").strip() or str(release.id)
    log.info("DDEX delivery requested: primary_uuid=%s upc=%s user=%s", primary_uuid, upc, getattr(request.user, "email", request.user))

    def _safe_deliver(name, fn):
        try:
            return fn()
        except Exception as e:
            log.exception("DDEX delivery %s failed with exception: %s", name, e)
            return (False, str(e), {"message": f"{name}: {e}"})

    a_ok, a_err, a_detail = _safe_deliver("Audiomack", lambda: deliver_release_to_audiomack(release))
    g_ok, g_err, g_detail = _safe_deliver("Gaana", lambda: deliver_release_to_gaana(release))
    t_ok, t_err, t_detail = _safe_deliver("TikTok", lambda: deliver_release_to_tiktok(release))

    all_ok = a_ok and g_ok and t_ok
    any_ok = a_ok or g_ok or t_ok
    parts = []
    if a_ok:
        parts.append("Audiomack")
    if g_ok:
        parts.append("Gaana")
    if t_ok:
        parts.append("TikTok")
    if all_ok:
        msg = "DDEX delivery completed for Audiomack, Gaana and TikTok. XML + cover + audio saved/delivered as configured."
        return JsonResponse({
            "success": True,
            "message": msg,
            "detail": {"audiomack": a_detail, "gaana": g_detail, "tiktok": t_detail},
        })
    if not any_ok:
        errs = []
        if not a_ok:
            errs.append("Audiomack: " + (a_err or a_detail.get("message", "failed")))
        if not g_ok:
            errs.append("Gaana: " + (g_err or g_detail.get("message", "failed")))
        if not t_ok:
            errs.append("TikTok: " + (t_err or t_detail.get("message", "failed")))
        return JsonResponse({
            "success": False,
            "message": " ".join(errs),
            "detail": {"audiomack": a_detail, "gaana": g_detail, "tiktok": t_detail},
        }, status=400)
    # Some succeeded, some failed
    who_ok = ", ".join(parts)
    who_fail = []
    if not a_ok:
        who_fail.append("Audiomack: " + (a_err or a_detail.get("message", "failed")))
    if not g_ok:
        who_fail.append("Gaana: " + (g_err or g_detail.get("message", "failed")))
    if not t_ok:
        who_fail.append("TikTok: " + (t_err or t_detail.get("message", "failed")))
    msg = f"Delivered to {who_ok}. Failed: " + "; ".join(who_fail)
    return JsonResponse({
        "success": False,
        "message": msg,
        "detail": {"audiomack": a_detail, "gaana": g_detail, "tiktok": t_detail},
    }, status=400)


@csrf_exempt
@login_required
def ddex_deliver_apple_music(request, primary_uuid):
    """Deliver this release to Apple Music via Merlin Bridge (Apple iTunes Importer format). Admin only. No DDEX package required."""
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"success": False, "message": "Only admin or staff can use Apple Music delivery."}, status=403)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"success": False, "message": "Release not found."}, status=404)
    if (release.approval_status or "").strip() != APPROVED:
        return JsonResponse({
            "success": False,
            "message": "Release must be approved before Apple Music delivery. Approve the release first, then click Apple Music (Merlin Bridge).",
        }, status=400)
    import logging
    log = logging.getLogger(__name__)
    from releases.merlin_bridge_delivery import deliver_release_to_merlin_bridge

    upc = (getattr(release, "upc", None) or "").strip() or str(release.id)
    log.info("Apple Music (Merlin Bridge) delivery requested: primary_uuid=%s upc=%s user=%s", primary_uuid, upc, getattr(request.user, "email", request.user))

    try:
        ok, err, detail = deliver_release_to_merlin_bridge(release)
    except Exception as e:
        log.exception("Apple Music delivery failed: %s", e)
        return JsonResponse({"success": False, "message": str(e), "detail": {}}, status=400)
    if ok:
        return JsonResponse({
            "success": True,
            "message": detail.get("message") or "Apple Music (Merlin Bridge) delivery completed.",
            "detail": detail,
        })
    return JsonResponse({
        "success": False,
        "message": err or "Apple Music delivery failed.",
        "detail": detail,
    }, status=400)


@csrf_exempt
@login_required
def ddex_takedown_apple_music(request, primary_uuid):
    """Send takedown (PurgeReleaseMessage) to Apple Music via Merlin Bridge SFTP. Admin only."""
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"success": False, "message": "Only admin or staff can use Apple Music takedown."}, status=403)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"success": False, "message": "Release not found."}, status=404)
    import logging
    log = logging.getLogger(__name__)
    from releases.merlin_bridge_delivery import deliver_takedown_to_merlin_bridge

    upc = (getattr(release, "upc", None) or "").strip() or str(release.id)
    log.info("Apple Music (Merlin Bridge) takedown requested: primary_uuid=%s upc=%s user=%s", primary_uuid, upc, getattr(request.user, "email", request.user))

    try:
        ok, err, detail = deliver_takedown_to_merlin_bridge(release)
    except Exception as e:
        log.exception("Apple Music takedown failed: %s", e)
        return JsonResponse({"success": False, "message": str(e), "detail": {}}, status=400)
    if ok:
        return JsonResponse({
            "success": True,
            "message": detail.get("message") or "Apple Music (Merlin Bridge) takedown sent.",
            "detail": detail,
        })
    return JsonResponse({
        "success": False,
        "message": err or "Apple Music takedown failed.",
        "detail": detail,
    }, status=400)


@csrf_exempt
@login_required
def ddex_deliver_all_stores(request, primary_uuid):
    """Queue background job: deliver this release to all configured stores. Admin only."""
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"success": False, "message": "Only admin or staff can distribute to stores."}, status=403)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"success": False, "message": "Release not found."}, status=404)
    if (release.approval_status or "").strip() != APPROVED:
        return JsonResponse({
            "success": False,
            "message": "Release must be approved before distribution. Approve the release first, then distribute.",
        }, status=400)
    job = _queue_distribution_job(release, DistributionJob.ACTION.DISTRIBUTE, request.user)
    return JsonResponse({
        "success": True,
        "message": "Distribute to stores queued.",
        "job_id": job.id,
    })


@csrf_exempt
@login_required
def ddex_takedown_all_stores(request, primary_uuid):
    """Queue background job: takedown this release from all stores. Admin only."""
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"success": False, "message": "Only admin or staff can takedown from stores."}, status=403)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"success": False, "message": "Release not found."}, status=404)
    job = _queue_distribution_job(release, DistributionJob.ACTION.TAKEDOWN, request.user)
    return JsonResponse({
        "success": True,
        "message": "Takedown from stores queued.",
        "job_id": job.id,
    })


def _queue_distribution_job(release: Release, action: str, user: CDUser) -> DistributionJob:
    existing = DistributionJob.objects.filter(
        release=release,
        action=action,
        status__in=[DistributionJob.STATUS.QUEUED, DistributionJob.STATUS.RUNNING],
    ).order_by("-id").first()
    if existing:
        return existing
    job = DistributionJob.objects.create(
        release=release,
        requested_by=user,
        action=action,
        status=DistributionJob.STATUS.QUEUED,
        message="Queued",
    )
    thread = threading.Thread(target=_run_distribution_job, args=(job.id,), daemon=True)
    thread.start()
    return job


def _run_distribution_job(job_id: int) -> None:
    import logging
    log = logging.getLogger(__name__)
    close_old_connections()
    try:
        job = DistributionJob.objects.select_related("release").get(pk=job_id)
        release = job.release
        job.status = DistributionJob.STATUS.RUNNING
        job.started_at = timezone.now()
        job.message = "Running"
        job.save(update_fields=["status", "started_at", "message"])

        if job.action == DistributionJob.ACTION.DISTRIBUTE:
            from releases.audiomack_delivery import deliver_release_to_audiomack
            from releases.gaana_delivery import deliver_release_to_gaana
            from releases.tiktok_delivery import deliver_release_to_tiktok
            from releases.merlin_bridge_delivery import deliver_release_to_merlin_bridge
            ops = [
                ("audiomack", lambda: deliver_release_to_audiomack(release)),
                ("gaana", lambda: deliver_release_to_gaana(release)),
                ("tiktok", lambda: deliver_release_to_tiktok(release)),
                (
                    "apple_music",
                    lambda: deliver_release_to_merlin_bridge(
                        release, distribution_job_id=job.id
                    ),
                ),
            ]
        else:
            from releases.audiomack_delivery import deliver_takedown_to_audiomack
            from releases.gaana_delivery import deliver_takedown_to_gaana
            from releases.tiktok_delivery import deliver_takedown_to_tiktok
            from releases.merlin_bridge_delivery import deliver_takedown_to_merlin_bridge
            ops = [
                ("audiomack", lambda: deliver_takedown_to_audiomack(release)),
                ("gaana", lambda: deliver_takedown_to_gaana(release)),
                ("tiktok", lambda: deliver_takedown_to_tiktok(release)),
                ("apple_music", lambda: deliver_takedown_to_merlin_bridge(release)),
            ]

        results = {}
        for store_code, fn in ops:
            started = time.time()
            try:
                ok, err, detail = fn()
                results[store_code] = {
                    "success": bool(ok),
                    "message": (detail or {}).get("message") or ("" if ok else (err or "failed")),
                    "detail": detail or {},
                    "duration_seconds": round(time.time() - started, 2),
                }
            except Exception as e:
                log.exception("Distribution job %s store %s failed: %s", job_id, store_code, e)
                results[store_code] = {
                    "success": False,
                    "message": str(e),
                    "detail": {},
                    "duration_seconds": round(time.time() - started, 2),
                }

        success_count = sum(1 for r in results.values() if r.get("success"))
        total = len(results)
        if success_count == total:
            status = DistributionJob.STATUS.SUCCESS
            msg = "Completed successfully."
        elif success_count == 0:
            status = DistributionJob.STATUS.FAILED
            msg = "All stores failed."
        else:
            status = DistributionJob.STATUS.PARTIAL
            msg = f"Completed with partial success ({success_count}/{total})."

        finished = timezone.now()
        job.status = status
        job.finished_at = finished
        job.duration_seconds = round((finished - (job.started_at or finished)).total_seconds(), 2)
        job.store_results = results
        job.message = msg
        job.save(update_fields=["status", "finished_at", "duration_seconds", "store_results", "message"])
    except Exception as e:
        log.exception("Distribution job %s failed unexpectedly: %s", job_id, e)
        try:
            job = DistributionJob.objects.get(pk=job_id)
            finished = timezone.now()
            job.status = DistributionJob.STATUS.FAILED
            job.finished_at = finished
            if job.started_at:
                job.duration_seconds = round((finished - job.started_at).total_seconds(), 2)
            job.message = str(e)
            job.save(update_fields=["status", "finished_at", "duration_seconds", "message"])
        except Exception:
            pass
    finally:
        close_old_connections()


@csrf_exempt
@login_required
def ddex_distribution_jobs(request, primary_uuid):
    if request.user.role != CDUser.ROLES.ADMIN and not getattr(request.user, "is_staff", False):
        return JsonResponse({"success": False, "message": "Only admin or staff can view delivery history."}, status=403)
    try:
        release = Release.objects.get(pk=primary_uuid)
    except Release.DoesNotExist:
        return JsonResponse({"success": False, "message": "Release not found."}, status=404)
    jobs = DistributionJob.objects.filter(release=release).select_related("requested_by").order_by("-id")[:50]
    data = []
    from django.utils import timezone as dj_tz

    for j in jobs:
        sr = j.store_results or {}
        live = sr.get("_live") or {}
        elapsed_running = 0.0
        if j.status == DistributionJob.STATUS.RUNNING and j.started_at:
            elapsed_running = round(
                (dj_tz.now() - j.started_at).total_seconds(), 1
            )
        data.append({
            "id": j.id,
            "action": j.action,
            "status": j.status,
            "message": j.message,
            "requested_at": j.requested_at.isoformat() if j.requested_at else "",
            "started_at": j.started_at.isoformat() if j.started_at else "",
            "finished_at": j.finished_at.isoformat() if j.finished_at else "",
            "duration_seconds": j.duration_seconds or 0,
            "requested_by": (j.requested_by.email if j.requested_by else ""),
            "store_results": sr,
            "live_step": live.get("step", ""),
            "live_updated_at": live.get("updated_at", ""),
            "elapsed_running_seconds": elapsed_running,
        })
    return JsonResponse({"success": True, "jobs": data})


@csrf_exempt
def release_report(request):
    requesting_user_role = processor.get_user_role(request.user)
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and requesting_user_role == "admin"
        and request.method == "POST"
    ):
        selectedRows = request.POST.getlist("selectedRows[]")
        if selectedRows and len(selectedRows) > 0:
            file_path, df = processor.generate_release_metadata_csv(selectedRows)
        else:
            # ================= ORIGINAL QUERY (FOR REFERENCE) ===================
            # primary_uuids_list = sql_client.read_sql(
            #     "SELECT primary_uuid from rl_release;"
            # )["primary_uuid"].tolist()
            # ===================================================================
            
            # New ORM-based implementation
            primary_uuids_list = list(Release.objects.values_list('id', flat=True))
            
            file_path, df = processor.generate_release_metadata_csv(primary_uuids_list)

        with open(file_path, "rb") as file:
            file_content = base64.b64encode(file.read()).decode("utf-8")

        os.remove(file_path)
        return JsonResponse({"my_csv": file_content})
    else:
        return JsonResponse({"report_error": "report_error"})


@csrf_exempt
def add_new_artist(request, artist_name):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "error", "message": "Authentication Failed!"})
    try:
        artist_name = (artist_name or "").strip()
        if not artist_name:
            return JsonResponse({"error": "error", "message": "Artist name is required."})
        creator = request.user
        if request.user.role == CDUser.ROLES.MEMBER:
            creator = get_leader(request.user)
        if Artist.objects.filter(user=creator, name=artist_name).exists():
            return JsonResponse(
                {
                    "error": "error",
                    "message": "Similar artist already exists in your account. Please use the previous one.",
                }
            )
        # Assign artist_id (exclude NULL to avoid TypeError)
        max_artist = Artist.objects.filter(artist_id__isnull=False).order_by('-artist_id').first()
        new_artist_id = 1 if not max_artist or max_artist.artist_id is None else max_artist.artist_id + 1
        # Build create kwargs: only include fields that exist on this deployment's Artist model
        # (live server may have older model without audiomack_id)
        create_kwargs = {
            "user": creator,
            "name": artist_name,
            "artist_id": new_artist_id,
        }
        optional_field_names = [
            "first_name", "last_name", "apple_music_id", "spotify_id", "youtube_username",
            "audiomack_id", "soundcloud_page", "facebook_page", "x_username", "website", "biography",
        ]
        for fname in optional_field_names:
            try:
                Artist._meta.get_field(fname)
                create_kwargs[fname] = ""
            except Exception:
                pass  # Field does not exist on this model, skip
        artist = Artist.objects.create(**create_kwargs)
        artist.save()
        return JsonResponse({"success": "success", "id": artist.pk})
    except Exception as e:
        return JsonResponse(
            {"error": "error", "message": str(e) or "Please contact administrators!"}
        )


@csrf_exempt
def add_new_label(request, data):
    # requesting_user_role = CDUser.get_user_role(request.user)
    if request.user.is_authenticated:
        data = data.split("|_|")
        username = data[1]
        if request.user.role == CDUser.ROLES.MEMBER:
            username = get_leader(request.user)
        new_label = data[0]
        print("new_label", new_label)
        #add new_label check to must be string not empty string
        if not new_label or not isinstance(new_label, str):
            return JsonResponse({"error": "error", "message": "New label must be a non-empty string!"})
        
        # ================= ORIGINAL QUERY (FOR REFERENCE) ===================
        # query = f"Select * from rl_labels where user_name like '{username}' and label like '{new_label}';"
        # df = sql_client.read_sql(query)
        # if len(df) == 0:
        #     df = pd.DataFrame(
        #         list(zip([username], [new_label])), columns=["user_name", "label"]
        #     )
        #     sql_client.df_to_sql(df=df, table_name="rl_labels")
        # ===================================================================
        
        # New ORM-based implementation
        user = CDUser.objects.get(email=username)
        if not Label.objects.filter(user=user, label=new_label).exists():
            Label.objects.create(user=user, label=new_label)
        return JsonResponse({"success": "success"})
    else:
        return JsonResponse({"error": "error"})


@csrf_exempt
def upload_releases(request):
    requesting_user_role = request.user.role
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.method == "POST"
        and request.FILES["releases_file"]
        and requesting_user_role == "admin"
    ):
        try:
            releases_file = request.FILES["releases_file"].file
            file_handler = FileHandler(releases_file, "release", "excel")
            validator = DataValidator(
                file_handler.data,
                [release_validations, track_validations, license_validations],
                file_handler.file_type,
            )
            status, handler_response = validator.validate()
            if status:
                status, handler_response, data = validator.process()
                if status:
                    # ================= ORIGINAL SQL LOGIC (FOR REFERENCE) ===================
                    # sql_client.df_to_sql(df=data[0], table_name="rl_release")
                    # sql_client.df_to_sql(df=data[1], table_name="rl_licenses")
                    # sql_client.df_to_sql(df=data[2], table_name="rl_tracks")
                    # ===================================================================

                    # New ORM-based implementation
                    # Process releases
                    for _, row in data[0].iterrows():
                        Release.objects.create(
                            title=row.get('title', ''),
                            cover_art_url=row.get('cover_art_url', ''),
                            remix_version=row.get('remix_version', ''),
                            primary_genre=row.get('primary_genre', ''),
                            secondary_genre=row.get('secondary_genre', ''),
                            language=row.get('language', ''),
                            album_format=row.get('album_format', Release.ALBUM_FORMAT.SINGLE),
                            upc=row.get('upc', ''),
                            reference_number=row.get('reference_number', ''),
                            grid=row.get('grid', ''),
                            description=row.get('description', ''),
                            created_by_id=row.get('created_by_id'),
                            published=row.get('published', False),
                            published_at=row.get('published_at'),
                            label_id=row.get('label_id'),
                            apple_music_commercial_model=Release.APPLE_MUSIC_COMMERCIAL_MODEL.BOTH,
                        )

                    # Process tracks
                    for _, row in data[2].iterrows():
                        Track.objects.create(
                            release_id=row.get('release_id'),
                            remix_version=row.get('remix_version', ''),
                            title=row.get('title', ''),
                            created_by_id=row.get('created_by_id'),
                            audio_track_url=row.get('audio_track_url', ''),
                            primary_genre=row.get('primary_genre', ''),
                            secondary_genre=row.get('secondary_genre', ''),
                            isrc=row.get('isrc', ''),
                            iswc=row.get('iswc', ''),
                            publishing_rights_owner=row.get('publishing_rights_owner', ''),
                            publishing_rights_year=row.get('publishing_rights_year', ''),
                            lyrics=row.get('lyrics', ''),
                            explicit_lyrics=row.get('explicit_lyrics', Track.EXPLICIT_LYRICS.NOT_EXPLICIT),
                            language=row.get('language', ''),
                            available_separately=row.get('available_separately', False),
                            start_point=row.get('start_point', ''),
                            notes=row.get('notes', '')
                        )

                    response = {
                        "success": f"{len(data[0])} releases, {len(data[2])} tracks have been uploaded successfully!",
                        "status_code": 200,
                    }
                else:
                    response = {
                        "error": handler_response,
                        "status_code": 200,
                    }
            else:
                response = {
                    "error": handler_response,
                    "status_code": 200,
                }
        except Exception as e:
            print(traceback.format_exc())
            response = {
                "error": "Error while uploading data. Please try again later.",
                "status_code": 500,
            }
        return JsonResponse(response)
    else:
        response = HttpResponse()
        response.status_code = 403
        return response
# ================= ORIGINAL FUNCTION (FOR REFERENCE) ===================
# @csrf_exempt
# def update_release_title(request, primary_uuid, new_release_title):
#     if (
#         request.user.is_authenticated
#         and is_active(request.user)
#         and has_release_access(request.user, primary_uuid)
#     ):
#         query = f"Update rl_release set title = '{new_release_title}' where primary_uuid like '{primary_uuid}';"
#         sql_client.execute_sql(query)
#         return JsonResponse(
#             {"message": f"Release title updated to {new_release_title}!"}
#         )
#     else:
#         return JsonResponse({"message": "You are not authorized to view this page!"})
# ===================================================================

# New ORM-based implementation
@csrf_exempt
def update_release_title(request, primary_uuid, new_release_title):
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and has_release_access(request.user, primary_uuid)
    ):
        Release.objects.filter(id=primary_uuid).update(title=new_release_title)
        return JsonResponse(
            {"message": f"Release title updated to {new_release_title}!"}
        )
    else:
        return JsonResponse({"message": "You are not authorized to view this page!"})


def file_uploader(request, primary_uuid):
    if request.method == "POST":
        file = request.FILES["file"].read()
        fileName = request.POST["filename"]
        existingPath = request.POST["existingPath"]
        end = request.POST["end"]
        nextSlice = request.POST["nextSlice"]
        if (
            file == ""
            or fileName == ""
            or existingPath == ""
            or end == ""
            or nextSlice == ""
        ):
            res = JsonResponse({"data": "Invalid Request"})
            return res
        else:
            if existingPath == "null":
                path = "media/" + primary_uuid + "." + fileName.split(".")[1]
                with open(path, "wb+") as destination:
                    destination.write(file)
                if int(end):
                    res = JsonResponse(
                        {
                            "data": "Uploaded Successfully",
                            "existingPath": primary_uuid + "." + fileName.split(".")[1],
                        }
                    )
                else:
                    res = JsonResponse(
                        {"existingPath": primary_uuid + "." + fileName.split(".")[1]}
                    )
                return res
            else:
                path = "media/" + primary_uuid + "." + fileName.split(".")[1]
                with open(path, "ab+") as destination:
                    destination.write(file)
                if int(end):
                    res = JsonResponse(
                        {"data": "Uploaded Successfully", "existingPath": existingPath}
                    )
                else:
                    res = JsonResponse({"existingPath": existingPath})
                return res


def file_uploader_atmos_track(request, primary_uuid, track_uuid):
    """
    Chunked upload for Dolby Atmos master (BWF .wav). Writes to
    media/{release_id}_{track_id}_atmos.wav so it does not overwrite stereo upload.
    """
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({"data": "Unauthorized"}, status=401)
    if not has_release_access(request.user, primary_uuid):
        return JsonResponse({"data": "Forbidden"}, status=403)
    try:
        Track.objects.get(pk=track_uuid, release_id=primary_uuid)
    except Track.DoesNotExist:
        return JsonResponse({"data": "Track not found"}, status=404)

    if request.method != "POST":
        return JsonResponse({"data": "Method not allowed"}, status=405)

    file = request.FILES["file"].read()
    fileName = request.POST["filename"]
    existingPath = request.POST["existingPath"]
    end = request.POST["end"]
    nextSlice = request.POST["nextSlice"]
    if (
        file == b""
        or fileName == ""
        or existingPath == ""
        or end == ""
        or nextSlice == ""
    ):
        return JsonResponse({"data": "Invalid Request"})
    ext = (fileName.rsplit(".", 1)[-1] if "." in fileName else "").lower()
    if ext != "wav":
        return JsonResponse({"data": "Dolby Atmos upload must be a .wav file"}, status=400)

    base_name = f"{primary_uuid}_{track_uuid}_atmos.wav"
    media_path = os.path.join("media", base_name)

    if existingPath == "null":
        with open(media_path, "wb+") as destination:
            destination.write(file)
        if int(end):
            res = JsonResponse(
                {
                    "data": "Atmos file received — click Update on the track to save to cloud storage.",
                    "existingPath": base_name,
                }
            )
        else:
            res = JsonResponse({"existingPath": base_name})
        return res
    with open(media_path, "ab+") as destination:
        destination.write(file)
    if int(end):
        res = JsonResponse(
            {"data": "Atmos file received — click Update on the track to save to cloud storage.", "existingPath": existingPath}
        )
    else:
        res = JsonResponse({"existingPath": existingPath})
    return res


def check_audio_meta_info(request, primary_uuid_with_extension):

    if request.method == "GET":
        try:
            audio_file_name = f"media/{primary_uuid_with_extension}"
            if os.path.exists(audio_file_name):
                with wave.open(audio_file_name, "rb") as wav_file:
                    sample_width = wav_file.getsampwidth() * 8  # Convert bytes to bits
                    sample_rate = wav_file.getframerate()
                    if sample_width == 16 and sample_rate == 44100:
                        return JsonResponse(
                            {
                                "error": "Audio file cannot be of 16 Bit Depth + 44100Hz Sample Rate!!"
                            }
                        )
                return JsonResponse(
                    {"success": "Audio file passed the bit-rate check!"}
                )
            else:
                return JsonResponse({"error": "Audio file not found!"})
        except Exception as e:
            print(f"Error: {e}")
            return JsonResponse(
                {"error": "Error while checking audio file, please check your audio!"}
            )


def _send_ddex_takedown_to_dsps(release):
    """Send DDEX takedown (PurgeReleaseMessage / TakeDown) to Audiomack, Gaana, TikTok, and Apple Music (Merlin Bridge). Logs errors; does not raise."""
    import logging
    log = logging.getLogger(__name__)
    try:
        from releases.audiomack_delivery import deliver_takedown_to_audiomack
        from releases.gaana_delivery import deliver_takedown_to_gaana
        from releases.tiktok_delivery import deliver_takedown_to_tiktok
        from releases.merlin_bridge_delivery import deliver_takedown_to_merlin_bridge
        a_ok, a_err, _ = deliver_takedown_to_audiomack(release)
        g_ok, g_err, _ = deliver_takedown_to_gaana(release)
        t_ok, t_err, _ = deliver_takedown_to_tiktok(release)
        m_ok, m_err, _ = deliver_takedown_to_merlin_bridge(release)
        if a_ok:
            log.info("DDEX takedown sent to Audiomack for release %s (UPC %s)", release.id, getattr(release, "upc", ""))
        else:
            log.warning("DDEX takedown to Audiomack failed for release %s: %s", release.id, a_err or "unknown")
        if g_ok:
            log.info("DDEX takedown sent to Gaana for release %s (UPC %s)", release.id, getattr(release, "upc", ""))
        else:
            log.warning("DDEX takedown to Gaana failed for release %s: %s", release.id, g_err or "unknown")
        if t_ok:
            log.info("DDEX takedown sent to TikTok for release %s (UPC %s)", release.id, getattr(release, "upc", ""))
        else:
            log.warning("DDEX takedown to TikTok failed for release %s: %s", release.id, t_err or "unknown")
        if m_ok:
            log.info("DDEX takedown sent to Apple Music (Merlin Bridge) for release %s (UPC %s)", release.id, getattr(release, "upc", ""))
        else:
            log.warning("DDEX takedown to Apple Music (Merlin Bridge) failed for release %s: %s", release.id, m_err or "unknown")
    except Exception as e:
        log.exception("DDEX takedown to DSPs failed for release %s: %s", release.id, e)


def takedown_request(request, takedown_primary_uuid, takedown_upc, takedown_requester):
    if (
        request.user.is_authenticated
        and request.user.is_active
        and has_release_access(request.user, takedown_primary_uuid)
    ):
        # Check if a takedown request is already submitted for this release
        release = Release.objects.get(pk=takedown_primary_uuid)
        if not release.takedown_requested:
            # Marking release as takedown requested
            release.takedown_requested = True
            release.save()
            # Sending takedown request emails to support and deployment
            processor.send_takedown_emails(takedown_upc, takedown_requester)
            # Send DDEX takedown to all stores: Audiomack, Gaana, TikTok, Apple Music (Merlin Bridge)
            _send_ddex_takedown_to_dsps(release)
            message = "Takedown request submitted. Release will be taken down from Audiomack, Gaana, TikTok, and Apple Music. You have been notified by email."
        else:
            message = "A takedown request was already submitted for this release."
        return JsonResponse({"success": True, "message": message})
    else:
        return JsonResponse({"message": "You are not authorized to view this page!"})


def claims_removal_view(request, data):
    if request.user.is_authenticated and is_active(request.user):
        processor.send_whitelist_emails(data, request.user)
        return JsonResponse({"message": "Request submitted for Claims Releasing!"})
    else:
        return JsonResponse({"message": "You are not authorized to view this page!"})


def release_delete_view(request, primary_uuid):
    if (
        request.user.is_authenticated
        and request.user.is_active
        and has_release_access(request.user, primary_uuid)
    ):
        if request.method == "GET":
            delete_release(primary_uuid)
            return JsonResponse({"message": "Release deleted successfully!"})
        else:
            return HttpResponseNotFound("Request Method not allowed!")
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


def artists_view(request):
    if request.user.is_authenticated and request.user.is_active:
        if request.method == "GET":
            return render(
                request,
                "volt_artists.html",
                context={
                    "username": request.user,
                    "requesting_user_role": request.user.role,
                },
            )
        else:
            return HttpResponseNotFound("Request Method not allowed!")
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


def artists_list_view(request):
    if request.user.is_authenticated and request.user.is_active:
        if request.method == "GET":
            queryset = []
            if request.user.role == CDUser.ROLES.ADMIN:
                queryset = Artist.objects.all()
            else:
                queryset = Artist.objects.filter(user=request.user)
            headers = "<th>Artist</th><th>Created By</th><th>Update</th>"
            body = ""
            for artist in queryset:
                body += "<tr>"
                body += f"<td>{artist.name}</td>"
                body += f"<td>{artist.user.email}</td>"
                body += f'<td><a href="/releases/artists/update/{artist.pk}"><span style="cursor:pointer;" class="material-symbols-outlined">edit</span></a></td>'
                body += "</tr>"
            table = f"""<table class="table table-hover" id="data_table_artists">
                <thead>
                    {headers}
                </thead>
                <tbody>
                    {body}
                </tbody>
                </table>
            """
            return JsonResponse({"table": table})
        else:
            return HttpResponseNotFound("Request Method not allowed!")
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


def artists_add_view(request):
    if request.user.is_authenticated and request.user.is_active:
        if request.method == "POST":
            creator = request.user
            artist_name = (request.POST.get("artist_name_input") or "").strip()
            first_name = (request.POST.get("first_name_input") or "").strip()
            last_name = (request.POST.get("last_name_input") or "").strip()
            apple_music = request.POST.get("apple_music_input", "").strip()
            youtube_username = request.POST.get("youtube_username_input", "").strip()
            spotify_id = request.POST.get("spotify_id_input", "").strip()
            audiomack_id = request.POST.get("audiomack_id_input", "").strip()
            soundcloud_page = request.POST.get("soundcloud_page_input", "").strip()
            facebook_page = request.POST.get("facebook_page_input", "").strip()
            website_page = request.POST.get("website_page_input", "").strip()
            x_username = request.POST.get("x_username_input", "").strip()
            biography = request.POST.get("biography_input", "").strip()

            if not artist_name:
                message = "Artist name is required. Please enter a valid artist name."
                return render(
                    request,
                    "volt_artists.html",
                    context={
                        "username": request.user,
                        "requesting_user_role": request.user.role,
                        "message": message,
                    },
                )

            if request.user.role == CDUser.ROLES.MEMBER:
                creator = get_leader(request.user)
            # Get the maximum artist_id and increment by 1 (exclude NULL artist_ids)
            max_artist = Artist.objects.filter(artist_id__isnull=False).order_by('-artist_id').first()
            new_artist_id = 1 if not max_artist or max_artist.artist_id is None else max_artist.artist_id + 1
            
            
            if not Artist.objects.filter(user=creator, name=artist_name).exists():
                new_artist = Artist.objects.create(
                    user=creator,
                    artist_id=new_artist_id,
                    name=artist_name,
                    first_name=first_name,
                    last_name=last_name,
                    apple_music_id=apple_music,
                    spotify_id=spotify_id,
                    youtube_username=youtube_username,
                    audiomack_id=audiomack_id,
                    soundcloud_page=soundcloud_page,
                    facebook_page=facebook_page,
                    x_username=x_username,
                    website=website_page,
                    biography=biography,
                )
                new_artist.save()
                message = f"Succesfully created artist {artist_name}"
            else:
                message = "Artist already exists! Please try another name."
            return render(
                request,
                "volt_artists.html",
                context={
                    "username": request.user,
                    "requesting_user_role": request.user.role,
                    "message": message,
                },
            )
        else:
            return HttpResponseNotFound("Request Method not allowed!")
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


def artists_update_view(request, artist_id):
    if request.user.is_authenticated and request.user.is_active:
        if request.method == "GET":
            context = {
                "username": request.user,
                "requesting_user_role": request.user.role,
                "artist_id": artist_id,
            }
            if Artist.objects.filter(id=artist_id).exists():
                artist = Artist.objects.get(id=artist_id)
                context["artist_name"] = artist.name
                context["first_name"] = artist.first_name if artist.first_name else ""
                context["last_name"] = artist.last_name if artist.last_name else ""
                context["apple_music"] = artist.apple_music_id
                context["youtube_username"] = artist.youtube_username
                context["spotify_id"] = artist.spotify_id
                context["audiomack_id"] = artist.audiomack_id or ""
                context["soundcloud_page"] = artist.soundcloud_page
                context["facebook_page"] = artist.facebook_page
                context["website_page"] = artist.website
                context["x_username"] = artist.x_username
                context["biography"] = artist.biography
            return render(
                request,
                "volt_artist_update.html",
                context=context,
            )
        if request.method == "POST":
            artist_id = request.POST.get("artist_id")
            artist_name_input = request.POST.get("artist_name_input")
            first_name = request.POST.get("first_name_input", "").strip()
            last_name = request.POST.get("last_name_input", "").strip()
            apple_music = request.POST.get("apple_music_input", "").strip()
            youtube_username = request.POST.get("youtube_username_input", "").strip()
            spotify_id = request.POST.get("spotify_id_input", "").strip()
            audiomack_id = request.POST.get("audiomack_id_input", "").strip()
            soundcloud_page = request.POST.get("soundcloud_page_input", "").strip()
            facebook_page = request.POST.get("facebook_page_input", "").strip()
            website_page = request.POST.get("website_page_input", "").strip()
            x_username = request.POST.get("x_username_input", "").strip()
            biography = request.POST.get("biography_input", "").strip()
            try:
                artist_object = Artist.objects.get(id=artist_id)
                if request.user.role == CDUser.ROLES.ADMIN:
                    artist_object.name = artist_name_input
                # All users can update first_name and last_name (optional)
                    artist_object.first_name = first_name
                    artist_object.last_name = last_name
                artist_object.apple_music_id = apple_music
                artist_object.youtube_username = youtube_username
                artist_object.spotify_id = spotify_id
                artist_object.audiomack_id = audiomack_id
                artist_object.soundcloud_page = soundcloud_page
                artist_object.facebook_page = facebook_page
                artist_object.x_username = x_username
                artist_object.biography = biography
                artist_object.website = website_page
                artist_object.save()
                message = f"Succesfully updated artist!"
            except:
                message = "Failed to update artist! Please contact admin."
            return render(
                request,
                "volt_artists.html",
                context={
                    "username": request.user,
                    "requesting_user_role": request.user.role,
                    "message": message,
                },
            )
        else:
            return HttpResponseNotFound("Request Method not allowed!")
    else:
        return HttpResponseNotFound("You are not authorized to view this page!")


def fetch_artist_releases_view(request, artist_id):
    if request.user and request.user.is_authenticated and request.user.is_active:
        artist = Artist.objects.get(id=artist_id)
        related_artists = RelatedArtists.objects.filter(
            artist=artist,
            relation_key="release",
            role__in=("Primary Artist", "Featuring"),
        )
        rows = ""
        for related_artist in related_artists:
            rows += f"<tr><td><a target='_blank' href='/releases/release_info/{related_artist.release.pk}'>{related_artist.release.title}</a></td></tr>"
        table = f"""
            <table class="table table-hover" id="artist_releases_datatable">
                <thead>
                    <th>Title<th>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        """
        return JsonResponse({"success": "success", "data": table})
    else:
        return {}


def fetch_artist_tracks_view(request, artist_id):
    if request.user and request.user.is_authenticated and request.user.is_active:
        artist = Artist.objects.get(id=artist_id)
        related_artists = RelatedArtists.objects.filter(
            artist=artist,
            relation_key="track",
            role__in=("Primary Artist", "Featuring"),
        )
        rows = ""
        for related_artist in related_artists:
            rows += f"<tr><td><a target='_blank' href='/releases/tracks_info/{related_artist.track.release.pk}/track/{related_artist.track.pk}'>{related_artist.track.title}</a></td></tr>"
        table = f"""
            <table class="table table-hover" id="artist_tracks_datatable">
                <thead>
                    <th>Title<th>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        """
        return JsonResponse({"success": "success", "data": table})
    else:
        return {}


@csrf_exempt
def create_split_release_royalty(request):
    # Split royalty is only available to normal users
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error': 'Authentication required.'}, status=401)
    
    if request.user.role != CDUser.ROLES.NORMAL:
        return JsonResponse({'error': 'Split royalty is only available to normal users.'}, status=403)
    
    if not request.user.split_royalties_enabled:
        return JsonResponse({'error': 'Split royalties are not enabled for your account.'}, status=403)
    
    if request.method == "POST":
        try:
            data = request.POST or json.loads(request.body)
            user_id = data.get('user_id')
            release_id = data.get('release_id')
            track_id = data.get('track_id')
            recipient_name = data.get('recipient_name')
            recipient_email = data.get('recipient_email')
            recipient_role = data.get('recipient_role')
            recipient_percentage_str = data.get('recipient_percentage')

            if not all([user_id, release_id, track_id, recipient_name, recipient_email, recipient_role, recipient_percentage_str]):
                return JsonResponse({'error': 'All fields are required.'}, status=400)
            
            # Ensure the user_id matches the requesting user (normal users can only create splits for their own tracks)
            if int(user_id) != request.user.id:
                return JsonResponse({'error': 'You can only create splits for your own tracks.'}, status=403)

            try:
                recipient_percentage = float(recipient_percentage_str)
            except ValueError:
                return JsonResponse({'error': 'Invalid percentage value. Please provide a number.'}, status=400)

            if recipient_percentage <= 0:
                return JsonResponse({'error': 'Percentage must be greater than 0.'}, status=400)

            user = CDUser.objects.get(pk=user_id)
            release = Release.objects.get(pk=release_id)
            track = Track.objects.get(pk=track_id)

            # Check if a split with this email already exists
            existing_split_with_email = SplitReleaseRoyalty.objects.filter(
                track_id=track,
                recipient_email=recipient_email
            ).first()
            
            if existing_split_with_email:
                # If split exists, this should be an UPDATE, not CREATE
                # But if frontend calls CREATE, we'll handle it by treating as update scenario
                return JsonResponse({
                    'error': f'A split with email {recipient_email} already exists for this track. Please use the update endpoint instead.'
                }, status=400)

            # Validate total splits don't exceed 100%
            # Count all existing splits (including owner's split)
            existing_splits = SplitReleaseRoyalty.objects.filter(
                track_id=track,
                release_id=release
            )
            total_percentage = sum(split.recipient_percentage for split in existing_splits)
            
            # Calculate available percentage
            available_percentage = 100 - total_percentage
            
            if total_percentage + recipient_percentage > 100:
                return JsonResponse({
                    'error': f'Total split percentage would exceed 100%. Current total: {total_percentage}%, New: {recipient_percentage}%, Available: {available_percentage}%'
                }, status=400)

            # Normal users: Auto-balancing system
            # The frontend calculates exact percentages for all splits including the owner
            # We just need to validate the percentage is not negative
            if recipient_percentage < 0:
                return JsonResponse({'error': 'Percentage cannot be negative.'}, status=400)

            # Create or get recipient user
            create_user_if_not_exists(recipient_email, user)

            # Create the new split
            split = SplitReleaseRoyalty.objects.create(
                user_id=user, # Associate with the track creator (owner)
                release_id=release,
                track_id=track,
                recipient_name=recipient_name,
                recipient_email=recipient_email,
                recipient_role=recipient_role,
                recipient_percentage=recipient_percentage
            )
            return JsonResponse({'message': 'Split created successfully.', 'id': split.id, 'refresh': True})
        except (CDUser.DoesNotExist, Release.DoesNotExist, Track.DoesNotExist) as e:
            return JsonResponse({'error': str(e)}, status=400) # Bad request if related objects not found
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'error': 'An unexpected error occurred: ' + str(e)}, status=500)
    else:
        return JsonResponse({'error': 'POST required'}, status=405)


@csrf_exempt
def update_split_release_royalty(request, split_id):
    # Split royalty is only available to normal users
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error': 'Authentication required.'}, status=401)
    
    if request.user.role != CDUser.ROLES.NORMAL:
        return JsonResponse({'error': 'Split royalty is only available to normal users.'}, status=403)
    
    if not request.user.split_royalties_enabled:
        return JsonResponse({'error': 'Split royalties are not enabled for your account.'}, status=403)
    
    context = {}
    if request.method == "POST":
        try:
            data = request.POST or json.loads(request.body)
            recipient_name = data.get('recipient_name')
            recipient_email = data.get('recipient_email')
            recipient_role = data.get('recipient_role')
            recipient_percentage = data.get('recipient_percentage')

            split = SplitReleaseRoyalty.objects.get(pk=split_id)
            
            # Ensure the split belongs to the requesting user (normal users can only update their own splits)
            if split.user_id != request.user:
                return JsonResponse({'error': 'You can only update splits for your own tracks.'}, status=403)

            if recipient_name is not None:
                split.recipient_name = recipient_name
            if recipient_email is not None and split.recipient_email != recipient_email:
                # Check for existing split with the new email for the same track and user


                if SplitReleaseRoyalty.objects.filter(
                    user_id=split.user_id,
                    release_id=split.release_id,
                    track_id=split.track_id,
                    recipient_email=recipient_email
                ).exclude(pk=split_id).exists():
                    return JsonResponse({'error': 'A split with this recipient email already exists for this track.'}, status=400)
                split.recipient_email = recipient_email
            if recipient_role is not None:
                split.recipient_role = recipient_role
            if recipient_percentage is not None:
                try:
                    new_percentage = float(recipient_percentage)
                except (TypeError, ValueError):
                    return JsonResponse({'error': 'Invalid percentage value.'}, status=400)
                
                # Validate total splits don't exceed 100%
                other_total = SplitReleaseRoyalty.objects.filter(
                    track_id=split.track_id,
                    release_id=split.release_id
                ).exclude(pk=split_id).aggregate(total=Sum('recipient_percentage'))['total'] or 0
                
                if new_percentage + other_total > 100:
                    return JsonResponse({
                        'error': f'Total split percentage cannot exceed 100%. Current total: {other_total}%, New: {new_percentage}%, Available: {100 - other_total}%'
                    }, status=400)
                
                if new_percentage < 0:
                    return JsonResponse({'error': 'Percentage cannot be negative.'}, status=400)
                
                split.recipient_percentage = new_percentage

            split.save()
            return JsonResponse({'message': 'Split updated successfully.', 'refresh': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'POST required'}, status=405)


def list_split_release_royalties(request):
    # Split royalty is available to admin users (to see all splits) and normal users with split_royalties_enabled
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error': 'Authentication required.'}, status=401)
    
    # Admin can see all splits
    if request.user.role == CDUser.ROLES.ADMIN:
        splits = SplitReleaseRoyalty.objects.all().select_related('user_id', 'release_id', 'track_id')
    elif request.user.role == CDUser.ROLES.NORMAL:
        if not request.user.split_royalties_enabled:
            return JsonResponse({'error': 'Split royalties are not enabled for your account.'}, status=403)
        # Normal users can only see splits for their own tracks
        splits = SplitReleaseRoyalty.objects.filter(user_id=request.user).select_related('user_id', 'release_id', 'track_id')
    else:
        return JsonResponse({'error': 'Split royalty is only available to admin or normal users with split royalties enabled.'}, status=403)
    
    release_id = request.GET.get('release_id')
    track_id = request.GET.get('track_id')
    if release_id:
        splits = splits.filter(release_id=release_id)
    if track_id:
        splits = splits.filter(track_id=track_id)
    data = [
        {
            'id': split.id,
            'user_id': split.user_id.id,
            'user_email': split.user_id.email,
            'release_id': split.release_id.id,
            'track_id': split.track_id.id,
            'recipient_name': split.recipient_name,
            'recipient_email': split.recipient_email,
            'recipient_role': split.recipient_role,
            'recipient_percentage': split.recipient_percentage,
            'created_at': split.created_at,
            'updated_at': split.updated_at,
        }
        for split in splits
    ]
    return JsonResponse({'splits': data})


@csrf_exempt
def delete_split_release_royalty(request, split_id):
    # Split royalty is only available to normal users
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error': 'Authentication required.'}, status=401)
    
    if request.user.role != CDUser.ROLES.NORMAL:
        return JsonResponse({'error': 'Split royalty is only available to normal users.'}, status=403)
    
    if not request.user.split_royalties_enabled:
        return JsonResponse({'error': 'Split royalties are not enabled for your account.'}, status=403)
    
    if request.method == "POST":
        try:
            split = SplitReleaseRoyalty.objects.get(pk=split_id)
            
            # Ensure the split belongs to the requesting user (normal users can only delete their own splits)
            if split.user_id != request.user:
                return JsonResponse({'error': 'You can only delete splits for your own tracks.'}, status=403)
            
            # For normal users: No additional logic needed - auto-balancing system handles it
            split.delete()
            return JsonResponse({'message': 'Split deleted successfully.', 'refresh': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'POST required'}, status=405)




def split_royalty_page(request):
    # Split royalty is available to admin users (to see all splits) and normal users with split_royalties_enabled
    if request.user.is_authenticated and request.user.is_active and (
        request.user.role == CDUser.ROLES.ADMIN or 
        (request.user.role == CDUser.ROLES.NORMAL and request.user.split_royalties_enabled)
    ):
        return render(request, 'volt_split_royalty.html', {
            'username': request.user,
            'requesting_user_role': getattr(request.user, 'role', None),
        })
    else:
        return HttpResponseNotFound("<h1>You are not authorized to view this page!</h1>")


@require_GET
def get_user_tracks(request):
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error': 'Authentication required'}, status=403)
    user = request.user
    if hasattr(user, 'role') and user.role == CDUser.ROLES.MEMBER:
        # If user is a member, get their leader
        leader = get_leader(user)
        tracks = Track.objects.filter(created_by=leader)
    else:
        tracks = Track.objects.filter(created_by=user)
    data = [
        {
            'id': track.id,
            'title': track.title,
            'release_id': track.release.id
        }
        for track in tracks
    ]
    return JsonResponse({'tracks': data})


@require_GET
def get_track_split_percentage(request):
    # Split royalty is available to admin users (to see all splits) and normal users with split_royalties_enabled
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error': 'Authentication required.'}, status=401)
    
    track_id = request.GET.get('track_id')
    print(track_id)
    if not track_id:
        return JsonResponse({'error': 'track_id required'}, status=400)
    
    try:
        track = Track.objects.get(pk=track_id)
        
        # Admin can check any track, normal users can only check their own tracks
        if request.user.role == CDUser.ROLES.ADMIN:
            # Admin can check any track
            pass
        elif request.user.role == CDUser.ROLES.NORMAL:
            if not request.user.split_royalties_enabled:
                return JsonResponse({'error': 'Split royalties are not enabled for your account.'}, status=403)
            # Normal users can only check splits for their own tracks
            if track.release.created_by != request.user:
                return JsonResponse({'error': 'You can only check splits for your own tracks.'}, status=403)
        else:
            return JsonResponse({'error': 'Split royalty is only available to admin or normal users with split royalties enabled.'}, status=403)
        
        # For admin, get total for track owner. For normal users, get total for their own tracks.
        if request.user.role == CDUser.ROLES.ADMIN:
            # Admin can see total for any track (use track owner)
            total = SplitReleaseRoyalty.objects.filter(track_id=track_id).aggregate(
                total=Sum('recipient_percentage')
            )['total'] or 0
        else:
            # Normal users see total for their own tracks
            total = SplitReleaseRoyalty.objects.filter(track_id=track_id, user_id=request.user).aggregate(
                total=Sum('recipient_percentage')
            )['total'] or 0
        return JsonResponse({'total_percentage': float(total)})
    except Track.DoesNotExist:
        return JsonResponse({'error': 'Track not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def user_split_royalties_list(request):
    # Split royalty is available to admin users (to see all splits) and normal users with split_royalties_enabled
    if request.user.role == CDUser.ROLES.ADMIN:
        # Admin can see all splits
        splits = SplitReleaseRoyalty.objects.all().select_related('release_id', 'track_id', 'user_id')
    elif request.user.role == CDUser.ROLES.NORMAL:
        if not request.user.split_royalties_enabled:
            return JsonResponse({'error': 'Split royalties are not enabled for your account.'}, status=403)
        # Normal users see only their splits (as owner or recipient)
        user = request.user
        splits = SplitReleaseRoyalty.objects.filter(
            Q(user_id=user) | Q(recipient_email=user.email)
        ).select_related('release_id', 'track_id')
    else:
        return JsonResponse({'error': 'Split royalty is only available to admin or normal users with split royalties enabled.'}, status=403)
    data = [
        {
            'id': split.id,
            'user_email': split.user_id.email,
            'release_title': split.release_id.title,
            'track_title': split.track_id.title,
            'recipient_name': split.recipient_name,
            'recipient_email': split.recipient_email,
            'recipient_role': split.recipient_role,
            'recipient_percentage': split.recipient_percentage,
            'created_at': split.created_at,
            'updated_at': split.updated_at,
        }
        for split in splits
    ]
    return JsonResponse({'splits': data})



@login_required
def admin_track_split_royalties_list(request):
    if not hasattr(request.user, 'role') or request.user.role != CDUser.ROLES.ADMIN:
        return JsonResponse({'error': 'You are not authorized to view this page!'}, status=403)

    # Fetch all split royalties and group them by track
    splits = SplitReleaseRoyalty.objects.select_related('track_id', 'release_id', 'user_id').order_by('track_id__title')

    grouped_data = defaultdict(lambda: {'track_title': '', 'release_title': '', 'splits': [], 'total_amount': 0})

    # Get total amounts for each track from royalties
    with connection.cursor() as cursor:
        for split in splits:
            track_key = f"{split.track_id.id}"
            if not grouped_data[track_key]['track_title']:
                grouped_data[track_key]['track_title'] = split.track_id.title
                # Get total amount for this track
                track_query = """
                    SELECT SUM(r.net_total_INR) as total_amount
                    FROM releases_royalties r
                    LEFT JOIN releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc)
                    LEFT JOIN releases_track t ON UPPER(m.isrc) = UPPER(t.isrc) AND m.track = t.title
                    WHERE t.id = %s
                """
                cursor.execute(track_query, [split.track_id.id])
                result = cursor.fetchone()
                grouped_data[track_key]['total_amount'] = float(result[0] if result[0] else 0)

            if not grouped_data[track_key]['release_title']:
                grouped_data[track_key]['release_title'] = split.release_id.title

            # Calculate split due amount based on percentage
            split_due_amount = round(grouped_data[track_key]['total_amount'] * (split.recipient_percentage / 100.0), 2)

            grouped_data[track_key]['splits'].append({
                'owner_email': split.user_id.email,
                'recipient_name': " " if split.recipient_name =='Unknown User' else split.recipient_name,
                'recipient_email': split.recipient_email,
                'recipient_role': split.recipient_role,
                'recipient_percentage': split.recipient_percentage,
                'split_due_amount': split_due_amount
            })
    
    # Convert defaultdict to a list of dicts for JSON serialization
    final_data = []
    for track_id, track_data in grouped_data.items():
        final_data.append({
            'track_id': track_id,
            'track_title': track_data['track_title'],
            'release_title': track_data['release_title'],
            'total_amount': track_data['total_amount'],
            'splits': track_data['splits']
        })

    return JsonResponse({'all_track_splits': final_data})


@login_required
def user_tracks_with_splits(request):
    """
    Get tracks owned by the user with their associated splits organized by track
    """
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error': 'Authentication required'}, status=403)
    
    user = request.user
    if hasattr(user, 'role') and user.role == CDUser.ROLES.MEMBER:
        # If user is a member, get their leader's tracks
        leader = get_leader(user)
        tracks = Track.objects.filter(created_by=leader).select_related('release')
    else:
        tracks = Track.objects.filter(created_by=user).select_related('release')
    
    tracks_data = []
    for track in tracks:
        # Get all splits for this track
        splits = SplitReleaseRoyalty.objects.filter(track_id=track).select_related('user_id')
        splits_data = []
        total_percentage = 0
        
        for split in splits:
            splits_data.append({
                'id': split.id,
                'recipient_name': split.recipient_name,
                'recipient_email': split.recipient_email,
                'recipient_role': split.recipient_role,
                'recipient_percentage': split.recipient_percentage,
                'owner_email': split.user_id.email,
            })
            total_percentage += split.recipient_percentage
        
        tracks_data.append({
            'id': track.id,
            'title': track.title,
            'release_id': track.release.id,
            'release_title': track.release.title,
            'splits': splits_data,
            'total_percentage': total_percentage,
            'remaining_percentage': 100 - total_percentage
        })
    
    return JsonResponse({'tracks': tracks_data})


