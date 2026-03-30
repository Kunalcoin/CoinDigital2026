# ========== CELL 1: Mount Google Drive (run this first, then authorize) ==========
from google.colab import drive

drive.mount("/content/drive")

# ========== CELL 2: Main script (channel → aggregate → calculation + zip) ==========
"""
Royalties Colab pipeline (matches legacy behavior):
  Excel → DB enrichment → per-channel date files → groupby (isrc, currency_rate)
  → merge DB fields → single calculation_df → domain split → calculation/data.csv + zip

Improvements: pymysql, safe month-end date, Excel date coercion, NA fill, robust paths.
"""
import calendar
import os
import shutil
import subprocess
import sys
import warnings
import zipfile
from datetime import date

try:
    import pymysql  # noqa: F401 — SQLAlchemy mysql+pymysql needs this
except ModuleNotFoundError:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", "pymysql"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text


def current_month_end_iso():
    """Last calendar day of the current month as YYYY-MM-DD."""
    today = date.today()
    last = calendar.monthrange(today.year, today.month)[1]
    return f"{today.year:04d}-{today.month:02d}-{last:02d}"


MISSING_PLACEHOLDER = "NA"


def fill_empty_cells_with_na(frame: pd.DataFrame) -> pd.DataFrame:
    """NaN/NaT, None, and blank strings → MISSING_PLACEHOLDER for CSV export."""
    out = frame.copy()
    out = out.fillna(MISSING_PLACEHOLDER)
    for col in out.columns:
        if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
            out[col] = [
                MISSING_PLACEHOLDER
                if v is None or (isinstance(v, str) and v.strip() == "")
                else v
                for v in out[col].tolist()
            ]
    return out


def _series_to_datetime_us_mmddyyyy(series: pd.Series) -> pd.Series:
    """
    Parse dates as US-style month-first (MM/DD/YYYY), never day-first.
    Also accepts ISO YYYY-MM-DD from intermediate CSV. Excel datetimes pass through.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        out = pd.to_datetime(series, errors="coerce")
        try:
            if out.dt.tz is not None:
                out = out.dt.tz_convert("UTC").dt.tz_localize(None)
        except (TypeError, AttributeError):
            pass
        return out
    str_s = series.astype(str).str.strip()
    str_s = str_s.replace({"nan": pd.NA, "NaT": pd.NA, "None": pd.NA})
    out = pd.to_datetime(str_s, format="%Y-%m-%d", errors="coerce")
    miss = out.isna()
    if miss.any():
        out = out.fillna(
            pd.to_datetime(str_s.loc[miss], format="%m/%d/%Y", errors="coerce")
        )
    miss = out.isna()
    if miss.any():
        out = out.fillna(
            pd.to_datetime(str_s.loc[miss], format="%m/%d/%y", errors="coerce")
        )
    miss = out.isna()
    if miss.any():
        out = out.fillna(pd.to_datetime(str_s.loc[miss], dayfirst=False, errors="coerce"))
    miss = out.isna()
    if miss.any():
        out = out.fillna(pd.to_datetime(series.loc[miss], errors="coerce"))
    return out


def normalize_statement_dates_to_calendar_month(df: pd.DataFrame) -> pd.DataFrame:
    """
    Each row's period is a full calendar month: start_date → 1st, end_date → last day.

    Prefer end_date to infer the month when both columns exist: Excel often stores
    month-first display (e.g. 02/01/2026) as Timestamp 2026-01-02, while end_date
    still arrives as MM/DD text (e.g. 02/28/2026) and correctly identifies February.
    """
    out = df.copy()
    if "start_date" not in out.columns:
        return out
    ts_start = _series_to_datetime_us_mmddyyyy(out["start_date"])
    if "end_date" in out.columns:
        ts_end = _series_to_datetime_us_mmddyyyy(out["end_date"])
        period_source = ts_end.where(ts_end.notna(), ts_start)
    else:
        period_source = ts_start
    bad = period_source.isna().sum()
    if bad:
        print(
            f"Warning: {bad} row(s) have unparseable statement dates after MM/DD/YYYY rules."
        )
    period = period_source.dt.to_period("M")
    m = period_source.notna()
    # datetime.date in object columns — avoids pandas upcasting to Timestamp (Excel "12:00:00 AM")
    st = period[m].dt.start_time.dt.normalize()
    en = period[m].dt.end_time.dt.normalize()
    out["start_date"] = out["start_date"].astype(object)
    out["end_date"] = out["end_date"].astype(object)
    out.loc[m, "start_date"] = np.asarray(st.dt.date)
    out.loc[m, "end_date"] = np.asarray(en.dt.date)
    return out


def read_csv_royalties_normalize(path: str) -> pd.DataFrame:
    """Read channel/calc CSV and re-apply US date parse + month bounds."""
    d = pd.read_csv(path)
    return normalize_statement_dates_to_calendar_month(d)


warnings.filterwarnings("ignore")
df = None
calculation_df = None
file_paths = []

drive_path = "/content/drive/My Drive/Royalties"

DATABASES = [
    {
        "SITE_ID": "cd",
        "SITE": "Coin Digital",
        "CONNECTION_STRING": "mysql+pymysql://admincoin:coinDigital12345@54.147.21.20:3306/db4",
        "CONNECTION": None,
    }
]


def get_artists_information():
    query = "SELECT id, name AS artist_name FROM releases_artist"
    cd_conn = DATABASES[0]["CONNECTION"]
    df_artists = pd.read_sql(query, cd_conn)
    return df_artists.set_index("id")["artist_name"].to_dict()


all_artist_info = {}


def create_directory(name):
    if not os.path.exists(name):
        os.makedirs(name)


def get_no_pay_attributes():
    query = """
      SELECT
        rt.isrc                AS isrc,
        u.email                AS user,
        l.label                AS label,
        (SELECT GROUP_CONCAT(a.name SEPARATOR ',')
           FROM releases_relatedartists ra
           JOIN releases_artist a ON ra.artist_id = a.id
          WHERE ra.track_id = rt.id
            AND ra.relation_key = 'track'
            AND ra.role = 'Primary Artist'
        )                      AS display_artist,
        rr.title               AS `release`,
        rr.upc                 AS upc,
        rt.title               AS track
      FROM releases_release rr
      JOIN releases_track rt ON rr.id = rt.release_id
      JOIN main_cduser u ON rt.created_by_id = u.id
      LEFT JOIN releases_label l ON rr.label_id = l.id
      WHERE rt.isrc LIKE 'INC01'
      ORDER BY rt.id
      LIMIT 1;
    """
    cd_conn = DATABASES[0]["CONNECTION"]
    df_np = pd.read_sql(text(query), cd_conn)
    return (
        df_np["isrc"].tolist()[0],
        df_np["user"].tolist()[0],
        df_np["label"].tolist()[0],
        df_np["display_artist"].tolist()[0],
        df_np["release"].tolist()[0],
        df_np["upc"].tolist()[0],
        df_np["track"].tolist()[0],
    )


def input_file_health_check():
    global df
    df = pd.read_excel(f"{drive_path}/data.xlsx", engine="openpyxl")

    required_fields = [
        "start_date",
        "end_date",
        "country",
        "currency",
        "type",
        "units",
        "gross_total",
        "currency_rate",
        "isrc",
        "channel",
    ]
    missing_columns = set(required_fields).difference(df.columns)

    if missing_columns:
        print("Missing columns in the File:")
        for column in missing_columns:
            print(column)
        return False

    print("All required columns are present in the File.")

    # MM/DD/YYYY (US) + calendar month: day 1 .. last day (fixes Feb vs Jan swap)
    df = normalize_statement_dates_to_calendar_month(df)

    df["isrc"].fillna("INC01", inplace=True)
    return True


def prepare_db_data():
    global df, DATABASES, all_artist_info
    for database in DATABASES:
        database["CONNECTION"] = create_engine(database["CONNECTION_STRING"]).connect()

    all_artist_info = get_artists_information()

    unique_isrcs = df["isrc"].unique()
    unique_isrcs_clean = [
        str(s).replace("'", "").replace('"', "").lower().strip()
        for s in unique_isrcs
        if str(s).strip() and str(s).lower() != "nan"
    ]
    if not unique_isrcs_clean:
        print("Error: No valid ISRCs found in the input file.")
        return

    unique_isrcs_formatted_string = "('" + "', '".join(unique_isrcs_clean) + "')"

    query_cd = text(f"""
      SELECT
        TRIM(LOWER(rt.isrc))   AS isrc,
        u.email                AS user,
        l.label                AS label,
        (SELECT GROUP_CONCAT(a.name SEPARATOR ',')
          FROM releases_relatedartists ra
          JOIN releases_artist a ON ra.artist_id = a.id
          WHERE ra.track_id = rt.id
            AND ra.relation_key = 'track'
            AND ra.role = 'Primary Artist'
        )                      AS display_artist,
        rr.title               AS `release`,
        rr.upc                 AS upc,
        rt.title               AS track
      FROM releases_release rr
      JOIN releases_track rt ON rr.id = rt.release_id
      JOIN main_cduser u ON rt.created_by_id = u.id
      LEFT JOIN releases_label l ON rr.label_id = l.id
      WHERE TRIM(LOWER(rt.isrc)) IN {unique_isrcs_formatted_string};
    """)

    DATABASES[0]["data"] = pd.read_sql(query_cd, con=DATABASES[0]["CONNECTION"])
    return


def divide_into_channel_dfs():
    """Write per-channel, per-date-range CSVs under drive_path/channels/."""
    global file_paths
    file_paths = []
    channels = df["channel"].unique()
    channel_dfs = [df[df["channel"] == value].copy() for value in channels]

    create_directory(f"{drive_path}/channels")
    for idx, channel in enumerate(channels):
        create_directory(f"{drive_path}/channels/{channel}")
        current_channel_df = channel_dfs[idx]

        unique_date_combinations = current_channel_df[["start_date", "end_date"]].drop_duplicates()
        for _, row in unique_date_combinations.iterrows():
            start_date = row["start_date"]
            end_date = row["end_date"]

            date_df = current_channel_df[
                (current_channel_df["start_date"] == start_date)
                & (current_channel_df["end_date"] == end_date)
            ]
            safe_ch = str(channel).replace("/", "-")
            file_path = (
                f"{drive_path}/channels/{safe_ch}/"
                f"{start_date.strftime('%d_%m_%y')}_{end_date.strftime('%d_%m_%y')}.csv"
            )
            date_df.to_csv(file_path, index=False, date_format="%Y-%m-%d")
            file_paths.append(file_path)


def create_calculation_data():
    """Aggregate by (isrc, currency_rate) per channel/date file (legacy behavior)."""
    agg_dict = {
        "start_date": "first",
        "end_date": "first",
        "country": "first",
        "type": "first",
        "currency": "first",
        "units": "sum",
        "gross_total": "sum",
        "channel": "first",
    }
    for file_path in file_paths:
        storage_path = os.path.dirname(file_path)
        distinction = os.path.basename(file_path)
        current_df = read_csv_royalties_normalize(file_path)
        current_df_aggregated = current_df.groupby(["isrc", "currency_rate"], as_index=False).agg(agg_dict)
        current_df_aggregated.to_csv(
            os.path.join(storage_path, f"aggregated_{distinction}"),
            index=False,
            date_format="%Y-%m-%d",
        )


def add_remaining_fields():
    """Per aggregated file: computed columns, DB merge, no-pay fallback."""
    merged_df = DATABASES[0]["data"]
    np_isrc, np_user, np_label, np_artist, np_release, np_upc, np_track = get_no_pay_attributes()

    for file_path in file_paths:
        storage_path = os.path.dirname(file_path)
        distinction = os.path.basename(file_path)
        agg_path = os.path.join(storage_path, f"aggregated_{distinction}")
        current_df = read_csv_royalties_normalize(agg_path)

        zero_list = [0] * len(current_df)
        current_df["channel_costs"] = zero_list
        current_df["taxes"] = zero_list
        current_df["other_costs_client_currency"] = zero_list
        current_df["channel_costs_client_currency"] = zero_list
        current_df["taxes_client_currency"] = zero_list

        current_df["unit_price"] = current_df.apply(
            lambda x: x.gross_total / x.units if x.units != 0 else 0,
            axis=1,
        )
        current_df["net_total"] = current_df.apply(
            lambda x: x.gross_total - x.channel_costs - x.taxes,
            axis=1,
        )
        current_df["gross_total_client_currency"] = current_df.apply(
            lambda x: x.net_total * x.currency_rate,
            axis=1,
        )
        current_df["net_total_client_currency"] = current_df.apply(
            lambda x: x.gross_total_client_currency
            - x.other_costs_client_currency
            - x.channel_costs_client_currency
            - x.taxes_client_currency,
            axis=1,
        )
        current_df["net_total_INR"] = current_df.apply(
            lambda x: x.net_total * x.currency_rate,
            axis=1,
        )
        current_df["confirmed_date"] = current_month_end_iso()
        current_df["isrc"] = current_df["isrc"].apply(lambda x: str(x).lower())

        current_df = pd.merge(current_df, merged_df, on="isrc", how="left")

        df_data_not_found = current_df[
            (current_df["upc"].isnull())
            & (current_df["track"].isnull())
            & (current_df["release"].isnull())
            & (current_df["label"].isnull())
        ]
        df_data_found = current_df[~current_df["isrc"].isin(df_data_not_found["isrc"])]

        df_data_not_found = df_data_not_found.copy()
        df_data_not_found["upc"] = np_upc
        df_data_not_found["user"] = np_user
        df_data_not_found["label"] = np_label
        df_data_not_found["display_artist"] = np_artist
        df_data_not_found["release"] = np_release
        df_data_not_found["track"] = np_track

        current_df = pd.concat([df_data_found, df_data_not_found], ignore_index=True)
        out_path = os.path.join(storage_path, f"db_data_added_{distinction}")
        current_df.to_csv(out_path, index=False, date_format="%Y-%m-%d")


def create_single_data_file():
    global calculation_df
    dataframes = []
    for file_path in file_paths:
        storage_path = os.path.dirname(file_path)
        distinction = os.path.basename(file_path)
        read_path = os.path.join(storage_path, f"db_data_added_{distinction}")
        dataframes.append(read_csv_royalties_normalize(read_path))
    calculation_df = pd.concat(dataframes, ignore_index=True)


def divide_domain_based_data():
    """Split catalog vs unmatched ISRCs; write calculation CSV + zip."""
    create_directory(f"{drive_path}/domain_division/cd/calculation")

    FETCH_QUERY_ISRC_CD = "SELECT DISTINCT TRIM(isrc) AS isrc FROM releases_track;"
    database = DATABASES[0]
    isrcs = pd.read_sql(text(FETCH_QUERY_ISRC_CD), con=database["CONNECTION"])
    database["ISRC"] = [str(isrc).strip().lower() for isrc in isrcs["isrc"].tolist()]

    calculation_df["LOWERCASE_ISRC"] = calculation_df["isrc"].apply(lambda x: str(x).strip().lower())
    database["DATA"] = calculation_df[calculation_df["LOWERCASE_ISRC"].isin(database["ISRC"])].copy()
    unmatched_data = calculation_df[~calculation_df["LOWERCASE_ISRC"].isin(database["ISRC"])].copy()
    unmatched_data.drop(["LOWERCASE_ISRC"], axis=1, inplace=True)
    database["DATA"].drop(["LOWERCASE_ISRC"], axis=1, inplace=True)
    database["DATA"] = pd.concat([database["DATA"], unmatched_data], ignore_index=True)

    columns = [
        "start_date",
        "end_date",
        "country",
        "currency",
        "type",
        "units",
        "unit_price",
        "gross_total",
        "channel_costs",
        "taxes",
        "net_total",
        "currency_rate",
        "gross_total_client_currency",
        "other_costs_client_currency",
        "channel_costs_client_currency",
        "taxes_client_currency",
        "net_total_client_currency",
        "user",
        "channel",
        "label",
        "display_artist",
        "release",
        "upc",
        "track",
        "isrc",
    ]
    database["DATA"] = database["DATA"][columns]
    database["DATA"] = fill_empty_cells_with_na(database["DATA"])

    calc_dir = f"{drive_path}/domain_division/{database['SITE_ID']}/calculation"
    csv_path = os.path.join(calc_dir, "data.csv")
    database["DATA"].to_csv(csv_path, index=False)

    zip_path = os.path.join(calc_dir, "data.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(csv_path, arcname="data.csv")

    return csv_path, zip_path


def cleanup():
    folder_path = f"{drive_path}/channels/"
    try:
        shutil.rmtree(folder_path)
    except Exception as e:
        print(e)


def main():
    health_check = input_file_health_check()
    if not health_check:
        print("Please resolve above mentioned issues in input file!")
        return
    prepare_db_data()
    divide_into_channel_dfs()
    create_calculation_data()
    add_remaining_fields()
    create_single_data_file()
    csv_path, zip_path = divide_domain_based_data()
    cleanup()
    print("Royalties calculation data generated!")
    print(f"CSV:  {csv_path}")
    print(f"Zip:  {zip_path}")


if __name__ == "__main__":
    main()
