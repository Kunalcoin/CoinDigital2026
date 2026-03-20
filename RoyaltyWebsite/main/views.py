# Standard library
import logging
logger = logging.getLogger(__name__)
import json
import traceback
import calendar
from datetime import datetime, timedelta
from subprocess import Popen
from collections import defaultdict
from releases.models import Track, SplitReleaseRoyalty, Release  # Add these imports if not present

# Django imports
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.db import connection, transaction
from django.db.models import (
    Sum, Q, Case, When, Value, OuterRef, Subquery, DecimalField, F
)
from django.db.models.functions import TruncMonth, Round
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

# Third-party imports
import pandas as pd

# Local app imports
from .models import (
    CDUser, Ratio, Request, Payment, DueAmount,
    Announcement, LANGUAGES, COUNTRIES
)
from .processor import processor, admin, intermediate, normal
from .reset_token_handler import TokenHandler
from handlers import FileHandler, DataValidator
from constants import *
from commons.navigation import get_navigation, navigation as _navigation
from releases.models import Royalties, Metadata, Release, Artist


def is_valid_value(value):
    """Check if value is valid (not NaN, None, or string representations of null)"""
    if pd.isna(value):  # Handles actual NaN, None
        return False
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in ['nan', 'na', 'null', 'none', '']:
            return False
    return True

def safe_get(row, key, default, converter=None):
    """Safely get value from row, handling all types of null/NaN values"""
    value = row.get(key, default)
    if is_valid_value(value):
        return converter(value) if converter else value
    return default

def fetch_artist_from_id(id):
    """
    Fetch artist name by ID using Django ORM
    """
    try:
        artist = Artist.objects.get(id=int(id))
        return artist.name
    except Artist.DoesNotExist:
        return None
    except Exception as e:
        print(f"Error fetching artist: {e}")
    return None


def update_password(username, new_password):
    """
    Update user password using Django ORM
    """
    try:
        user = CDUser.objects.get(email=username)
        user.set_password(new_password)  # Django handles password hashing
        user.save()
        return True
    except CDUser.DoesNotExist:
        return False
    except Exception as e:
        print(f"Error updating password: {e}")
        return False


def get_navigation(page, navigation):
    output = []
    for name, icon in navigation.items():
        nav_item = "nav-item"
        extension = name.lower().replace(" ", "_")
        if name == page or extension == page:
            nav_item += " active"
        output.append((name, extension, nav_item, icon))
    return output


def divide_channels(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]

def get_leader(username):
    """
    Get team leader for a member user using Django ORM
    Uses the parent field in CDUser model to determine team hierarchy
    """
    try:
        user = CDUser.objects.get(email=username)
        if user.parent:
            return user.parent.email
        return username  # If no parent, user is their own leader
    except CDUser.DoesNotExist:
        return None


def is_active(user):
    """
    Check if user is active using Django ORM
    """
    try:
        if isinstance(user, str):
            # If username string is passed, get user object
            user_obj = CDUser.objects.get(email=user)
            return user_obj.is_active
        else:
            # If user object is passed directly
            return user.is_active
    except CDUser.DoesNotExist:
        return False
    except Exception as e:
        print(f"Error checking user status: {e}")
        return False


# Views
def analytics_detailed(request, section):
    if request.user.is_authenticated and is_active(request.user):
        requesting_user_role = processor.get_user_role(request.user)
        if request.method == "GET":

            def transform_revenue(
                df, current_user, requesting_user_role, children=None
            ):
                """Input dataframe will contain username,ratio in each record"""

                has_channels = "channel" in df.columns

                if requesting_user_role == "normal" or requesting_user_role == "member":
                    # revenue is as the ration of normal user
                    df["revenue"] = df.apply(
                        lambda x: round(
                            (
                                x["revenue"] * (x["yt_ratio"] / 100)
                                if has_channels
                                and x["channel"] == "Youtube Official Channel"
                                else x["revenue"] * (x["ratio"] / 100)
                            ),
                            2,
                        ),
                        axis=1,
                    )

                if requesting_user_role == "intermediate":
                    # Revenue will be intermediates_ratio - normal_user_ratio * revenue e.g. (90-80) * revenue
                    requested_user_role, ratio, yt_ratio = processor.get_user_info(
                        current_user
                    )
                    intermediate_user_ratio = ratio
                    intermediate_user_yt_ratio = yt_ratio
                    df["revenue"] = df.apply(
                        lambda x: round(
                            (
                                x["revenue"]
                                * (
                                    intermediate_user_yt_ratio / 100
                                    - x["yt_ratio"] / 100
                                )
                                if has_channels
                                and x["channel"] == "Youtube Official Channel"
                                else x["revenue"]
                                * (intermediate_user_ratio / 100 - x["ratio"] / 100)
                            ),
                            2,
                        ),
                        axis=1,
                    )

                if requesting_user_role == "admin":
                    # Revenue will be 100 - intermediates_ratio  * revenue e.g. (100-90) * revenue
                    # Fetching ratios of users first for which we are computing
                    # Updated table references for new schema with Ratio joins - Convert to Django database manager
                    ratios_query = f"""select * from (    
                                        select distinct u.email as username, u.role, u.parent_id as belongs_to, COALESCE(r.stores, 0) as ratio, COALESCE(r.youtube, 0) as yt_ratio
                                        from main_cduser u 
                                        LEFT JOIN main_ratio r ON u.id = r.user_id AND r.status = 'active'
                                        where u.role = 'normal' and ( u.parent_id is NULL or u.parent_id = (SELECT id FROM main_cduser WHERE email = '{current_user}') or u.parent_id in 
                                                (select id from main_cduser where role = 'admin') )
                                    UNION ALL
                                        select distinct u1.email as username, u1.role, u1.parent_id as belongs_to, COALESCE(r2.stores, 0) as ratio, COALESCE(r2.youtube, 0) as yt_ratio 
                                        from main_cduser u1
                                        LEFT JOIN main_ratio r1 ON u1.id = r1.user_id AND r1.status = 'active'
                                        JOIN main_cduser u2 on u1.parent_id = u2.id
                                        LEFT JOIN main_ratio r2 ON u2.id = r2.user_id AND r2.status = 'active'
                                        where u1.parent_id in (select id from main_cduser where role = 'intermediate')
                                    UNION ALL
                                        select distinct u.email as username, u.role, u.parent_id as belongs_to, COALESCE(r.stores, 0) as ratio, COALESCE(r.youtube, 0) as yt_ratio
                                        from main_cduser u
                                        LEFT JOIN main_ratio r ON u.id = r.user_id AND r.status = 'active'
                                        where u.role = 'intermediate'
                                    ) tt order by username;
                                """
                    with connection.cursor() as cursor:
                        cursor.execute(ratios_query)
                        columns = [col[0] for col in cursor.description]
                        ratios_ytratio = pd.DataFrame(cursor.fetchall(), columns=columns)
                    ratios = {
                        row["username"].lower(): row["ratio"]
                        for index, row in ratios_ytratio.iterrows()
                    }
                    yt_ratios = {
                        row["username"].lower(): row["yt_ratio"]
                        for index, row in ratios_ytratio.iterrows()
                    }
                    # Now the above ratios we just extracted will be used for revenue calculation as normal users having intermediate as parents are also handled, not the ones which are in dataframe
                    admin_ratio = 100
                    admin_yt_ratio = 100
                    df["revenue"] = df.apply(
                        lambda x: round(
                            (
                                x["revenue"]
                                * (
                                    admin_yt_ratio / 100
                                    - yt_ratios[f'{x["user"].lower()}'] / 100
                                )
                                if has_channels
                                and x["channel"] == "Youtube Official Channel"
                                else x["revenue"]
                                * (
                                    admin_ratio / 100
                                    - ratios[f'{x["user"].lower()}'] / 100
                                )
                            ),
                            2,
                        ),
                        axis=1,
                    )

                # Drop the ratio and other unnecssary columns and return df

                return df

            filter_ = ""
            children = None
            if requesting_user_role == "normal":
                filter_ = f" AND ul.email = '{request.user.get_username()}' "
            elif requesting_user_role == "intermediate":
                children = processor.get_users_belongs_to(request.user)
                children.append(request.user)
                children = [f"'{child}'" for child in children]
                children = ",".join(children)
                filter_ = f" AND ul.email in ({children}) "
            elif requesting_user_role == "member":
                leader = get_leader(request.user)
                filter_ = f" AND ul.email = '{leader}' "
            else:
                pass
            if section == "tracks":
                fetch_query = f"""
                    SELECT 
                        ry.serial_number, 
                        rt.title AS title, 
                        COALESCE(artists.artist_names, 'N/A') AS artist, 
                        ry.revenue as revenue, 
                        rt.primary_genre as genre, 
                        upper(rt.isrc) as isrc, 
                        rr.title as release_title,
                        rr.original_release_date as release_date,
                        COALESCE(ur.stores, 0) as ratio,
                        COALESCE(ur.youtube, 0) as yt_ratio,
                        ul.email as `user`
                    FROM 
                        releases_track rt 
                    JOIN (
                        SELECT 
                            row_number() over (order by round(SUM(ry.net_total_INR), 2) desc) serial_number,
                            upper(ry.isrc) as isrc, round(SUM(ry.net_total_INR), 2) AS revenue
                        FROM
                            releases_royalties ry
                        JOIN 
                            releases_track rt2 on 
                                upper(ry.isrc) = upper(rt2.isrc) 
                        JOIN releases_release rr2 ON rt2.release_id = rr2.id
                        JOIN main_cduser ul2 ON rr2.created_by_id = ul2.id
                        WHERE ry.end_date > NOW()-interval 3 month {filter_.replace('ul.email', 'ul2.email') if filter_ else ''}
                        GROUP BY ry.isrc
                        LIMIT 10
                    ) ry ON upper(ry.isrc) = upper(rt.isrc)
                    JOIN releases_release rr ON rt.release_id = rr.id 
                    JOIN main_cduser ul ON rr.created_by_id = ul.id
                    LEFT JOIN main_ratio ur ON ul.id = ur.user_id AND ur.status = 'active'
                    LEFT JOIN (
                        SELECT 
                            ra.track_id,
                            GROUP_CONCAT(DISTINCT ra_art.name ORDER BY ra.role = 'Primary Artist' DESC, ra_art.name SEPARATOR ', ') as artist_names
                        FROM releases_relatedartists ra
                        LEFT JOIN releases_artist ra_art ON ra.artist_id = ra_art.id
                        WHERE ra_art.name IS NOT NULL AND ra_art.name NOT LIKE '%_release_%'
                        GROUP BY ra.track_id
                    ) artists ON rt.id = artists.track_id
                    WHERE rr.published = true;
                """
                # Convert to Django database manager
                with connection.cursor() as cursor:
                    cursor.execute(fetch_query)
                    columns = [col[0] for col in cursor.description]
                    df = pd.DataFrame(cursor.fetchall(), columns=columns)
                df = transform_revenue(df, request.user, requesting_user_role, children)
                df = df.drop(columns=["ratio", "yt_ratio", "user"])
                df["revenue"] = df["revenue"].apply(lambda revenue: round(revenue, 2))
                df["release_date"] = df["release_date"].apply(
                    lambda release_date: str(release_date).split(" ")[0]
                )
                headers = "<th>S No.</th><th>Title</th><th>Artist</th><th>Revenue</th><th>Genre</th><th>ISRC</th><th>Release Name</th><th>Publish Date</th>"
            elif section == "releases":
                fetch_query = f"""
                    SELECT 
                        ROW_NUMBER() OVER (ORDER BY ry.revenue DESC) as serial_number,
                        rr.title as release_title,
                        COALESCE(ra_art.name, 'N/A') AS artist, 
                        ry.revenue as revenue, 
                        rr.primary_genre as genre, 
                        rr.language as language,
                        rr.upc as upc, 
                        rr.original_release_date as release_date,
                        COALESCE(ur.stores, 0) as ratio,
                        COALESCE(ur.youtube, 0) as yt_ratio,
                        ul.email as `user`
                    FROM 
                        (SELECT 
                            rt.release_id,
                            round(SUM(ry.net_total_INR), 2) AS revenue
                        FROM
                            releases_royalties ry
                        JOIN 
                            releases_track rt on 
                                upper(ry.isrc) = upper(rt.isrc) 
                        JOIN releases_release rr2 ON rt.release_id = rr2.id
                        JOIN main_cduser ul2 ON rr2.created_by_id = ul2.id
                        WHERE ry.end_date > NOW()-interval 3 month {filter_.replace('ul.email', 'ul2.email') if filter_ else ''}
                        GROUP BY rt.release_id
                        ORDER BY revenue DESC
                        LIMIT 10
                        ) ry 
                    JOIN releases_release rr ON ry.release_id = rr.id 
                    JOIN main_cduser ul ON rr.created_by_id = ul.id
                    LEFT JOIN main_ratio ur ON ul.id = ur.user_id AND ur.status = 'active'
                    LEFT JOIN releases_relatedartists ra ON rr.id = ra.release_id AND ra.role = 'Primary Artist'
                    LEFT JOIN releases_artist ra_art ON ra.artist_id = ra_art.id
                    WHERE rr.published = true;
                """
                # Convert to Django database manager
                with connection.cursor() as cursor:
                    cursor.execute(fetch_query)
                    columns = [col[0] for col in cursor.description]
                    df = pd.DataFrame(cursor.fetchall(), columns=columns)
                df = transform_revenue(df, request.user, requesting_user_role, children)
                df = df.drop(columns=["ratio", "yt_ratio", "user"])
                df["revenue"] = df["revenue"].apply(lambda revenue: round(revenue, 2))
                df["release_date"] = df["release_date"].apply(
                    lambda release_date: str(release_date).split(" ")[0]
                )
                df["language"] = df["language"].apply(
                    lambda language: str(language).capitalize()
                )
                headers = "<th>S No.</th><th>Title</th><th>Artist</th><th>Revenue</th><th>Genre</th><th>Language</th><th>UPC</th><th>Publish Date</th>"
            elif section == "artists":
                fetch_query = f""" 
                    SELECT 
                        ROW_NUMBER() OVER (ORDER BY SUM(ry.net_total_INR) DESC) as serial_number,
                        COALESCE(ra_art.name, 'N/A') as artist, 
                        round(SUM(ry.net_total_INR), 2) AS revenue, 
                        GROUP_CONCAT(DISTINCT ry.channel SEPARATOR '|_|') AS channel,
                        ul.email as `user`,
                        COALESCE(ur.stores, 0) as ratio,
                        COALESCE(ur.youtube, 0) as yt_ratio
                    FROM
                        releases_royalties ry
                    JOIN 
                        releases_track rt on 
                            upper(ry.isrc) = upper(rt.isrc)
                    JOIN releases_release rr ON rt.release_id = rr.id
                    JOIN main_cduser ul ON rr.created_by_id = ul.id
                    LEFT JOIN main_ratio ur ON ul.id = ur.user_id AND ur.status = 'active'
                    JOIN releases_relatedartists ra ON rt.id = ra.track_id
                    LEFT JOIN releases_artist ra_art ON ra.artist_id = ra_art.id
                    WHERE ry.end_date > NOW()-interval 3 month 
                        AND rr.published = true 
                        AND ra_art.name IS NOT NULL
                        AND ra_art.name NOT LIKE '%_release_%'
                        {filter_ if filter_ else ''}
                    GROUP BY ra_art.id, ra_art.name, ul.email, ur.stores, ur.youtube
                    ORDER BY revenue DESC
                    LIMIT 10;
                    """
                # Convert to Django database manager
                with connection.cursor() as cursor:
                    cursor.execute(fetch_query)
                    columns = [col[0] for col in cursor.description]
                    df = pd.DataFrame(cursor.fetchall(), columns=columns)
                df = transform_revenue(df, request.user, requesting_user_role, children)
                df = df.drop(columns=["ratio", "yt_ratio", "user"])
                df = (
                    df.groupby(["serial_number", "artist", "channel"])
                    .agg({"revenue": "sum"})
                    .reset_index()
                    .sort_values(by="revenue", ascending=False)
                )
                df = df[["serial_number", "artist", "revenue", "channel"]]  # Reorder
                df["revenue"] = df["revenue"].apply(lambda revenue: round(revenue, 2))
                df["channel"] = df["channel"].apply(
                    lambda channel: "<br>".join(
                        [
                            ",".join(nest)
                            for nest in divide_channels(
                                channel.split("|_|")[0].split(","), 5
                            )
                        ]
                    )
                )
                headers = "<th>S No.</th><th>Artist</th><th>Generated Revenue</th><th>Platforms</th>"
            elif section == "labels":
                fetch_query = f"""
                        SELECT
                                ROW_NUMBER() OVER (ORDER BY SUM(ry.net_total_INR) DESC) as serial_number,
                                lb.label as label,
                                round(SUM(ry.net_total_INR), 2) as revenue,
                                ul.email as `user`,
                                COALESCE(ur.stores, 0) as ratio,
                                COALESCE(ur.youtube, 0) as yt_ratio
                                FROM 
                                releases_royalties ry
                                JOIN releases_track rt ON upper(ry.isrc) = upper(rt.isrc)
                                JOIN releases_release rr ON rt.release_id = rr.id
                                JOIN main_cduser ul ON rr.created_by_id = ul.id
                                LEFT JOIN main_ratio ur ON ul.id = ur.user_id AND ur.status = 'active'
                                LEFT JOIN releases_label lb ON rr.label_id = lb.id
                                WHERE ry.end_date > NOW()-interval 3 month 
                                    AND rr.published = true 
                                    AND lb.label IS NOT NULL
                                    {filter_ if filter_ else ''}
                                GROUP BY lb.label, ul.email, ur.stores, ur.youtube
                                ORDER BY revenue DESC
                                LIMIT 10;
                """
                with connection.cursor() as cursor:
                    cursor.execute(fetch_query)
                    columns = [col[0] for col in cursor.description]
                    df = pd.DataFrame(cursor.fetchall(), columns=columns)
                df = transform_revenue(df, request.user, requesting_user_role, children)
                df = df.drop(columns=["ratio", "yt_ratio", "user"])
                df = (
                    df.groupby(["serial_number", "label"])
                    .agg({"revenue": "sum"})
                    .reset_index()
                    .sort_values(by="revenue", ascending=False)
                )
                df = df[["serial_number", "label", "revenue"]]  # Reorder
                df["revenue"] = df["revenue"].apply(lambda revenue: round(revenue, 2))
                df = df.sort_values(by="revenue", ascending=False)

                headers = "<th>S No.</th><th>Label</th><th>Revenue</th>"
            elif section == "stores":
                fetch_query = f"""
                    SELECT 
                        ROW_NUMBER() OVER (ORDER BY SUM(ry.net_total_INR) DESC) as serial_number,
                        ry.channel, 
                        round(SUM(ry.net_total_INR), 2) AS revenue, 
                        ul.email as `user`,
                        COALESCE(ur.stores, 0) as ratio,
                        COALESCE(ur.youtube, 0) as yt_ratio
                    FROM
                        releases_royalties ry
                    JOIN 
                        releases_track rt ON upper(ry.isrc) = upper(rt.isrc)
                    JOIN releases_release rr ON rt.release_id = rr.id 
                    JOIN main_cduser ul ON rr.created_by_id = ul.id
                    LEFT JOIN main_ratio ur ON ul.id = ur.user_id AND ur.status = 'active'
                    WHERE ry.channel IS NOT NULL 
                        AND ry.end_date > NOW()-interval 3 month 
                        AND rr.published = true
                        {filter_ if filter_ else ''}
                    GROUP BY ry.channel, ul.email, ur.stores, ur.youtube
                    ORDER BY revenue DESC;
                """
                # Convert to Django database manager
                with connection.cursor() as cursor:
                    cursor.execute(fetch_query)
                    columns = [col[0] for col in cursor.description]
                    df = pd.DataFrame(cursor.fetchall(), columns=columns)
                df = transform_revenue(df, request.user, requesting_user_role, children)
                df = df.drop(columns=["ratio", "yt_ratio", "user"])
                df = (
                    df.groupby(["serial_number", "channel"])
                    .agg({"revenue": "sum"})
                    .reset_index()
                    .sort_values(by="revenue", ascending=False)
                )
                df = df[["serial_number", "channel", "revenue"]]  # Reorder
                df["revenue"] = df["revenue"].apply(lambda revenue: round(revenue, 2))

                headers = "<th>S No.</th><th>Store</th><th>Revenue</th>"
            elif section == "languages":
                fetch_query = f""" 
                    SELECT 
                        ROW_NUMBER() OVER (ORDER BY SUM(ry.net_total_INR) DESC) as serial_number,
                        rt.language as `language`,
                        round(SUM(ry.net_total_INR), 2) AS revenue,
                        COALESCE(ur.stores, 0) as ratio,
                        COALESCE(ur.youtube, 0) as yt_ratio,
                        ul.email as `user`
                    FROM
                        releases_royalties ry
                    JOIN 
                        releases_track rt ON upper(ry.isrc) = upper(rt.isrc)
                    JOIN releases_release rr ON rt.release_id = rr.id 
                    JOIN main_cduser ul ON rr.created_by_id = ul.id
                    LEFT JOIN main_ratio ur ON ul.id = ur.user_id AND ur.status = 'active'
                    WHERE ry.end_date > NOW()-interval 3 month 
                        AND rr.published = true
                        AND rt.language IS NOT NULL
                        {filter_ if filter_ else ''}
                    GROUP BY rt.language, ul.email, ur.stores, ur.youtube
                    ORDER BY revenue DESC;

                """
                # Convert to Django database manager
                with connection.cursor() as cursor:
                    cursor.execute(fetch_query)
                    columns = [col[0] for col in cursor.description]
                    df = pd.DataFrame(cursor.fetchall(), columns=columns)
                df = transform_revenue(df, request.user, requesting_user_role, children)
                df = df.drop(columns=["ratio", "yt_ratio", "user"])
                df["language"] = df["language"].apply(
                    lambda language: str(language).capitalize()
                )  # Because there is inconsistent language values
                df = (
                    df.groupby(["serial_number", "language"])
                    .agg({"revenue": "sum"})
                    .reset_index()
                    .sort_values(by="revenue", ascending=False)
                )
                df = df[["serial_number", "language", "revenue"]]  # Reorder
                df["revenue"] = df["revenue"].apply(lambda revenue: round(revenue, 2))

                headers = "<th>S No.</th><th>Language</th><th>Revenue</th>"
            else:
                return JsonResponse({"message": "Invalid section!"})

            body = ""
            for index, row in df.iterrows():
                body += f"<tr>"
                for column in df.columns:
                    body += f"<td>{row[column]}</td>"
                body += "</tr>"
            table = f"""<table class="table table-hover" id="data_table">
                <thead>
                    {headers}
                </thead>
                <tbody>
                    {body}
                </tbody>
                </table>
            """
            return JsonResponse(
                {"table": table, "requesting_user_role": requesting_user_role}
            )

        else:
            return JsonResponse({"message": "Invalid request!"})
    else:
        return JsonResponse({"message": "Authentication Failed!"})


def analytics(request):
    if request.user.is_authenticated and is_active(request.user):
        requesting_user_role = processor.get_user_role(request.user)
        if request.method == "GET":
            return render(
                request,
                "volt_analytics.html",
                context={"requesting_user_role": requesting_user_role},
            )
        else:
            return HttpResponseNotFound("<h1>Invalid Request!</h1>")
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def add_announcement(request):
    if request.user.is_authenticated and is_active(request.user):
        if request.method == "POST":
            requesting_user_role = request.user.role
            if requesting_user_role == "admin":
                try:
                    new_announcement = request.POST.get("new_announcement").replace(
                        "\n", "|_|"
                    )
                    Announcement.objects.create(announcement=new_announcement)
                    return JsonResponse(
                        {"announcement_success_message": "announcement_success_message"}
                    )
                except Exception as e:
                    return JsonResponse(
                        {
                            "announcement_error_message": "You are not authorized to perform this action!"
                        }
                    )
            else:
                return JsonResponse(
                    {
                        "announcement_error_message": "You are not authorized to perform this action!"
                    }
                )
        else:
            return JsonResponse({"announcement_error_message": "Invalid Request!"})
    else:
        return JsonResponse({"announcement_error_message": "Authentication failed!"})

# ================= ORIGINAL FUNCTION (FOR REFERENCE) ===================
# def get_dashboard_data(request, section):
#     if request.user.is_authenticated and is_active(request.user):
#         requesting_user_role = processor.get_user_role(request.user)
#         if request.method == "GET":
#             filter_ = ""
#             if requesting_user_role == "normal":
#                 filter_ = f" AND created_by = '{request.user.get_username()}' "
#             elif requesting_user_role == "intermediate":
#                 children = processor.get_users_belongs_to(request.user)
#                 children.append(request.user)
#                 children = [f"'{child}'" for child in children]
#                 children = ",".join(children)
#                 filter_ = f" AND created_by in ({children}) "
#             elif requesting_user_role == "member":
#                 leader = get_leader(request.user)
#                 filter_ = f" AND created_by = '{leader}' "
#             else:
#                 pass
# =========================================================================

# New Django ORM-based implementation
def get_dashboard_data(request, section):
    if request.user.is_authenticated and is_active(request.user):
        requesting_user_role = processor.get_user_role(request.user)
        if request.method == "GET":
            # Build user filter based on role using Django ORM
            user_filter = []
            is_split_recipient = (requesting_user_role == "split_recipient")
            if requesting_user_role == "normal":
                user_filter = [request.user.get_username()]
            elif requesting_user_role == "intermediate":
                children = processor.get_users_belongs_to(request.user)
                children.append(request.user)
                user_filter = children
            elif requesting_user_role == "member":
                leader = get_leader(request.user)
                user_filter = [leader]
            elif is_split_recipient:
                # For split recipients, we'll filter by tracks where they are recipients
                user_filter = None  # Will be handled differently
            else:
                user_filter = None

            three_months_ago = datetime.now() - timedelta(days=90)

            if section == 2:
                announcements = Announcement.objects.all().order_by('-created_at')

                headers = "<th>Announcement</th><th>Time</th>"
                body = ""
                for announcement in announcements:
                    formatted_announcement = announcement.announcement.replace("|_|", "<br>")
                    body += f"<tr>"
                    body += f"<td>{formatted_announcement}</td>"
                    body += f"<td>{announcement.created_at}</td>"
                    body += "</tr>"
                    
                table = f"""<table class="table table-hover" id="data_table">
                    <thead>
                        {headers}
                    </thead>
                    <tbody>
                        {body}
                    </tbody>
                    </table>
                """
                return JsonResponse(
                    {"table": table, "requesting_user_role": requesting_user_role}
                )
            elif section == 3:
                # Build base queryset
                queryset = Royalties.objects.filter(
                    channel__isnull=False,
                    end_date__gt=three_months_ago
                )
                
                # Apply user filter if needed
                if is_split_recipient:
                    # For split recipients, get ISRCs from tracks where they are recipients
                    from releases.models import SplitReleaseRoyalty
                    split_isrcs = SplitReleaseRoyalty.objects.filter(
                        recipient_email=request.user.email
                    ).values_list('track_id__isrc', flat=True).distinct()
                    queryset = queryset.filter(isrc__in=split_isrcs)
                elif user_filter:
                    queryset = queryset.filter(
                        isrc__in=Metadata.objects.filter(user__in=user_filter).values_list('isrc', flat=True)
                    )
                
                # Group by channel and sum revenue
                channel_revenue = queryset.values('channel').annotate(
                    revenue=Sum('net_total_INR')
                ).order_by('-revenue')[:5]
                
                # Convert to lists for chart data
                channels = [item['channel'] for item in channel_revenue]
                revenues = [round(item['revenue'], 2) for item in channel_revenue]
                
                data = {
                    "labels": channels,
                    "datasets": [
                        {
                            "label": "Top Stores",
                            "data": revenues,
                            "backgroundColor": [
                                "#EEB15D",
                                "#A1A955",
                                "#5D9764",
                                "#297F71",
                                "#171D27",
                            ],
                            "hoverOffset": 4,
                        }
                    ],
                }
                return JsonResponse({"chart_data": data})
            elif section == 4:
                # Split recipients don't see releases
                if is_split_recipient:
                    return JsonResponse({"latest_releases": ""})
                
                # Build base queryset for published releases
                queryset = Release.objects.filter(published=True)
                
                # Apply user filter if needed
                if user_filter:
                    queryset = queryset.filter(created_by__email__in=user_filter)
                
                # Get latest 5 releases ordered by published date
                releases = queryset.annotate(
                    cover_art_display=Case(
                        When(cover_art_url__isnull=True, then=Value(f"/static/img/{settings.LOGO['light']}")),
                        When(cover_art_url__exact='', then=Value(f"/static/img/{settings.LOGO['light']}")),
                        default='cover_art_url'
                    )
                ).order_by('-published_at')[:5]

                response_html = ""
                for release in releases:
                    response_html += f"""
                        <div class="col-lg-3 col-md-6 col-sm-12 col-xs-12 mb-4">
                            <div class="card" style="width: 18rem;">
                                <img src="{release.cover_art_display}" class="card-img-top">
                                <div class="card-body">
                                    <h5 class="card-title">{release.title}</h5>
                                    <a href="/releases/release_info/{release.id}" class="btn btn-primary">View Release</a>
                                </div>
                            </div>
                        </div>
                    """
                return JsonResponse({"latest_releases": response_html})
            elif section == 5:
                # Build user filter condition for raw SQL
                filter_condition = ""
                if is_split_recipient:
                    # For split recipients, get ISRCs from tracks where they are recipients
                    from releases.models import SplitReleaseRoyalty
                    split_isrcs = SplitReleaseRoyalty.objects.filter(
                        recipient_email=request.user.email
                    ).values_list('track_id__isrc', flat=True).distinct()
                    isrc_list = [isrc.upper().strip() for isrc in split_isrcs if isrc]
                    if isrc_list:
                        filter_condition = f" AND t.isrc IN {tuple(isrc_list)}"
                    else:
                        filter_condition = " AND 1=0"  # No data
                elif user_filter:
                    isrc_list = Metadata.objects.filter(user__in=user_filter).values_list('isrc', flat=True)
                    isrc_list = [isrc.upper().strip() for isrc in isrc_list]
                    filter_condition = f" AND t.isrc IN {tuple(isrc_list)}"
                
                # Optimized raw SQL query using existing indexes and proper joins
                query = f"""
                    SELECT 
                        t.language,
                        ROUND(SUM(r.net_total_INR), 2) AS revenue
                    FROM releases_royalties r
                    INNER JOIN releases_track t ON UPPER(TRIM(r.isrc)) = UPPER(TRIM(t.isrc))
                    WHERE r.end_date > DATE_SUB(NOW(), INTERVAL 3 MONTH)
                    AND t.language IS NOT NULL 
                    AND t.language != ''
                    AND TRIM(t.language) != '' {filter_condition}
                    GROUP BY t.language
                    ORDER BY revenue DESC
                    LIMIT 5;
                """
                
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    results = cursor.fetchall()
                
                languages = [result[0].capitalize() for result in results]
                revenues = [result[1] for result in results]
                
                data = {
                    "labels": languages,
                    "datasets": [
                        {
                            "label": "Top Languages",
                            "data": revenues,
                            "backgroundColor": [
                                "#EEB15D",
                                "#A1A955",
                                "#5D9764",
                                "#297F71",
                                "#171D27",
                            ],
                            "hoverOffset": 4,
                        }
                    ],
                }
                return JsonResponse({"chart_data": data})
            elif section == 6:
                current_year = datetime.now().year
                
                # Get streams data for current year
                queryset = Royalties.objects.filter(
                    end_date__year=current_year,
                    type='streams'
                )
                
                # Apply user filter if needed
                if is_split_recipient:
                    # For split recipients, get ISRCs from tracks where they are recipients
                    from releases.models import SplitReleaseRoyalty
                    split_isrcs = SplitReleaseRoyalty.objects.filter(
                        recipient_email=request.user.email
                    ).values_list('track_id__isrc', flat=True).distinct()
                    queryset = queryset.filter(isrc__in=split_isrcs)
                elif user_filter:
                    queryset = queryset.filter(
                        isrc__in=Metadata.objects.filter(user__in=user_filter).values_list('isrc', flat=True)
                    )
                
                # Group by month and sum units
                monthly_streams = queryset.annotate(
                    month=TruncMonth('end_date')
                ).values('month').annotate(
                    total_units=Sum('units')
                ).order_by('month')
                
                # Convert to lists for chart data
                labels = []
                units = []
                
                for item in monthly_streams:
                    # Format the month as YYYY-MM-01 for consistency
                    month_date = item['month']
                    labels.append(month_date.strftime('%Y-%m-%d'))
                    units.append(item['total_units'])
                
                data = {
                    "labels": labels,
                    "datasets": [
                        {
                            "label": "Audio Streams",
                            "data": units,
                            "backgroundColor": "rgba(17,25,39,0.4)",
                            "fill": True,
                            "borderWidth": 4,
                            "borderColor": "#111927",
                            "hoverOffset": 4,
                        }
                    ],
                }
                return JsonResponse({"chart_data": data})
            else:
                return JsonResponse({"message": "Invalid request!"})
        else:
            return JsonResponse({"message": "Invalid request!"})
    else:
        return JsonResponse({"message": "Authentication Failed!"})


def get_dashboard(request):
    if request.user.is_authenticated and is_active(request.user):
        requesting_user_role = processor.get_user_role(request.user)
        if request.method == "GET":
            
            # Build the query based on user role
            if requesting_user_role == "normal":
                releases = Release.objects.filter(created_by=request.user)
            elif requesting_user_role == "intermediate":
                children = processor.get_users_belongs_to(request.user)
                children.append(request.user)
                releases = Release.objects.filter(created_by__email__in=children)
            elif requesting_user_role == "member":
                leader = get_leader(request.user)
                releases = Release.objects.filter(created_by__email=leader)
            elif requesting_user_role == "split_recipient":
                # Split recipients see only tracks where they are recipients
                from releases.models import SplitReleaseRoyalty
                # Count unique tracks where user is a recipient
                tracks_with_splits = SplitReleaseRoyalty.objects.filter(
                    recipient_email=request.user.email
                ).values('track_id').distinct().count()
                
                return render(
                    request,
                    "volt_dashboard.html",
                    context={
                        "requesting_user_role": requesting_user_role,
                        "logged_user_name": str(request.user).split("@")[0],
                        "username": request.user,
                        "total_releases_count": 0,  # Not shown for split recipients
                        "published_releases_count": tracks_with_splits,  # Show tracks with splits
                        "draft_releases_count": 0,  # Not shown for split recipients
                        "pending_approval_count": 0,
                    },
                )
            else:
                releases = Release.objects.all()
            
            # Calculate counts using ORM
            total_releases = releases.count()
            published = releases.filter(published=True).count()
            draft = releases.filter(published=False).count()
            pending_approval = releases.filter(
                published=False,
                approval_status__iexact="pending_approval",
            ).count()
            return render(
                request,
                "volt_dashboard.html",
                context={
                    "requesting_user_role": requesting_user_role,
                    "logged_user_name": str(request.user).split("@")[0],
                    "username": request.user,
                    "total_releases_count": total_releases,
                    "published_releases_count": published,
                    "draft_releases_count": draft,
                    "pending_approval_count": pending_approval,
                },
            )
        else:
            return HttpResponseNotFound("<h1>Invalid Request</h1>")
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def file_uploaders_info(request, type):
    if request.user.is_authenticated:
        validation_mapping = {
            "codes": codes_validations,
            "releases": release_validations,
            "royalties": royalties_validations,
            "payments": payments_validations,
        }
        return JsonResponse(
            {"message": "".join(validation_mapping[type]["validation_text"])}
        )
    else:
        return JsonResponse({"message": "Authentication failed!"})


@csrf_exempt
def request_feedback(request):
    if request.user.is_authenticated and is_active(request.user):
        if request.method == "POST":
            try:
                request_object = Request.objects.get(pk=int(request.POST.get("request_id")))
                request_object.status = request.POST.get("status")
                request_object.feedback = request.POST.get("feedback")
                request_object.save()
                return JsonResponse({"requests_success_message": "success"})
            except:
                return JsonResponse({"requests_error_message": "error"})
        else:
            return HttpResponseNotFound("<h1>Invalid Request</h1>")
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def delete_my_request(request, request_id):
    if request.user.is_authenticated and is_active(request.user):
        if request.method == "GET":
            try:
                request_object = Request.objects.get(pk=request_id)
                request_object.delete()
                return JsonResponse({"requests_success_message": "success"})
            except:
                return JsonResponse({"requests_error_message": "error"})
        else:
            return HttpResponseNotFound("<h1>Invalid Request</h1>")
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def my_requests(request):
    if request.user.is_authenticated and is_active(request.user):
        if request.method == "GET":
            if request.user.role == CDUser.ROLES.ADMIN:
                request_objects = Request.objects.exclude(status=Request.STATUS.CLOSED)
            else:
                request_objects = Request.objects.filter(user=request.user)
            df = pd.DataFrame(list(request_objects.values("id", "user", "title", "description", "created_at", "status", "feedback")))
            df.rename(columns={
                'id': 'request_id',
                'user': 'requester_user',
                'title': 'ticket_name',
                'feedback': 'admin_comments'
            }, inplace=True)
            headers = ""
            if request.user.role == CDUser.ROLES.ADMIN:
                headers += "<th>User</th>"
            headers += "<th>Title</th><th>Description</th><th>Opened At</th><th>Status</th><th>Feedback</th><th>Close</th>"
            if request.user.role == CDUser.ROLES.ADMIN:
                headers += "<th>Review</th>"
            body = ""
            for index, row in df.iterrows():
                body += f'<tr id="row_{row["request_id"]}" style="cursor:pointer">'
                if request.user.role == CDUser.ROLES.ADMIN:
                    body += f"""<td>{row['requester_user']}</td>"""
                for column in df.columns:
                    if column not in ("request_id", "requester_user"):
                        body += f"<td>{row[column]}</td>"
                body += f'<td onclick="delete_request({row["request_id"]})"><span class="material-symbols-outlined">delete</span></td>'
                if request.user.role == CDUser.ROLES.ADMIN:
                    body += f"""<td onclick="edit_request({row['request_id']})"><span class="material-symbols-outlined">edit</span></td>"""
                body += "</tr>"
            table = f"""<table class="table table-hover" id="data_table">
                <thead>
                    {headers}
                </thead>
                <tbody>
                    {body}
                </tbody>
                </table>
            """
            return JsonResponse(
                {"table": table, "requesting_user_role": request.user.role}
            )
        else:
            return HttpResponseNotFound("<h1>Invalid Request</h1>")
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def requests(request):
    if request.user.is_authenticated and is_active(request.user):
        if request.method == "GET":
            return render(
                request,
                "volt_requests.html",
                context={"requesting_user_role": request.user.role},
            )
        else:
            try:
                title = request.POST.get("title")
                description = request.POST.get("description")
                user_request = Request.objects.create(
                    user=request.user,
                    title=title,
                    description=description,
                )
                user_request.save()
                return JsonResponse({"requests_success_message": "success"})
            except:
                return JsonResponse({"requests_error_message": "error"})

    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def main_page(request):
    if (
        request.user.is_authenticated
        and is_active(request.user)
    ):
        requesting_user_role = processor.get_user_role(request.user)

        # Distinct confirmed dates values after April 2025
        confirmed_dates = Royalties.objects.filter(confirmed_date__gte=datetime(2025, 4, 1)).values_list('confirmed_date', flat=True).distinct()
        confirmed_dates_list = list(confirmed_dates)
        confirmed_dates_list.sort(reverse=True)
        confirmed_dates_display = {
            date.strftime('%B, %Y'): date.strftime("%Y-%m-%d") for date in confirmed_dates_list
            }
        
        if requesting_user_role == "admin":
            navigation = admin.navigation
        elif requesting_user_role == "intermediate":
            navigation = intermediate.navigation
        elif requesting_user_role == "split_recipient":
            navigation = _navigation['split_recipient']  # Use split_recipient navigation
        else:
            navigation = intermediate.navigation
            
        return render(
            request,
            "volt_admin.html",
            context={
                "confirmed_dates_list": confirmed_dates_display,
                "navigation": get_navigation("home", navigation),
                "requesting_user_role": requesting_user_role,
                "username": request.user,
                "is_show_due_balance": True,
            },
        )
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def manage_users(request):
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.user.role in [CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE]
    ):
        role = request.user.role
        navigation = (
            admin.navigation
            if role == "admin"
            else intermediate.navigation
        )
        return render(
            request,
            "volt_admin_manage_users.html",
            context={
                "navigation": get_navigation("manage_users", navigation),
                "requesting_user_role": role,
                "username": request.user,
            },
        )
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def get_royalties_data(request, field_category, field, start_date, end_date):
    if request.user.is_authenticated and is_active(request.user):
        processor.send_royalties_data(
            request.user, field_category, field, start_date, end_date
        )
        return JsonResponse(
            {
                "message": "Your data is being prepared. It will be emailed to you as soon as it is ready!"
            }
        )
    else:
        return JsonResponse({"message": "Authentication Error!"})


def download_royalties(request):
    requesting_user_role = processor.get_user_role(request.user)
    if request.user.is_authenticated and is_active(request.user):
        return render(
            request,
            "volt_normal_download_royalties.html",
            context={
                "username": request.user,
                "navigation": get_navigation("download_royalties", normal.navigation),
                "requesting_user_role": requesting_user_role,
            },
        )
    else:
        return HttpResponseNotFound("<h2>Authentication Failed!</h2>")


# New ORM-based implementation
def get_payments(request, username):
    """
    Get payment data aggregated by month using Django ORM
    """
    
    requesting_user_role = processor.get_user_role(request.user)
    
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.method == "GET"
    ):
        # Get payments based on user role
        if requesting_user_role == "admin":
            payments = Payment.objects.all()
        else:
            payments = Payment.objects.filter(username=username)
        
        # Select only needed fields and get the data
        payment_data = payments.values('date_of_payment', 'amount_paid', 'tds')
        
        # Group by month and aggregate
        month_data = defaultdict(lambda: {'amount_paid': 0, 'tds': 0})
        
        for payment in payment_data:
            month_key = payment['date_of_payment'].strftime("%Y-%m")
            month_data[month_key]['amount_paid'] += payment['amount_paid']
            month_data[month_key]['tds'] += payment['tds']
        
        # Build the HTML table
        total_amount = 0
        total_tds = 0
        headers = "<th>Month of Payment</th><th>Total Amount</th><th>Total TDS</th>"
        body = ""
        
        for month, data in sorted(month_data.items()):
            total_amount += data['amount_paid']
            total_tds += data['tds']
            body += f'<tr onclick=get_monthly_payments("{month}") style="cursor:pointer">'
            body += f"<td>{month}</td>"
            body += f"<td>{data['amount_paid']}</td>"
            body += f"<td>{data['tds']}</td>"
            body += "</tr>"
            
        footer = f"<tr><td><b>Total<b></td><td><b>{round(total_amount,2)}</b></td><td><b>{round(total_tds,2)}</b></td></tr>"
        table = f"""<table class="table table-hover" id="data_table">
            <thead>
            {headers}
            </thead>
            <tbody>
                {body}
            </tbody>
            <tfoot>
            {footer}
            </tfoot>
            </table>
        """

        return JsonResponse(
            {"table": table, "requesting_user_role": requesting_user_role}
        )
    else:
        response = HttpResponse()
        response.status_code = 403
        return response


def get_month_payments(request, month):
    """
    Get detailed payment data for a specific month using Django ORM
    """

    
    if request.user.is_authenticated and is_active(request.user):
        requesting_user_role = processor.get_user_role(request.user)
        
        # Parse month string (format: YYYY-MM)
        year, month_num = month.split('-')
        year = int(year)
        month_num = int(month_num)
        
        # Get first and last day of the month
        first_day = datetime(year, month_num, 1).date()
        last_day = datetime(year, month_num, calendar.monthrange(year, month_num)[1]).date()
        
        # Filter payments based on user role and date range
        if requesting_user_role == "admin":
            payments = Payment.objects.filter(
                date_of_payment__gte=first_day,
                date_of_payment__lte=last_day
            )
        else:
            payments = Payment.objects.filter(
                username=str(request.user),
                date_of_payment__gte=first_day,
                date_of_payment__lte=last_day
            )
        
        # Get payment data with all required fields
        payment_data = payments.values(
            'username', 'date_of_payment', 'amount_paid', 'tds',
            'tds_percentage', 'source_account', 'sent_to_name', 
            'sent_to_account_number', 'sent_to_ifsc_code', 'transfer_id'
        )
        
        headers = "<th>Payee</th><th>Date of Payment</th><th>Total Amount</th><th>Total TDS</th> <th>Percentage TDS</th> <th>Payer Account No.</th> <th>Payee Name</th> <th>Payee Account No.</th> <th>Payee IFSC Code</th> <th>Transfer ID</th> "
        
        total_amount = 0
        total_tds = 0
        body = ""
        
        for payment in payment_data:
            total_amount += payment['amount_paid']
            total_tds += payment['tds']
            body += "<tr>"
            body += f"<td>{payment['username']}</td>"
            body += f"<td>{payment['date_of_payment']}</td>"
            body += f"<td>{payment['amount_paid']}</td>"
            body += f"<td>{payment['tds']}</td>"
            body += f"<td>{payment['tds_percentage']}</td>"
            body += f"<td>{payment['source_account']}</td>"
            body += f"<td>{payment['sent_to_name']}</td>"
            body += f"<td>{payment['sent_to_account_number']}</td>"
            body += f"<td>{payment['sent_to_ifsc_code']}</td>"
            body += f"<td>{payment['transfer_id']}</td>"
            body += "</tr>"

        footer = f"<tr><td><b>Total<b></td><td>-</td><td><b>{round(total_amount,2)}</b></td><td><b>{round(total_tds,2)}</b></td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>"
        table = f"""<table class="table table-hover" id="month_data_table">
            <thead>
                {headers}
            </thead>
            <tbody>
                {body}
            </tbody>
            <tfoot>
                {footer}
            </tfoot>
            </table>
        """
        return JsonResponse({"table": table})
    else:
        response = HttpResponse()
        response.status_code = 403
        return response


def payments(request):
    requesting_user_role = processor.get_user_role(request.user)
    if request.user.is_authenticated and is_active(request.user):
        if request.method == "GET":
            if requesting_user_role == "admin":
                return render(
                    request,
                    "volt_admin_payments.html",
                    context={
                        "requesting_user_role": requesting_user_role,
                        "navigation": get_navigation("payments", admin.navigation),
                        "username": request.user,
                    },
                )
            else:
                navigation = (
                    get_navigation("payments", intermediate.navigation)
                    if requesting_user_role == "intermediate"
                    else get_navigation("payments", normal.navigation)
                )
                return render(
                    request,
                    "volt_admin_payments.html",
                    context={
                        "requesting_user_role": requesting_user_role,
                        "navigation": navigation,
                        "username": request.user,
                    },
                )
        if (
            request.method == "POST"
            and request.FILES["payments_file"]
            and requesting_user_role == "admin"
        ):
            try:
                payments_file = request.FILES["payments_file"].file

                file_handler = FileHandler(payments_file, "payments", "excel")
                # File validation validation
                validator = DataValidator(
                    file_handler.data,
                    [
                        payments_validations,
                    ],
                    file_handler.file_type,
                )
                status, response = validator.validate()
                if status:

                    
                    # Payments processing
                    payments_df = validator.process(file_type="payments")
                    
                    # Bulk create payment records using Django ORM
                    payment_objects = []
                    for _, row in payments_df.iterrows():
                        payment_obj = payment_obj = Payment(
                            username=safe_get(row, 'username', ''),
                            date_of_payment=pd.to_datetime(row['date_of_payment']).date() if pd.notna(row.get('date_of_payment')) else None,
                            amount_paid=safe_get(row, 'amount_paid', 0.0, float),
                            tds=safe_get(row, 'tds', 0.0, float),
                            tds_percentage=safe_get(row, 'tds_percentage', 0.0, float),
                            source_account=safe_get(row, 'source_account', ''),
                            sent_to_name=safe_get(row, 'sent_to_name', ''),
                            sent_to_account_number=safe_get(row, 'sent_to_account_number', ''),
                            sent_to_ifsc_code=safe_get(row, 'sent_to_ifsc_code', ''),
                            transfer_id=safe_get(row, 'transfer_id', '')
                        )
                        payment_objects.append(payment_obj)
                    
                    # Use transaction for bulk insert
                    with transaction.atomic():
                        Payment.objects.bulk_create(payment_objects, batch_size=1000)
                    
                    return JsonResponse(
                        {
                            "payments_success_message": f"Success! {int(payments_df.shape[0])} new rows added to payments db.",
                            "status_code": 200,
                        }
                    )
                else:
                    return JsonResponse(
                        {
                            "payments_error_message": f"{response}",
                            "status_code": 500,
                        }
                    )
            except:
                print(traceback.format_exc())
                response = {
                    "payments_error_message": "Error! Internal Server error occured while uploading data, contact admin",
                    "status_code": 500,
                }
            return JsonResponse(response)
    else:
        response = HttpResponse()
        response.status_code = 403
        return response


@csrf_exempt
def change_ownership(request, id):
    response = HttpResponse()
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.user.role == CDUser.ROLES.ADMIN
    ):
        user = CDUser.objects.get(pk=id)
        new_owner = str(request.POST["new_owner"]).split(" ")[0]
        owner = CDUser.objects.get(email=new_owner)
        user.parent = owner
        user.save()
        # process = Popen(["python", "populate_due_amounts.py"])
        # TODO: Will do once all models are created
        response.status_code = 200
        return response
    else:
        response.status_code = 400
        return response


def remove_ownership(request, id):
    response = HttpResponse()
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.user.role == CDUser.ROLES.ADMIN
    ):
        user = CDUser.objects.get(pk=id)
        user.parent = request.user
        user.save()
        # process = Popen(["python", "populate_due_amounts.py"])
        # TODO: Will do once all models are created
        response.status_code = 200
        return response
    else:
        response.status_code = 400
        return response


def update_lower_dependencies(username, selected_role):
    """
    Update user hierarchies when role changes using Django ORM
    """
    try:
        user = CDUser.objects.get(email=username)
        current_role = user.role
        
        # When downgrading to normal role, remove children from this user
        if (current_role == CDUser.ROLES.INTERMEDIATE and selected_role == CDUser.ROLES.NORMAL) or (
            current_role == CDUser.ROLES.ADMIN and selected_role == CDUser.ROLES.NORMAL
    ):
            CDUser.objects.filter(parent=user).update(parent=None)

        # When upgrading to admin, remove parent relationship for this user
        elif (current_role == CDUser.ROLES.INTERMEDIATE and selected_role == CDUser.ROLES.ADMIN) or (
            current_role == CDUser.ROLES.NORMAL and selected_role == CDUser.ROLES.ADMIN
        ):
            user.parent = None
            user.save()

        # When upgrading from normal to intermediate, check parent constraints
        elif current_role == CDUser.ROLES.NORMAL and selected_role == CDUser.ROLES.INTERMEDIATE:
            if user.parent and user.parent.role == CDUser.ROLES.INTERMEDIATE:
                # If parent is intermediate, remove parent relationship
                user.parent = None
                user.save()
                
    except CDUser.DoesNotExist:
        pass  # User not found, nothing to update


def update_user_status(request):
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.method == "POST"
    ):
        try:
            user_id = request.POST.get("user")
            user = CDUser.objects.get(pk=user_id)
            status = int(request.POST.get("status"))
            user.is_active = True if status == 1 else False
            user.save()
            return JsonResponse({"message": f"Status updated for {user.email}!"})
        except:
            return JsonResponse(
                {
                    "message": "There was en error while setting status for this user. Please try again!"
                }
            )
    else:
        return JsonResponse({"message": "Authentication Failed!"})
@csrf_exempt
def edit_splitroyalities_enabled(request):
    # Only admins can enable/disable split royalties
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({"success": False, "message": "Authentication required."}, status=401)
    
    if request.user.role != CDUser.ROLES.ADMIN:
        return JsonResponse({"success": False, "message": "Only admins can enable/disable split royalties."}, status=403)
    
    if request.method == "POST":
        user_id = request.POST.get("user")
        enabled = request.POST.get("splitroyalities") == "1"
        try:
            user = CDUser.objects.get(pk=user_id)
            
            # Split royalties can only be enabled for normal users
            if enabled and user.role != CDUser.ROLES.NORMAL:
                return JsonResponse({"success": False, "message": "Split royalties can only be enabled for normal users."}, status=400)
            
            user.split_royalties_enabled = enabled
            user.save()
            if enabled:
                tracks = Track.objects.filter(created_by=user)
               
               
                created_count = 0
                for track in tracks:
                    existing_splits = SplitReleaseRoyalty.objects.filter(
                        user_id=user,
                        release_id=track.release,
                        track_id=track,
                        recipient_email=user.email
                    ).exists()
                    print("existing_splits", existing_splits)
                    print("track", track)
                    print("track_real", track.release.id)
                    if not existing_splits:
                        SplitReleaseRoyalty.objects.create(
                            user_id=user,
                            release_id=track.release,
                            track_id=track,
                            recipient_name=f"{user.first_name} {user.last_name}".strip() or user.email,
                            recipient_email=user.email,
                            recipient_role="Primary Artist",
                            recipient_percentage=100.0
                        )
                        created_count += 1
                return JsonResponse({"success": True, "message": f"Split royalties enabled. {created_count} splits created."})
            else:
                return JsonResponse({"success": True, "message": "Split royalties disabled."})
        except CDUser.DoesNotExist:
            return JsonResponse({"success": False, "message": "User not found."}, status=404)
    return JsonResponse({"success": False, "message": "POST required."}, status=405)

def edit_user(request, id):
    
    selected_user = CDUser.objects.get(pk=id)
    print("selected_user", selected_user.split_royalties_enabled)

    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.user.role == CDUser.ROLES.ADMIN
    ):
        if request.method == "POST":
            user = CDUser.objects.get(pk=id)
            if request.POST["password"]:
                user.set_password(request.POST["password"])
            if request.POST["role"] != user.role:
                user.role = request.POST["role"]
                # update_lower_dependencies(username, request.POST["role"])
                # process = Popen(["python", "populate_due_amounts.py"])
                # TODO: Will do once all models are created
            
            # Set remaining fields
            user.first_name = request.POST["name"]
            user.last_name = request.POST["surname"]
            user.country = request.POST["country"]
            user.language = request.POST["language"]
            user.city = request.POST["city"]
            user.street = request.POST["street"]
            user.postal_code = request.POST["postal_code"]
            user.contact_phone = request.POST["contact_phone"]
            user.company = request.POST["company"]
            user.company_name = request.POST["company_name"]
            user.fiskal_id_number = request.POST["fiskal_id_number"]
            user.country_phone = request.POST["country_phone"]
            user.company_contact_phone = request.POST["company_contact_phone"]
            user.pan = request.POST["pan_number"]
            user.gst_number = request.POST["gst_number"]
            user.account_name = request.POST["account_name"]
            user.account_number = request.POST["account_number"]
            user.ifsc = request.POST["ifsc_code"]
            user.sort_code = request.POST["sort_code"]
            user.swift_code = request.POST["swift_code"]
            user.iban = request.POST["iban_number"]
            user.bank_country = request.POST["country_of_bank"]
            user.bank_name = request.POST["bank_name"]
            user.save()

            # Check Ratios
            ratios = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
            if (
                request.POST["ratio"] != ratios.stores
                or request.POST["yt_ratio"] != ratios.youtube
                or request.POST["sales_payout"] != ratios.sales_payout
                or request.POST["sales_payout_threshold"] != ratios.sales_payout_threshold
            ):
                ratios.status = Ratio.STATUS.IN_ACTIVE
                ratios.save()
                new_ratios = Ratio.objects.create(
                    user=user,
                    stores=request.POST["ratio"],
                    youtube=request.POST["yt_ratio"],
                    sales_payout=request.POST["sales_payout"],
                    sales_payout_threshold=request.POST["sales_payout_threshold"],
                    status=Ratio.STATUS.ACTIVE
                )
                new_ratios.save()
                
                # Clear the cache for this user so updated ratios are reflected
                from cache import cache
                cache.clean(user.email)
            return render(
                request,
                "volt_admin_manage_users.html",
                context={
                    "edit_success": "success",
                    "navigation": get_navigation("manage_users", admin.navigation),
                    "requesting_user_role": request.user.role,
                    "username": user.email,
                },
            )
        if request.method == "GET":
            selected_user = CDUser.objects.get(pk=id)
            current_owner = f"{selected_user.parent.email} - {selected_user.parent.role}"
            eligible_parents = CDUser.objects.filter(role__in=(CDUser.ROLES.ADMIN,CDUser.ROLES.INTERMEDIATE))
            eligible_parents = [f"{parent.email} - {parent.role}" for parent in eligible_parents]
            ratios = Ratio.objects.filter(user=selected_user, status=Ratio.STATUS.ACTIVE).first()
            show_split_royalty_button = (
                selected_user.role == CDUser.ROLES.NORMAL and selected_user.split_royalties_enabled
            )
            context = {
                "navigation": get_navigation("manage_users", admin.navigation),
                "roles": [
                    CDUser.ROLES.ADMIN,
                    CDUser.ROLES.INTERMEDIATE,
                    CDUser.ROLES.NORMAL,
                ],
                "countries": COUNTRIES,
                "languages": LANGUAGES,
                "intermediate_users": eligible_parents,
                "selected_user": selected_user,
                "current_owner": current_owner,
                "requesting_user_role": request.user.role,
                "ratios": ratios,
                "show_split_royalty_button": show_split_royalty_button,
            }
            return render(request, "volt_admin_edit_user.html", context=context)
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def manage_users_get_all_users(request):
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.user.role in [CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE]
    ):
        return processor.manage_users_display(request.user)
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def admin_view_custom_user(request, username):
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.user.role in [CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE]
    ):
        requesting_user_role = processor.get_user_role(request.user)
        requested_user_role = processor.get_user_role(username)
        navigation = (
            admin.navigation
            if requesting_user_role == "admin"
            else intermediate.navigation
        )
        # Distinct confirmed dates values after April 2025
        confirmed_dates = Royalties.objects.filter(confirmed_date__gte=datetime(2025, 4, 1)).values_list('confirmed_date', flat=True).distinct()
        confirmed_dates_list = list(confirmed_dates)
        confirmed_dates_list.sort(reverse=True)
        confirmed_dates_display = {
            date.strftime('%B, %Y'): date.strftime('%B, %Y') for date in confirmed_dates_list
            }
        
        if requested_user_role in ("admin", "intermediate"):
            return render(
                request,
                "volt_admin.html",
                context={
                    "navigation": get_navigation("royalty_stats", navigation),
                    "requesting_user_role": requesting_user_role,
                    "username": username,
                    "page_name": "Royalty Stats",
                    "is_show_due_balance": True,
                    "confirmed_dates_list": confirmed_dates_display,
                },
            )
        return render(
            request,
            "volt_normal.html",
            context={
                "navigation": get_navigation("royalty_stats", navigation),
                "username": username,
                "requesting_user_role": requesting_user_role,
                "is_show_due_balance": True,
                "confirmed_dates_list": confirmed_dates_display,
            },
        )


def login_page(request):
    if request.user.is_authenticated and is_active(request.user):
        if request.user.is_superuser:
            return redirect("dashboard")
        else:
            return redirect("dashboard")
    return render(request, "volt_login.html")


# New ORM-based implementation
def reset_password(request, token):
    """
    Reset user password using token validation with Django ORM
    """
    user_found = False
    user = None
    
    # Get all users and check token match using ORM
    all_users = CDUser.objects.all().values_list('email', flat=True)
    for username in all_users:
        if processor.generate_token(username) == token:
            user_found = True
            user = username
            break
    token_handler = TokenHandler()
    if request.method == "GET":
        if user_found and token_handler.is_token_present(token=token):
            return render(request, "volt_reset_password.html", context={"token": token})
        else:
            return HttpResponseNotFound("<h1>Page not found</h1>")
    if request.method == "POST":
        new_password = request.POST["newpassword"]
        new_password_conf = request.POST["newpasswordconfirm"]
        if user_found:
            if new_password == new_password_conf:
                if update_password(user, new_password):
                    success_message = "Password updated successfully!"
                    token_handler.delete_token(token=token)
                    return render(
                        request,
                        "volt_login.html",
                        context={"success_message": success_message},
                    )
                else:
                    error_message = "Failed to update password!"
                    return render(
                        request,
                        "volt_reset_password.html",
                        context={"error_message": error_message},
                    )
            else:
                error = "New entered passwords don't match!"
                return render(
                    request,
                    "volt_reset_password.html",
                    context={"error_message": error},
                )
        else:
            error = "Invalid token!"
            return render(
                request, "volt_reset_password.html", context={"error_message": error}
            )


def forgot_password(request):
    def email(email_to):
        token = processor.generate_token(email_to)
        reset_url = f"{settings.DOMAIN_URL_}reset_password/{token}"
        body = f"""Click the following link to reset your password\n{reset_url}"""
        response = send_mail("Reset Password", body, settings.EMAIL_FROM, [email_to])
        if response == 1:
            token_handler = TokenHandler()
            token_handler.save_session_token(token=token)
            return True
        else:
            return False

    if request.method == "POST":
        user_email = request.POST["email"]
        if is_active(user_email):
            try:
                user = CDUser.objects.get(email=user_email)
                # User exists, proceed with password reset
                try:
                    success_message = (
                        "Please check your email for further instructions..."
                    )
                    if email(user_email):
                        return render(
                            request,
                            "volt_forgot_password.html",
                            context={"success_message": success_message},
                        )
                    else:
                        error = "Failed to reset password!"
                        return render(
                            request,
                            "volt_forgot_password.html",
                            context={"error_message": error},
                        )
                except Exception as e:
                    error = "Failed to reset password!"
                    return render(
                        request,
                        "volt_forgot_password.html",
                        context={"error_message": error},
                    )
            except CDUser.DoesNotExist:
                error = "Invalid email!"
                return render(
                    request,
                    "volt_forgot_password.html",
                    context={"error_message": error},
                )
        else:
            return render(
                request,
                "volt_forgot_password.html",
                context={
                    "error_message": "This account is in-active. Please contact admin."
                },
            )
    if request.method == "GET":
        return render(
            request,
            "volt_forgot_password.html",
        )


def change_password(request):
    navigation = (
        admin.navigation
        if request.user.role == CDUser.ROLES.ADMIN
        else (
            intermediate.navigation
            if request.user.role == CDUser.ROLES.INTERMEDIATE
            else normal.navigation
        )
    )
    if request.method == "POST" and is_active(request.user):
        if request.user.check_password(request.POST["oldpassword"]):
            if request.POST["newpassword"] == request.POST["newpasswordconfirm"]:
                try:
                    request.user.set_password(request.POST["newpassword"])
                    request.user.save()
                    message = "Password updated successfully!"
                    return render(
                        request,
                        "volt_admin_change_password.html",
                        context={
                            "success_message": message,
                            "username": request.user.email,
                            "requesting_user_role": request.user.role,
                            "navigation": get_navigation("change_password", navigation),
                        },
                    )
                except:
                    error = "Failed to update password!"
                    return render(
                        request,
                        "volt_admin_change_password.html",
                        context={
                            "error_message": error,
                            "username": request.user.email,
                            "requesting_user_role": request.user.role,
                            "navigation": get_navigation("change_password", navigation),
                        },
                    )
            else:
                error = "New entered passwords don't match!"
                return render(
                    request,
                    "volt_admin_change_password.html",
                    context={
                        "error_message": error,
                        "username": request.user.email,
                        "requesting_user_role": request.user.role,
                        "navigation": get_navigation("change_password", navigation),
                    },
                )
        else:
            error = "Invalid old password entered!"

            return render(
                request,
                "volt_admin_change_password.html",
                context={
                    "error_message": error,
                    "username": request.user.email,
                    "requesting_user_role": request.user.role,
                    "navigation": get_navigation("change_password", navigation),
                },
            )

    if request.method == "GET":
        if request.user.is_authenticated and is_active(request.user):
            return render(
                request,
                "volt_admin_change_password.html",
                context={
                    "username": request.user.email,
                    "requesting_user_role": request.user.role,
                    "navigation": get_navigation("change_password", navigation),
                },
            )
        else:
            return render(request, "volt_login.html")


def insert_user(request):
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.user.role in [CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE]
        and request.method == "GET"
    ):
        user = CDUser.objects.get(pk=request.user.pk)
        active_ratio = user.ratios.filter(status=Ratio.STATUS.ACTIVE).first()
        requesting_user_role = user.role
        requesting_user_payout = active_ratio.sales_payout if active_ratio else 0
        navigation = (
            admin.navigation
            if requesting_user_role == CDUser.ROLES.ADMIN
            else intermediate.navigation
        )
        return render(
            request,
            "volt_admin_add_user.html",
            context={
                "navigation": get_navigation("Insert User", navigation),
                "requesting_user_role": requesting_user_role,
                "requesting_user_payout": requesting_user_payout,
                "username": request.user,
            },
        )
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and request.user.role in [CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE]
        and request.method == "POST"
    ):
        if CDUser.objects.filter(email=request.POST["username"]).exists():
            navigation = (
                admin.navigation
                if request.user.role == CDUser.ROLES.ADMIN
                else intermediate.navigation
            )
            return render(
                request,
                "volt_admin_add_user.html",
                context={
                    "navigation": get_navigation("manage_user", navigation),
                    "requesting_user_role": request.user.role,
                    "duplicate_error": True,
                    "username": request.user,
                },
            )
        else:
            role = None
            try:
                role = request.POST["role"]
            except:
                role = CDUser.ROLES.NORMAL
            if role.lower() == CDUser.ROLES.ADMIN and request.user.role == CDUser.ROLES.ADMIN:
                pass
            else:
                if role.lower() == CDUser.ROLES.ADMIN:
                    role = CDUser.ROLES.NORMAL

            created_user = CDUser.objects.create_user(
                email=request.POST["username"],
                password=request.POST["password"],
                role=(
                    CDUser.ROLES.ADMIN
                    if "admin" in role.lower()
                    else (
                        CDUser.ROLES.INTERMEDIATE
                        if "intermediate" in role.lower()
                        else CDUser.ROLES.NORMAL
                    )
                ),
                first_name=request.POST["name"],
                last_name=request.POST["surname"],
                country=request.POST["country"],
                city=request.POST["city"],
                street=request.POST["street"],
                postal_code=request.POST["postal_code"],
                contact_phone=request.POST["contact_phone"],
                company=request.POST["company"],
                company_name=request.POST["company_name"],
                fiskal_id_number=request.POST["fiskal_id_number"],
                country_phone=request.POST["country_phone"],
                company_contact_phone=request.POST["company_contact_phone"],
                pan=request.POST["pan_number"],
                gst_number=request.POST["gst_number"],
                account_name=request.POST["account_name"],
                account_number=request.POST["account_number"],
                ifsc=request.POST["ifsc_code"],
                sort_code=request.POST["sort_code"],
                swift_code=request.POST["swift_code"],
                iban=request.POST["iban_number"],
                bank_country=request.POST["country_of_bank"],
                bank_name=request.POST["bank_name"],
                parent=request.user
            )
            created_user.save()
            ratio = Ratio.objects.create(
                user=created_user,
                stores=request.POST["ratio"],
                youtube=request.POST["yt_ratio"],
                sales_payout=request.POST["sales_payout"],
                sales_payout_threshold=request.POST["sales_payout_threshold"],
            )
            ratio.save()

            # Code for adding team member (if provided)
            member_email = request.POST["team_member_email"]
            member_password = request.POST["team_member_password"]

            if (
                member_email != ""
                and member_password != ""
                and role == CDUser.ROLES.NORMAL
                and not CDUser.objects.filter(email=member_email.lower()).exists()
            ):
                created_member = CDUser.objects.create_user(
                    email=member_email.lower(),
                    password=member_password,
                    role=CDUser.ROLES.MEMBER,
                    parent=created_user,
                    first_name="Member",
                    last_name="Member",
                    contact_phone="NaN",
                    company_contact_phone="NaN",
                    pan="NaN"
                )
                created_member.save()

            navigation = (
                admin.navigation
                if request.user.role == CDUser.ROLES.ADMIN
                else intermediate.navigation
            )
            return render(
                request,
                "volt_admin_manage_users.html",
                context={
                    "navigation": get_navigation("manage_users", navigation),
                    "requesting_user_role": request.user.role,
                    "success": True,
                },
            )
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def redirect_main(request):
    if request.user.is_authenticated and is_active(request.user):
        return redirect("dashboard")
    else:   
        return redirect("login_page")


def login_view(request):
    if request.method == "POST":
        print("request.POST", request.POST)
        print("request.POST.get('username')", request.POST.get("username"))
        username = request.POST.get("username")
        password = request.POST.get("password")
        print("username", username)
        print("password", password)
        
        # Authenticate using CDUser directly
        user = authenticate(username=username, password=password)
        print("user", user)
        print("authenticate(username=username, password=password)", authenticate(username=username, password=password))
        
        if user and is_active(user):
            login(request, user)
            # user is now a CDUser object (from CustomBackend)
            if user.role in [CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE, CDUser.ROLES.NORMAL, CDUser.ROLES.SPLIT_RECIPIENT]:
                return redirect("dashboard")
            elif user.role == CDUser.ROLES.MEMBER:
                return render(
                    request,
                    "volt_normal.html",
                    context={
                        "username": username,
                        "requesting_user_role": "member",
                        "is_show_due_balance": False,
                    },
                )
            else:
                return redirect("manage_users")
    return render(
        request,
        "volt_login.html",
        context={"error_message": "Error logging in, please try again later."},
    )


@csrf_exempt
def refresh_payments(request):
    requesting_user_role = processor.get_user_role(request.user)
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and requesting_user_role == "admin"
    ):
        import os
        from pathlib import Path
        import subprocess
        # Get the base directory (where manage.py is located)
        base_dir = Path(__file__).resolve().parent.parent
        script_path = base_dir / "populate_due_amounts.py"
        
        # Create log file for output
        log_file = base_dir / "populate_due_amounts.log"
        
        # Run the script from the base directory with output redirected to log file
        # Use subprocess.Popen with stdout/stderr redirection so it doesn't block
        with open(log_file, 'w') as log:
            process = Popen(
                ["python", str(script_path)],
                cwd=str(base_dir),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True  # Start in new session so it doesn't get killed when request ends
            )
        
        return JsonResponse({"success": "success", "message": "Due amounts refresh started. Check populate_due_amounts.log for progress."})
    else:
        return JsonResponse({})


def fetch_track_channels(request):
    if request.user.is_authenticated and is_active(request.user):
        username = request.GET["username"]
        track = request.GET["track"]
        left_date = request.GET.get("left_date", "NONE")
        right_date = request.GET.get("right_date", "NONE")
        confirmed_sales_month = request.GET.get("confirmed_sales_month", None)
        filter_type = request.GET.get("filter_type", "basic-filters")
        return processor.fetch_track_channels(username, track, left_date, right_date, confirmed_sales_month, filter_type)
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def get_due_balance(request, username):
    """
    Get due balance using Django ORM
    """
    if request.user.is_authenticated and is_active(request.user):
        try:
            user = CDUser.objects.get(email=username)
            due_amount = DueAmount.objects.filter(user=user).first()
            due_balance = due_amount.amount if due_amount else 0
            return JsonResponse({"due_balance": round(due_balance, 2)})
        except CDUser.DoesNotExist:
            return JsonResponse({"due_balance": 0})
    else:
        return HttpResponseNotFound("<h4>Authentication failed!</h4>")


def refresh_due_balance(request, username):
    if request.user.is_authenticated and is_active(request.user):
        due_balance = processor.refresh_due_balance(username)
        return JsonResponse({"due_balance": round(due_balance, 2)})
    else:
        return HttpResponseNotFound("<h4>Authentication failed!</h4>")


@csrf_exempt
def get_due_reports(request):
    if (
        request.user.is_authenticated
        
        and is_active(request.user)
    ):
        if request.method == "POST":
          
            active_users = CDUser.objects.filter(is_active=True).select_related()
            due_amounts = DueAmount.objects.filter(user__is_active=True).select_related('user')
            
            my_csv = []
            for due_amount in due_amounts:
                user = due_amount.user
                record = {
                    'username': user.email,
                    'amount_due': due_amount.amount,
                    'pan_number': user.pan,
                    'gst_number': user.gst_number,
                    'account_name': user.account_name,
                    'account_number': user.account_number,
                    'ifsc_code': user.ifsc,
                    'sort_code': user.sort_code,
                    'swift_code': user.swift_code,
                    'iban_number': user.iban,
                    'country_of_bank': user.bank_country,
                    'bank_name': user.bank_name
                }
                my_csv.append(record)
            return JsonResponse({"my_csv": my_csv})
        if request.method == "GET":
            role, ratio, yt_ratio = processor.get_user_info(request.user)
            return render(
                request,
                "volt_admin_due_balance_reports.html",
                context={
                    "navigation": get_navigation(
                        "due_balance_reports", admin.navigation
                    ),
                    "requesting_user_role": role,
                    "username": request.user,
                },
            )
    else:
        return HttpResponseNotFound("<h1>Authentication failed!</h1>")


def get_line_chart_and_top_tracks(request):
    logger.error(f"\n>>> VIEW: get_line_chart_and_top_tracks called")
    logger.error(f">>> User: {request.user}")
    if request.user.is_authenticated and is_active(request.user):
        username = None
        if not request.user.is_superuser:
            username = request.user.get_username()
        elif request.user.is_superuser and "username" in request.GET:
            username = request.GET["username"]
        else:
            return redirect("login_page")

        left_date = request.GET.get("left_date", "NONE")
        right_date = request.GET.get("right_date", "NONE")
        confirmed_sales_month = request.GET.get("confirmed_sales_month")
        filter_type = request.GET.get("filter_type", "basic-filters")

        return processor.get_royalty_stats(
            username, left_date, right_date, confirmed_sales_month, filter_type
        )
    else:
        return redirect("login_page")


def clear_user_cache(request, username):
    """Clear cache for a specific user - useful when ratios are updated"""
    if request.user.is_authenticated and is_active(request.user) and request.user.role == CDUser.ROLES.ADMIN:
        from cache import cache
        cache.clean(username)
        return JsonResponse({
            "success": True,
            "message": f"Cache cleared for user: {username}"
        })
    else:
        return JsonResponse({
            "success": False,
            "message": "Unauthorized"
        }, status=403)




def royalty_stats(request):
    requesting_user_role = processor.get_user_role(request.user)
    if request.user.is_authenticated and is_active(request.user):
# Distinct confirmed dates values after April 2025
        confirmed_dates = Royalties.objects.filter(confirmed_date__gte=datetime(2025, 4, 1)).values_list('confirmed_date', flat=True).distinct()
        confirmed_dates_list = list(confirmed_dates)
        confirmed_dates_list.sort(reverse=True)
        confirmed_dates_display = {
            date.strftime("%B, %Y"):date.strftime('%B, %Y') for date in confirmed_dates_list
            }        
        
        return render(
            request,
            "volt_normal.html",
            context={
                "confirmed_dates_list": confirmed_dates_display,
                "username": request.user,
                "navigation": get_navigation("royalty_stats", normal.navigation),
                "requesting_user_role": requesting_user_role,
                "is_show_due_balance": True,
            },
        )
    else:
        return HttpResponse("<h2>Authentication Failed!</h2>")


def logout_view(request):
    logout(request)
    return redirect("login_page")


def upload_calculation_royalties(request):
    requesting_user_role = processor.get_user_role(request.user)
    if (
        request.user.is_authenticated
        and is_active(request.user)
        and requesting_user_role == "admin"
    ):
        if request.method == "POST":
            try:
                calculation_royalties_file = request.FILES[
                    "calculation_royalties_file"
                ].file
                file_handler = FileHandler(
                    calculation_royalties_file, "royalties", "excel"
                )
                # File validation validation
                validator = DataValidator(
                    file_handler.data,
                    [
                        royalties_validations,
                        royalties_meta_validations,
                    ],
                    file_handler.file_type,
                )
                status, response = validator.validate()
                if status:
                                       
                    # Royalties processing
                    royalties_df = validator.process(file_type="royalties")
                    # Royalties meta validation
                    meta_df = validator.process(file_type="royalties_meta")
                    
                    with transaction.atomic():
                        # Process royalties data
                        royalty_objects = []
                        for _, row in royalties_df.iterrows():
                            royalty_obj = Royalties(
                                start_date=pd.to_datetime(row['start_date']).date() if pd.notna(row.get('start_date')) else None,
                                end_date=pd.to_datetime(row['end_date']).date() if pd.notna(row.get('end_date')) else None,
                                country=row.get('country', ''),
                                currency=row.get('currency', ''),
                                type=row.get('type', ''),
                                units=int(row.get('units', 0)),
                                unit_price=float(row.get('unit_price', 0.0)),
                                gross_total=float(row.get('gross_total', 0.0)),
                                channel_costs=float(row.get('channel_costs', 0.0)),
                                taxes=float(row.get('taxes', 0.0)),
                                net_total=float(row.get('net_total', 0.0)),
                                currency_rate=float(row.get('currency_rate', 1.0)),
                                net_total_INR=float(row.get('net_total_INR', 0.0)),
                                channel=row.get('channel', ''),
                                isrc=row.get('isrc', ''),
                                gross_total_INR=float(row.get('gross_total_INR', 0.0)),
                                other_costs_INR=float(row.get('other_costs_INR', 0.0)),
                                channel_costs_INR=float(row.get('channel_costs_INR', 0.0)),
                                taxes_INR=float(row.get('taxes_INR', 0.0)),
                                gross_total_client_currency=float(row.get('gross_total_client_currency', 0.0)),
                                other_costs_client_currency=float(row.get('other_costs_client_currency', 0.0)),
                                channel_costs_client_currency=float(row.get('channel_costs_client_currency', 0.0)),
                                taxes_client_currency=float(row.get('taxes_client_currency', 0.0)),
                                net_total_client_currency=float(row.get('net_total_client_currency', 0.0)),
                                confirmed_date=pd.to_datetime(row['confirmed_date']).date() if pd.notna(row.get('confirmed_date')) else None
                            )
                            royalty_objects.append(royalty_obj)
                        
                        # Process metadata
                        metadata_objects = []
                        for _, row in meta_df.iterrows():
                            metadata_obj = Metadata(
                                isrc=row['isrc'].upper(),
                                release=row['release'],
                                display_artist=row.get('display_artist'),
                                release_launch=pd.to_datetime(row['release_launch']) if pd.notna(row.get('release_launch')) else None,
                                user=row['user'],
                                label_name=row.get('label_name'),
                                primary_genre=row.get('primary_group'),
                                secondary_genre=row.get('secondary_genre'),
                                track_no=row.get('track_no') if pd.notna(row.get('track_no')) else None,
                                track=row['track'],
                                track_display_artist=row.get('track_display_artist'),
                                track_primary_genre=row.get('track_primary_genre'),
                                upc=row.get('upc')
                            )
                            metadata_objects.append(metadata_obj)
                        
                        # Bulk create both royalties and metadata
                        Royalties.objects.bulk_create(royalty_objects, batch_size=1000)
                        Metadata.objects.bulk_create(metadata_objects, batch_size=1000, ignore_conflicts=True)  # ignore_conflicts for duplicate ISRCs
                    
                    return JsonResponse({"success": "Calculation Royalties Uploaded!"})
                else:
                    return JsonResponse({"error": f"{response}"})
            except Exception as e:
                print(traceback.format_exc())
                return JsonResponse(
                    {"error": "Upload Failed! Please check your file and try again."}
                )
        else:
            return JsonResponse({"error": "Invalid Request!"})
    else:
        return JsonResponse({"error": "Authentication Failed!"})


def teams(request):
    """
    Team management using Django ORM with parent-child user relationships
    """
    requesting_user_role = processor.get_user_role(request.user)
    if request.user.is_authenticated and is_active(request.user):
        if request.method == "GET":
            return render(
                request,
                "volt_normal_teams.html",
                {
                    "requesting_user_role": requesting_user_role,
                    "username": request.user,
                },
            )
        elif request.method == "POST":
            member_email = request.POST.get("email_id")
            password = request.POST.get("password_id")

            # Check if user already exists as a team member or regular user
            existing_user = CDUser.objects.filter(email=member_email).first()
            
            if not existing_user:
                # Create new team member user
                try:
                    team_member = CDUser.objects.create_user(
                        email=member_email,
                        password=password,
                        role=CDUser.ROLES.MEMBER,
                        parent=request.user,
                        first_name="Team",
                        last_name="Member",
                        contact_phone="NaN",
                        company_contact_phone="NaN",
                        pan="NaN"
                    )
                    message = "Team member successfully added!"
                    return render(
                        request,
                        "volt_normal_teams.html",
                        {
                            "requesting_user_role": requesting_user_role,
                            "username": request.user,
                            "success": message,
                        },
                    )
                except Exception as e:
                    message = f"Failed to create team member: {str(e)}"
                    return render(
                        request,
                        "volt_normal_teams.html",
                        {
                            "requesting_user_role": requesting_user_role,
                            "username": request.user,
                            "error": message,
                        },
                    )
            else:
                message = "This user is already registered!"
                return render(
                    request,
                    "volt_normal_teams.html",
                    {
                        "requesting_user_role": requesting_user_role,
                        "username": request.user,
                        "error": message,
                    },
                )
    else:
        return HttpResponse("Authentication Failed!")


def get_my_team(request):
    """
    Get team members using Django ORM parent-child relationships
    """
    if request.user.is_authenticated and is_active(request.user):
        if request.method == "GET":
            # Get all team members (users where current user is the parent)
            team_members = CDUser.objects.filter(
                parent=request.user,
                role=CDUser.ROLES.MEMBER
            ).values_list('email', flat=True)
            
            headers = "<th>Members</th><th></th>"
            body = ""
            for member in team_members:
                body += f"""<tr><td>{member}</td><td><span style="cursor:pointer;" class="material-symbols-outlined" onclick="delete_member('{member}')">person_remove</span></td></tr>"""
            
            table = f"""<table class="table table-hover" id="data_table">
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
            return HttpResponse("Invalid Request!")
    else:
        return HttpResponse("Authentication Failed!")



# New ORM-based implementation
def delete_member(request, member):
    """
    Delete team member using Django ORM
    """
    if request.user.is_authenticated and is_active(request.user):
        if request.method == "POST":
            try:
                # Find and delete the team member
                team_member = CDUser.objects.filter(
                    email=member,
                    parent=request.user,
                    role=CDUser.ROLES.MEMBER
                ).first()
                
                if team_member:
                    team_member.delete()
                    return JsonResponse({"success": "success"})
                else:
                    return JsonResponse({"error": "Team member not found"})
            except Exception as e:
                return JsonResponse({"error": f"Error deleting member: {str(e)}"})
        else:
            return HttpResponse("Invalid Request!")
    else:
        return HttpResponse("Authentication Failed!")
