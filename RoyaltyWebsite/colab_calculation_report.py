"""
Colab Royalties Calculation Report - Coin Digital only
Flow:
1. Separate report channel-wise
2. For each channel: aggregate by ISRC (sum units, gross_total, INR totals) - unique ISRC per channel
3. Combine all channels into one calculation file
"""
import calendar
from datetime import date

import pandas as pd
from sqlalchemy import create_engine, text
import os
import warnings


def current_month_end_iso():
    """Last calendar day of the current month as YYYY-MM-DD."""
    today = date.today()
    last = calendar.monthrange(today.year, today.month)[1]
    return f"{today.year:04d}-{today.month:02d}-{last:02d}"


MISSING_PLACEHOLDER = "NA"


def fill_empty_cells_with_na(frame: pd.DataFrame) -> pd.DataFrame:
    """NaN/NaT, None, and blank strings become MISSING_PLACEHOLDER for CSV export."""
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


warnings.filterwarnings("ignore")
df = None
drive_path = "drive/MyDrive/Royalties"

DATABASES = [
    {
        "SITE_ID": "cd",
        "SITE": "Coin Digital",
        "CONNECTION_STRING": "mysql://admincoin:coinDigital12345@ec2-44-201-199-47.compute-1.amazonaws.com:3306/db4",
        "CONNECTION": None
    }
]

def create_directory(name):
    if not os.path.exists(name):
        os.makedirs(name)

def get_no_pay_attributes():
    query = """
      SELECT
        rt.isrc AS isrc,
        u.email AS user,
        l.label AS label,
        (SELECT GROUP_CONCAT(a.name SEPARATOR ',')
           FROM releases_relatedartists ra
           JOIN releases_artist a ON ra.artist_id = a.id
          WHERE ra.track_id = rt.id AND ra.relation_key = 'track' AND ra.role = 'Primary Artist'
        ) AS display_artist,
        rr.title AS `release`,
        rr.upc AS upc,
        rt.title AS track
      FROM releases_release rr
      JOIN releases_track rt ON rr.id = rt.release_id
      JOIN main_cduser u ON rt.created_by_id = u.id
      LEFT JOIN releases_label l ON rr.label_id = l.id
      WHERE rt.isrc LIKE 'INC01'
      ORDER BY rt.id
      LIMIT 1;
    """
    conn = DATABASES[0]["CONNECTION"]
    df_np = pd.read_sql(text(query), conn)
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
    df = pd.read_excel(f"{drive_path}/data.xlsx", engine='openpyxl')
    required_fields = [
        "start_date", "end_date", "country", "currency", "type",
        "units", "gross_total", "currency_rate", "isrc", "channel",
    ]
    missing_columns = set(required_fields).difference(df.columns)
    if missing_columns:
        print("Missing columns:", list(missing_columns))
        return False
    print("All required columns present.")
    for _col in ("start_date", "end_date"):
        if _col in df.columns:
            df[_col] = pd.to_datetime(df[_col], errors="coerce")
    df["isrc"].fillna("INC01", inplace=True)
    return True

def prepare_db_data():
    global df, DATABASES
    for db in DATABASES:
        db["CONNECTION"] = create_engine(db["CONNECTION_STRING"]).connect()

    unique_isrcs = df["isrc"].unique()
    unique_isrcs_clean = [
        str(s).replace("'", "").replace('"', "").lower().strip()
        for s in unique_isrcs
        if str(s).strip() and str(s).lower() != 'nan'
    ]
    if not unique_isrcs_clean:
        print("Error: No valid ISRCs found.")
        return

    isrcs_str = "('" + "', '".join(unique_isrcs_clean) + "')"
    query = text(f"""
      SELECT
        TRIM(LOWER(rt.isrc)) AS isrc,
        u.email AS user,
        l.label AS label,
        (SELECT GROUP_CONCAT(a.name SEPARATOR ',')
          FROM releases_relatedartists ra
          JOIN releases_artist a ON ra.artist_id = a.id
          WHERE ra.track_id = rt.id AND ra.relation_key = 'track' AND ra.role = 'Primary Artist'
        ) AS display_artist,
        rr.title AS `release`,
        rr.upc AS upc,
        rt.title AS track
      FROM releases_release rr
      JOIN releases_track rt ON rr.id = rt.release_id
      JOIN main_cduser u ON rt.created_by_id = u.id
      LEFT JOIN releases_label l ON rr.label_id = l.id
      WHERE TRIM(LOWER(rt.isrc)) IN {isrcs_str};
    """)
    DATABASES[0]["data"] = pd.read_sql(query, con=DATABASES[0]["CONNECTION"])

def separate_and_aggregate_by_channel():
    """
    1. Separate by channel
    2. For each channel: aggregate by ISRC - sum units, gross_total, INR totals
       Result: one row per unique ISRC per channel (total count & royalties preserved)
    """
    global df
    # Pre-compute INR value per row (gross * rate) for correct aggregation
    df["gross_total_INR"] = df["gross_total"] * df["currency_rate"]

    channel_dfs = []
    for channel in df["channel"].unique():
        ch_df = df[df["channel"] == channel].copy()
        # Aggregate by ISRC: sum all numerical, first for metadata
        agg_dict = {
            "start_date": "first",
            "end_date": "first",
            "country": "first",
            "type": "first",
            "currency": "first",
            "units": "sum",
            "gross_total": "sum",
            "gross_total_INR": "sum",
        }
        aggregated = ch_df.groupby("isrc", as_index=False).agg(agg_dict)
        # Effective currency_rate = total_INR / total_gross (for mixed currencies)
        aggregated["currency_rate"] = aggregated.apply(
            lambda r: r["gross_total_INR"] / r["gross_total"] if r["gross_total"] != 0 else 1,
            axis=1
        )
        aggregated["channel"] = channel
        channel_dfs.append(aggregated)

    calculation_df = pd.concat(channel_dfs, ignore_index=True)
    return calculation_df

def add_computed_fields(calculation_df):
    """Add unit_price, net_total, client currency fields."""
    zero = [0] * len(calculation_df)
    calculation_df["channel_costs"] = zero
    calculation_df["taxes"] = zero
    calculation_df["other_costs_client_currency"] = zero
    calculation_df["channel_costs_client_currency"] = zero
    calculation_df["taxes_client_currency"] = zero

    calculation_df["unit_price"] = calculation_df.apply(
        lambda x: x.gross_total / x.units if x.units != 0 else 0, axis=1
    )
    calculation_df["net_total"] = calculation_df.apply(
        lambda x: x.gross_total - x.channel_costs - x.taxes, axis=1
    )
    calculation_df["gross_total_client_currency"] = calculation_df.apply(
        lambda x: x.net_total * x.currency_rate, axis=1
    )
    calculation_df["net_total_client_currency"] = calculation_df.apply(
        lambda x: x.gross_total_client_currency
        - x.other_costs_client_currency
        - x.channel_costs_client_currency
        - x.taxes_client_currency,
        axis=1,
    )
    calculation_df["net_total_INR"] = calculation_df.apply(
        lambda x: x.net_total * x.currency_rate, axis=1
    )
    calculation_df["confirmed_date"] = current_month_end_iso()
    return calculation_df

def merge_db_and_finalize(calculation_df):
    """Merge DB data (user, label, display_artist, etc.) and handle no-pay for missing ISRCs."""
    merged_df = DATABASES[0]["data"]
    calculation_df["isrc"] = calculation_df["isrc"].apply(lambda x: str(x).lower())
    result = pd.merge(calculation_df, merged_df, on="isrc", how="left")

    # No-pay for rows not found in DB
    np_isrc, np_user, np_label, np_artist, np_release, np_upc, np_track = get_no_pay_attributes()
    mask = result["upc"].isnull() & result["track"].isnull() & result["release"].isnull() & result["label"].isnull()
    result.loc[mask, "upc"] = np_upc
    result.loc[mask, "user"] = np_user
    result.loc[mask, "label"] = np_label
    result.loc[mask, "display_artist"] = np_artist
    result.loc[mask, "release"] = np_release
    result.loc[mask, "track"] = np_track

    return result

def main():
    if not input_file_health_check():
        return
    prepare_db_data()

    # 1. Separate channel-wise and aggregate by ISRC (unique ISRC per channel)
    calculation_df = separate_and_aggregate_by_channel()
    print(f"After aggregation: {len(calculation_df)} rows (unique ISRC per channel)")

    # 2. Add computed fields
    calculation_df = add_computed_fields(calculation_df)

    # 3. Merge DB data and combine into one
    final_df = merge_db_and_finalize(calculation_df)

    columns = [
        "start_date", "end_date", "country", "currency", "type", "units",
        "unit_price", "gross_total", "channel_costs", "taxes", "net_total",
        "currency_rate", "gross_total_client_currency", "other_costs_client_currency",
        "channel_costs_client_currency", "taxes_client_currency", "net_total_client_currency",
        "user", "channel", "label", "display_artist", "release", "upc", "track", "isrc",
    ]
    final_df = final_df[columns]

    total_units = final_df["units"].sum()
    total_gross = final_df["gross_total"].sum()
    final_df = fill_empty_cells_with_na(final_df)

    create_directory(f"{drive_path}/domain_division/cd/calculation")
    output_path = f"{drive_path}/domain_division/cd/calculation/data.csv"
    final_df.to_csv(output_path, index=False)

    print("Royalties calculation report generated!")
    print(f"Output: {output_path}")
    print(f"Total rows: {len(final_df)} (unique ISRC per channel)")
    print(f"Total units: {total_units:,.0f}")
    print(f"Total gross: {total_gross:,.2f}")

if __name__ == "__main__":
    main()
