from sqlalchemy import create_engine
import sys
import logging
logger = logging.getLogger(__name__)
from RoyaltyWebsite.settings import RAW_MYSQL_CONNECTION
import hashlib
import json
from subprocess import Popen
import pandas as pd
from django.http import JsonResponse
from cache import cache
from datetime import date
from dateutil.relativedelta import relativedelta
from commons.navigation import navigation as _navigation
from commons.sql_client import sql_client
from main.models import CDUser, Ratio, DueAmount
from django.db.models import Subquery, OuterRef, IntegerField, Sum
from django.db.models.functions import Coalesce
from django.db import connection
from django.db import models
import pandas as pd
import json, csv, os
from django.conf import settings
from main.models import CDUser, Ratio
import pandas as pd
from releases.models import SplitReleaseRoyalty, Track
from datetime import datetime
import calendar

class ProcessorMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Processor(metaclass=ProcessorMeta):
    # Attributes
    db = None
    ROLES = ["normal", "intermediate", "admin"]
    colors = [
        "#ff1744",
        "#3D5AFE",
        "#00E676",
        "#FF9100",
        "#EEFF41",
        "#E65100",
        "#E91E63",
        "#388E3C",
        "#795548",
        "#18FFFF",
    ] * 10


    # Helper Methods
    def get_sql_connection(self):
        if not self.db:
            self.db = create_engine(RAW_MYSQL_CONNECTION, echo=False)
            return self.db
        else:
            return self.db

    def encode_pass(self, p):
        return hashlib.md5(str.encode(p)).digest()

    def generate_token(self, email):
        return hashlib.md5(str.encode(str(email).lower())).hexdigest()

    def get_user_info(self, username):
        record = cache.hit(username)
        if record:
            return record[0], record[1], record[2]
        else:
          
            try:
                user = CDUser.objects.get(email=username)
                role = user.role.lower()
                
                # Get active ratio for this user
                active_ratio = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
                if active_ratio:
                    ratio = active_ratio.stores
                    yt_ratio = active_ratio.youtube
                else:
                    ratio = 0
                    yt_ratio = 0
                    
                cache.store(username, (role, ratio, yt_ratio))
                return role, ratio, yt_ratio
            except CDUser.DoesNotExist:
                # Handle case where user doesn't exist
                return None, 0, 0

    def get_user_role(self, username):
        record = cache.hit(username)
        if record:
            return record[0].lower()
        else:
           
            try:
                user = CDUser.objects.get(email=username)
                role = user.role.lower()
                
                # Get active ratio for this user
                active_ratio = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
                if active_ratio:
                    ratio = active_ratio.stores
                    yt_ratio = active_ratio.youtube
                else:
                        ratio = 0
                        yt_ratio = 0
                    
                cache.store(username, (role, ratio, yt_ratio))
                return role
            except CDUser.DoesNotExist:
                return 'normal'

    def get_users_belongs_to(self, username):
       
        try:
            parent_user = CDUser.objects.get(email=username)
            child_users = CDUser.objects.filter(parent=parent_user).values_list('email', flat=True)
            return list(child_users)
        except CDUser.DoesNotExist:
            return list()

    # Processor methods
    def get_royalty_stats(self, username, left_date, right_date, confirmed_sales_month, filter_type):
        requested_user_role, ratio, yt_ratio = self.get_user_info(username)
        
        # Check if user exists for split royalty queries
        try:
            user_obj = CDUser.objects.get(email=username)
        except CDUser.DoesNotExist:
            user_obj = None
        
        if left_date == 'NONE' and right_date == 'NONE':
            right_date = date.today()
            left_date = date.today()-relativedelta(months=6)
            right_date = "/".join(str(right_date).split("-")[:2][::-1])
            left_date = "/".join(str(left_date).split("-")[:2][::-1])
        
        response = None
        if requested_user_role == 'admin':
            print('confirmed_sales_month', confirmed_sales_month)
            response = admin.get_royalty_stats(username, left_date, right_date, confirmed_sales_month, filter_type, ratio, yt_ratio)
        elif requested_user_role == 'intermediate':
            response = intermediate.get_royalty_stats(username, left_date, right_date, confirmed_sales_month, filter_type, ratio, yt_ratio)
        else:
            # Get split_royalties_enabled flag for the user
            try:
                user_obj = CDUser.objects.get(email=username)
                split_royalties_enabled = user_obj.split_royalties_enabled
            except CDUser.DoesNotExist:
                split_royalties_enabled = False
            response = normal.get_royalty_stats(username, left_date, right_date, confirmed_sales_month, filter_type, ratio, yt_ratio, split_royalties_enabled)

        # So channel breakdown uses same date range on first load: pass effective dates to frontend
        response['effective_left_date'] = left_date
        response['effective_right_date'] = right_date
        return JsonResponse(response)

    def manage_users_display(self, user):
        if user.role == CDUser.ROLES.ADMIN:
            return admin.manage_users_display(user)
        elif user.role == CDUser.ROLES.INTERMEDIATE:
            return intermediate.manage_users_display(user)
        else:
            return JsonResponse({"error": "Authorization failed!"})

    def fetch_track_channels(self, username, track, left_date, right_date, confirmed_sales_month=None, filter_type="basic-filters"):
        # Treat missing/undefined/empty as NONE so channel breakdown uses same default date range as top tracks (last 6 months)
        if not left_date or (isinstance(left_date, str) and left_date.strip().upper() in ("NONE", "UNDEFINED")):
            left_date = "NONE"
        if not right_date or (isinstance(right_date, str) and right_date.strip().upper() in ("NONE", "UNDEFINED")):
            right_date = "NONE"
        if left_date == 'NONE' and right_date == 'NONE' and not confirmed_sales_month:
            right_date = date.today()
            left_date = date.today()-relativedelta(months=6)
            right_date = "/".join(str(right_date).split("-")[:2][::-1])
            left_date = "/".join(str(left_date).split("-")[:2][::-1])
        role, ratio, yt_ratio = self.get_user_info(username)
        if role == 'admin':
            return JsonResponse(admin.fetch_track_channels(username, ratio, yt_ratio, left_date, right_date, track, confirmed_sales_month, filter_type))
        elif role == 'intermediate':
            return JsonResponse(intermediate.fetch_track_channels(username, ratio, yt_ratio, left_date, right_date, track, confirmed_sales_month, filter_type))
        else:
            return JsonResponse(normal.fetch_track_channels(username, ratio, yt_ratio, left_date, right_date, track, confirmed_sales_month, filter_type))
    
    def send_royalties_data(self, email, field_category, field, start_date, end_date):
        normal.send_royalties_data(email, field_category, field, start_date, end_date)


    def refresh_due_balance(self, username):
        # Bypass cache so we always use current role from DB (cache can have stale role)
        try:
            user = CDUser.objects.get(email__iexact=username)
            requested_user_role = (user.role or "").strip().lower().replace(" ", "_")
            canonical_email = user.email  # use DB email for queries and DueAmount
        except CDUser.DoesNotExist:
            return 0
        _, ratio, yt_ratio = self.get_user_info(username)

        response = None
        if requested_user_role == 'admin':
            response = admin.refresh_due_balance(canonical_email, 100, 100)
        elif requested_user_role == 'intermediate':
            response = intermediate.refresh_due_balance(canonical_email, ratio, yt_ratio)
        elif requested_user_role == 'split_recipient':
            response = normal.refresh_due_balance_for_split_recipient(canonical_email)
        else:
            response = normal.refresh_due_balance(canonical_email, ratio, yt_ratio)

        return response

class AdminProcessor():
    role = 'admin'
    navigation = _navigation['admin']
    def get_royalty_stats(self, username, left_date, right_date, confirmed_sales_month, filter_type, ratio, yt_ratio):
        admin_ratio = 100
        admin_ytratio = 100

       
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT DISTINCT u1.email as username, u1.role, u2.email as belongs_to, 
                       COALESCE(r1.stores, 0) as ratio, COALESCE(r1.youtube, 0) as yt_ratio  
                FROM main_cduser u1 
                LEFT JOIN main_cduser u2 ON u1.parent_id = u2.id 
                LEFT JOIN main_ratio r1 ON u1.id = r1.user_id AND r1.status = 'active'
                WHERE u1.role = 'normal' AND (u1.parent_id IS NULL OR u2.email = '{username}')
                UNION ALL
                SELECT DISTINCT u1.email as username, u1.role, u2.email as belongs_to,
                       COALESCE(r2.stores, 0) as ratio, COALESCE(r2.youtube, 0) as yt_ratio 
                FROM main_cduser u1 
                JOIN main_cduser u2 ON u1.parent_id = u2.id 
                LEFT JOIN main_ratio r2 ON u2.id = r2.user_id AND r2.status = 'active'
                WHERE u2.role = 'intermediate'
            """)
            columns = [col[0] for col in cursor.description]
            ratios_ytratio = pd.DataFrame(cursor.fetchall(), columns=columns)
        list_of_users = ",".join( [f"'{user}'" for user in ratios_ytratio['username'].tolist()] )
        filter_ = []

        if 'confirmed' in filter_type:
            filter_.append(f" LAST_DAY(confirmed_date) = LAST_DAY('{confirmed_sales_month}')")
        else:
            if left_date != "NONE":
                left_date = left_date.split("/")[1] + "-" + left_date.split("/")[0]
                filter_.append(f" LAST_DAY(end_date) >= '{left_date}-01'")

            if right_date != "NONE":
                right_date = right_date.split(
                    "/")[1] + "-" + right_date.split("/")[0]
                filter_.append(f"  LAST_DAY(end_date) <= LAST_DAY('{right_date}-01')")

        if len(filter_):
            filter_ =" and " +' and '.join(filter_)
        else:
            filter_=''
        # Updated to use Django database manager with new table references
        # Top tracks query - EXCLUDE YouTube Official Channel
        top_tracks_query = f""" select LOWER(m.user) as user,m.track,sum(r.units) as units,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where m.user in ({list_of_users}) and r.channel != 'Youtube Official Channel' {filter_} group by m.user,m.track;"""
        print(top_tracks_query)
        # YouTube Official Channel query - separate query for YouTube channels
        top_youtube_channels_query = f""" select LOWER(m.user) as user,m.track as channel_name,sum(r.units) as units,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where m.user in ({list_of_users}) and r.channel = 'Youtube Official Channel' {filter_} group by m.user,m.track;"""
        top_channels_query = f""" select  LOWER(m.user) as user,r.channel,sum(r.units) as units,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where m.user in ({list_of_users}) and r.channel != 'Youtube Official Channel' {filter_}  group by m.user,r.channel;"""
        line_graph_query =  f"""select r.end_date,r.channel,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where m.user in ({list_of_users}) {filter_} group by r.end_date,r.channel;"""

        with connection.cursor() as cursor:
            sys.stderr.write(f"ABOUT_TO_EXECUTE: username={username}, filter={filter_}\n"); sys.stderr.flush()
            sys.stderr.write(f"top_tracks_query (first 500 chars): {top_tracks_query[:500]}\n"); sys.stderr.flush()
            cursor.execute(top_tracks_query)
            columns = [col[0] for col in cursor.description]
            top_tracks = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_top_tracks: shape={top_tracks.shape}, empty={top_tracks.empty}, row_count={len(top_tracks)}\n"); sys.stderr.flush()
            
            # Execute YouTube channels query
            cursor.execute(top_youtube_channels_query)
            columns = [col[0] for col in cursor.description]
            top_youtube_channels = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_top_youtube_channels: shape={top_youtube_channels.shape}, empty={top_youtube_channels.empty}, row_count={len(top_youtube_channels)}\n"); sys.stderr.flush()
            
            cursor.execute(top_channels_query)
            columns = [col[0] for col in cursor.description]
            top_channels = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_top_channels: shape={top_channels.shape}, empty={top_channels.empty}, row_count={len(top_channels)}\n"); sys.stderr.flush()
            
            cursor.execute(line_graph_query)
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(cursor.fetchall(), columns=columns)

        # Return empty data structures instead of error - UI elements should still be visible
        # Only check if line_df is empty (needed for chart), but allow empty data for tables
        if df.empty:
            # Return empty structures but still provide ratio info for UI
            return {
                "lines": {},
                "labels": [],
                "top_channels": {},
                "ratio": int(admin_ratio),
                "yt_ratio": int(admin_ytratio),
                "table": """<table class="table table-flush" id="data_table_tracks">
                    <thead class="thead-light">
                    <th>Track Name</th><th>Units Sold</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                    </thead>
                    <tbody>
                        <tr><td colspan="4" style="text-align:center;">No track data found</td></tr>
                    </tbody>
                    </table>
                """,
                "youtube_channels_table": """<table class="table table-flush" id="data_table_youtube_channels">
                    <thead class="thead-light">
                    <th>Channel Name</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                    </thead>
                    <tbody>
                        <tr><td colspan="3" style="text-align:center;">No YouTube Channel data found</td></tr>
                    </tbody>
                    </table>
                """
            }
        
        ratios = {row['username'].lower(): row['ratio']
                for index, row in ratios_ytratio.iterrows()}
        yt_ratios = {row['username'].lower(): row['yt_ratio']
                    for index, row in ratios_ytratio.iterrows()}

        # Process top tracks (excluding YouTube)
        if not top_tracks.empty:
            top_tracks['net_total_INR'] = top_tracks['gross_total']
        else:
            top_tracks = pd.DataFrame(columns=['user', 'track', 'units', 'gross_total', 'net_total_INR'])
        
        # Process YouTube channels separately
        if not top_youtube_channels.empty:
            top_youtube_channels['net_total_INR'] = top_youtube_channels.apply(
                lambda x: round(x['gross_total'] * (admin_ytratio/100 - yt_ratios[f'{x["user"]}']/100), 2), axis=1)
            top_youtube_channels = top_youtube_channels.drop(columns=['user', 'units'])
            top_youtube_channels = (
                top_youtube_channels.groupby(["channel_name"])[
                    ['gross_total', 'net_total_INR']]
                .sum()
                .reset_index()
            )
            top_youtube_channels.columns = ["Channel Name", "Gross Total (INR)","Net Total (INR)"]
            top_youtube_channels["Net Total (INR)"] = top_youtube_channels["Net Total (INR)"].apply(
                lambda x: round(x, 2)
            )
            top_youtube_channels["Gross Total (INR)"] = top_youtube_channels["Gross Total (INR)"].apply(
                lambda x: round(x, 2)
            )
            youtube_channels_body = "".join(
                top_youtube_channels.applymap(lambda x: f"<td>{x}</td>")
                .apply(lambda x: "".join(x), axis=1)
                .apply(lambda x: f"<tr>{x}</tr>")
            )
            youtube_headers = "".join([f"<th>{x}</th>" for x in top_youtube_channels.columns])
            total_gross = top_youtube_channels["Gross Total (INR)"].sum()
            total_net = top_youtube_channels["Net Total (INR)"].sum()
            youtube_total_row = f"<tfoot><tr><td><b>Total</b></td><td><b>{total_gross:,.2f}</b></td><td><b>{total_net:,.2f}</b></td></tr></tfoot>"
            youtube_channels_table = f"""<table class="table table-flush" id="data_table_youtube_channels">
                <thead class="thead-light">
                {youtube_headers}
                </thead>
                <tbody>
                    {youtube_channels_body}
                </tbody>
                {youtube_total_row}
                </table>
            """
        else:
            youtube_channels_table = """<table class="table table-flush" id="data_table_youtube_channels">
                <thead class="thead-light">
                <th>Channel Name</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                </thead>
                <tbody>
                    <tr><td colspan="3" style="text-align:center;">No YouTube Channel data found</td></tr>
                </tbody>
                </table>
            """
        
        if not top_channels.empty:
            top_channels['net_total_INR'] = top_channels['gross_total']
            top_channels['net_total_INR'] = top_channels.apply(
                lambda x: round(x['gross_total'] *
                                (admin_ratio/100 -
                                ratios[f'{x["user"]}']/100)
                                if x['channel'] != 'Youtube Official Channel' else x['gross_total']
                                * (admin_ytratio/100 - yt_ratios[f'{x["user"]}']/100), 2), axis=1)
            top_channels = top_channels.drop(columns=['user'])
            top_channels = (
                top_channels.groupby(["channel"])[
                    ["units", 'gross_total', 'net_total_INR']]
                .sum()
                .reset_index()
            )
        else:
            top_channels = pd.DataFrame(columns=['channel', 'units', 'gross_total', 'net_total_INR'])
        
        df['net_total_INR'] = df['gross_total']
        line_df = (
            df.pivot(index="end_date", columns="channel",
                    values="net_total_INR")
            .sort_index()
            .fillna(0)
        )
        
        line_df.index = pd.to_datetime(line_df.index)
        line_df = line_df.resample("M").sum()
        lines = {}
        labels = []
        for i,v in enumerate(line_df.index):
            if len(line_df.index) > 1 and i == 0:
                v = v.replace(day=1)
                labels.append(v.date().isoformat())
            else:
                labels.append(v.date().isoformat())

        for ind, val in sorted(enumerate(line_df.columns)):
            line = {}
            line["label"] = val
            line["data"] = list(line_df[val])
            line["lineTension"] = 0.3
            line["fill"] = True
            line['pointBorderColor'] = 'white'
            line['pointRadius'] = 5
            line["borderColor"] = processor.colors[ind]
            lines[val] = line
        
        if not top_channels.empty:
            top_channels = top_channels.set_index(
                "channel").to_dict(orient="index")
        else:
            top_channels = {}
        
        # Process top tracks (excluding YouTube)
        if not top_tracks.empty:
            top_tracks['net_total_INR'] = top_tracks.apply(
                lambda x: round(x['gross_total'] * (admin_ratio/100 - ratios[f'{x["user"]}']/100), 2), axis=1)
        
        # Process top tracks (excluding YouTube)
        if not top_tracks.empty:
            top_tracks = top_tracks.drop(columns=['user'])
            top_tracks = (
                top_tracks.groupby(["track"])[
                    ["units", 'gross_total', 'net_total_INR']]
                .sum()
                .reset_index()
            )
            top_tracks.columns = ["Track Name", "Units Sold", "Gross Total (INR)","Net Total (INR)"]
            top_tracks["Net Total (INR)"] = top_tracks["Net Total (INR)"].apply(
                lambda x: round(x, 2)
            )
            top_tracks["Gross Total (INR)"] = top_tracks["Gross Total (INR)"].apply(
                lambda x: round(x, 2)
            )

            top_tracks_body = "".join(
                top_tracks.applymap(lambda x: f"<td>{x}</td>")
                .apply(lambda x: "".join(x), axis=1)
                .apply(
                    lambda x: "<tr"
                    + f' onClick=break_down_tracks("{x.split("</td>")[0].replace("<td>","").replace(" ", "|_|")}")  style="cursor: pointer;"'
                    + f">{x}</tr>"
                )
            )
            headers = "".join([f"<th>{x}</th>" for x in top_tracks.columns])
            table = f"""<table class="table table-flush" id="data_table_tracks">
                <thead class="thead-light">
                {headers}
                </thead>
                <tbody>
                    {top_tracks_body}
                </tbody>
                </table>
            """
        else:
            table = """<table class="table table-flush" id="data_table_tracks">
                <thead class="thead-light">
                <th>Track Name</th><th>Units Sold</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                </thead>
                <tbody>
                    <tr><td colspan="4" style="text-align:center;">No track data found</td></tr>
                </tbody>
                </table>
            """

        print(lines)
        print(labels)
        print(top_channels)
        print(ratio)
        print(yt_ratio)

        return {
            "lines": lines,
            "labels": labels,
            "top_channels": top_channels,
            "ratio": int(admin_ratio),
            "yt_ratio": int(admin_ytratio),
            "table": table,
            "youtube_channels_table": youtube_channels_table
        }

    def manage_users_display(self, user):
        normal_users = CDUser.objects.filter(role=CDUser.ROLES.NORMAL)
        admin_specific_intermediate_users = CDUser.objects.filter(role=CDUser.ROLES.INTERMEDIATE, parent=user)
        admin_users = CDUser.objects.filter(role=CDUser.ROLES.ADMIN).exclude(email=user.email)
        split_recipient_users = CDUser.objects.filter(role=CDUser.ROLES.SPLIT_RECIPIENT)
        users_qs = normal_users | admin_specific_intermediate_users | admin_users | split_recipient_users
        active_ratios = Ratio.objects.filter(
            user=OuterRef("pk"),
            status=Ratio.STATUS.ACTIVE
        )
        users_qs = users_qs.annotate(
            stores=Coalesce(
                Subquery(active_ratios.values("stores")[:1]),
                0,
                output_field=IntegerField()
            ),
            youtube=Coalesce(
                Subquery(active_ratios.values("youtube")[:1]),
                0,
                output_field=IntegerField()
            ),
        )
        users_qs = users_qs.values("id", "email", "role", "stores", "youtube", "parent__email", "split_royalties_enabled")
        users = pd.DataFrame.from_records(users_qs)
        
        # Define all expected columns for the DataFrame
        expected_columns = ['id', 'username', 'role', 'ratio', 'yt_ratio', 'amount_due', 'belongs_to', 'split_royalties_enabled', ' ']

        if not users.empty:
            users = users.rename(columns={
                'email': 'username',
                'stores': 'ratio',
                'youtube': 'yt_ratio',
                'parent__email': 'belongs_to'
            })
            users[" "] = users.apply(
                lambda x: f'<a href=\"/edit_user/{x["id"]}\"><span class=\"material-symbols-outlined\">edit</span></a>',
                axis=1,
                result_type="reduce",
            )
            users["ratio"] = users["ratio"].fillna(
                "").apply(lambda x: f"{x}%" if x else "")
            users["yt_ratio"] = (
                users["yt_ratio"].fillna("").apply(lambda x: f"{x}%" if x else "")
            )
            users["split_royalties_enabled"] = users["split_royalties_enabled"].apply(lambda x: "✅" if x else "❌")
            users = users.drop(columns=['id'])

            due_amount_qs = DueAmount.objects.all().values("user__email", "amount")
            due_amount_df = pd.DataFrame.from_records(due_amount_qs)
            due_amount_df = due_amount_df.rename(columns={
                'user__email': 'username',
                'amount': 'amount_due',
            })
            users = pd.merge(users, due_amount_df, on='username', how='left').fillna(0)
            users = users[['username', 'role', 'ratio', 'yt_ratio', 'amount_due', 'belongs_to', 'split_royalties_enabled', ' ']]
            users["username"] = users.apply(
                lambda x: f'<a href=\"/custom_user/{x["username"]}\">{x["username"]}</a>',
                axis=1,
                result_type="reduce",
            )
        else:
            # Create an empty DataFrame with all expected columns if the queryset was empty
            users = pd.DataFrame(columns=expected_columns)
            # Drop the 'id' column from the empty DataFrame as it's not needed for display
            users = users.drop(columns=['id']) 

        headers = "<th>Username</th><th>Role</th><th>Ratio</th><th>Youtube Official Channel Ratio</th><th>Due Amount</th><th>Belongs to</th><th>Split Royalty</th><th>Edit</th>"
        body = "".join(
            users.applymap(lambda x: f"<td>{x}</td>")
            .apply(lambda x: "".join(x), axis=1)
            .apply(lambda x: f"<tr>{x}</tr>")
        )
        table = f"""<table class=\"table table-hover\" id=\"data_table\">\
            <thead>\
            {headers}\
            </thead>\
            <tbody>\
                {body}\
            </tbody>\
            </table>\
        """
        return JsonResponse({"table": table})

    def fetch_track_channels(self,  username, ratio, yt_ratio, left_date, right_date, track_name, confirmed_sales_month=None, filter_type="basic-filters"):
        track_name = track_name.replace("|_|", " ")
        admin_ratio = 100
        admin_ytratio = 100
        # Updated to use Django database manager with new table references
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT DISTINCT u1.email as username, u1.role, u2.email as belongs_to, 
                       COALESCE(r1.stores, 0) as ratio, COALESCE(r1.youtube, 0) as yt_ratio  
                FROM main_cduser u1 
                LEFT JOIN main_cduser u2 ON u1.parent_id = u2.id 
                LEFT JOIN main_ratio r1 ON u1.id = r1.user_id AND r1.status = 'active'
                WHERE u1.role = 'normal' AND (u1.parent_id IS NULL OR u2.email = '{username}')
                UNION ALL
                SELECT DISTINCT u1.email as username, u1.role, u3.email as belongs_to,
                       COALESCE(r2.stores, 0) as ratio, COALESCE(r2.youtube, 0) as yt_ratio 
                FROM main_cduser u1 
                JOIN main_cduser u2 ON u1.parent_id = u2.id 
                JOIN main_cduser u3 ON u2.parent_id = u3.id
                LEFT JOIN main_ratio r2 ON u2.id = r2.user_id AND r2.status = 'active'
                WHERE u2.role = 'intermediate'
            """)
            columns = [col[0] for col in cursor.description]
            ratios_ytratio = pd.DataFrame(cursor.fetchall(), columns=columns)
        list_of_users = ",".join( [f"'{user}'" for user in ratios_ytratio['username'].tolist()] )
        filt = []
        
        # Handle confirmed sales month filter (same logic as get_royalty_stats)
        if 'confirmed' in filter_type and confirmed_sales_month:
            filt.append(f" LAST_DAY(confirmed_date) = LAST_DAY('{confirmed_sales_month}')")
        else:
            if left_date != "NONE":
                left_date = left_date.split("/")[1] + "-" + left_date.split("/")[0]
                filt.append(f" LAST_DAY(end_date) >= '{left_date}-01'")

            if right_date != "NONE":
                right_date = right_date.split(
                    "/")[1] + "-" + right_date.split("/")[0]
                filt.append(f"  LAST_DAY(end_date) <= LAST_DAY('{right_date}-01')")
        if len(filt):
            filt = ' and ' + ' and '.join(filt)
        else:
            filt=''

        # track_channels_query = f""" select channel,sum(units) as units,sum(net_total_INR) as gross_total from royalties left join metadata using (isrc) {filt} and track='{track_name}' group by channel;"""
        # tracks_channels_df = pd.read_sql(track_channels_query, db)
        # if tracks_channels_df.empty:
        #     return {'track_error':'No Data Found!'}
        
        ##
        track_channels_query =  f""" select LOWER(m.user) as user,r.channel,sum(r.units) as units,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where LOWER(m.user) in ({list_of_users}) and m.track = '{track_name}'  {filt} group by m.user,r.channel;"""

        with connection.cursor() as cursor:
            sys.stderr.write(f"ABOUT_TO_EXECUTE: username={username}, filter={filt}\n"); sys.stderr.flush()
            sys.stderr.write(f"track_channels_query (first 500 chars): {track_channels_query[:500]}\n"); sys.stderr.flush()
            cursor.execute(track_channels_query)
            columns = [col[0] for col in cursor.description]
            tracks_channels_df = pd.DataFrame(cursor.fetchall(), columns=columns)

        if (tracks_channels_df.empty) :
            return {'error':'No Data Found!'}
        
        ratios = {row['username'].lower(): row['ratio']
                for index, row in ratios_ytratio.iterrows()}
        yt_ratios = {row['username'].lower(): row['yt_ratio']
                    for index, row in ratios_ytratio.iterrows()}

        tracks_channels_df['net_total_INR'] = tracks_channels_df.apply(
            lambda x: round(x['gross_total'] *
                            (admin_ratio/100 -
                            ratios[f'{x["user"]}']/100)
                            if x['channel'].lower() != 'youtube official channel' else x['gross_total']
                            * (admin_ytratio/100 - yt_ratios[f'{x["user"]}']/100), 2), axis=1)

        tracks_channels_df = tracks_channels_df.drop(columns=['user'])
        tracks_channels_df = (
            tracks_channels_df.groupby(["channel"])[
                ["units", 'gross_total', 'net_total_INR']]
            .sum()
            .reset_index()
        )

        channels = []
        for index, row in tracks_channels_df.iterrows():
            current_channel = {
                'channel': row['channel'],
                'units': row['units'],
                'gross_total': row['gross_total'],
                'net_total_INR': row['net_total_INR']
            }
            channels.append(current_channel)
        tracks_channels = {track_name: channels}

        return {
            "track_channels": tracks_channels
        }

    
    def refresh_due_balance(self, username,ratio,yt_ratio):
        query = f"""
            -- Admin Users
            WITH ADMIN_USERS AS (
                SELECT email as username FROM main_cduser WHERE role LIKE 'admin'
            ),
            -- Intermediate Users
            INTERMEDIATE_USERS AS (
                SELECT email as username FROM main_cduser WHERE role LIKE 'intermediate'
            ),
            -- Normal Users
            NORMAL_USERS AS (
                SELECT email as username FROM main_cduser WHERE role LIKE 'normal'
            ),
            -- Amount from normal/intermediate users, belonging directly to admins
            NORMAL_INTERMEDIATE_BELONG_TO_ADMIN AS (
                SELECT ROUND(SUM(calculated_net_total_INR), 2) as net_total_INR
                FROM (
                    SELECT 
                        ADMIN1.user, 
                        ADMIN1.channel_type,
                        CASE 
                            WHEN ADMIN1.channel_type LIKE 'stores' THEN 
                                ADMIN1.net_total_INR * ((100 - ADMIN1.stores_ratio)/100)
                            ELSE 
                                ADMIN1.net_total_INR * ((100 - ADMIN1.youtube_ratio)/100) 
                        END AS calculated_net_total_INR
                    FROM (
                        SELECT 
                            metadata.user as user, 
                            CASE 
                                WHEN royalties.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                                ELSE 'stores' 
                            END AS channel_type,
                            ratio.stores as stores_ratio,
                            ratio.youtube as youtube_ratio,
                            SUM(royalties.net_total_INR) as net_total_INR
                        FROM releases_royalties royalties 
                        LEFT JOIN releases_metadata metadata ON LOWER(royalties.isrc) = LOWER(metadata.isrc)
                        LEFT JOIN main_cduser user_login ON metadata.user = user_login.email
                        LEFT JOIN main_ratio ratio ON user_login.id = ratio.user_id AND ratio.status = 'active'
                                                 WHERE 
                             -- Normal Users belonging directly to admins
                             (user_login.email IN (SELECT nu.username FROM NORMAL_USERS nu) AND user_login.parent_id IN (SELECT au_parent.id FROM main_cduser au_parent WHERE au_parent.email IN (SELECT au.username FROM ADMIN_USERS au))) OR		
                             -- Intermediate Users belonging directly to admins
                             (user_login.email IN (SELECT iu.username FROM INTERMEDIATE_USERS iu) AND user_login.parent_id IN (SELECT au_parent2.id FROM main_cduser au_parent2 WHERE au_parent2.email IN (SELECT au2.username FROM ADMIN_USERS au2)))	
                        GROUP BY metadata.user, 
                                CASE 
                                    WHEN royalties.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                                    ELSE 'stores' 
                                END, 
                                ratio.stores, ratio.youtube
                    ) ADMIN1
                ) ADMIN2
            ),
            -- Amount from normal users, belonging to intermediates, which belong to admins
            NORMAL_BELONG_TO_INTERMEDIATE_BELONG_TO_ADMIN AS (
                SELECT ROUND(SUM(calculated_net_total_INR), 2) as net_total_INR
                FROM (
                    SELECT 
                        ADMIN3.user, 
                        ADMIN3.channel_type,
                        CASE 
                            WHEN ADMIN3.channel_type LIKE 'stores' THEN 
                                ADMIN3.net_total_INR * ((100 - ADMIN3.parent_stores_ratio)/100)
                            ELSE 
                                ADMIN3.net_total_INR * ((100 - ADMIN3.parent_youtube_ratio)/100) 
                        END AS calculated_net_total_INR
                    FROM (
                        SELECT 
                            metadata.user as user, 
                            CASE 
                                WHEN royalties.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                                ELSE 'stores' 
                            END AS channel_type,
                            SUM(royalties.net_total_INR) as net_total_INR,
                            parent_ratio.stores as parent_stores_ratio,
                            parent_ratio.youtube as parent_youtube_ratio
                        FROM releases_royalties royalties 
                        LEFT JOIN releases_metadata metadata ON LOWER(royalties.isrc) = LOWER(metadata.isrc)
                        LEFT JOIN main_cduser user_login ON metadata.user = user_login.email
                        LEFT JOIN main_cduser as parent_user_login ON user_login.parent_id = parent_user_login.id
                        LEFT JOIN main_ratio parent_ratio ON parent_user_login.id = parent_ratio.user_id AND parent_ratio.status = 'active'
                                                 WHERE 
                             -- Normal Users belonging directly to intermediates (whose parents are admins)
                             (user_login.email IN (SELECT nu2.username FROM NORMAL_USERS nu2) AND user_login.parent_id IN (SELECT iu_parent.id FROM main_cduser iu_parent WHERE iu_parent.email IN (SELECT iu2.username FROM INTERMEDIATE_USERS iu2)))
                        GROUP BY metadata.user, 
                                CASE 
                                    WHEN royalties.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                                    ELSE 'stores' 
                                END, 
                                parent_ratio.stores, parent_ratio.youtube
                    ) ADMIN3
                ) ADMIN4
            ),
            -- Total Amount generated for admins
            NET_TOTAL_ADMINS AS (
                SELECT 'admin@admin.com' as username, SUM(net_total_INR) as net_total_INR FROM (
                    SELECT net_total_INR FROM NORMAL_INTERMEDIATE_BELONG_TO_ADMIN
                    UNION ALL
                    SELECT net_total_INR FROM NORMAL_BELONG_TO_INTERMEDIATE_BELONG_TO_ADMIN
                ) ADMIN5
            ),
            -- Total amount paid to admins
            PAYMENTS AS (
                SELECT 
                    username, 
                    SUM(amount_paid) + SUM(tds) as completed_payments 
                FROM (
                    SELECT 
                        'admin@admin.com' as username, 
                        SUM(payments.amount_paid) as amount_paid, 
                        SUM(payments.tds) as tds 
                    FROM main_payment payments 
                    WHERE LOWER(payments.username) IN (SELECT LOWER(au3.username) FROM ADMIN_USERS au3) 
                    GROUP BY payments.username
                ) ADMIN6
                GROUP BY ADMIN6.username
            )
            SELECT 
                NET_TOTAL_ADMINS.username, 
                ROUND(COALESCE(NET_TOTAL_ADMINS.net_total_INR, 0) - COALESCE(PAYMENTS.completed_payments, 0), 2) as due_amount
            FROM NET_TOTAL_ADMINS
            LEFT JOIN PAYMENTS ON NET_TOTAL_ADMINS.username = PAYMENTS.username;
        """
        
        # Execute query using Django's database connection
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(cursor.fetchall(), columns=columns)
            
        if len(df):
            amount_due = df['due_amount'].tolist()[0]
        else:
            amount_due = 0

        # Update or insert due amount using Django model references
        try:
            user = CDUser.objects.get(email=username)
            due_amount_obj, created = DueAmount.objects.get_or_create(
                user=user,
                defaults={'amount': amount_due}
            )
            if not created:
                due_amount_obj.amount = amount_due
                due_amount_obj.save()
        except CDUser.DoesNotExist:
            pass
            
        return amount_due


class IntermediateProcessor():
    role = 'intermediate'
    navigation = _navigation['intermediate']

    def get_royalty_stats(self, username, left_date, right_date, confirmed_sales_month, filter_type, ratio, yt_ratio):
        intermediate_user_ratio = ratio
        intermediate_user_ytratio = yt_ratio
        list_of_childs = processor.get_users_belongs_to(username)
        if not list_of_childs:
            return {'error': 'No data found'}
        list_of_childs_str = ",".join([f"'{str(v).lower()}'" for v in list_of_childs])
        filter = ''
        if 'confirmed' in filter_type:
            filter += f" and LAST_DAY(confirmed_date) = LAST_DAY('{confirmed_sales_month}')"
        else:
            if left_date != "NONE":
                left_date = left_date.split("/")[1] + "-" + left_date.split("/")[0]
                filter += f" and LAST_DAY(end_date) >= '{left_date}-01'"

            if right_date != "NONE":
                right_date = right_date.split(
                    "/")[1] + "-" + right_date.split("/")[0]
                filter += f" and LAST_DAY(end_date) <= LAST_DAY('{right_date}-01')"
        sys.stderr.write(f"FILTER_STRING: {filter}\n"); sys.stderr.flush()
        sys.stderr.write(f"FILTER_STRING length: {len(filter)}\n"); sys.stderr.flush()

        # Updated to use Django database manager with new table references
        # Top tracks query - EXCLUDE YouTube Official Channel (for backward compat / display)
        top_tracks_query = f""" select LOWER(m.user) as user,m.track,sum(r.units) as units,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where LOWER(m.user) in ({list_of_childs_str}) and r.channel != 'Youtube Official Channel' {filter} group by m.user,m.track;"""
        # Per (user, track, channel) so Net Total matches channel breakdown total (same formula per channel)
        top_tracks_by_channel_query = f""" select LOWER(m.user) as user,m.track,r.channel,sum(r.units) as units,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where LOWER(m.user) in ({list_of_childs_str}) {filter} group by m.user,m.track,r.channel;"""
        # (Intermediate only: use per-channel net so Top Tracks Net Total matches channel breakdown total)
        # YouTube Official Channel query - separate query for YouTube channels
        top_youtube_channels_query = f""" select LOWER(m.user) as user,m.track as channel_name,sum(r.units) as units,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where LOWER(m.user) in ({list_of_childs_str}) and r.channel = 'Youtube Official Channel' {filter} group by m.user,m.track;"""
        top_channels_query = f""" select  LOWER(m.user) as user,r.channel,sum(r.units) as units,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where LOWER(m.user) in ({list_of_childs_str}) and r.channel != 'Youtube Official Channel' {filter}  group by m.user,r.channel;"""
        line_graph_query =  f"""select r.end_date,r.channel,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where LOWER(m.user) in ({list_of_childs_str})   {filter} group by r.end_date,r.channel;"""

        with connection.cursor() as cursor:
            sys.stderr.write(f"ABOUT_TO_EXECUTE: username={username}, filter={filter}\n"); sys.stderr.flush()
            sys.stderr.write(f"top_tracks_query (first 500 chars): {top_tracks_query[:500]}\n"); sys.stderr.flush()
            cursor.execute(top_tracks_query)
            columns = [col[0] for col in cursor.description]
            top_tracks = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_top_tracks: shape={top_tracks.shape}, empty={top_tracks.empty}, row_count={len(top_tracks)}\n"); sys.stderr.flush()
            cursor.execute(top_tracks_by_channel_query)
            columns_tbc = [col[0] for col in cursor.description]
            top_tracks_by_channel = pd.DataFrame(cursor.fetchall(), columns=columns_tbc)
            # Execute YouTube channels query
            cursor.execute(top_youtube_channels_query)
            columns = [col[0] for col in cursor.description]
            top_youtube_channels = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_top_youtube_channels: shape={top_youtube_channels.shape}, empty={top_youtube_channels.empty}, row_count={len(top_youtube_channels)}\n"); sys.stderr.flush()
            
            cursor.execute(top_channels_query)
            columns = [col[0] for col in cursor.description]
            top_channels = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_top_channels: shape={top_channels.shape}, empty={top_channels.empty}, row_count={len(top_channels)}\n"); sys.stderr.flush()
            
            cursor.execute(line_graph_query)
            columns = [col[0] for col in cursor.description]
            line_df = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_line_df: shape={line_df.shape}, empty={line_df.empty}, row_count={len(line_df)}\n"); sys.stderr.flush()

        # Return empty data structures instead of error - UI elements should still be visible
        # Only check if line_df is empty (needed for chart), but allow empty data for tables
        if line_df.empty:
            # Return empty structures but still provide ratio info for UI
            return {
                "lines": {},
                "labels": [],
                "top_channels": {},
                "ratio": int(intermediate_user_ratio),
                "yt_ratio": int(intermediate_user_ytratio),
                "table": """<table class="table table-flush" id="data_table_tracks">
                    <thead class="thead-light">
                    <th>Track Name</th><th>Units Sold</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                    </thead>
                    <tbody>
                        <tr><td colspan="4" style="text-align:center;">No track data found</td></tr>
                    </tbody>
                    </table>
                """,
                "youtube_channels_table": """<table class="table table-flush" id="data_table_youtube_channels">
                    <thead class="thead-light">
                    <th>Channel Name</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                    </thead>
                    <tbody>
                        <tr><td colspan="3" style="text-align:center;">No YouTube Channel data found</td></tr>
                    </tbody>
                    </table>
                """
            }

        
        child_emails = [email.strip("'") for email in list_of_childs_str.split(",")]
        users_with_ratios = CDUser.objects.filter(email__in=child_emails).select_related()
        
        ratios = {}
        yt_ratios = {}
        
        for user in users_with_ratios:
            active_ratio = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
            if active_ratio:
                ratios[user.email.lower()] = active_ratio.stores
                yt_ratios[user.email.lower()] = active_ratio.youtube
            else:
                ratios[user.email.lower()] = 0
                yt_ratios[user.email.lower()] = 0

        # Process top tracks (excluding YouTube)
        if not top_tracks.empty:
            top_tracks['net_total_INR'] = top_tracks['gross_total']
        else:
            top_tracks = pd.DataFrame(columns=['user', 'track', 'units', 'gross_total', 'net_total_INR'])
        
        # Process YouTube channels separately
        if not top_youtube_channels.empty:
            top_youtube_channels['net_total_INR'] = top_youtube_channels.apply(
                lambda x: round(x['gross_total'] * (intermediate_user_ytratio/100 - yt_ratios[f'{x["user"]}']/100), 2), axis=1)
            top_youtube_channels = top_youtube_channels.drop(columns=['user', 'units'])
            top_youtube_channels = (
                top_youtube_channels.groupby(["channel_name"])[
                    ['gross_total', 'net_total_INR']]
                .sum()
                .reset_index()
            )
            top_youtube_channels.columns = ["Channel Name", "Gross Total (INR)","Net Total (INR)"]
            top_youtube_channels["Net Total (INR)"] = top_youtube_channels["Net Total (INR)"].apply(
                lambda x: round(x, 2)
            )
            top_youtube_channels["Gross Total (INR)"] = top_youtube_channels["Gross Total (INR)"].apply(
                lambda x: round(x, 2)
            )
            youtube_channels_body = "".join(
                top_youtube_channels.applymap(lambda x: f"<td>{x}</td>")
                .apply(lambda x: "".join(x), axis=1)
                .apply(lambda x: f"<tr>{x}</tr>")
            )
            youtube_headers = "".join([f"<th>{x}</th>" for x in top_youtube_channels.columns])
            total_gross = top_youtube_channels["Gross Total (INR)"].sum()
            total_net = top_youtube_channels["Net Total (INR)"].sum()
            youtube_total_row = f"<tfoot><tr><td><b>Total</b></td><td><b>{total_gross:,.2f}</b></td><td><b>{total_net:,.2f}</b></td></tr></tfoot>"
            youtube_channels_table = f"""<table class="table table-flush" id="data_table_youtube_channels">
                <thead class="thead-light">
                {youtube_headers}
                </thead>
                <tbody>
                    {youtube_channels_body}
                </tbody>
                {youtube_total_row}
                </table>
            """
        else:
            youtube_channels_table = """<table class="table table-flush" id="data_table_youtube_channels">
                <thead class="thead-light">
                <th>Channel Name</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                </thead>
                <tbody>
                    <tr><td colspan="3" style="text-align:center;">No YouTube Channel data found</td></tr>
                </tbody>
                </table>
            """
        
        if not top_channels.empty:
            top_channels['net_total_INR'] = top_channels['gross_total']
            top_channels['net_total_INR'] = top_channels.apply(
                lambda x: round(x['gross_total'] *
                                (intermediate_user_ratio/100 -
                                ratios[f'{x["user"]}']/100), 2), axis=1)
            top_channels = top_channels.drop(columns=['user'])
            top_channels = (
                top_channels.groupby(["channel"])[
                    ["units", 'gross_total', 'net_total_INR']]
                .sum()
                .reset_index()
            )
        else:
            top_channels = pd.DataFrame(columns=['channel', 'units', 'gross_total', 'net_total_INR'])
        
        line_df['net_total_INR'] = line_df['gross_total']
        line_df = (
            line_df.pivot(index="end_date", columns="channel",
                    values="net_total_INR")
            .sort_index()
            .fillna(0)
        )
        line_df.index = pd.to_datetime(line_df.index)
        line_df = line_df.resample("M").sum()
        lines = {}
        labels = []
        for i,v in enumerate(line_df.index):
            if len(line_df.index) > 1 and i == 0:
                v = v.replace(day=1)
                labels.append(v.date().isoformat())
            else:
                labels.append(v.date().isoformat())

        for ind, val in sorted(enumerate(line_df.columns)):
            line = {}
            line["label"] = val
            line["data"] = list(line_df[val])
            line["lineTension"] = 0.3
            line["fill"] = True
            line['pointBorderColor'] = 'white'
            line['pointRadius'] = 5
            line["borderColor"] = processor.colors[ind]
            lines[val] = line

        # Process top tracks: use per-channel net (same formula as fetch_track_channels) so Net Total matches channel breakdown total.
        # Per-channel rule: if channel == "Youtube Official Channel" use youtube_ratio; else use stores_ratio. Then sum by track.
        if not top_tracks_by_channel.empty:
            def _net_per_channel(x):
                if x['channel'].lower() == 'youtube official channel':
                    return round(x['gross_total'] * (intermediate_user_ytratio/100 - yt_ratios[f'{x["user"]}']/100), 2)
                return round(x['gross_total'] * (intermediate_user_ratio/100 - ratios[f'{x["user"]}']/100), 2)
            top_tracks_by_channel['net_total_INR'] = top_tracks_by_channel.apply(_net_per_channel, axis=1)
            top_tracks = (
                top_tracks_by_channel.groupby(["track"])[["units", "gross_total", "net_total_INR"]]
                .sum()
                .reset_index()
            )
            top_tracks.columns = ["Track Name", "Units Sold", "Gross Total (INR)", "Net Total (INR)"]
            top_tracks["Net Total (INR)"] = top_tracks["Net Total (INR)"].apply(lambda x: round(x, 2))
            top_tracks["Gross Total (INR)"] = top_tracks["Gross Total (INR)"].apply(lambda x: round(x, 2))

            top_tracks_body = "".join(
                top_tracks.applymap(lambda x: f"<td>{x}</td>")
                .apply(lambda x: "".join(x), axis=1)
                .apply(
                    lambda x: "<tr"
                    + f' onClick=break_down_tracks("{x.split("</td>")[0].replace("<td>","").replace(" ", "|_|")}")  style="cursor: pointer;"'
                    + f">{x}</tr>"
                )
            )
            headers = "".join([f"<th>{x}</th>" for x in top_tracks.columns])
            table = f"""<table class="table table-flush" id="data_table_tracks">
                <thead class="thead-light">
                {headers}
                </thead>
                <tbody>
                    {top_tracks_body}
                </tbody>
                </table>
            """
        elif not top_tracks.empty:
            top_tracks['net_total_INR'] = top_tracks.apply(
                lambda x: round(x['gross_total'] * (intermediate_user_ratio/100 - ratios[f'{x["user"]}']/100), 2), axis=1)
            top_tracks = top_tracks.drop(columns=['user'])
            top_tracks = (
                top_tracks.groupby(["track"])[["units", 'gross_total', 'net_total_INR']]
                .sum()
                .reset_index()
            )
            top_tracks.columns = ["Track Name", "Units Sold", "Gross Total (INR)","Net Total (INR)"]
            top_tracks["Net Total (INR)"] = top_tracks["Net Total (INR)"].apply(lambda x: round(x, 2))
            top_tracks["Gross Total (INR)"] = top_tracks["Gross Total (INR)"].apply(lambda x: round(x, 2))
            top_tracks_body = "".join(
                top_tracks.applymap(lambda x: f"<td>{x}</td>")
                .apply(lambda x: "".join(x), axis=1)
                .apply(
                    lambda x: "<tr"
                    + f' onClick=break_down_tracks("{x.split("</td>")[0].replace("<td>","").replace(" ", "|_|")}")  style="cursor: pointer;"'
                    + f">{x}</tr>"
                )
            )
            headers = "".join([f"<th>{x}</th>" for x in top_tracks.columns])
            table = f"""<table class="table table-flush" id="data_table_tracks">
                <thead class="thead-light">
                {headers}
                </thead>
                <tbody>
                    {top_tracks_body}
                </tbody>
                </table>
            """
        else:
            table = """<table class="table table-flush" id="data_table_tracks">
                <thead class="thead-light">
                <th>Track Name</th><th>Units Sold</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                </thead>
                <tbody>
                    <tr><td colspan="4" style="text-align:center;">No track data found</td></tr>
                </tbody>
                </table>
            """

        top_channels = top_channels.set_index(
            "channel").to_json(orient="index")
        top_channels = json.loads(top_channels)

        return {
            "lines": lines,
            "labels": labels,
            "top_channels": top_channels,
            "ratio": int(intermediate_user_ratio),
            "yt_ratio": int(intermediate_user_ytratio),
            "table": table,
            "youtube_channels_table": youtube_channels_table
        }

    def manage_users_display(self, user):
        users_qs = CDUser.objects.filter(role=CDUser.ROLES.NORMAL, parent=user)
        active_ratios = Ratio.objects.filter(
            user=OuterRef("pk"),
            status=Ratio.STATUS.ACTIVE
        )
        users_qs = users_qs.annotate(
            stores=Coalesce(
                Subquery(active_ratios.values("stores")[:1]),
                0,
                output_field=IntegerField()
            ),
            youtube=Coalesce(
                Subquery(active_ratios.values("youtube")[:1]),
                0,
                output_field=IntegerField()
            ),
        )
        users_qs = users_qs.values("email", "role", "stores", "youtube", "parent__email")
        users = pd.DataFrame.from_records(users_qs)
        users = users.rename(columns={
            'email': 'username',
            'stores': 'ratio',
            'youtube': 'yt_ratio',
            'parent__email': 'belongs_to'
        })
        if len(users):
            users["ratio"] = users["ratio"].fillna(
                "").apply(lambda x: f"{x}%" if x else "")
            users["yt_ratio"] = (
                users["yt_ratio"].fillna("").apply(lambda x: f"{x}%" if x else "")
            )
            due_amount_qs = DueAmount.objects.all().values("user__email", "amount")
            due_amount_df = pd.DataFrame.from_records(due_amount_qs)
            due_amount_df = due_amount_df.rename(columns={
                'user__email': 'username',
                'amount': 'amount_due',
            })
            users = pd.merge(users, due_amount_df, on='username', how='left').fillna(0)
            users = users[['username', 'role', 'ratio', 'yt_ratio', 'amount_due', 'belongs_to']]
            users["username"] = users.apply(
                lambda x: f'<a href="/custom_user/{x["username"]}">{x["username"]}</a>',
                axis=1,
                result_type="reduce",
            )
        headers = "<th>Username</th><th>Role</th><th>Ratio</th><th>Youtube Official Channel Ratio</th><th>Due Amount</th><th>Belongs to</th>"

        body = "".join(
            users.applymap(lambda x: f"<td>{x}</td>")
            .apply(lambda x: "".join(x), axis=1)
            .apply(lambda x: f"<tr>{x}</tr>")
        )
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

    def fetch_track_channels(self, username, ratio, yt_ratio, left_date, right_date, track_name, confirmed_sales_month=None, filter_type="basic-filters"):
        track_name = track_name.replace("|_|", " ")
        intermediate_user_ratio = ratio
        intermediate_user_ytratio = yt_ratio
        list_of_childs = processor.get_users_belongs_to(username)
        if not list_of_childs:
            return {'error': 'No data found'}
        list_of_childs_str = ",".join([f"'{str(v).lower()}'" for v in list_of_childs])
        filter = ''
        
        # Handle confirmed sales month filter (same logic as get_royalty_stats)
        if 'confirmed' in filter_type and confirmed_sales_month:
            filter += f" and LAST_DAY(confirmed_date) = LAST_DAY('{confirmed_sales_month}')"
        else:
            if left_date != "NONE":
                left_date = left_date.split("/")[1] + "-" + left_date.split("/")[0]
                filter += f" and LAST_DAY(end_date) >= '{left_date}-01'"

            if right_date != "NONE":
                right_date = right_date.split(
                    "/")[1] + "-" + right_date.split("/")[0]
                filter += f" and LAST_DAY(end_date) <= LAST_DAY('{right_date}-01')"
        sys.stderr.write(f"FILTER_STRING: {filter}\n"); sys.stderr.flush()
        sys.stderr.write(f"FILTER_STRING length: {len(filter)}\n"); sys.stderr.flush()

        track_channels_query =  f""" select LOWER(m.user) as user,r.channel,sum(r.units) as units,sum(r.net_total_INR) as gross_total from releases_royalties r left join releases_metadata m on upper(r.isrc) = upper(m.isrc) where LOWER(m.user) in ({list_of_childs_str}) and m.track = '{track_name}'  {filter} group by m.user,r.channel;"""

        with connection.cursor() as cursor:
            sys.stderr.write(f"ABOUT_TO_EXECUTE: username={username}, filter={filter}\n"); sys.stderr.flush()
            sys.stderr.write(f"top_tracks_query (first 500 chars): {top_tracks_query[:500]}\n"); sys.stderr.flush()
            cursor.execute(track_channels_query)
            columns = [col[0] for col in cursor.description]
            tracks_channels_df = pd.DataFrame(cursor.fetchall(), columns=columns)

        if (tracks_channels_df.empty) :
            return {'error':'No Data Found!'}

       
        child_emails = [email.strip("'") for email in list_of_childs_str.split(",")]
        users_with_ratios = CDUser.objects.filter(email__in=child_emails).select_related()
        
        ratios = {}
        yt_ratios = {}
        
        for user in users_with_ratios:
            active_ratio = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
            if active_ratio:
                ratios[user.email.lower()] = active_ratio.stores
                yt_ratios[user.email.lower()] = active_ratio.youtube
            else:
                ratios[user.email.lower()] = 0
                yt_ratios[user.email.lower()] = 0

        tracks_channels_df['net_total_INR'] = tracks_channels_df.apply(
            lambda x: round(x['gross_total'] *
                            (intermediate_user_ratio/100 -
                            ratios[f'{x["user"]}']/100)
                            if x['channel'].lower() != 'youtube official channel' else x['gross_total']
                            * (intermediate_user_ytratio/100 - yt_ratios[f'{x["user"]}']/100), 2), axis=1)

        tracks_channels_df = tracks_channels_df.drop(columns=['user'])
        tracks_channels_df = (
            tracks_channels_df.groupby(["channel"])[
                ["units", 'gross_total', 'net_total_INR']]
            .sum()
            .reset_index()
        )

        channels = []
        for index, row in tracks_channels_df.iterrows():
            current_channel = {
                'channel': row['channel'],
                'units': row['units'],
                'gross_total': row['gross_total'],
                'net_total_INR': row['net_total_INR']
            }
            channels.append(current_channel)
        tracks_channels = {track_name: channels}

        return {
            "track_channels": tracks_channels
        }

    
    def refresh_due_balance(self,username,ratio,yt_ratio):
        query = f"""
            WITH net_totals AS (
                SELECT 
                    '{username}' as username, 
                    ROUND(SUM(calculated_net_total_INR), 2) as net_total_INR
                FROM (
                    SELECT 
                        t1.user,
                        CASE 
                            WHEN t1.channel_type LIKE 'stores' THEN 
                                t1.net_total_INR * (({ratio}/100) - (rt.stores/100))
                            ELSE 
                                t1.net_total_INR * (({yt_ratio}/100) - (rt.youtube/100))
                        END AS calculated_net_total_INR
                    FROM (
                        SELECT 
                            m.user as user, 
                            CASE 
                                WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                                ELSE 'stores'
                            END AS channel_type,
                            SUM(r.net_total_INR) as net_total_INR
                        FROM 
                            releases_royalties r 
                        JOIN 
                            releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc)
                        WHERE 
                            m.user IN (
                                SELECT u.email 
                                FROM main_cduser u 
                                WHERE u.parent_id = (
                                    SELECT id FROM main_cduser WHERE email = '{username}'
                                )
                            )
                        GROUP BY 
                            m.user, channel_type
                    ) t1
                    JOIN main_cduser u ON t1.user = u.email
                    JOIN main_ratio rt ON u.id = rt.user_id AND rt.status = 'active'
                ) t2
            ),
            net_totals_normal AS (
                SELECT 
                    t2.user as username, 
                    ROUND(SUM(calculated_net_total_INR), 2) as net_total
                FROM (
                    SELECT 
                        t1.user,
                        t1.channel_type,
                        CASE 
                            WHEN t1.channel_type LIKE 'stores' THEN 
                                t1.net_total_INR * (rt.stores/100)
                            ELSE 
                                t1.net_total_INR * (rt.youtube/100)
                        END AS calculated_net_total_INR
                    FROM (
                        SELECT 
                            m.user as user, 
                            CASE 
                                WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                                ELSE 'stores'
                            END AS channel_type,
                            SUM(r.net_total_INR) as net_total_INR
                        FROM 
                            releases_royalties r 
                        JOIN 
                            releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc)
                        WHERE 
                            m.user = '{username}'
                        GROUP BY 
                            m.user, channel_type
                    ) t1
                    JOIN main_cduser u ON t1.user = u.email
                    JOIN main_ratio rt ON u.id = rt.user_id AND rt.status = 'active'
                ) t2
                GROUP BY t2.user
            ),
            aggregated_payments AS (
                SELECT 
                    u.email as username, 
                    SUM(p.amount_paid) as amount_paid, 
                    SUM(p.tds) as tds 
                FROM main_payment p 
                JOIN main_cduser u ON p.username = u.email 
                WHERE u.email = '{username}' 
                GROUP BY u.email
            )
            SELECT 
                net_totals.username,
                CASE 
                    WHEN net_totals.net_total_INR IS NULL THEN 
                        0 + COALESCE(net_totals_normal.net_total, 0) 
                    WHEN amount_paid IS NULL AND tds IS NULL THEN 
                        net_totals.net_total_INR + COALESCE(net_totals_normal.net_total, 0) 
                    ELSE 
                        net_totals.net_total_INR - amount_paid - tds + COALESCE(net_totals_normal.net_total, 0)
                END AS amount_due
            FROM net_totals 
            LEFT JOIN aggregated_payments AS payments ON net_totals.username = payments.username
            LEFT JOIN net_totals_normal ON net_totals_normal.username = net_totals.username;
        """
        
        # Execute query using Django's database connection
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(cursor.fetchall(), columns=columns)
            
        if len(df) > 0:
            amount_due = df['amount_due'].tolist()[0]
        else:
            amount_due = 0

        # Update or insert due amount using Django model references
        try:
            user = CDUser.objects.get(email=username)
            due_amount_obj, created = DueAmount.objects.get_or_create(
                user=user,
                defaults={'amount': amount_due}
            )
            if not created:
                due_amount_obj.amount = amount_due
                due_amount_obj.save()
        except CDUser.DoesNotExist:
            pass
            
        return amount_due


class NormalProcessor():
    role = 'normal'
    navigation =  _navigation['normal']

    def get_royalty_stats(self, username, left_date, right_date, confirmed_sales_month, filter_type, ratio, yt_ratio, split_royalties_enabled):
        sys.stderr.write(f"\n>>> ENTRY: normal.get_royalty_stats called for {username}\n"); sys.stderr.flush()
        sys.stderr.write(f">>> Parameters: left_date={left_date}, right_date={right_date}, filter_type={filter_type}\n"); sys.stderr.flush()
        sys.stderr.write(f"\n>>> ENTRY: normal.get_royalty_stats called for {username}\n"); sys.stderr.flush()
        sys.stderr.write(f">>> Parameters: left_date={left_date}, right_date={right_date}, filter_type={filter_type}\n"); sys.stderr.flush()
        filter = ''
        if 'confirmed' in filter_type:
            print('confirmed_sales_month', confirmed_sales_month)
            confirmed_month_dt = datetime.strptime(confirmed_sales_month.replace(" ", ""), "%B,%Y")
            last_day = calendar.monthrange(confirmed_month_dt.year, confirmed_month_dt.month)[1]
            confirmed_month_sql = confirmed_month_dt.strftime(f"%Y-%m-{last_day}")
            filter += f" and LAST_DAY(confirmed_date) = LAST_DAY('{confirmed_month_sql}')"
        else:
            if left_date != "NONE":
                left_date = left_date.split("/")[1] + "-" + left_date.split("/")[0]
                filter += f" and LAST_DAY(end_date) >= '{left_date}-01'"

            if right_date != "NONE":
                right_date = right_date.split(
                    "/")[1] + "-" + right_date.split("/")[0]
                filter += f" and LAST_DAY(end_date) <= LAST_DAY('{right_date}-01')"
        sys.stderr.write(f"FILTER_STRING: {filter}\n"); sys.stderr.flush()
        sys.stderr.write(f"FILTER_STRING length: {len(filter)}\n"); sys.stderr.flush()

        # Single query to get tracks with split handling - EXCLUDE YouTube Official Channel
        # First CTE: Get totals per track and ISRC
        # Second CTE: For each track name, select the ISRC with highest gross total
        # Final SELECT: Aggregate only the top ISRC per track name
        top_tracks_query = f"""
            WITH owner_tracks AS (
                SELECT 
                    m.track,
                    UPPER(m.isrc) as isrc,
                    sum(r.units) as units,
                    sum(r.net_total_INR) as gross_total,
                    sum(r.net_total_INR * (CASE WHEN r.channel LIKE 'Youtube Official Channel' THEN COALESCE(owner_ratio.youtube, 0) ELSE COALESCE(owner_ratio.stores, 0) END / 100) * COALESCE(sr.recipient_percentage, 100) / 100) as net_total
                FROM 
                    releases_royalties r 
                LEFT JOIN 
                    releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
                LEFT JOIN 
                    releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
                LEFT JOIN 
                    releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                        AND t.release_id = sr.release_id_id 
                        AND LOWER(sr.recipient_email) = '{username}'
                LEFT JOIN 
                    main_cduser owner ON LOWER(owner.email) = LOWER(m.user)
                LEFT JOIN 
                    main_ratio owner_ratio ON owner.id = owner_ratio.user_id AND owner_ratio.status = 'active'
                WHERE 
                    (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}')
                    AND (m.user IS NOT NULL OR sr.recipient_email IS NOT NULL)
                    AND m.track IS NOT NULL
                    AND r.channel != 'Youtube Official Channel'
                    {filter}
                GROUP BY 
                    m.track, UPPER(m.isrc), t.id, t.release_id
            ),
            top_isrc AS (
                SELECT 
                    track,
                    isrc,
                    ROW_NUMBER() OVER (PARTITION BY track ORDER BY gross_total DESC) as rn
                FROM owner_tracks
            )
            SELECT 
                ot.track,
                sum(ot.units) as units,
                sum(ot.gross_total) as gross_total,
                sum(ot.net_total) as net_total
            FROM 
                owner_tracks ot
            INNER JOIN 
                top_isrc ti ON ot.track = ti.track AND ot.isrc = ti.isrc AND ti.rn = 1
            GROUP BY 
                ot.track
        """
        
        # YouTube Official Channel query - separate query for YouTube channels with split handling
        # Split percentage is applied to post-admin remainder (gross * owner_ratio), not gross
        top_youtube_channels_query = f"""
            SELECT 
                m.track as channel_name,
                sum(r.units) as units,
                sum(r.net_total_INR) as gross_total,
                sum(r.net_total_INR * (COALESCE(owner_ratio.youtube, 0) / 100) * COALESCE(sr.recipient_percentage, 100) / 100) as net_total
            FROM 
                releases_royalties r 
            LEFT JOIN 
                releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
            LEFT JOIN 
                releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
            LEFT JOIN 
                releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                    AND t.release_id = sr.release_id_id 
                    AND LOWER(sr.recipient_email) = '{username}'
            LEFT JOIN 
                main_cduser owner ON LOWER(owner.email) = LOWER(m.user)
            LEFT JOIN 
                main_ratio owner_ratio ON owner.id = owner_ratio.user_id AND owner_ratio.status = 'active'
            WHERE 
                (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}')
                AND (m.user IS NOT NULL OR sr.recipient_email IS NOT NULL)
                AND r.channel = 'Youtube Official Channel'
                {filter}
            GROUP BY 
                m.track
        """
        
        # Single query to get channels with split handling - EXCLUDE YouTube Official Channel
        # Split percentage is applied to post-admin remainder (gross * owner_ratio), not gross
        top_channels_query = f"""
            SELECT 
                r.channel,
                sum(r.units) as units,
                sum(r.net_total_INR) as gross_total,
                sum(r.net_total_INR * (CASE WHEN r.channel LIKE 'Youtube Official Channel' THEN COALESCE(owner_ratio.youtube, 0) ELSE COALESCE(owner_ratio.stores, 0) END / 100) * COALESCE(sr.recipient_percentage, 100) / 100) as net_total
            FROM 
                releases_royalties r 
            LEFT JOIN 
                releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
            LEFT JOIN 
                releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
            LEFT JOIN 
                releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                    AND t.release_id = sr.release_id_id 
                    AND LOWER(sr.recipient_email) = '{username}'
            LEFT JOIN 
                main_cduser owner ON LOWER(owner.email) = LOWER(m.user)
            LEFT JOIN 
                main_ratio owner_ratio ON owner.id = owner_ratio.user_id AND owner_ratio.status = 'active'
            WHERE 
                (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}')
                AND (m.user IS NOT NULL OR sr.recipient_email IS NOT NULL)
                AND r.channel != 'Youtube Official Channel'
                {filter}
            GROUP BY 
                r.channel
        """
        
        # Line graph query with split handling
        # Split percentage is applied to post-admin remainder (gross * owner_ratio), not gross
        line_graph_query = f"""
            SELECT 
                r.end_date,
                r.channel,
                sum(r.net_total_INR) as gross_total,
                sum(r.net_total_INR * (CASE WHEN r.channel LIKE 'Youtube Official Channel' THEN COALESCE(owner_ratio.youtube, 0) ELSE COALESCE(owner_ratio.stores, 0) END / 100) * COALESCE(sr.recipient_percentage, 100) / 100) as net_total
            FROM 
                releases_royalties r 
            LEFT JOIN 
                releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
            LEFT JOIN 
                releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
            LEFT JOIN 
                releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                    AND t.release_id = sr.release_id_id 
                    AND LOWER(sr.recipient_email) = '{username}'
            LEFT JOIN 
                main_cduser owner ON LOWER(owner.email) = LOWER(m.user)
            LEFT JOIN 
                main_ratio owner_ratio ON owner.id = owner_ratio.user_id AND owner_ratio.status = 'active'
            WHERE 
                (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}')
                AND (m.user IS NOT NULL OR sr.recipient_email IS NOT NULL)
                {filter}
            GROUP BY 
                r.end_date, r.channel
        """

        with connection.cursor() as cursor:
            sys.stderr.write(f"ABOUT_TO_EXECUTE: username={username}, filter={filter}\n"); sys.stderr.flush()
            sys.stderr.write(f"top_tracks_query (first 500 chars): {top_tracks_query[:500]}\n"); sys.stderr.flush()
            cursor.execute(top_tracks_query)
            columns = [col[0] for col in cursor.description]
            top_tracks = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_top_tracks: shape={top_tracks.shape}, empty={top_tracks.empty}, row_count={len(top_tracks)}\n"); sys.stderr.flush()
            
            # Execute YouTube channels query
            cursor.execute(top_youtube_channels_query)
            columns = [col[0] for col in cursor.description]
            top_youtube_channels = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_top_youtube_channels: shape={top_youtube_channels.shape}, empty={top_youtube_channels.empty}, row_count={len(top_youtube_channels)}\n"); sys.stderr.flush()
            
            cursor.execute(top_channels_query)
            columns = [col[0] for col in cursor.description]
            top_channels = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_top_channels: shape={top_channels.shape}, empty={top_channels.empty}, row_count={len(top_channels)}\n"); sys.stderr.flush()
            
            cursor.execute(line_graph_query)
            columns = [col[0] for col in cursor.description]
            line_df = pd.DataFrame(cursor.fetchall(), columns=columns)
            sys.stderr.write(f"AFTER_line_df: shape={line_df.shape}, empty={line_df.empty}, row_count={len(line_df)}\n"); sys.stderr.flush()

        sys.stderr.write(f"\n=== DEBUG for {username} ===\n"); sys.stderr.flush()
        sys.stderr.write(f"top_channels.empty: {top_channels.empty}, shape: {top_channels.shape}\n"); sys.stderr.flush()
        sys.stderr.write(f"top_tracks.empty: {top_tracks.empty}, shape: {top_tracks.shape}\n"); sys.stderr.flush()
        sys.stderr.write(f"top_youtube_channels.empty: {top_youtube_channels.empty}, shape: {top_youtube_channels.shape}\n"); sys.stderr.flush()
        sys.stderr.write(f"line_df.empty: {line_df.empty}, shape: {line_df.shape}\n"); sys.stderr.flush()
        if not top_channels.empty:
            print(f"top_channels columns: {list(top_channels.columns)}")
            print(f"top_channels sample: {top_channels.head(2).to_dict()}")
        if not top_tracks.empty:
            print(f"top_tracks columns: {list(top_tracks.columns)}")
            print(f"top_tracks sample: {top_tracks.head(2).to_dict()}")
        if not top_youtube_channels.empty:
            print(f"top_youtube_channels columns: {list(top_youtube_channels.columns)}")
            print(f"top_youtube_channels sample: {top_youtube_channels.head(2).to_dict()}")
        if not line_df.empty:
            print(f"line_df columns: {list(line_df.columns)}")
            print(f"line_df sample: {line_df.head(2).to_dict()}")
        print(f"=== END DEBUG ===\n")
        # Return empty data structures instead of error - UI elements should still be visible
        # Only check if line_df is empty (needed for chart), but allow empty data for tables
        if line_df.empty:
            # Return empty structures but still provide ratio info for UI
            return {
                "lines": {},
                "labels": [],
                "top_channels": {},
                "ratio": ratio,
                "yt_ratio": yt_ratio,
                "table": """<table class="table table-flush" id="data_table_tracks">
                    <thead class="thead-light">
                    <th>Track Name</th><th>Units Sold</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                    </thead>
                    <tbody>
                        <tr><td colspan="4" style="text-align:center;">No track data found</td></tr>
                    </tbody>
                    </table>
                """,
                "youtube_channels_table": """<table class="table table-flush" id="data_table_youtube_channels">
                    <thead class="thead-light">
                    <th>Channel Name</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                    </thead>
                    <tbody>
                        <tr><td colspan="3" style="text-align:center;">No YouTube Channel data found</td></tr>
                    </tbody>
                    </table>
                """
            }

        # Process YouTube channels separately
        if not top_youtube_channels.empty:
            # net_total from SQL is already post-admin remainder * split % (owner ratio applied in SQL)
            top_youtube_channels['net_total'] = top_youtube_channels.apply(
                lambda x: round(x['net_total'], 2), axis=1)
            # Drop units column before renaming
            top_youtube_channels = top_youtube_channels.drop(columns=['units'])
            top_youtube_channels.columns = ["Channel Name", "Gross Total (INR)","Net Total (INR)"]
            top_youtube_channels["Net Total (INR)"] = top_youtube_channels["Net Total (INR)"].apply(
                lambda x: round(x, 2)
            )
            top_youtube_channels["Gross Total (INR)"] = top_youtube_channels["Gross Total (INR)"].apply(
                lambda x: round(x, 2)
            )
            youtube_channels_body = "".join(
                top_youtube_channels.applymap(lambda x: f"<td>{x}</td>")
                .apply(lambda x: "".join(x), axis=1)
                .apply(lambda x: f"<tr>{x}</tr>")
            )
            youtube_headers = "".join([f"<th>{x}</th>" for x in top_youtube_channels.columns])
            total_gross = top_youtube_channels["Gross Total (INR)"].sum()
            total_net = top_youtube_channels["Net Total (INR)"].sum()
            youtube_total_row = f"<tfoot><tr><td><b>Total</b></td><td><b>{total_gross:,.2f}</b></td><td><b>{total_net:,.2f}</b></td></tr></tfoot>"
            youtube_channels_table = f"""<table class="table table-flush" id="data_table_youtube_channels">
                <thead class="thead-light">
                {youtube_headers}
                </thead>
                <tbody>
                    {youtube_channels_body}
                </tbody>
                {youtube_total_row}
                </table>
            """
        else:
            youtube_channels_table = """<table class="table table-flush" id="data_table_youtube_channels">
                <thead class="thead-light">
                <th>Channel Name</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                </thead>
                <tbody>
                    <tr><td colspan="3" style="text-align:center;">No YouTube Channel data found</td></tr>
                </tbody>
                </table>
            """

        # net_total from SQL is already post-admin remainder * split % (owner ratio applied in SQL)
        if not top_channels.empty:
            top_channels['net_total_INR'] = top_channels.apply(
                lambda x: round(x['net_total'], 2), 
                axis=1
            )
        else:
            top_channels = pd.DataFrame(columns=['channel', 'units', 'gross_total', 'net_total', 'net_total_INR'])

        # net_total from SQL is already post-admin remainder * split % (owner ratio applied in SQL)
        if not top_tracks.empty:
            top_tracks['net_total'] = top_tracks.apply(
                lambda x: round(x['net_total'], 2), axis=1)
        else:
            top_tracks = pd.DataFrame(columns=['track', 'units', 'gross_total', 'net_total'])

        # Process line graph data
        line_df = (
            line_df.pivot(index="end_date", columns="channel", values="gross_total")
            .sort_index()
            .fillna(0)
        )
        line_df.index = pd.to_datetime(line_df.index)
        line_df = line_df.resample("M").sum()
        
        lines = {}
        labels = []
        for i, v in enumerate(line_df.index):
            if len(line_df.index) > 1 and i == 0:
                v = v.replace(day=1)
                labels.append(v.date().isoformat())
            else:
                labels.append(v.date().isoformat())

        for ind, val in sorted(enumerate(line_df.columns)):
            line = {}
            line["label"] = val
            line["data"] = list(line_df[val])
            line["lineTension"] = 0.3
            line["fill"] = True
            line['pointBorderColor'] = 'white'
            line['pointRadius'] = 5
            line["borderColor"] = processor.colors[ind]
            lines[val] = line

        # Format final output
        if not top_tracks.empty:
            top_tracks.columns = ["Track Name", "Units Sold", "Gross Total (INR)","Net Total (INR)"]
            top_tracks["Net Total (INR)"] = top_tracks["Net Total (INR)"].apply(
                lambda x: round(x, 2)
            )
            top_tracks["Gross Total (INR)"] = top_tracks["Gross Total (INR)"].apply(
                lambda x: round(x, 2)
            )

            top_tracks_body = "".join(
                top_tracks.applymap(lambda x: f"<td>{x}</td>")
                .apply(lambda x: "".join(x), axis=1)
                .apply(
                    lambda x: "<tr"
                    + f' onClick=break_down_tracks("{x.split("</td>")[0].replace("<td>","").replace(" ", "|_|")}")  style="cursor: pointer;"'
                    + f">{x}</tr>"
                )
            )
            headers = "".join([f"<th>{x}</th>" for x in top_tracks.columns])
            table = f"""<table class="table table-flush" id="data_table_tracks">
                <thead class="thead-light">
                {headers}
                </thead>
                <tbody>
                    {top_tracks_body}
                </tbody>
                </table>
            """
        else:
            table = """<table class="table table-flush" id="data_table_tracks">
                <thead class="thead-light">
                <th>Track Name</th><th>Units Sold</th><th>Gross Total (INR)</th><th>Net Total (INR)</th>
                </thead>
                <tbody>
                    <tr><td colspan="4" style="text-align:center;">No track data found</td></tr>
                </tbody>
                </table>
            """

        if not top_channels.empty:
            top_channels = top_channels.set_index(
                "channel").to_json(orient="index")
            top_channels = json.loads(top_channels)
        else:
            top_channels = {}

        return {
            "lines": lines,
            "labels": labels,
            "ratio": ratio,
            "yt_ratio": yt_ratio,
            "top_channels": top_channels,
            "table": table,
            "youtube_channels_table": youtube_channels_table
        }

    def send_royalties_data(self, email, field_category, field, start_date, end_date):
        start_date = start_date.split('-')[1] + '-' + start_date.split('-')[0]
        end_date = end_date.split('-')[1] + '-' + end_date.split('-')[0]
        process = Popen(['python', f'send_royalties_data.py', f"{email}", f"{field_category}", f"{field}", f"{start_date}", f"{end_date}"])
        return

    def refresh_due_balance(self, username, ratio, yt_ratio):
        # Check if user has split_royalties_enabled
        try:
            user_obj = CDUser.objects.get(email=username)
            split_royalties_enabled = user_obj.split_royalties_enabled
        except CDUser.DoesNotExist:
            split_royalties_enabled = False
        
        query = f"""
            WITH royalty_totals AS (
                -- First, get total royalties per ISRC and channel to avoid duplication
                SELECT 
                    UPPER(r.isrc) as isrc,
                    CASE 
                        WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                        ELSE 'stores'
                    END AS channel_type,
                    SUM(r.net_total_INR) as net_total_INR
                FROM 
                    releases_royalties r 
                JOIN 
                    releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc)
                WHERE 
                    LOWER(m.user) = '{username}'
                GROUP BY 
                    UPPER(r.isrc),
                    CASE 
                        WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                        ELSE 'stores'
                    END
            ),
            split_percentages AS (
                -- Get split percentage for each track where user is owner and has split enabled
                SELECT DISTINCT
                    UPPER(t.isrc) as isrc,
                    sr.recipient_percentage
                FROM 
                    releases_track t
                JOIN 
                    releases_metadata m ON UPPER(t.isrc) = UPPER(m.isrc)
                JOIN 
                    main_cduser owner_user ON LOWER(owner_user.email) = '{username}'
                JOIN 
                    releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                        AND t.release_id = sr.release_id_id 
                        AND sr.user_id_id = owner_user.id
                        AND LOWER(sr.recipient_email) = '{username}'
                WHERE 
                    LOWER(m.user) = '{username}'
            ),
            owner_royalties AS (
                -- Apply split percentage if exists, otherwise use 100%
                SELECT 
                    rt.channel_type,
                    SUM(
                        CASE 
                            WHEN sp.recipient_percentage IS NOT NULL THEN 
                                rt.net_total_INR * sp.recipient_percentage / 100
                            ELSE 
                                rt.net_total_INR
                        END
                    ) as net_total_INR
                FROM 
                    royalty_totals rt
                LEFT JOIN 
                    split_percentages sp ON rt.isrc = sp.isrc
                GROUP BY 
                    rt.channel_type
            ),
            recipient_royalty_totals AS (
                -- First, get total royalties per ISRC and channel for recipient tracks (include owner for ratio)
                SELECT 
                    UPPER(r.isrc) as isrc,
                    CASE 
                        WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                        ELSE 'stores'
                    END AS channel_type,
                    LOWER(m.user) as owner_email,
                    SUM(r.net_total_INR) as net_total_INR
                FROM 
                    releases_royalties r 
                JOIN 
                    releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc)
                JOIN 
                    releases_track t ON UPPER(r.isrc) = UPPER(m.isrc) 
                JOIN 
                    releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                        AND t.release_id = sr.release_id_id 
                        AND LOWER(sr.recipient_email) = '{username}'
                WHERE 
                    LOWER(m.user) != '{username}'  -- User is recipient, not owner
                GROUP BY 
                    UPPER(r.isrc),
                    CASE 
                        WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                        ELSE 'stores'
                    END,
                    LOWER(m.user)
            ),
            owner_ratios_for_recipient AS (
                SELECT 
                    LOWER(u.email) as owner_email,
                    COALESCE(r.stores, 0) as stores_ratio,
                    COALESCE(r.youtube, 0) as youtube_ratio
                FROM main_cduser u
                LEFT JOIN main_ratio r ON u.id = r.user_id AND r.status = 'active'
            ),
            recipient_split_percentages AS (
                -- Get split percentage for recipient tracks
                SELECT DISTINCT
                    UPPER(t.isrc) as isrc,
                    sr.recipient_percentage
                FROM 
                    releases_track t
                JOIN 
                    releases_metadata m ON UPPER(t.isrc) = UPPER(m.isrc)
                JOIN 
                    releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                        AND t.release_id = sr.release_id_id 
                        AND LOWER(sr.recipient_email) = '{username}'
                WHERE 
                    LOWER(m.user) != '{username}'
            ),
            recipient_royalties AS (
                -- Apply split percentage to post-admin remainder (gross * owner_ratio), not gross
                SELECT 
                    rrt.channel_type,
                    SUM(rrt.net_total_INR * (CASE WHEN rrt.channel_type = 'youtube' THEN COALESCE(orr.youtube_ratio, 0) ELSE COALESCE(orr.stores_ratio, 0) END / 100) * rsp.recipient_percentage / 100) as net_total_INR
                FROM 
                    recipient_royalty_totals rrt
                JOIN 
                    recipient_split_percentages rsp ON rrt.isrc = rsp.isrc
                LEFT JOIN 
                    owner_ratios_for_recipient orr ON rrt.owner_email = orr.owner_email
                GROUP BY 
                    rrt.channel_type
            ),
            net_totals AS (
                -- Apply ratio only to owner royalties (post-admin); recipient_royalties is already final share
                SELECT 
                    '{username}' as username,
                    ROUND(
                        COALESCE((SELECT SUM(CASE WHEN channel_type = 'stores' THEN net_total_INR * ({ratio}/100) ELSE net_total_INR * ({yt_ratio}/100) END) FROM owner_royalties), 0)
                        + COALESCE((SELECT SUM(net_total_INR) FROM recipient_royalties), 0)
                    , 2) as net_total
                FROM (SELECT 1) _one
            ),
            aggregated_payments AS (
                -- Get total payments made to this user
                SELECT 
                    username, 
                    SUM(amount_paid) as amount_paid, 
                    SUM(tds) as tds 
                FROM main_payment 
                WHERE username = '{username}' 
                GROUP BY username
            )
            SELECT 
                net_totals.username, 
                CASE 
                    WHEN amount_paid IS NULL AND tds IS NULL THEN COALESCE(net_total, 0)
                    ELSE ROUND(COALESCE(net_total, 0) - COALESCE(amount_paid, 0) - COALESCE(tds, 0), 2)
                END AS amount_due
            FROM net_totals
            LEFT JOIN aggregated_payments AS payments ON net_totals.username = payments.username
        """
        
        # Execute query using Django's database connection
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(cursor.fetchall(), columns=columns)
            
        if len(df) > 0:
            amount_due = df['amount_due'].tolist()[0]
        else:
            amount_due = 0

        # Update or insert due amount using Django model references
        try:
            user = CDUser.objects.get(email=username)
            due_amount_obj, created = DueAmount.objects.get_or_create(
                user=user,
                defaults={'amount': amount_due}
            )
            if not created:
                due_amount_obj.amount = amount_due
                due_amount_obj.save()
        except CDUser.DoesNotExist:
            pass
            
        return amount_due
    
    def refresh_due_balance_for_split_recipient(self, username):
        """
        Calculate and update due balance for split_recipient users.
        Split recipients only get royalties from tracks where they are recipients.
        They use the owner's ratio, not their own.
        """
        query = f"""
            WITH recipient_royalty_totals AS (
                -- Get total royalties per ISRC and channel for tracks where user is a recipient
                SELECT 
                    UPPER(r.isrc) as isrc,
                    CASE 
                        WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                        ELSE 'stores'
                    END AS channel_type,
                    SUM(r.net_total_INR) as net_total_INR
                FROM 
                    releases_royalties r 
                JOIN 
                    releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc)
                JOIN 
                    releases_track t ON UPPER(r.isrc) = UPPER(m.isrc) 
                JOIN 
                    releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                        AND t.release_id = sr.release_id_id 
                        AND LOWER(sr.recipient_email) = '{username}'
                WHERE 
                    LOWER(m.user) != '{username}'  -- User is recipient, not owner
                GROUP BY 
                    UPPER(r.isrc),
                    CASE 
                        WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' 
                        ELSE 'stores'
                    END
            ),
            recipient_split_percentages AS (
                -- Get split percentage and owner info for recipient tracks
                SELECT DISTINCT
                    UPPER(t.isrc) as isrc,
                    sr.recipient_percentage,
                    LOWER(m.user) as owner_email
                FROM 
                    releases_track t
                JOIN 
                    releases_metadata m ON UPPER(t.isrc) = UPPER(m.isrc)
                JOIN 
                    releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                        AND t.release_id = sr.release_id_id 
                        AND LOWER(sr.recipient_email) = '{username}'
                WHERE 
                    LOWER(m.user) != '{username}'
            ),
            owner_ratios AS (
                -- Get active ratios for all owners
                SELECT DISTINCT
                    LOWER(u.email) as owner_email,
                    COALESCE(r.stores, 0) as stores_ratio,
                    COALESCE(r.youtube, 0) as youtube_ratio
                FROM 
                    main_cduser u
                LEFT JOIN 
                    main_ratio r ON u.id = r.user_id AND r.status = 'active'
            ),
            recipient_royalties_with_ratios AS (
                -- Split % applied to post-admin remainder (gross * owner_ratio), not gross
                SELECT 
                    rrt.channel_type,
                    rrt.net_total_INR * (CASE WHEN rrt.channel_type = 'youtube' THEN COALESCE(orr.youtube_ratio, 0) ELSE COALESCE(orr.stores_ratio, 0) END / 100) * rsp.recipient_percentage / 100 as split_amount
                FROM 
                    recipient_royalty_totals rrt
                JOIN 
                    recipient_split_percentages rsp ON rrt.isrc = rsp.isrc
                LEFT JOIN 
                    owner_ratios orr ON rsp.owner_email = orr.owner_email
            ),
            net_totals AS (
                -- Sum final split amounts (already: remainder * recipient_percentage)
                SELECT 
                    '{username}' as username,
                    ROUND(COALESCE(SUM(split_amount), 0), 2) as net_total
                FROM recipient_royalties_with_ratios
            ),
            aggregated_payments AS (
                -- Get total payments made to this user
                SELECT 
                    username, 
                    SUM(amount_paid) as amount_paid, 
                    SUM(tds) as tds 
                FROM main_payment 
                WHERE username = '{username}' 
                GROUP BY username
            )
            SELECT 
                net_totals.username, 
                CASE 
                    WHEN amount_paid IS NULL AND tds IS NULL THEN COALESCE(net_total, 0)
                    ELSE ROUND(COALESCE(net_total, 0) - COALESCE(amount_paid, 0) - COALESCE(tds, 0), 2)
                END AS amount_due
            FROM net_totals
            LEFT JOIN aggregated_payments AS payments ON net_totals.username = payments.username
        """
        
        # Execute query using Django's database connection
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(cursor.fetchall(), columns=columns)
            
        if len(df) > 0:
            amount_due = df['amount_due'].tolist()[0]
        else:
            amount_due = 0

        # Update or insert due amount using Django model references
        try:
            user = CDUser.objects.get(email=username)
            due_amount_obj, created = DueAmount.objects.get_or_create(
                user=user,
                defaults={'amount': amount_due}
            )
            if not created:
                due_amount_obj.amount = amount_due
                due_amount_obj.save()
        except CDUser.DoesNotExist:
            pass
            
        return amount_due
    
    def fetch_track_channels(self, username, ratio, yt_ratio, left_date, right_date, track_name, confirmed_sales_month=None, filter_type="basic-filters"):
        track_name = track_name.replace("|_|", " ")
        filter = ''
        
        # Handle confirmed sales month filter (same logic as get_royalty_stats)
        if 'confirmed' in filter_type and confirmed_sales_month:
            import calendar
            from datetime import datetime
            confirmed_month_dt = datetime.strptime(confirmed_sales_month.replace(" ", ""), "%B,%Y")
            last_day = calendar.monthrange(confirmed_month_dt.year, confirmed_month_dt.month)[1]
            confirmed_month_sql = confirmed_month_dt.strftime(f"%Y-%m-{last_day}")
            filter += f" and LAST_DAY(confirmed_date) = LAST_DAY('{confirmed_month_sql}')"
        else:
            if left_date != "NONE":
                left_date = left_date.split("/")[1] + "-" + left_date.split("/")[0]
                filter += f" and LAST_DAY(end_date) >= '{left_date}-01'"

            if right_date != "NONE":
                right_date = right_date.split(
                    "/")[1] + "-" + right_date.split("/")[0]
                filter += f" and LAST_DAY(end_date) <= LAST_DAY('{right_date}-01')"
        sys.stderr.write(f"FILTER_STRING: {filter}\n"); sys.stderr.flush()
        sys.stderr.write(f"FILTER_STRING length: {len(filter)}\n"); sys.stderr.flush()

        # Single query to get track channels with split handling
        # First, find the ISRC with highest gross total for this track name
        # Then, show breakdown only for that ISRC
        track_channels_query = f"""
            WITH owner_tracks AS (
                SELECT 
                    m.track,
                    UPPER(m.isrc) as isrc,
                    sum(r.net_total_INR) as gross_total
                FROM 
                    releases_royalties r 
                LEFT JOIN 
                    releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
                LEFT JOIN 
                    releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
                LEFT JOIN 
                    releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                        AND t.release_id = sr.release_id_id 
                        AND LOWER(sr.recipient_email) = '{username}'
                WHERE 
                    (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}')
                    AND m.track = '{track_name}'
                    AND m.track IS NOT NULL
                    {filter}
                GROUP BY 
                    m.track, UPPER(m.isrc), t.id, t.release_id
            ),
            top_isrc AS (
                SELECT 
                    isrc
                FROM owner_tracks
                ORDER BY gross_total DESC
                LIMIT 1
            )
            SELECT 
                r.channel,
                sum(r.units) as units,
                sum(r.net_total_INR) as gross_total,
                sum(r.net_total_INR * (CASE WHEN r.channel LIKE 'Youtube Official Channel' THEN COALESCE(owner_ratio.youtube, 0) ELSE COALESCE(owner_ratio.stores, 0) END / 100) * COALESCE(sr.recipient_percentage, 100) / 100) as net_total
            FROM 
                releases_royalties r 
            LEFT JOIN 
                releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
            LEFT JOIN 
                releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
            LEFT JOIN 
                releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                    AND t.release_id = sr.release_id_id 
                    AND LOWER(sr.recipient_email) = '{username}'
            LEFT JOIN 
                main_cduser owner ON LOWER(owner.email) = LOWER(m.user)
            LEFT JOIN 
                main_ratio owner_ratio ON owner.id = owner_ratio.user_id AND owner_ratio.status = 'active'
            INNER JOIN 
                top_isrc ti ON UPPER(m.isrc) = ti.isrc
            WHERE 
                (LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}') 
                AND m.track = '{track_name}' {filter}
            GROUP BY 
                r.channel
        """
        print(track_channels_query)

        with connection.cursor() as cursor:
            sys.stderr.write(f"ABOUT_TO_EXECUTE: username={username}, filter={filter}\n"); sys.stderr.flush()
            sys.stderr.write(f"track_channels_query (first 500 chars): {track_channels_query[:500]}\n"); sys.stderr.flush()
            cursor.execute(track_channels_query)
            columns = [col[0] for col in cursor.description]
            tracks_channels_df = pd.DataFrame(cursor.fetchall(), columns=columns)

        if tracks_channels_df.empty:
            return {'error': 'No Data Found!'}

        # net_total from SQL is already post-admin remainder * split % (owner ratio applied in SQL)
        tracks_channels_df['net_total'] = tracks_channels_df.apply(
            lambda x: round(x['net_total'], 2), axis=1
        )

        channels = []
        for index, row in tracks_channels_df.iterrows():
            current_channel = {
                'channel': row['channel'],
                'units': row['units'],
                'gross_total': row['gross_total'],
                'net_total_INR': row['net_total']
            }
            channels.append(current_channel)
        tracks_channels = {track_name: channels}

        return {
            "track_channels": tracks_channels
        }

processor = Processor()
admin = AdminProcessor()
intermediate = IntermediateProcessor()
normal = NormalProcessor()