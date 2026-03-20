from .processor import processor
from .models import CDUser

def user_role(request):
    """
    Context processor to make requesting_user_role available in all templates
    """
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            # request.user should be a CDUser object (AUTH_USER_MODEL)
            if isinstance(request.user, CDUser):
                requesting_user_role = processor.get_user_role(request.user)
            else:
                # Fallback if it's a Django User object - get CDUser by email
                cd_user = CDUser.objects.get(email__iexact=request.user.email)
                requesting_user_role = processor.get_user_role(cd_user)
            return {'requesting_user_role': requesting_user_role}
        except Exception as e:
            print(f"Error in user_role context processor: {e}")
            return {'requesting_user_role': None}
    return {'requesting_user_role': None}

