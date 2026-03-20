import pandas as pd
from constants import *
from main.processor import processor
from releases.processor import processor
import re
import uuid
from datetime import datetime
from commons.sql_client import sql_client
from releases.models import UniqueCode, Release, Track, Metadata
class DataValidator:
    def __init__(self, data, validations, type) -> None:
        self.data = data
        self.validations = validations
        self.type = type
        self.checkpoints = [
            self.checkpoint_one,
            self.checkpoint_two,
            self.checkpoint_three,
        ]
        self.category = {
            "release": self.release_processor,
            "royalties": self.royalties_processor,
            "royalties_meta": self.royalties_meta_processor,
            "payments": self.payments_processor,
            "codes": self.codes_processor
        }

    def validate(self):
        # Triggers all checkpoints for all validations
        status, response = True, "Ok"
        for validation in self.validations:
            for checkpoint in self.checkpoints:
                status, response = checkpoint(validation)
                if not status:
                    return status, response
        return status, response

    # Checkpoints
    def checkpoint_one(self, validation):
        # Checks required columns in the dataframe
        result = [
            column
            for column in validation["required_columns"]
            if column in self.data.columns
        ]
        if result == validation["required_columns"]:
            return True, ""
        else:
            missing_columns = ", ".join(
                [
                    column
                    for column in validation["required_columns"]
                    if column not in self.data.columns
                ]
            )
            return (
                False,
                f"Following columns are missing in the file!\n{missing_columns}",
            )

    def checkpoint_two(self, validation):
        # Checks not null fields in the dataframe
        # for field in validation["not_null_fields"]:
        #     if self.data[field].isnull().any():
        #         return (
        #             False,
        #             f"You have empty cells in {field}. This field can not have empty data.",
        #         )
        return True, ""

    def checkpoint_three(self, validation):
        # Checks fields format defined in validation
        for field, pattern in validation["field_formats"].items():
            if not self.data[field].astype(str).str.match(pattern).all():
                return (
                    False,
                    f"Not all records match the desired format for column {field}. Please correct the format for this field.",
                )
        return True, ""

    # Processors
    def process(self, file_type=None):
        if file_type:
            self.type = file_type
        return self.category[self.type]()

    def codes_processor(self):
        upc_from_codes = list(UniqueCode.objects.filter(type=UniqueCode.TYPE.UPC).values_list('code', flat=True).distinct())
        isrc_from_codes = list(UniqueCode.objects.filter(type=UniqueCode.TYPE.ISRC).values_list('code', flat=True).distinct())
        upc_from_releases = list(Release.objects.all().values_list('upc', flat=True).distinct())
        isrc_from_releases = list(Track.objects.all().values_list('isrc', flat=True).distinct())

        upcs = upc_from_codes + upc_from_releases
        isrcs = isrc_from_codes + isrc_from_releases

        new_upcs = self.data[self.data['type'] == 'upc']['code'].tolist()
        new_isrcs = self.data[self.data['type'] == 'isrc']['code'].tolist()

        # CAPS
        upcs = [str(upc).upper() for upc in upcs]
        isrcs = [str(isrc).upper() for isrc in isrcs]
        new_upc = [str(upc).upper() for upc in new_upcs]
        new_isrc = [str(isrc).upper() for isrc in new_isrcs]

        conflicting_upcs = [str(upc) for upc in new_upc if str(upc) in upcs]
        conflicting_isrcs = [str(isrc) for isrc in new_isrc if str(isrc) in isrcs]

        if conflicting_upcs:
            message = f"There are some UPC's in the file which are already present in the database. Please remove them first. Conflicting UPC's are as follows.\n{conflicting_upcs}"
            return False, message
        
        if conflicting_isrcs:
            message = f"There are some ISRC's in the file which are already present in the database. Please remove them first. Conflicting ISRC's are as follows.\n{conflicting_isrcs}"
            return False, message

        return True, ""
        
    def release_processor(self):
        # db = processor.get_sql_connection()  # Not needed with ORM but kept for reference
        # ================= ORIGINAL RAW SQL (FOR REFERENCE) ===================
        # query = """ SELECT distinct upc_code from rl_release; """
        # release_upc_list = sql_client.read_sql(query)["upc_code"].tolist()
        # query = """ SELECT distinct code from assignable_code where type like 'upc'; """
        # upc_codes_list = sql_client.read_sql(query)["code"].tolist()
        # =====================================================================

        # ORM-based implementation
        release_upc_list = list(
            Release.objects.values_list("upc", flat=True).distinct()
        )
        upc_codes_list = list(
            UniqueCode.objects.filter(type=UniqueCode.TYPE.UPC)
            .values_list("code", flat=True)
            .distinct()
        )

        upc_list = set(upc_codes_list + release_upc_list)
        file_upc_list = set(self.data["release_upc_code"].tolist())

        repeating_upcs = upc_list.intersection(file_upc_list)
        if repeating_upcs:
            repeating_upcs = [str(upc) for upc in repeating_upcs]
            repeating_upcs = ", ".join(list(repeating_upcs))
            return (
                False,
                f"Uploaded file has UPCs, that are already present in the database. Please use new ones. Repeating UPCs are as follows.\n{repeating_upcs}",
                0,
            )

        # Check 2: ISRC are new. There are no matching ISRC's in database
        # ================= ORIGINAL RAW SQL (FOR REFERENCE) ===================
        # query = """ SELECT distinct upper(isrc_code) as isrc_code from rl_tracks; """
        # tracks_isrc_list = sql_client.read_sql(query)["isrc_code"].tolist()
        # query = (
        #     """ SELECT distinct upper(code) as code from assignable_code where type like 'isrc'; """
        # )
        # isrc_codes_list = sql_client.read_sql(query)["code"].tolist()
        # =====================================================================

        # ORM-based implementation
        tracks_isrc_list = [
            str(code).upper()
            for code in Track.objects.values_list("isrc", flat=True).distinct()
        ]
        isrc_codes_list = [
            str(code).upper()
            for code in UniqueCode.objects.filter(type=UniqueCode.TYPE.ISRC)
            .values_list("code", flat=True)
            .distinct()
        ]

        isrc_list = set(isrc_codes_list + tracks_isrc_list)
        file_isrc_list = set(self.data["track_isrc_code"].tolist())
        file_isrc_list = set([str(isrc).upper() for isrc in file_isrc_list])

        repeating_isrcs = isrc_list.intersection(file_isrc_list)
        if repeating_isrcs:
            repeating_isrcs = [str(isrc) for isrc in repeating_isrcs]
            repeating_isrcs = ", ".join(list(repeating_isrcs))
            return (
                False,
                f"Uploaded file has ISRCs, that are already present in the database. Please use new ones. Repeating ISRCs are as follows.\n{repeating_isrcs}",
                0,
            )

        # Update format for release and tracks artists
        release_artists = []
        track_artists = []
        for index, row in self.data.iterrows():
            release_artists.append(self.extract_artists_dict(row["release_artists"]))
            track_artists.append(self.extract_artists_dict(row["track_artists"]))
        self.data["release_artists"] = release_artists
        self.data["track_artists"] = track_artists

        # Column data cleaning
        for column in ["release_title", "release_label", "track_title"]:
            self.data[column] = self.data[column].apply(
                lambda x: str(x).replace("`", "").replace("'", "").replace('"', "")
            )
        
        # Set Date format
        for column in ['licenses_digital_release_date', 'licenses_original_release_date']:
            self.data[column] = self.data[column].dt.strftime('%m/%d/%Y')

        # Divide data into separate dataframes and keep unique records for releases and licenses
        release_validation = self._get_validation("release")
        track_validation = self._get_validation("track")
        license_validation = self._get_validation("license")

        rest_df = self.data[
            release_validation["required_columns"]
            + license_validation["required_columns"]
        ]
        rest_df = rest_df.drop_duplicates(subset=['release_upc_code'])

        # Assign UUIDs
        primary_uuids = []
        for _ in range(len(rest_df)):
            primary_uuids.append(uuid.uuid4())
        rest_df['primary_uuid'] = primary_uuids
        rest_df['release_fk'] = primary_uuids
        rest_df["is_published"] = [True] * len(rest_df)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rest_df["published_at_time"] = [current_time] * len(rest_df)

        release_df = rest_df[release_validation["required_columns"] + ["primary_uuid", "is_published"]]
        license_df = rest_df[license_validation["required_columns"] + ["release_fk"]]
        track_df = self.data[track_validation["required_columns"] + ['release_upc_code']]

        # Apply file to database column names mapping
        release_df.rename(columns=release_validation["db_mapping"], inplace=True)
        track_df.rename(columns=track_validation["db_mapping"], inplace=True)
        license_df.rename(columns=license_validation["db_mapping"], inplace=True)

        # Assign release_fk to tracks
        release_fks = []
        tracks_uuids = []
        for index, row in track_df.iterrows():
            release_fks.append(release_df.loc[release_df['upc_code'] == row['release_upc_code'], 'primary_uuid'].values[0])
            tracks_uuids.append(uuid.uuid4())
        track_df['release_fk'] = release_fks
        track_df['primary_track_uuid'] = tracks_uuids

        return True, "", [release_df, license_df, track_df]

    def royalties_processor(self):
        validation = self._get_validation(self.type)
        df = self.data[validation['required_columns']]
        df['type'] = df.apply(lambda x: royalties_type_mappings.get( str(x.channel).upper().strip() ,'others') ,axis=1)
        df["net_total_INR"] = df.apply(
            lambda x: x.net_total * x.currency_rate, axis=1
        )
        # add confirmed date column
        df['confirmed_date'] = (pd.Timestamp.now() + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')
        return df

    def royalties_meta_processor(self):
        validation = self._get_validation(self.type)
        df = self.data[validation["required_columns"]]

        df = df.rename(columns={"label": "label_name"})
        df = df.drop_duplicates(subset="isrc")
        # ================= ORIGINAL RAW SQL (FOR REFERENCE) ===================
        # old_isrc = sql_client.read_sql("SELECT upper(isrc) as isrc from metadata;")["isrc"].tolist()
        # =====================================================================

        # ORM-based implementation
        old_isrc = [
            str(isrc).upper() for isrc in Metadata.objects.values_list("isrc", flat=True)
        ]
        df["isrc"] = df.apply(lambda x: str(x.isrc).upper(), axis=1)
        df = df[~df["isrc"].isin(old_isrc)]
        df[["label_name", "release", "track"]] = df[
            ["label_name", "release", "track"]
        ].applymap(lambda x: str(x).encode("utf8"))

        return df

    def payments_processor(self):
        validation = self._get_validation(self.type)
        df = self.data[validation['required_columns']]
        return df
        

    # Utils
    def _get_validation(self, type):
        for validation in self.validations:
            if validation["name"] == type:
                return validation

    def extract_artists_dict(self, artists):
        result = {}
        matches = re.findall(r"([A-Za-z0-9\s]+)\s+\(([^)]+)\)", artists)
        for name, role in matches:
            name = name.strip()
            if role not in result:
                result[role] = [name]
            else:
                result[role].append(name)
        response = {key: [",".join(value)] for key, value in result.items()}
        return str(response)


class FileHandler:
    read_method = {"csv": pd.read_csv, "excel": pd.read_excel}

    def __init__(self, file, file_type, file_extension) -> None:
        self.file_type = file_type
        self.file_extension = file_extension
        self.data = self.read_method[file_extension](file.read())

    def display(self):
        print(self.data.head())
