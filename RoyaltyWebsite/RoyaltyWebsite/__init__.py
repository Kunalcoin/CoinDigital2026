# Use PyMySQL as a drop-in replacement for MySQLdb
# This allows Django to use PyMySQL instead of mysqlclient
import pymysql
pymysql.install_as_MySQLdb()

# Load Celery app when Django starts (optional for local run without Redis)
try:
    from .celery import app as celery_app
    __all__ = ("celery_app",)
except Exception:
    celery_app = None
    __all__ = ()
