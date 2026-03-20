from django.contrib.auth.models import User
from django.contrib.auth.backends import BaseBackend
from .processor import processor
from commons.sql_client import sql_client
from .models import CDUser

# ================= ORIGINAL FUNCTION (FOR REFERENCE) ===================
# def check_login(user, pwd):
#     login = False
#     role = None
#     try:
#         df = sql_client.read_sql(
#             f'select password, role from user_login where username like "{user}"')
#         login = processor.encode_pass(pwd) == df['password'].iloc[0]
#         role = df['role'].iloc[0]
#     except:
#         pass
#     return login, role
# ===================================================================

# New ORM-based implementation - SECURITY FIX
def check_login(user, pwd):
    login = False
    role = None
    try:
        # Use case-insensitive email lookup
        cd_user = CDUser.objects.get(email__iexact=user)
        # Note: This assumes password is stored in a custom field. 
        # In production, this should use Django's built-in password hashing
        if hasattr(cd_user, 'password_hash'):
            login = processor.encode_pass(pwd) == cd_user.password_hash
        else:
            # Fallback to check_password if using Django's built-in auth
            login = cd_user.check_password(pwd)
        role = cd_user.role
    except CDUser.DoesNotExist:
        pass
    return login, role


class CustomBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        login, role = check_login(username, password)

        if login:
            try:
                # Return CDUser object directly instead of Django User
                cd_user = CDUser.objects.get(email__iexact=username)
                return cd_user
            except CDUser.DoesNotExist:
                return None
        return None

    def get_user(self, user_id):
        try:
            return CDUser.objects.get(pk=user_id)
        except CDUser.DoesNotExist:
            return None
