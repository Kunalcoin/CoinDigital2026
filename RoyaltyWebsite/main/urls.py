from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.get_dashboard, name="dashboard"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('dashboard/data/<int:section>/', views.get_dashboard_data, name="get_dashboard_data"),  # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('due_balance/<str:username>', views.get_due_balance, name='due_balance'),# Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('refresh_due_balance/<str:username>', views.refresh_due_balance, name='refresh_due_balance'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('login_view', views.login_view, name='login_view'),  # Admin working: ✅ || intermediate working: ✅ || normal working: ✅ Updated: ✅
    path('login_page', views.login_page, name='login_page'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('logout_view', views.logout_view, name='logout_view'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('home', views.redirect_main), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('', views.redirect_main), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅ Updated: ✅
    
    path('main_page', views.main_page, name='main_page'),  # Admin working: ✅ (Not available for normal and intermediate)
    path('get_my_team', views.get_my_team, name='get_my_team'),  # normal working: ✅ (Not available for admin and intermediate)
    path('teams/', views.teams, name='teams'), # normal working: ✅ (Not available for admin and intermediate)
    
    path('manage_users_get_all_users', views.manage_users_get_all_users,name='manage_users_get_all_users'),   # Admin working: ✅ || intermediate working: ✅ (Not available for normal)
    path('manage_users', views.manage_users, name='manage_users'), # Admin working: ✅ || intermediate working: ✅ (Not available for normal)
    path('insert_user', views.insert_user, name='insert_user'), # Admin working: ✅ || intermediate working: ✅ (Not available for normal)
    path('edit_user/<int:id>/', views.edit_user, name="edit_user"), # Admin working: ✅ ✅ (Not available for normal and intermediate)
    path('change_password/', views.change_password, name='change_password'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('forgot_password/', views.forgot_password, name='forgot_password'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('reset_password/<str:token>',views.reset_password, name='reset_password'), # Working ✅
    path('custom_user/<str:username>', views.admin_view_custom_user), # Admin working: ✅
    path('remove_ownership/<int:id>',views.remove_ownership, name="remove_ownership"),  # Admin working: ✅
    path('change_ownership/<int:id>',views.change_ownership, name="change_ownership"),  # Admin working: ✅
    path('delete_member/<str:member>/', views.delete_member, name='delete_member'), # Admin working: ✅
    
    path('requests/', views.requests, name='requests'), # Working: ✅
    path('user/requests/', views.my_requests, name="my_requests"), #Working: ✅
    path('user/requests/delete/<int:request_id>/', views.delete_my_request, name="delete_my_request"), #Working: ✅
    path("users/status/edit/", views.update_user_status, name="update_user_status"),
    path('users/splitroyalitiesenabled/edit/', views.edit_splitroyalities_enabled, name='edit_splitroyalities_enabled'),
    path(
        'users/applemusicdolbyatmos/edit/',
        views.edit_apple_music_dolby_atmos_enabled,
        name='edit_apple_music_dolby_atmos_enabled',
    ),
    path("request/feedback/", views.request_feedback, name='request_feedback'), #Working: ✅
    path("announcements/add/", views.add_announcement, name="add_announcement"), # Admin working: ✅

    path('get_payments/<str:username>', views.get_payments, name='get_payments'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅    
    path('payments', views.payments, name='payments'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('refresh_payments', views.refresh_payments, name='refresh_payments'), # TODO: Need translation
    path('balance_reports/', views.get_due_reports, name='get_due_reports'), # Working for admin and available for admin only
    path('get_month_payments/<str:month>', views.get_month_payments, name='get_month_payments'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    
    path('download_royalties', views.download_royalties, name='download_royalties'), # Only normal has access Working
    path('get_royalties_data/<str:field_category>/<str:field>/<str:start_date>/<str:end_date>', views.get_royalties_data, name='get_royalties_data'), # TODO: Need conversion and verification
    
    path('fetch_track_channels', views.fetch_track_channels, name='fetch_track_channels'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('get_line_chart_and_top_tracks', views.get_line_chart_and_top_tracks, name='get_line_chart_and_top_tracks'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('royalty_stats', views.royalty_stats, name='royalty_stats'), # normal working: ✅ (Not available for admin and intermediate)

    path("analytics/", views.analytics, name="analytics"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path("analytics/<str:section>/", views.analytics_detailed, name="analytics_detailed"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅

    # path('upload_royalty', views.upload_royalty, name='upload_royalty'),
    # path('upload_metadata', views.upload_metadata, name='upload_metadata'),
    path('upload_calculation_royalties/', views.upload_calculation_royalties, name='upload_calculation_royalties'),
    path("files/uploaders/info/<str:type>/", views.file_uploaders_info, name="file_uploaders_info"),

]