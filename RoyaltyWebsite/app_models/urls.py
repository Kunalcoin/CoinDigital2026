from django.urls import path

from rest_framework import permissions

from . import views

# Swagger documentation setup
urlpatterns = [
    
    # Dashboard URLs
    # path('dashboard/', views.user_dashboard, name='dashboard'),
    
    # Artist URLs
    # path('artists/', views.artist_list, name='artist-list'),
    # path('artists/<int:artist_id>/', views.artist_detail, name='artist-detail'),
    
    # # Track URLs
    # path('tracks/', views.track_list, name='track-list'),
    # path('tracks/<int:track_id>/', views.track_detail, name='track-detail'),
    
    # # Release URLs
    # path('releases/', views.release_list, name='release-list'),
    # path('releases/<int:release_id>/', views.release_detail, name='release-detail'),
    
    # # Royalty URLs
    # path('royalties/summary/', views.royalty_summary, name='royalty-summary'),
    
    # # Payment URLs
    # path('payments/history/', views.payment_history, name='payment-history'),
    
    # # Request URLs
    # path('requests/', views.request_list, name='request-list'),
]
