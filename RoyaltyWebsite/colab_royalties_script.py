# ========== CELL 1: Mount Google Drive (run this first, then authorize) ==========
from google.colab import drive
drive.mount('/content/drive')

# ========== CELL 2: Main script ==========
import pandas as pd
from sqlalchemy import create_engine, text
import ast, os
import warnings

warnings.filterwarnings("ignore")
df = None
calculation_df = None
# Correct path: "My Drive" has a space, and use full path for clarity
drive_path = "/content/drive/My Drive/Royalties"

DATABASES = [
    {
        "SITE_ID": "cd",
        "SITE": "Coin Digital",
        "CONNECTION_STRING": "mysql://admincoin:coinDigital12345@ec2-54-84-50-236.compute-1.amazonaws.com:3306/db4",
        "CONNECTION": None  # Will be set in prepare_db_data
    }
]

def get_artists_information():
    query = "SELECT id, name AS artist_name FROM releases_artist"
    cd_conn = DATABASES[0]["CONNECTION"]
    df_artists = pd.read_sql(query, cd_conn)
    artists_info = df_artists.set_index('id')['artist_name'].to_dict()
    return artists_info

# Will be set after DB connection
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
    df = pd.read_excel(f"{drive_path}/data.xlsx", engine='openpyxl')

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
    else:
        print("All required columns are present in the File.")

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
        if str(s).strip() and str(s).lower() != 'nan'
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

    database = DATABASES[0]
    database["data"] = pd.read_sql(query_cd, con=database["CONNECTION"])
    return


def add_remaining_fields():
    global df
    zero_list = [0] * len(df)
    df["channel_costs"] = zero_list
    df["taxes"] = zero_list
    df["other_costs_client_currency"] = zero_list
    df["channel_costs_client_currency"] = zero_list
    df["taxes_client_currency"] = zero_list

    df["unit_price"] = df.apply(
        lambda x: x.gross_total / x.units if x.units != 0 else 0, axis=1
    )
    df["net_total"] = df.apply(
        lambda x: x.gross_total - x.channel_costs - x.taxes, axis=1
    )
    df["gross_total_client_currency"] = df.apply(
        lambda x: x.net_total * x.currency_rate, axis=1
    )
    df["net_total_client_currency"] = df.apply(
        lambda x: x.gross_total_client_currency
        - x.other_costs_client_currency
        - x.channel_costs_client_currency
        - x.taxes_client_currency,
        axis=1,
    )
    df["net_total_INR"] = df.apply(lambda x: x.net_total * x.currency_rate, axis=1)
    df["confirmed_date"] = (pd.Timestamp.now() + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")

    merged_df = DATABASES[0]["data"]
    df['isrc'] = df.apply(lambda x: str(x.isrc).lower(), axis=1)
    df = pd.merge(df, merged_df, on="isrc", how="left")

    df_data_not_found = df[
        (df["upc"].isnull())
        & (df["track"].isnull())
        & (df["release"].isnull())
        & (df["label"].isnull())
    ]
    df_data_found = df[~df['isrc'].isin(df_data_not_found['isrc'])]

    isrc, user, label, display_artist, release, upc, track = get_no_pay_attributes()
    df_data_not_found["upc"] = upc
    df_data_not_found["user"] = user
    df_data_not_found["label"] = label
    df_data_not_found["display_artist"] = display_artist
    df_data_not_found["release"] = release
    df_data_not_found["track"] = track

    df = pd.concat([df_data_found, df_data_not_found], ignore_index=True)
    return


def divide_domain_based_data():
    create_directory(f"{drive_path}/domain_division/cd/download")

    FETCH_QUERY_ISRC_CD = "SELECT DISTINCT TRIM(isrc) AS isrc FROM releases_track;"
    database = DATABASES[0]
    isrcs = pd.read_sql(text(FETCH_QUERY_ISRC_CD), con=database["CONNECTION"])
    database["ISRC"] = [str(isrc).strip().lower() for isrc in isrcs["isrc"].tolist()]

    df["LOWERCASE_ISRC"] = df["isrc"].apply(lambda x: str(x).strip().lower())
    database["DATA"] = df[df["LOWERCASE_ISRC"].isin(database["ISRC"])]
    unmatched_data = df[~df["LOWERCASE_ISRC"].isin(database["ISRC"])]
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
    database["DATA"].to_csv(
        f"{drive_path}/domain_division/{database['SITE_ID']}/download/data.csv",
        index=False
    )
    return


def main():
    health_check = input_file_health_check()
    if not health_check:
        print("Please resolve above mentioned issues in input file!")
        return
    prepare_db_data()
    add_remaining_fields()
    divide_domain_based_data()
    print("Royalties data generated!")
    print(f"Output saved to: {drive_path}/domain_division/cd/download/data.csv")


if __name__ == "__main__":
    main()
