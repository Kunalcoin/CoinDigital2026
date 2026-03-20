# from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
# from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth import authenticate, login, logout
# from django.contrib.auth.decorators import login_required
# from django.views.decorators.csrf import csrf_exempt
# from django.core.mail import send_mail
# from django.conf import settings
# from django.db.models import Q, Sum, Count
# from django.core.exceptions import ObjectDoesNotExist
# from django.utils import timezone
# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from rest_framework import status
# import json
# import traceback
# import pandas as pd
# import numpy as np

# from .models import (
#     CDUser, Ratio, Request, UniqueCode, Label, Release, Track, 
#     Artist, RelatedArtists, Announcement, Payment, Royalties, 
#     Sharing, DueAmount
# )
# from .constants import LANGUAGES, COUNTRIES


# # Helper functions converted to use Django ORM
# def fetch_artist_from_id(artist_id):
#     """
#     Fetch artist name from artist ID using Django ORM
#     """
#     try:
#         artist = Artist.objects.get(id=int(artist_id))
#         return artist.name
#     except (Artist.DoesNotExist, ValueError):
#         return None


# def update_password(username, new_password):
#     """
#     Update user password using Django ORM
#     """
#     try:
#         user = CDUser.objects.get(email=username)
#         user.set_password(new_password)
#         user.save()
#         return True
#     except CDUser.DoesNotExist:
#         return False
#     except Exception as e:
#         print(f"Error updating password: {e}")
#         return False


# def get_navigation(page, navigation):
#     """
#     Helper function to generate navigation items
#     """
#     output = []
#     for name, icon in navigation.items():
#         nav_item = "nav-item"
#         extension = name.lower().replace(" ", "_")
#         if name == page or extension == page:
#             nav_item += " active"
#         output.append((name, extension, nav_item, icon))
#     return output


# def divide_channels(l, n):
#     """
#     Helper function to divide channels into chunks
#     """
#     for i in range(0, len(l), n):
#         yield l[i : i + n]


# def get_leader(username):
#     """
#     Get team leader for a member user using Django ORM
#     Note: This function assumes there's a team relationship in the CDUser model
#     """
#     try:
#         user = CDUser.objects.get(email=username)
#         if user.parent:
#             return user.parent.email
#         return None
#     except CDUser.DoesNotExist:
#         return None


# def is_user_active(user):
#     """
#     Check if user is active using Django ORM
#     """
#     try:
#         if isinstance(user, str):
#             user_obj = CDUser.objects.get(email=user)
#             return user_obj.is_active
#         else:
#             return user.is_active
#     except CDUser.DoesNotExist:
#         return False
#     except Exception as e:
#         print(f"Error checking user status: {e}")
#         return False


# def get_user_role(user):
#     """
#     Get user role using Django ORM
#     """
#     try:
#         if isinstance(user, str):
#             user_obj = CDUser.objects.get(email=user)
#             return user_obj.role
#         else:
#             return user.role
#     except CDUser.DoesNotExist:
#         return None


# def get_user_ratios(user):
#     """
#     Get active user ratios using Django ORM
#     """
#     try:
#         if isinstance(user, str):
#             user_obj = CDUser.objects.get(email=user)
#         else:
#             user_obj = user
        
#         active_ratio = Ratio.objects.filter(
#             user=user_obj, 
#             status=Ratio.STATUS.ACTIVE
#         ).first()
        
#         if active_ratio:
#             return active_ratio.stores, active_ratio.youtube
#         return None, None
#     except CDUser.DoesNotExist:
#         return None, None


# def get_users_belongs_to(user):
#     """
#     Get users that belong to a specific user (for intermediate users)
#     """
#     try:
#         if isinstance(user, str):
#             user_obj = CDUser.objects.get(email=user)
#         else:
#             user_obj = user
        
#         children = CDUser.objects.filter(parent=user_obj).values_list('email', flat=True)
#         return list(children)
#     except CDUser.DoesNotExist:
#         return []


# @api_view(['GET', 'POST'])
# def login_view(request):
#     """
#     Handle user login with Django authentication
#     """
#     if request.method == 'GET':
#         # Check if user is already authenticated
#         if request.user.is_authenticated and is_user_active(request.user):
#             if request.user.role == CDUser.ROLES.MEMBER:
#                 return render(
#                     request,
#                     "volt_normal.html",
#                     context={
#                         "username": request.user.email,
#                         "requesting_user_role": "member",
#                         "is_show_due_balance": False,
#                     },
#                 )
#             else:
#                 return redirect("manage_users")
        
#         return render(request, "volt_login.html")
    
#     elif request.method == 'POST':
#         try:
#             username = request.data.get('username') or request.POST.get('username')
#             password = request.data.get('password') or request.POST.get('password')
            
#             if not username or not password:
#                 return render(
#                     request,
#                     "volt_login.html",
#                     context={"error_message": "Username and password are required."},
#                 )
            
#             # Authenticate user
#             user = authenticate(username=username, password=password)
            
#             if user and user.is_active:
#                 login(request, user)
                
#                 if user.role == CDUser.ROLES.MEMBER:
#                     return render(
#                         request,
#                         "volt_normal.html",
#                         context={
#                             "username": username,
#                             "requesting_user_role": "member",
#                             "is_show_due_balance": False,
#                         },
#                     )
#                 else:
#                     return redirect("manage_users")
#             else:
#                 error_message = "Invalid credentials or account is inactive."
#                 return render(
#                     request,
#                     "volt_login.html",
#                     context={"error_message": error_message},
#                 )
                
#         except Exception as e:
#             print(f"Login error: {e}")
#             return render(
#                 request,
#                 "volt_login.html",
#                 context={"error_message": "Error logging in, please try again later."},
#             )


# @api_view(['GET'])
# def login_page(request):
#     """
#     Display login page or redirect if already authenticated
#     """
#     if request.user.is_authenticated and is_user_active(request.user):
#         if request.user.is_superuser:
#             return redirect("dashboard")
#         else:
#             return redirect("dashboard")
#     return render(request, "volt_login.html")


# @api_view(['POST'])
# def logout_view(request):
#     """
#     Handle user logout
#     """
#     try:
#         logout(request)
#         return redirect("login_page")
#     except Exception as e:
#         print(f"Logout error: {e}")
#         return redirect("login_page")


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def my_requests(request):
#     """
#     Display user requests using Django ORM
#     """
#     try:
#         if not is_user_active(request.user):
#             return HttpResponseNotFound("<h1>Authentication failed!</h1>")
        
#         # Get requests based on user role
#         if request.user.role == CDUser.ROLES.ADMIN:
#             request_objects = Request.objects.exclude(
#                 status=Request.STATUS.CLOSED
#             ).select_related('user')
#         else:
#             request_objects = Request.objects.filter(
#                 user=request.user
#             ).select_related('user')
        
#         # Convert to list of dictionaries for table display
#         requests_data = []
#         for req in request_objects:
#             requests_data.append({
#                 'request_id': req.id,
#                 'requester_user': req.user.email,
#                 'ticket_name': req.title,
#                 'description': req.description,
#                 'created_at': req.created_at.strftime('%Y-%m-%d %H:%M:%S'),
#                 'status': req.status,
#                 'admin_comments': req.feedback or '',
#             })
        
#         # Build table headers
#         headers = ""
#         if request.user.role == CDUser.ROLES.ADMIN:
#             headers += "<th>User</th>"
#         headers += "<th>Title</th><th>Description</th><th>Opened At</th><th>Status</th><th>Feedback</th><th>Close</th>"
#         if request.user.role == CDUser.ROLES.ADMIN:
#             headers += "<th>Review</th>"
        
#         # Build table body
#         body = ""
#         for req_data in requests_data:
#             body += f'<tr id="row_{req_data["request_id"]}" style="cursor:pointer">'
            
#             if request.user.role == CDUser.ROLES.ADMIN:
#                 body += f"""<td>{req_data['requester_user']}</td>"""
            
#             # Add other columns (excluding request_id and requester_user if not admin)
#             columns_to_show = ['ticket_name', 'description', 'created_at', 'status', 'admin_comments']
#             for column in columns_to_show:
#                 body += f"<td>{req_data[column]}</td>"
            
#             body += f'<td onclick="delete_request({req_data["request_id"]})"><span class="material-symbols-outlined">delete</span></td>'
            
#             if request.user.role == CDUser.ROLES.ADMIN:
#                 body += f"""<td onclick="edit_request({req_data['request_id']})"><span class="material-symbols-outlined">edit</span></td>"""
            
#             body += "</tr>"
        
#         table = f"""<table class="table table-hover" id="data_table">
#             <thead>
#                 {headers}
#             </thead>
#             <tbody>
#                 {body}
#             </tbody>
#             </table>
#         """
        
#         return JsonResponse({
#             "table": table, 
#             "requesting_user_role": request.user.role
#         })
        
#     except Exception as e:
#         print(f"Error in my_requests: {e}")
#         return JsonResponse({
#             "error": "An error occurred while fetching requests"
#         }, status=500)


# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# def requests_view(request):
#     """
#     Handle requests page display and creation using Django ORM
#     """
#     try:
#         if not is_user_active(request.user):
#             return HttpResponseNotFound("<h1>Authentication failed!</h1>")
        
#         if request.method == "GET":
#             return render(
#                 request,
#                 "volt_requests.html",
#                 context={"requesting_user_role": request.user.role},
#             )
        
#         elif request.method == "POST":
#             title = request.data.get('title') or request.POST.get('title')
#             description = request.data.get('description') or request.POST.get('description')
            
#             if not title or not description:
#                 return JsonResponse({
#                     "requests_error_message": "Title and description are required"
#                 }, status=400)
            
#             # Create new request
#             user_request = Request.objects.create(
#                 user=request.user,
#                 title=title,
#                 description=description,
#             )
            
#             return JsonResponse({"requests_success_message": "success"})
            
#     except Exception as e:
#         print(f"Error in requests_view: {e}")
#         return JsonResponse({"requests_error_message": "error"}, status=500)


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# @csrf_exempt
# def request_feedback(request):
#     """
#     Handle request feedback update using Django ORM
#     """
#     try:
#         if not (request.user.is_authenticated and is_user_active(request.user)):
#             return JsonResponse({"requests_error_message": "Authentication failed"}, status=401)
        
#         request_id = request.data.get('request_id') or request.POST.get('request_id')
#         status_value = request.data.get('status') or request.POST.get('status')
#         feedback = request.data.get('feedback') or request.POST.get('feedback')
        
#         if not request_id:
#             return JsonResponse({"requests_error_message": "Request ID is required"}, status=400)
        
#         # Get and update the request
#         request_object = get_object_or_404(Request, pk=int(request_id))
        
#         if status_value:
#             request_object.status = status_value
#         if feedback:
#             request_object.feedback = feedback
        
#         request_object.save()
        
#         return JsonResponse({"requests_success_message": "success"})
        
#     except Request.DoesNotExist:
#         return JsonResponse({"requests_error_message": "Request not found"}, status=404)
#     except Exception as e:
#         print(f"Error in request_feedback: {e}")
#         return JsonResponse({"requests_error_message": "error"}, status=500)


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def delete_my_request(request, request_id):
#     """
#     Delete a user request using Django ORM
#     """
#     try:
#         if not is_user_active(request.user):
#             return JsonResponse({"requests_error_message": "Authentication failed"}, status=401)
        
#         request_object = get_object_or_404(Request, pk=request_id)
        
#         # Check if user owns the request or is admin
#         if request_object.user != request.user and request.user.role != CDUser.ROLES.ADMIN:
#             return JsonResponse({"requests_error_message": "Permission denied"}, status=403)
        
#         request_object.delete()
#         return JsonResponse({"requests_success_message": "success"})
        
#     except Request.DoesNotExist:
#         return JsonResponse({"requests_error_message": "Request not found"}, status=404)
#     except Exception as e:
#         print(f"Error in delete_my_request: {e}")
#         return JsonResponse({"requests_error_message": "error"}, status=500)


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def update_user_status(request):
#     """
#     Update user status using Django ORM
#     """
#     try:
#         if not is_user_active(request.user):
#             return JsonResponse({"message": "Authentication Failed!"}, status=401)
        
#         user_id = request.data.get('user') or request.POST.get('user')
#         status_value = request.data.get('status') or request.POST.get('status')
        
#         if not user_id or status_value is None:
#             return JsonResponse({
#                 "message": "User ID and status are required!"
#             }, status=400)
        
#         user = get_object_or_404(CDUser, pk=user_id)
#         user.is_active = True if int(status_value) == 1 else False
#         user.save()
        
#         return JsonResponse({"message": f"Status updated for {user.email}!"})
        
#     except CDUser.DoesNotExist:
#         return JsonResponse({
#             "message": "User not found!"
#         }, status=404)
#     except Exception as e:
#         print(f"Error updating user status: {e}")
#         return JsonResponse({
#             "message": "There was an error while setting status for this user. Please try again!"
#         }, status=500)


# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# def edit_user(request, id):
#     """
#     Edit user details using Django ORM
#     """
#     try:
#         if not (is_user_active(request.user) and request.user.role == CDUser.ROLES.ADMIN):
#             return HttpResponseNotFound("<h1>Authentication failed!</h1>")
        
#         user = get_object_or_404(CDUser, pk=id)
        
#         if request.method == "POST":
#             # Update password if provided
#             password = request.data.get('password') or request.POST.get('password')
#             if password:
#                 user.set_password(password)
            
#             # Update role if changed
#             new_role = request.data.get('role') or request.POST.get('role')
#             if new_role and new_role != user.role:
#                 user.role = new_role
            
#             # Update user fields
#             user.first_name = request.data.get('name') or request.POST.get('name', user.first_name)
#             user.last_name = request.data.get('surname') or request.POST.get('surname', user.last_name)
#             user.country = request.data.get('country') or request.POST.get('country', user.country)
#             user.language = request.data.get('language') or request.POST.get('language', user.language)
#             user.city = request.data.get('city') or request.POST.get('city', user.city)
#             user.street = request.data.get('street') or request.POST.get('street', user.street)
#             user.postal_code = request.data.get('postal_code') or request.POST.get('postal_code', user.postal_code)
#             user.contact_phone = request.data.get('contact_phone') or request.POST.get('contact_phone', user.contact_phone)
#             user.company = request.data.get('company') or request.POST.get('company', user.company)
#             user.company_name = request.data.get('company_name') or request.POST.get('company_name', user.company_name)
#             user.fiskal_id_number = request.data.get('fiskal_id_number') or request.POST.get('fiskal_id_number', user.fiskal_id_number)
#             user.country_phone = request.data.get('country_phone') or request.POST.get('country_phone', user.country_phone)
#             user.company_contact_phone = request.data.get('company_contact_phone') or request.POST.get('company_contact_phone', user.company_contact_phone)
#             user.pan = request.data.get('pan_number') or request.POST.get('pan_number', user.pan)
#             user.gst_number = request.data.get('gst_number') or request.POST.get('gst_number', user.gst_number)
#             user.account_name = request.data.get('account_name') or request.POST.get('account_name', user.account_name)
#             user.account_number = request.data.get('account_number') or request.POST.get('account_number', user.account_number)
#             user.ifsc = request.data.get('ifsc_code') or request.POST.get('ifsc_code', user.ifsc)
#             user.sort_code = request.data.get('sort_code') or request.POST.get('sort_code', user.sort_code)
#             user.swift_code = request.data.get('swift_code') or request.POST.get('swift_code', user.swift_code)
#             user.iban = request.data.get('iban_number') or request.POST.get('iban_number', user.iban)
#             user.bank_country = request.data.get('country_of_bank') or request.POST.get('country_of_bank', user.bank_country)
#             user.bank_name = request.data.get('bank_name') or request.POST.get('bank_name', user.bank_name)
            
#             user.save()
            
#             # Handle ratios
#             ratio_stores = request.data.get('ratio') or request.POST.get('ratio')
#             ratio_yt = request.data.get('yt_ratio') or request.POST.get('yt_ratio')
#             sales_payout = request.data.get('sales_payout') or request.POST.get('sales_payout')
#             sales_payout_threshold = request.data.get('sales_payout_threshold') or request.POST.get('sales_payout_threshold')
            
#             # Get current active ratio
#             current_ratio = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
            
#             if current_ratio and (
#                 str(ratio_stores) != str(current_ratio.stores) or
#                 str(ratio_yt) != str(current_ratio.youtube) or
#                 str(sales_payout) != str(current_ratio.sales_payout) or
#                 str(sales_payout_threshold) != str(current_ratio.sales_payout_threshold)
#             ):
#                 # Deactivate current ratio
#                 current_ratio.status = Ratio.STATUS.IN_ACTIVE
#                 current_ratio.save()
                
#                 # Create new ratio
#                 new_ratio = Ratio.objects.create(
#                     user=user,
#                     stores=int(ratio_stores) if ratio_stores else current_ratio.stores,
#                     youtube=int(ratio_yt) if ratio_yt else current_ratio.youtube,
#                     sales_payout=int(sales_payout) if sales_payout else current_ratio.sales_payout,
#                     sales_payout_threshold=int(sales_payout_threshold) if sales_payout_threshold else current_ratio.sales_payout_threshold,
#                     status=Ratio.STATUS.ACTIVE
#                 )
            
#             # For template rendering, we need to import navigation
#             from .processor import admin  # Assuming this exists
#             return render(
#                 request,
#                 "volt_admin_manage_users.html",
#                 context={
#                     "edit_success": "success",
#                     "navigation": get_navigation("manage_users", admin.navigation),
#                     "requesting_user_role": request.user.role,
#                     "username": user.email,
#                 },
#             )
        
#         elif request.method == "GET":
#             current_owner = f"{user.parent.email} - {user.parent.role}" if user.parent else "No parent"
#             eligible_parents = CDUser.objects.filter(
#                 role__in=(CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE)
#             )
#             eligible_parents_list = [f"{parent.email} - {parent.role}" for parent in eligible_parents]
            
#             current_ratio = Ratio.objects.filter(user=user, status=Ratio.STATUS.ACTIVE).first()
            
#             from .processor import admin  # Assuming this exists
#             context = {
#                 "navigation": get_navigation("manage_users", admin.navigation),
#                 "roles": [
#                     CDUser.ROLES.ADMIN,
#                     CDUser.ROLES.INTERMEDIATE,
#                     CDUser.ROLES.NORMAL,
#                 ],
#                 "countries": COUNTRIES,
#                 "languages": LANGUAGES,
#                 "intermediate_users": eligible_parents_list,
#                 "selected_user": user,
#                 "current_owner": current_owner,
#                 "requesting_user_role": request.user.role,
#                 "ratios": current_ratio
#             }
#             return render(request, "volt_admin_edit_user.html", context=context)
            
#     except CDUser.DoesNotExist:
#         return HttpResponseNotFound("<h1>User not found!</h1>")
#     except Exception as e:
#         print(f"Error in edit_user: {e}")
#         return HttpResponseNotFound("<h1>An error occurred!</h1>")


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# @csrf_exempt
# def change_ownership(request, id):
#     """
#     Change user ownership using Django ORM
#     """
#     try:
#         if not (is_user_active(request.user) and request.user.role == CDUser.ROLES.ADMIN):
#             return HttpResponse(status=400)
        
#         user = get_object_or_404(CDUser, pk=id)
#         new_owner_email = str(request.data.get('new_owner') or request.POST.get('new_owner')).split(' ')[0]
        
#         new_owner = get_object_or_404(CDUser, email=new_owner_email)
#         user.parent = new_owner
#         user.save()
        
#         return HttpResponse(status=200)
        
#     except CDUser.DoesNotExist:
#         return HttpResponse(status=404)
#     except Exception as e:
#         print(f"Error in change_ownership: {e}")
#         return HttpResponse(status=400)


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def remove_ownership(request, id):
#     """
#     Remove user ownership using Django ORM
#     """
#     try:
#         if not (is_user_active(request.user) and request.user.role == CDUser.ROLES.ADMIN):
#             return HttpResponse(status=400)
        
#         user = get_object_or_404(CDUser, pk=id)
#         user.parent = request.user
#         user.save()
        
#         return HttpResponse(status=200)
        
#     except CDUser.DoesNotExist:
#         return HttpResponse(status=404)
#     except Exception as e:
#         print(f"Error in remove_ownership: {e}")
#         return HttpResponse(status=400)


# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# def insert_user(request):
#     """
#     Create new user using Django ORM
#     """
#     try:
#         if not (is_user_active(request.user) and 
#                 request.user.role in [CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE]):
#             return HttpResponseNotFound("<h1>Authentication failed!</h1>")
        
#         if request.method == "GET":
#             # Get current user's active ratio for payout calculation
#             active_ratio = Ratio.objects.filter(
#                 user=request.user, 
#                 status=Ratio.STATUS.ACTIVE
#             ).first()
#             requesting_user_payout = active_ratio.sales_payout if active_ratio else 0
            
#             # Import navigation (assuming this exists)
#             from .processor import admin, intermediate
#             navigation = (
#                 admin.navigation if request.user.role == CDUser.ROLES.ADMIN 
#                 else intermediate.navigation
#             )
            
#             return render(
#                 request,
#                 "volt_admin_add_user.html",
#                 context={
#                     "navigation": get_navigation("Insert User", navigation),
#                     "requesting_user_role": request.user.role,
#                     "requesting_user_payout": requesting_user_payout,
#                     "username": request.user,
#                 },
#             )
        
#         elif request.method == "POST":
#             username = request.data.get('username') or request.POST.get('username')
            
#             # Check if user already exists
#             if CDUser.objects.filter(email=username).exists():
#                 from .processor import admin, intermediate
#                 navigation = (
#                     admin.navigation if request.user.role == CDUser.ROLES.ADMIN 
#                     else intermediate.navigation
#                 )
#                 return render(
#                     request,
#                     "volt_admin_add_user.html",
#                     context={
#                         "navigation": get_navigation("manage_user", navigation),
#                         "requesting_user_role": request.user.role,
#                         "duplicate_error": True,
#                         "username": request.user,
#                     },
#                 )
            
#             # Determine role
#             role = request.data.get('role') or request.POST.get('role', CDUser.ROLES.NORMAL)
            
#             # Admin role can only be created by admin
#             if role.lower() == CDUser.ROLES.ADMIN and request.user.role != CDUser.ROLES.ADMIN:
#                 role = CDUser.ROLES.NORMAL
            
#             # Map role string to proper choice
#             if "admin" in role.lower():
#                 role = CDUser.ROLES.ADMIN
#             elif "intermediate" in role.lower():
#                 role = CDUser.ROLES.INTERMEDIATE
#             else:
#                 role = CDUser.ROLES.NORMAL
            
#             # Create user
#             created_user = CDUser.objects.create_user(
#                 email=username,
#                 password=request.data.get('password') or request.POST.get('password'),
#                 role=role,
#                 first_name=request.data.get('name') or request.POST.get('name', ''),
#                 last_name=request.data.get('surname') or request.POST.get('surname', ''),
#                 country=request.data.get('country') or request.POST.get('country', COUNTRIES[0]),
#                 city=request.data.get('city') or request.POST.get('city', ''),
#                 street=request.data.get('street') or request.POST.get('street', ''),
#                 postal_code=request.data.get('postal_code') or request.POST.get('postal_code', ''),
#                 contact_phone=request.data.get('contact_phone') or request.POST.get('contact_phone', ''),
#                 company=request.data.get('company') or request.POST.get('company', ''),
#                 company_name=request.data.get('company_name') or request.POST.get('company_name', ''),
#                 fiskal_id_number=request.data.get('fiskal_id_number') or request.POST.get('fiskal_id_number', ''),
#                 country_phone=request.data.get('country_phone') or request.POST.get('country_phone', ''),
#                 company_contact_phone=request.data.get('company_contact_phone') or request.POST.get('company_contact_phone', ''),
#                 pan=request.data.get('pan_number') or request.POST.get('pan_number', ''),
#                 gst_number=request.data.get('gst_number') or request.POST.get('gst_number', ''),
#                 account_name=request.data.get('account_name') or request.POST.get('account_name', ''),
#                 account_number=request.data.get('account_number') or request.POST.get('account_number', ''),
#                 ifsc=request.data.get('ifsc_code') or request.POST.get('ifsc_code', ''),
#                 sort_code=request.data.get('sort_code') or request.POST.get('sort_code', ''),
#                 swift_code=request.data.get('swift_code') or request.POST.get('swift_code', ''),
#                 iban=request.data.get('iban_number') or request.POST.get('iban_number', ''),
#                 bank_country=request.data.get('country_of_bank') or request.POST.get('country_of_bank', ''),
#                 bank_name=request.data.get('bank_name') or request.POST.get('bank_name', ''),
#                 parent=request.user
#             )
            
#             # Create ratio for the user
#             ratio = Ratio.objects.create(
#                 user=created_user,
#                 stores=int(request.data.get('ratio') or request.POST.get('ratio', 0)),
#                 youtube=int(request.data.get('yt_ratio') or request.POST.get('yt_ratio', 0)),
#                 sales_payout=int(request.data.get('sales_payout') or request.POST.get('sales_payout', 0)),
#                 sales_payout_threshold=int(request.data.get('sales_payout_threshold') or request.POST.get('sales_payout_threshold', 0)),
#             )
            
#             # Create team member if provided and role is normal
#             member_email = request.data.get('team_member_email') or request.POST.get('team_member_email', '')
#             member_password = request.data.get('team_member_password') or request.POST.get('team_member_password', '')
            
#             if (member_email and member_password and 
#                 role == CDUser.ROLES.NORMAL and 
#                 not CDUser.objects.filter(email=member_email.lower()).exists()):
                
#                 created_member = CDUser.objects.create_user(
#                     email=member_email.lower(),
#                     password=member_password,
#                     role=CDUser.ROLES.MEMBER,
#                     parent=created_user,
#                     first_name="Member",
#                     last_name="Member",
#                     contact_phone="NaN",
#                     company_contact_phone="NaN",
#                     pan="NaN"
#                 )
            
#             # Render success page
#             from .processor import admin, intermediate
#             navigation = (
#                 admin.navigation if request.user.role == CDUser.ROLES.ADMIN 
#                 else intermediate.navigation
#             )
#             return render(
#                 request,
#                 "volt_admin_manage_users.html",
#                 context={
#                     "navigation": get_navigation("manage_users", navigation),
#                     "requesting_user_role": request.user.role,
#                     "success": True,
#                 },
#             )
            
#     except Exception as e:
#         print(f"Error in insert_user: {e}")
#         return HttpResponseNotFound("<h1>An error occurred!</h1>")


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def manage_users(request):
#     """
#     Display manage users page using Django ORM
#     """
#     try:
#         if not (is_user_active(request.user) and 
#                 request.user.role in [CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE]):
#             return HttpResponseNotFound("<h1>Authentication failed!</h1>")
        
#         from .processor import admin, intermediate
#         navigation = (
#             admin.navigation if request.user.role == CDUser.ROLES.ADMIN 
#             else intermediate.navigation
#         )
        
#         return render(
#             request,
#             "volt_admin_manage_users.html",
#             context={
#                 "navigation": get_navigation("manage_users", navigation),
#                 "requesting_user_role": request.user.role,
#                 "username": request.user,
#             },
#         )
        
#     except Exception as e:
#         print(f"Error in manage_users: {e}")
#         return HttpResponseNotFound("<h1>Authentication failed!</h1>")


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def manage_users_get_all_users(request):
#     """
#     Get all users for management display using Django ORM
#     """
#     try:
#         if not (is_user_active(request.user) and 
#                 request.user.role in [CDUser.ROLES.ADMIN, CDUser.ROLES.INTERMEDIATE]):
#             return HttpResponseNotFound("<h1>Authentication failed!</h1>")
        
#         # Get users based on role
#         if request.user.role == CDUser.ROLES.ADMIN:
#             users = CDUser.objects.all().select_related('parent').prefetch_related('ratios')
#         else:  # INTERMEDIATE
#             # Get users that belong to this intermediate user
#             users = CDUser.objects.filter(parent=request.user).select_related('parent').prefetch_related('ratios')
        
#         users_data = []
#         for user in users:
#             active_ratio = user.ratios.filter(status=Ratio.STATUS.ACTIVE).first()
#             users_data.append({
#                 'id': user.id,
#                 'email': user.email,
#                 'first_name': user.first_name,
#                 'last_name': user.last_name,
#                 'role': user.role,
#                 'is_active': user.is_active,
#                 'parent': user.parent.email if user.parent else 'No parent',
#                 'stores_ratio': active_ratio.stores if active_ratio else 0,
#                 'youtube_ratio': active_ratio.youtube if active_ratio else 0,
#                 'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
#             })
        
#         return JsonResponse({
#             'users': users_data,
#             'requesting_user_role': request.user.role
#         })
        
#     except Exception as e:
#         print(f"Error in manage_users_get_all_users: {e}")
#         return JsonResponse({'error': 'An error occurred'}, status=500)


# @api_view(['GET', 'POST'])
# def change_password(request):
#     """
#     Handle password change using Django ORM
#     """
#     try:
#         if not (request.user.is_authenticated and is_user_active(request.user)):
#             return render(request, "volt_login.html")
        
#         # Import navigation based on user role
#         from .processor import admin, intermediate, normal
#         if request.user.role == CDUser.ROLES.ADMIN:
#             navigation = admin.navigation
#         elif request.user.role == CDUser.ROLES.INTERMEDIATE:
#             navigation = intermediate.navigation
#         else:
#             navigation = normal.navigation
        
#         if request.method == "POST":
#             old_password = request.data.get('oldpassword') or request.POST.get('oldpassword')
#             new_password = request.data.get('newpassword') or request.POST.get('newpassword')
#             new_password_confirm = request.data.get('newpasswordconfirm') or request.POST.get('newpasswordconfirm')
            
#             if not old_password or not new_password or not new_password_confirm:
#                 error = "All password fields are required!"
#                 return render(
#                     request,
#                     "volt_admin_change_password.html",
#                     context={
#                         "error_message": error,
#                         "username": request.user.email,
#                         "requesting_user_role": request.user.role,
#                         "navigation": get_navigation("change_password", navigation),
#                     },
#                 )
            
#             if request.user.check_password(old_password):
#                 if new_password == new_password_confirm:
#                     try:
#                         request.user.set_password(new_password)
#                         request.user.save()
#                         message = "Password updated successfully!"
#                         return render(
#                             request,
#                             "volt_admin_change_password.html",
#                             context={
#                                 "success_message": message,
#                                 "username": request.user.email,
#                                 "requesting_user_role": request.user.role,
#                                 "navigation": get_navigation("change_password", navigation),
#                             },
#                         )
#                     except Exception as e:
#                         print(f"Error updating password: {e}")
#                         error = "Failed to update password!"
#                         return render(
#                             request,
#                             "volt_admin_change_password.html",
#                             context={
#                                 "error_message": error,
#                                 "username": request.user.email,
#                                 "requesting_user_role": request.user.role,
#                                 "navigation": get_navigation("change_password", navigation),
#                             },
#                         )
#                 else:
#                     error = "New entered passwords don't match!"
#                     return render(
#                         request,
#                         "volt_admin_change_password.html",
#                         context={
#                             "error_message": error,
#                             "username": request.user.email,
#                             "requesting_user_role": request.user.role,
#                             "navigation": get_navigation("change_password", navigation),
#                         },
#                     )
#             else:
#                 error = "Invalid old password entered!"
#                 return render(
#                     request,
#                     "volt_admin_change_password.html",
#                     context={
#                         "error_message": error,
#                         "username": request.user.email,
#                         "requesting_user_role": request.user.role,
#                         "navigation": get_navigation("change_password", navigation),
#                     },
#                 )
        
#         elif request.method == "GET":
#             return render(
#                 request,
#                 "volt_admin_change_password.html",
#                 context={
#                     "username": request.user.email,
#                     "requesting_user_role": request.user.role,
#                     "navigation": get_navigation("change_password", navigation),
#                 },
#             )
            
#     except Exception as e:
#         print(f"Error in change_password: {e}")
#         return render(request, "volt_login.html")


# @api_view(['GET', 'POST'])
# def forgot_password(request):
#     """
#     Handle forgot password using Django ORM
#     """
#     def send_reset_email(email_to):
#         """Send password reset email"""
#         try:
#             # Generate token (you'll need to implement token generation)
#             from .reset_token_handler import TokenHandler
#             # This is a placeholder - you'll need to implement proper token generation
#             token = f"reset_token_for_{email_to}"  # Replace with actual token generation
#             reset_url = f"{settings.DOMAIN_URL_}reset_password/{token}"
#             body = f"Click the following link to reset your password\n{reset_url}"
            
#             response = send_mail("Reset Password", body, settings.EMAIL_FROM, [email_to])
            
#             if response == 1:
#                 token_handler = TokenHandler()
#                 token_handler.save_session_token(token=token)
#                 return True
#             return False
#         except Exception as e:
#             print(f"Error sending reset email: {e}")
#             return False
    
#     if request.method == "POST":
#         user_email = request.data.get('email') or request.POST.get('email')
        
#         if not user_email:
#             return render(
#                 request,
#                 "volt_forgot_password.html",
#                 context={"error_message": "Email is required!"},
#             )
        
#         try:
#             user = CDUser.objects.get(email=user_email)
            
#             if not user.is_active:
#                 return render(
#                     request,
#                     "volt_forgot_password.html",
#                     context={
#                         "error_message": "This account is inactive. Please contact admin."
#                     },
#                 )
            
#             success_message = "Please check your email for further instructions..."
#             if send_reset_email(user_email):
#                 return render(
#                     request,
#                     "volt_forgot_password.html",
#                     context={"success_message": success_message},
#                 )
#             else:
#                 error = "Failed to reset password!"
#                 return render(
#                     request,
#                     "volt_forgot_password.html",
#                     context={"error_message": error},
#                 )
                
#         except CDUser.DoesNotExist:
#             error = "Invalid email!"
#             return render(
#                 request,
#                 "volt_forgot_password.html",
#                 context={"error_message": error},
#             )
#         except Exception as e:
#             print(f"Error in forgot_password: {e}")
#             error = "Failed to reset password!"
#             return render(
#                 request,
#                 "volt_forgot_password.html",
#                 context={"error_message": error},
#             )
    
#     elif request.method == "GET":
#         return render(request, "volt_forgot_password.html")


# @api_view(['GET', 'POST'])
# def reset_password(request, token):
#     """
#     Handle password reset using Django ORM
#     """
#     try:
#         # Validate token and find user (you'll need to implement proper token validation)
#         from .reset_token_handler import TokenHandler
#         token_handler = TokenHandler()
        
#         # This is a placeholder - implement proper token validation
#         user_found = False
#         user = None
        
#         # For now, extracting email from token (replace with proper implementation)
#         if token.startswith("reset_token_for_"):
#             email = token.replace("reset_token_for_", "")
#             try:
#                 user = CDUser.objects.get(email=email)
#                 user_found = True
#             except CDUser.DoesNotExist:
#                 user_found = False
        
#         if request.method == "GET":
#             if user_found and token_handler.is_token_present(token=token):
#                 return render(request, "volt_reset_password.html", context={"token": token})
#             else:
#                 return HttpResponseNotFound("<h1>Page not found</h1>")
        
#         elif request.method == "POST":
#             new_password = request.data.get('newpassword') or request.POST.get('newpassword')
#             new_password_conf = request.data.get('newpasswordconfirm') or request.POST.get('newpasswordconfirm')
            
#             if not new_password or not new_password_conf:
#                 error = "Both password fields are required!"
#                 return render(
#                     request,
#                     "volt_reset_password.html",
#                     context={"error_message": error, "token": token},
#                 )
            
#             if user_found:
#                 if new_password == new_password_conf:
#                     try:
#                         user.set_password(new_password)
#                         user.save()
#                         success_message = "Password updated successfully!"
#                         token_handler.delete_token(token=token)
#                         return render(
#                             request,
#                             "volt_login.html",
#                             context={"success_message": success_message},
#                         )
#                     except Exception as e:
#                         print(f"Error resetting password: {e}")
#                         error_message = "Failed to update password!"
#                         return render(
#                             request,
#                             "volt_reset_password.html",
#                             context={"error_message": error_message, "token": token},
#                         )
#                 else:
#                     error = "New entered passwords don't match!"
#                     return render(
#                         request,
#                         "volt_reset_password.html",
#                         context={"error_message": error, "token": token},
#                     )
#             else:
#                 error = "Invalid token!"
#                 return render(
#                     request, 
#                     "volt_reset_password.html", 
#                     context={"error_message": error, "token": token}
#                 )
                
#     except Exception as e:
#         print(f"Error in reset_password: {e}")
#         return HttpResponseNotFound("<h1>Page not found</h1>")


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def add_announcement(request):
#     """
#     Add new announcement using Django ORM
#     """
#     try:
#         if not (is_user_active(request.user) and request.user.role == CDUser.ROLES.ADMIN):
#             return JsonResponse({
#                 "announcement_error_message": "You are not authorized to perform this action!"
#             }, status=403)
        
#         new_announcement = request.data.get('new_announcement') or request.POST.get('new_announcement')
        
#         if not new_announcement:
#             return JsonResponse({
#                 "announcement_error_message": "Announcement text is required!"
#             }, status=400)
        
#         # Replace newlines with |_| for storage (maintaining original format)
#         announcement_text = new_announcement.replace("\n", "|_|")
        
#         # Create announcement
#         Announcement.objects.create(announcement=announcement_text)
        
#         return JsonResponse({
#             "announcement_success_message": "announcement_success_message"
#         })
        
#     except Exception as e:
#         print(f"Error in add_announcement: {e}")
#         return JsonResponse({
#             "announcement_error_message": "You are not authorized to perform this action!"
#         }, status=500)


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_dashboard_data(request, section):
#     """
#     Get dashboard data using Django ORM
#     """
#     try:
#         if not is_user_active(request.user):
#             return JsonResponse({"message": "Authentication Failed!"}, status=401)
        
#         requesting_user_role = request.user.role
        
#         # Build filter based on user role
#         filter_kwargs = {}
#         if requesting_user_role == CDUser.ROLES.NORMAL:
#             filter_kwargs['created_by'] = request.user
#         elif requesting_user_role == CDUser.ROLES.INTERMEDIATE:
#             children = get_users_belongs_to(request.user)
#             children.append(request.user.email)
#             filter_kwargs['created_by__email__in'] = children
#         elif requesting_user_role == CDUser.ROLES.MEMBER:
#             leader = get_leader(request.user.email)
#             if leader:
#                 filter_kwargs['created_by__email'] = leader
        
#         if section == 2:  # Announcements
#             announcements = Announcement.objects.all().order_by('-created_at')
            
#             headers = "<th>Announcement</th><th>Time</th>"
#             body = ""
#             for announcement in announcements:
#                 # Replace |_| with <br> for display
#                 announcement_text = announcement.announcement.replace("|_|", "<br>")
#                 body += f"<tr><td>{announcement_text}</td><td>{announcement.created_at}</td></tr>"
            
#             table = f"""<table class="table table-hover" id="data_table">
#                 <thead>
#                     {headers}
#                 </thead>
#                 <tbody>
#                     {body}
#                 </tbody>
#                 </table>
#             """
#             return JsonResponse({
#                 "table": table, 
#                 "requesting_user_role": requesting_user_role
#             })
        
#         elif section == 3:  # Top Stores Chart Data
#             # This would require royalties data - placeholder for now
#             # You'll need to implement this based on your Royalties model
#             data = {
#                 "labels": ["Store 1", "Store 2", "Store 3", "Store 4", "Store 5"],
#                 "datasets": [{
#                     "label": "Top Stores",
#                     "data": [100, 200, 150, 300, 250],
#                     "backgroundColor": [
#                         "#EEB15D", "#A1A955", "#5D9764", "#297F71", "#171D27"
#                     ],
#                     "hoverOffset": 4,
#                 }],
#             }
#             return JsonResponse({"chart_data": data})
        
#         elif section == 4:  # Latest Releases
#             releases = Release.objects.filter(
#                 published=True,
#                 **filter_kwargs
#             ).order_by('-published_at')[:5]
            
#             response_html = ""
#             for release in releases:
#                 cover_art_path = release.cover_art_url or f"/static/img/{settings.LOGO.get('light', 'default.png')}"
#                 response_html += f"""
#                     <div class="col-lg-3 col-md-6 col-sm-12 col-xs-12 mb-4">
#                         <div class="card" style="width: 18rem;">
#                             <img src="{cover_art_path}" class="card-img-top">
#                             <div class="card-body">
#                                 <h5 class="card-title">{release.title}</h5>
#                                 <a href="/releases/release_info/{release.id}" class="btn btn-primary">View Release</a>
#                             </div>
#                         </div>
#                     </div>
#                 """
#             return JsonResponse({"latest_releases": response_html})
        
#         elif section == 5:  # Top Languages Chart Data
#             # Placeholder - implement based on your royalties data
#             data = {
#                 "labels": ["English", "Hindi", "Spanish", "French", "German"],
#                 "datasets": [{
#                     "label": "Top Languages",
#                     "data": [300, 250, 200, 150, 100],
#                     "backgroundColor": [
#                         "#EEB15D", "#A1A955", "#5D9764", "#297F71", "#171D27"
#                     ],
#                     "hoverOffset": 4,
#                 }],
#             }
#             return JsonResponse({"chart_data": data})
        
#         elif section == 6:  # Audio Streams Chart Data
#             # Placeholder - implement based on your royalties data
#             data = {
#                 "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
#                 "datasets": [{
#                     "label": "Audio Streams",
#                     "data": [1000, 1200, 1100, 1300, 1250, 1400],
#                     "backgroundColor": "rgba(17,25,39,0.4)",
#                     "fill": True,
#                     "borderWidth": 4,
#                     "borderColor": "#111927",
#                     "hoverOffset": 4,
#                 }],
#             }
#             return JsonResponse({"chart_data": data})
        
#         else:
#             return JsonResponse({"message": "Invalid request!"}, status=400)
            
#     except Exception as e:
#         print(f"Error in get_dashboard_data: {e}")
#         return JsonResponse({"message": "Invalid request!"}, status=500)


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_dashboard(request):
#     """
#     Get dashboard page using Django ORM
#     """
#     try:
#         if not is_user_active(request.user):
#             return HttpResponseNotFound("<h1>Authentication failed!</h1>")
        
#         requesting_user_role = request.user.role
        
#         # Build filter based on user role
#         filter_kwargs = {}
#         if requesting_user_role == CDUser.ROLES.NORMAL:
#             filter_kwargs['created_by'] = request.user
#         elif requesting_user_role == CDUser.ROLES.INTERMEDIATE:
#             children = get_users_belongs_to(request.user)
#             children.append(request.user.email)
#             filter_kwargs['created_by__email__in'] = children
#         elif requesting_user_role == CDUser.ROLES.MEMBER:
#             leader = get_leader(request.user.email)
#             if leader:
#                 filter_kwargs['created_by__email'] = leader
        
#         # Get release counts
#         releases = Release.objects.filter(**filter_kwargs)
#         total_releases = releases.count()
#         published = releases.filter(published=True).count()
#         draft = releases.filter(published=False).count()
        
#         return render(
#             request,
#             "volt_dashboard.html",
#             context={
#                 "requesting_user_role": requesting_user_role,
#                 "logged_user_name": str(request.user.email).split("@")[0],
#                 "username": request.user.email,
#                 "total_releases_count": total_releases,
#                 "published_releases_count": published,
#                 "draft_releases_count": draft,
#             },
#         )
        
#     except Exception as e:
#         print(f"Error in get_dashboard: {e}")
#         return HttpResponseNotFound("<h1>Invalid Request</h1>")


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def main_page(request):
#     """
#     Main admin page using Django ORM
#     """
#     try:
#         if not (is_user_active(request.user) and request.user.is_superuser):
#             return HttpResponseNotFound("<h1>Authentication failed!</h1>")
        
#         requesting_user_role = request.user.role
        
#         # Import navigation
#         from .processor import admin, intermediate
#         navigation = (
#             admin.navigation if requesting_user_role == CDUser.ROLES.ADMIN 
#             else intermediate.navigation
#         )
        
#         return render(
#             request,
#             "volt_admin.html",
#             context={
#                 "navigation": get_navigation("home", navigation),
#                 "requesting_user_role": requesting_user_role,
#                 "username": request.user.email,
#                 "is_show_due_balance": True,
#             },
#         )
        
#     except Exception as e:
#         print(f"Error in main_page: {e}")
#         return HttpResponseNotFound("<h1>Authentication failed!</h1>")


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def royalty_stats(request):
#     """
#     Display royalty stats page using Django ORM
#     """
#     try:
#         if not is_user_active(request.user):
#             return HttpResponse("<h2>Authentication Failed!</h2>", status=401)
        
#         requesting_user_role = request.user.role
        
#         # Import navigation
#         from .processor import normal
        
#         return render(
#             request,
#             "volt_normal.html",
#             context={
#                 "username": request.user.email,
#                 "navigation": get_navigation("royalty_stats", normal.navigation),
#                 "requesting_user_role": requesting_user_role,
#                 "is_show_due_balance": True,
#             },
#         )
        
#     except Exception as e:
#         print(f"Error in royalty_stats: {e}")
#         return HttpResponse("<h2>Authentication Failed!</h2>", status=500)


# @api_view(['GET'])
# def redirect_main(request):
#     """
#     Redirect to login page
#     """
#     return redirect("login_page")
