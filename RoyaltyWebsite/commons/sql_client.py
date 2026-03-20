import pandas as pd
from django.conf import settings
from django.db import connection
from sqlalchemy import create_engine


class SqlClientMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class SqlClient(metaclass=SqlClientMeta):
    db = None

    def __init__(self) -> None:
        if not self.db:
            # Use mysqlclient via mysqldb
            self.db = create_engine(settings.RAW_MYSQL_CONNECTION, echo=False)

    def df_to_sql(self, df, table_name, if_exists="append", index=False):
        # Safer connection handling for SQLAlchemy
        with self.db.begin() as conn:
            df.to_sql(table_name, conn, if_exists=if_exists, index=index)

    def read_sql(self, query: str):
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)

    def execute_sql(self, query, fetch_all=False):
        with connection.cursor() as cursor:
            cursor.execute(query)
            if fetch_all:
                return cursor.fetchall()


# Singleton instance
sql_client = SqlClient()
