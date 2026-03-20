import json, csv, os
import tempfile
import uuid
from cache import cache
from django.core.mail import EmailMessage
from collections import defaultdict
from constants import *
from datetime import datetime
from django.conf import settings
from django.utils import timezone
import boto3
from commons.sql_client import sql_client
from releases.models import RelatedArtists, Release, Track
from main.models import CDUser
import pandas as pd


# ================= ORIGINAL FUNCTION (FOR REFERENCE) ===================
# def fetch_artist_from_id(id):
#     df = sql_client.read_sql(f"select artist from rl_artists where id={int(id)};")
#     if len(df):
#         return df["artist"].tolist()[0]
#     return None
# ===================================================================

def _format_audio_uploaded_at_ist(track_instance):
    """Return audio upload datetime formatted in IST (e.g. '2026-02-24 17:36:45 IST'), or ''."""
    try:
        dt = getattr(track_instance, "audio_uploaded_at", None)
    except Exception:
        return ""
    if not dt:
        return ""
    try:
        from zoneinfo import ZoneInfo
        ist = ZoneInfo("Asia/Kolkata")
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.utc)
        return dt.astimezone(ist).strftime("%Y-%m-%d %H:%M:%S IST")
    except ImportError:
        try:
            import pytz
            ist = pytz.timezone("Asia/Kolkata")
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.utc)
            return dt.astimezone(ist).strftime("%Y-%m-%d %H:%M:%S IST")
        except Exception:
            return str(dt)
    except Exception:
        return str(dt)


# New ORM-based implementation
def fetch_artist_from_id(id):
    try:
        from releases.models import Artist
        artist = Artist.objects.get(id=int(id))
        return artist.name
    except Artist.DoesNotExist:
        return None


class ProcessorMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Processor(metaclass=ProcessorMeta):
    # Attributes
    ROLES = ["normal", "intermediate", "admin"]

    # Helper Methods
    def get_s3_client(self):
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        return s3_client

    def get_media_files_bucket(self):
        return settings.AWS_STORAGE_BUCKET_NAME

    def move_object_s3(self, src_bkt, src_key, target_bkt, target_key):
        s3client = self.get_s3_client()
        s3client.copy_object(
            CopySource={"Bucket": src_bkt, "Key": src_key},
            Bucket=target_bkt,
            Key=target_key,
        )
        s3client.delete_object(Bucket=src_bkt, Key=src_key)

    # ================= ORIGINAL METHOD (FOR REFERENCE) ===================
    # def get_user_info(self, username):
    #     record = cache.hit(username)
    #     if record:
    #         return record[0], record[1], record[2]
    #     else:
    #         df = sql_client.read_sql(
    #             f"SELECT role, ratio, yt_ratio FROM user_login WHERE username like '{username}'"
    #         )
    #         role = df["role"].tolist()[0].lower()
    #         ratio = df["ratio"].tolist()[0]
    #         yt_ratio = df["yt_ratio"].tolist()[0]
    #         cache.store(username, (role, ratio, yt_ratio))
    #         return role, ratio, yt_ratio
    # ===================================================================

    # New ORM-based implementation
    def get_user_info(self, username):
        record = cache.hit(username)
        if record:
            return record[0], record[1], record[2]
        else:
            try:
                user = CDUser.objects.get(email=username)
                from main.models import Ratio
                
                # Get active ratios for the user
                ratio_obj = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
                ratio = ratio_obj.stores if ratio_obj else 0
                yt_ratio = ratio_obj.youtube if ratio_obj else 0
                
                role = user.role.lower()
                cache.store(username, (role, ratio, yt_ratio))
                return role, ratio, yt_ratio
            except CDUser.DoesNotExist:
                return None, 0, 0

    def send_email(self, release_name, published_by, email_to, attachment_files):
        attachments = []
        attachments_body = ""
        for index, file in enumerate(attachment_files):
            if file is not None:
                if file[0] == "LINK":
                    attachments_body += f"""{file[1]}\n"""
                if file[0] == "FILE":
                    attachments.append(file[1])
        body = f"""
                    Release Title: {release_name}\n
                    Published by: {published_by}\n
                    Attachments and Links: \n
                    {attachments_body}
                """
        email = EmailMessage(
            f"Release: {release_name} Published", body, settings.EMAIL_FROM, [email_to]
        )
        for attachment in attachments:
            email.attach_file(attachment)
        email.send()
        return

    def send_takedown_emails(self, upc, requester):
        body = (
            f"Requester: {requester}\nUPC: {upc}\n\n"
            "Takedown has been sent to all stores: Audiomack, Gaana, TikTok, and Apple Music (Merlin Bridge)."
        )
        email = EmailMessage(
            f"Takedown Request", body, settings.EMAIL_FROM, [settings.SUPPORT_EMAIL]
        )
        email.send()
        return

    def send_whitelist_emails(self, data, user):
        body = f"User: {user}\nSubmitted Data: \n{data}\n"
        email = EmailMessage(
            f"Whitelist and Claims Releasing",
            body,
            settings.EMAIL_FROM,
            [settings.SUPPORT_EMAIL, settings.DEPLOYMENT_EMAIL],
        )
        email.send()
        return

    # ================= ORIGINAL METHOD (FOR REFERENCE) ===================
    # def get_user_role(self, username):
    #     record = cache.hit(username)
    #     if record:
    #         return record[0].lower()
    #     else:
    #         df = sql_client.read_sql(
    #             f"SELECT role, ratio, yt_ratio FROM user_login WHERE username like '{username}'"
    #         )
    #         if len(df):
    #             role = df["role"].tolist()[0]
    #             ratio = df["ratio"].tolist()[0]
    #             yt_ratio = df["yt_ratio"].tolist()[0]
    #             cache.store(username, (role, ratio, yt_ratio))
    #             return role.lower()
    #         else:
    #             df = sql_client.read_sql(
    #                 f"SELECT * FROM teams WHERE member_username like '{username}';"
    #             )
    #             if len(df):
    #                 cache.store(username, ("member", 0, 0))
    #                 return "member"
    # ===================================================================

    # New ORM-based implementation
    def get_user_role(self, username):
        record = cache.hit(username)
        if record:
            return record[0].lower()
        else:
            try:
                user = CDUser.objects.get(email=username)
                if user.role == CDUser.ROLES.MEMBER:
                    cache.store(username, ("member", 0, 0))
                    return CDUser.ROLES.MEMBER.lower()

                from main.models import Ratio
                
                # Get active ratios for the user
                ratio_obj = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
                ratio = ratio_obj.stores if ratio_obj else 0
                yt_ratio = ratio_obj.youtube if ratio_obj else 0
                
                role = user.role.lower()
                cache.store(username, (role, ratio, yt_ratio))
                return role.lower()
            except CDUser.DoesNotExist:
                print(f"User {username} not found")
                return None

    # ================= ORIGINAL METHOD (FOR REFERENCE) ===================
    # def get_users_belongs_to(self, username):
    #     query = (
    #         f"""SELECT username FROM user_login where belongs_to like '{username}' """
    #     )
    #     df = sql_client.read_sql(query)
    #     if not df.empty:
    #         return df["username"].tolist()
    #     return list()
    # ===================================================================

    # New ORM-based implementation  
    def get_users_belongs_to(self, username):
        try:
            parent_user = CDUser.objects.get(email=username)
            child_users = CDUser.objects.filter(parent=parent_user).values_list('email', flat=True)
            return list(child_users)
        except CDUser.DoesNotExist:
            return list()

    def clean_dictionary(self, dictionary):
        """
        This method cleans the dictionary of None Values, and replaces them with Empty String ('')
        """
        for k, v in dictionary.items():
            if v == None or v == "None":
                dictionary[k] = ""
        return dictionary

    def format_artists_in_string(self, json_string):
        json_obj = json.loads(json_string)
        artists = []
        for k, v in json_obj.items():
            for value in v:
                artists.append(f"{value} ({k})")
        return ", ".join(artists)

    def unformat_artists_in_json(self, string):
        try:
            artists_dict = defaultdict(list)
            strings = string.strip().replace(")", "|").split("|")
            for st in strings[0 : len(strings) - 1]:
                sts = st.split("(")
                a_name = sts[0].strip()
                a_type = sts[1].strip()
                artists_dict[a_type].append(a_name)
        except:
            return {}, True
        return (
            artists_dict,
            False,
        )  # 2nd return varibale is used to see if there occured any issue while parsing

    def convert_artists_into_email_format(self, related_artists):
        artists = []
        for related_artist in related_artists:
            # Use .get() with default to handle missing role mappings gracefully
            role_mapping = roaylties_to_distribute_artists_mapping.get(
                related_artist.role, 
                related_artist.role.lower().replace(" ", "_")  # Fallback: convert role to lowercase with underscores
            )
            artists.append(
                f"{role_mapping}:{related_artist.artist.name}"
            )
        return ";".join(artists)

    def get_release_name(self, primary_uuid):
        try:
            release = Release.objects.get(id=primary_uuid)
            return [release.title, release.published]
        except:
            return ""

    def context_generator(self, instance, table_name):
        data = {}
        if not instance:
            return data
        if table_name == "rl_release":
            related_artists = RelatedArtists.objects.filter(release=instance)
            artists = {}
            for related_artist in related_artists:
                if related_artist.role in artists.keys():
                    artists[related_artist.role].append(
                        f"{related_artist.artist.name}|_|{related_artist.artist.pk}"
                    )
                else:
                    artists[related_artist.role] = [
                        f"{related_artist.artist.name}|_|{related_artist.artist.pk}"
                    ]
            if len(artists.keys()):
                artists = json.dumps(artists)
            else:
                artists = "{}"
            # artists = df['artist'].tolist()[0]
            # artists_updated = {}
            # if artists:
            #     artists = json.loads(artists)
            #     for role in artists.keys():
            #         underlying_artists = artists[role]
            #         underlying_artists_names = []
            #         for u_artist in underlying_artists:
            #             underlying_artists_names.append(str(fetch_artist_from_id(u_artist)) + "|_|" + str(u_artist))
            #         artists_updated[role] = underlying_artists_names
            #     artists = json.dumps(artists_updated)
            # else:
            #     artists = "{}"
            from releases.upc_utils import normalize_upc_to_13
            upc_display = (normalize_upc_to_13(instance.upc) or instance.upc or "").strip()
            data = {
                "remix_version": instance.remix_version,
                "labels": instance.label.label if instance.label else None,
                "primary_genere": instance.primary_genre,
                "secondary_genere": instance.secondary_genre,
                "language": instance.language,
                "album_format": instance.album_format,
                "upc_code": upc_display,
                "reference_number": instance.reference_number,
                "gr_id": instance.grid,
                "release_description": instance.description,
                "created_by": instance.created_by.email,
                "artists_listings": artists,
                "cover_art_path": instance.cover_art_url,
            }

        if table_name == "rl_licenses":
            data = {
                "price_category": instance.price_category,
                "digital_release_date": instance.digital_release_date,
                "original_release_date": instance.original_release_date,
                "license_type_format_toggle": instance.license_type,
                "license_holder_year": instance.license_holder_year,
                "license_holder_name": instance.license_holder_name,
                "copyright_recording_year": instance.copyright_recording_year,
                "copyright_recording_name": instance.copyright_recording_text,
                "territories": instance.territories,
            }

        if table_name == "rl_tracks":
            related_artists = RelatedArtists.objects.filter(
                track=instance, relation_key="track"
            )
            artists = {}
            for related_artist in related_artists:
                if related_artist.role in artists.keys():
                    artists[related_artist.role].append(
                        f"{related_artist.artist.name}|_|{related_artist.artist.pk}"
                    )
                else:
                    artists[related_artist.role] = [
                        f"{related_artist.artist.name}|_|{related_artist.artist.pk}"
                    ]
            if len(artists.keys()):
                artists = json.dumps(artists)
            else:
                artists = "{}"
            try:
                audio_wav_url = getattr(instance, "audio_wav_url", "") or ""
                audio_mp3_url = getattr(instance, "audio_mp3_url", "") or ""
                audio_flac_url = getattr(instance, "audio_flac_url", "") or ""
                audio_uploaded_at_ist = _format_audio_uploaded_at_ist(instance)
            except Exception:
                audio_wav_url = audio_mp3_url = audio_flac_url = ""
                audio_uploaded_at_ist = ""
            data = {
                "upc_code": instance.release.upc,
                "remix_version_track": instance.remix_version,
                "created_by_track": instance.created_by.email,
                "title_track": instance.title,
                "primary_genere_track": instance.primary_genre,
                "secondary_genere_track": instance.secondary_genre,
                "isrc_code_track": instance.isrc,
                "iswc_code_track": instance.iswc,
                "publishing_rights_year": instance.publishing_rights_year,
                "publishing_rights_name": instance.publishing_rights_owner,
                "lyrics_track": instance.lyrics,
                "explicit_lyrics_track": instance.explicit_lyrics,
                "language_track": instance.language,
                "available_seperatly_check_track": (
                    "on" if instance.available_separately else "off"
                ),
                "start_point_time_track": instance.start_point,
                "notes_track": instance.notes,
                "artists_listings_track": artists,
                "audio_path": instance.audio_track_url,
                "audio_wav_url": audio_wav_url,
                "audio_mp3_url": audio_mp3_url,
                "audio_flac_url": audio_flac_url,
                "audio_uploaded_at_ist": audio_uploaded_at_ist,
                "apple_music_dolby_atmos_url": getattr(
                    instance, "apple_music_dolby_atmos_url", ""
                )
                or "",
                "apple_music_dolby_atmos_isrc": getattr(
                    instance, "apple_music_dolby_atmos_isrc", ""
                )
                or "",
            }
            _atmos_u = (data.get("apple_music_dolby_atmos_url") or "").strip()
            _atmos_i = (data.get("apple_music_dolby_atmos_isrc") or "").strip()
            data["dolby_atmos_setup_percent"] = (
                (50 if _atmos_u else 0) + (50 if len(_atmos_i) >= 12 else 0)
            )

        return self.clean_dictionary(data)

    def get_pd_context(self, release):
        from releases.upc_utils import normalize_upc_to_13
        upc_display = (normalize_upc_to_13(release.upc) or release.upc or "").strip()
        data = {
            "cover_art_path": release.cover_art_url,
            "title": release.title,
            "label": release.label.label if release.label else "",
            "primary_genre": release.primary_genre,
            "reference_number": release.reference_number,
            "upc_code": upc_display,
            "takedown_requested": release.takedown_requested,
            "release_date": release.original_release_date,
            "rights_owner": release.copyright_recording_text,
            "publishing_owner": release.license_holder_name,
        }

        tracks = Track.objects.filter(release=release)
        # query = f"SELECT upper(isrc_code) as isrc_code, title,	artist , explicit_lyrics,start_point FROM rl_tracks where release_fk='{primary_uuid}';"
        # df = sql_client.read_sql(query)
        if len(tracks):
            headers = "<th>ISRC</th> <th>Track title</th> <th>Track artists</th> <th>Parental Advisory</th> <th>Time</th>"
            body = ""
            for _track in tracks:
                related_artists = RelatedArtists.objects.filter(track=_track)
                artists = []
                for related_artist in related_artists:
                    artists.append(f"{related_artist.role}: {related_artist.artist.name}")

                artists_str = ""
                for val in artists:
                    artists_str += f"{val}<br>"

                body += f'<tr style="cursor:pointer">'
                body += f"<td>{_track.isrc}</td>"
                body += f"<td>{_track.title}</td>"
                body += f"<td>{artists_str}</td>"
                body += f"<td>{_track.explicit_lyrics}</td>"
                body += f"<td>{_track.start_point}</td>"
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

            data = {
                **data,
                "tracks_table": table,
            }

        return self.clean_dictionary(data)

    def clean_dates(self, date: str):
        try:
            parts = date.split("/")
            return f"{parts[2]}-{parts[0]}-{parts[1]}"
        except:
            return ""

    def _date_to_yyyy_mm_dd(self, value):
        """Format date/datetime as yyyy-mm-dd for CSV export. Returns '' if None or invalid."""
        if value is None:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, str) and value.strip():
            if "/" in value:
                return self.clean_dates(value)
            if len(value) >= 10 and value[4] == "-" and value[7] == "-":
                return value[:10]
        return str(value)[:10] if value else ""

    def generate_release_metadata_csv(self, primary_uuids):
        releases = Release.objects.filter(pk__in=primary_uuids)
        data = []
        for release in releases:
            release_participants = RelatedArtists.objects.filter(
                relation_key="release", release=release
            )
            tracks = Track.objects.filter(release=release).order_by("created_at")
            for index, track in enumerate(tracks):
                track_participants = RelatedArtists.objects.filter(
                    relation_key="track", track=track
                )
                data.append(
                    {
                        "#action": "",
                        "#upc": release.upc or "",
                        "#catalog_number": release.upc or "",  # same as #upc per Sonosuite template
                        "#grid": release.grid or "",
                        "#title": release.title or "",
                        "#remix_or_version": release.remix_version or "",
                        "#user_email": (getattr(release.created_by, "email", None) or getattr(settings, "DEPLOYMENT_EMAIL", "") or ""),
                        "#label": release.label.label if release.label else "",
                        "#participants": release_participants,
                        "#primary_genre": release.primary_genre or "",
                        "#secondary_genre": release.secondary_genre or "",
                        "#language": release.language or "",
                    "#explicit_lyrics": (
                            "not_explicit"
                            if "not" in track.explicit_lyrics.lower() # Changed to use .lower() for case-insensitive check
                            else "explicit"
                        ),
                        "#price_category": release.price_category or "",
                        "#digital_release": self._date_to_yyyy_mm_dd(release.digital_release_date),
                        "#original_release": self._date_to_yyyy_mm_dd(release.original_release_date),
                        "#license_type": (
                            "(c)"
                            if release.license_type == release.LICENSE_TYPE.COPYRIGHT.label # Changed to compare with label
                            else "(cc)"
                        ),
                        "#license_info": "",
                        "#c_year": release.copyright_recording_year,
                        "#c_line": release.copyright_recording_text,
                        "#p_year": release.license_holder_year,
                        "#p_line": release.license_holder_name,
                        "#territories": "",
                        "#cover_url": release.cover_art_url,
                        "#track_count": len(tracks),
                        "#isrc": track.isrc,
                        "#iswc": track.iswc,
                        "#track_title": track.title,
                        "#track_remix_or_version": track.remix_version,
                        "#track_participants": track_participants,
                        "#track_primary_genre": track.primary_genre,
                        "#track_secondary_genre": track.secondary_genre,
                        "#track_language": track.language,
                        "#track_explicit_lyrics": (
                        "not_explicit"
                            if "not" in track.explicit_lyrics.lower()
                            else "explicit"
                        ),
                        "#track_p_year": track.publishing_rights_year,
                        "#track_p_line": track.publishing_rights_owner,
                        "#audio_url": track.audio_track_url,
                    }
                )
        df = pd.DataFrame.from_dict(data=data)
        df["#participants"] = df["#participants"].apply(
            lambda x: (
                processor.convert_artists_into_email_format(x)
                if x is not None
                else None
            )
        )
        df["#track_participants"] = df["#track_participants"].apply(
            lambda x: (
                processor.convert_artists_into_email_format(x)
                if x is not None
                else None
            )
        )
        df["#language"] = df["#language"].apply(
            lambda x: (
                royalties_to_distribute_language_mapping.get(x.capitalize(), "")
                if x is not None
                else None
            )
        )
        df["#track_language"] = df["#track_language"].apply(
            lambda x: (
                royalties_to_distribute_language_mapping.get(x.capitalize(), "")
                if x is not None
                else None
            )
        )
        # Sonosuite expects track section columns without #track_ prefix
        df_export = df.rename(columns={
            "#track_remix_or_version": "#remix_or_version_t",
            "#track_participants": "#participants_t",
            "#track_primary_genre": "#primary_genre_t",
            "#track_secondary_genre": "#secondary_genre_t",
            "#track_language": "#language_t",
            "#track_explicit_lyrics": "#explicit_lyrics_t",
            "#track_p_year": "#p_year_t",
            "#track_p_line": "#p_line_t",
        })
        # Column order matching Sonosuite template (correct file.csv)
        sonosuite_columns = [
            "#action", "#upc", "#catalog_number", "#grid", "#title", "#remix_or_version",
            "#user_email", "#label", "#participants", "#primary_genre", "#secondary_genre",
            "#language", "#explicit_lyrics", "#price_category", "#digital_release",
            "#original_release", "#license_type", "#license_info", "#c_year", "#c_line",
            "#p_year", "#p_line", "#territories", "#cover_url", "#track_count", "#isrc",
            "#iswc", "#track_title", "#remix_or_version_t", "#participants_t",
            "#primary_genre_t", "#secondary_genre_t", "#language_t", "#explicit_lyrics_t",
            "#p_year_t", "#p_line_t", "#audio_url"
        ]
        header_row = [
            "#action", "#upc", "#catalog_number", "#grid", "#title", "#remix_or_version",
            "#user_email", "#label", "#participants", "#primary_genre", "#secondary_genre",
            "#language", "#explicit_lyrics", "#price_category", "#digital_release",
            "#original_release", "#license_type", "#license_info", "#c_year", "#c_line",
            "#p_year", "#p_line", "#territories", "#cover_url", "#track_count", "#isrc",
            "#iswc", "#track_title", "#remix_or_version", "#participants", "#primary_genre",
            "#secondary_genre", "#language", "#explicit_lyrics", "#p_year", "#p_line",
            "#audio_url"
        ]
        tmpdir = tempfile.gettempdir()
        uid = uuid.uuid4().hex[:12]
        new_csv_file = os.path.join(tmpdir, "release_metadata_%s.csv" % uid)
        pad = [""] * 34  # Pad metadata rows to match Sonosuite format
        with open(new_csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["#metadata"] + pad)
            writer.writerow(["description", datetime.now().strftime("%Y-%m-%d") + "-UPLOAD-1"] + pad)
            writer.writerow(["format_version", "4"] + pad)
            writer.writerow(["total_releases", str(len(set(df["#upc"].tolist())))] + pad)
            writer.writerow(["total_tracks", str(len(set(df["#isrc"].tolist())))] + pad)
            writer.writerow(["#release_info"] + [""] * 24 + ["#track_info"] + [""] * 9)
            writer.writerow(header_row)
            for _, row in df_export.iterrows():
                data_row = []
                for col in sonosuite_columns:
                    val = row.get(col, "")
                    if val is None or (isinstance(val, float) and pd.isna(val)):
                        val = ""
                    data_row.append(str(val).strip() if val else "")
                writer.writerow(data_row)
        return new_csv_file, df

    def update_metadata_csv_in_s3(self, primary_uuid, upc):
        s3_client = self.get_s3_client()
        data_file_path, df = self.generate_release_metadata_csv([primary_uuid])
        s3_client.upload_file(
            data_file_path, settings.AWS_STORAGE_BUCKET_NAME, f"{upc}/{upc}.csv"
        )
        os.remove(data_file_path)
        return


processor = Processor()
