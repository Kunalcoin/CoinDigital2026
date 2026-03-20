from django.urls import path
from . import views

urlpatterns = [
    path('releases', views.releases,name='releases'),


    path('releases/delivered/', views.delivered_releases,name='delivered_releases'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('releases/pending_approval/', views.pending_approval_releases, name='pending_approval_releases'),
    path('releases/paginated/<str:request_type>/', views.releases_paginated,name='releases_paginated'), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅

    path('releases/release_info/<str:primary_uuid>', views.release_info, name="release_info"),
    path('releases/licenses_info/<str:primary_uuid>', views.licenses_info, name="licenses_info"),
    path('releases/tracks_info/<str:primary_uuid>', views.tracks_info, name="tracks_info"),
    path('releases/tracks_info/<str:primary_uuid>/catalog_tracks/', views.catalog_tracks, name="catalog_tracks"),
    path('releases/tracks_info/<str:primary_uuid>/add_from_catalog/', views.add_from_catalog, name="add_from_catalog"),
    path('releases/tracks_info/<str:primary_uuid>/reorder_tracks/', views.reorder_tracks, name="reorder_tracks"),
    path('releases/tracks_info/<str:primary_uuid>/track/<str:primary_track_uuid>', views.single_tracks_info, name="single_tracks_info"),
    path('releases/tracks_info/check_audio_meta_info/<str:primary_uuid_with_extension>', views.check_audio_meta_info, name="check_audio_meta_info"),
    path('releases/preview_distribute_info/<str:primary_uuid>', views.preview_distribute_info, name="preview_distribute_info"),
    # Admin: DDEX package status (must be before other releases/<uuid>/... to avoid 404)
    path('releases/<str:primary_uuid>/ddex-package-status/', views.ddex_package_status, name="ddex_package_status"),
    path('releases/<str:primary_uuid>/submit-for-approval/', views.submit_for_approval, name="submit_for_approval"),
    path('releases/<str:primary_uuid>/approve/', views.approve_release, name="approve_release"),
    path('releases/bulk_approve/', views.bulk_approve_releases, name="bulk_approve_releases"),
    path('releases/<str:primary_uuid>/reject/', views.reject_release, name="reject_release"),
    path('releases/<str:primary_uuid>/ddex-deliver-audiomack/', views.ddex_deliver_audiomack, name="ddex_deliver_audiomack"),
    path('releases/<str:primary_uuid>/ddex-deliver-apple-music/', views.ddex_deliver_apple_music, name="ddex_deliver_apple_music"),
    path('releases/<str:primary_uuid>/ddex-takedown-apple-music/', views.ddex_takedown_apple_music, name="ddex_takedown_apple_music"),
    path('releases/<str:primary_uuid>/ddex-deliver-all-stores/', views.ddex_deliver_all_stores, name="ddex_deliver_all_stores"),
    path('releases/<str:primary_uuid>/ddex-takedown-all-stores/', views.ddex_takedown_all_stores, name="ddex_takedown_all_stores"),
    path('releases/<str:primary_uuid>/ddex-distribution-jobs/', views.ddex_distribution_jobs, name="ddex_distribution_jobs"),
    path('releases/add_new_label/<str:data>', views.add_new_label, name="add_new_label"),
    path('releases/add_new_artist/<str:artist_name>/', views.add_new_artist, name='add_new_artist'),
    path('releases/update_release_title/<str:primary_uuid>/<str:new_release_title>', views.update_release_title, name="update_release_title"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅

    path('releases/file_uploader/<str:primary_uuid>', views.file_uploader, name="file_uploader"),
    path(
        'releases/file_uploader/<str:primary_uuid>/<str:track_uuid>/atmos/',
        views.file_uploader_atmos_track,
        name="file_uploader_atmos_track",
    ),
    path('releases/upload_releases', views.upload_releases, name='upload_releases'),
    path('releases/release_report', views.release_report, name="release_report"),
    
    path('releases/takedown/<str:takedown_primary_uuid>/<str:takedown_upc>/<str:takedown_requester>/', views.takedown_request, name="takedown_request"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('releases/unpublish/<str:unpublish_primary_uuid>/<str:unpublish_upc>/<str:unpublish_requester>/', views.unpublish_release_view, name="unpublish_release_view"), # Admin working: ✅ (Not available for intermediate and normal)
    path('releases/delete/<str:primary_uuid>', views.release_delete_view, name="release_delete_view"), # Admin working: ✅ (Not available for intermediate and normal)
    
    path('releases/whitelist/<str:data>', views.claims_removal_view, name="claims_removal_view"),# Intermediate working: ✅ (Not available for normal and admin)
    
    path('releases/codes/<str:code_type>/', views.fetch_unique_codes, name='fetch_unique_codes'), # Admin working: ✅ (Not available for intermediate and normal)
    path('releases/upload/codes/', views.release_codes_upload, name="release_codes_upload"), # Admin working: ✅ (Not available for intermediate and normal)
    
    path('releases/artists/', views.artists_view, name="artists_view"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('releases/artists/list/', views.artists_list_view, name="artists_list_view"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('releases/artists/add/', views.artists_add_view, name="artists_add_view"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('releases/artists/update/<int:artist_id>/', views.artists_update_view, name="artists_update_view"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('releases/artists/<int:artist_id>/albums/', views.fetch_artist_releases_view, name="fetch_artist_releases_view"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    path('releases/artists/<int:artist_id>/tracks/', views.fetch_artist_tracks_view, name="fetch_artist_tracks_view"), # Admin working: ✅ || intermediate working: ✅ || normal working: ✅
    
    path('releases/split/admin_all_track_list/', views.admin_track_split_royalties_list, name='admin_track_split_royalties_list'),
    path('releases/split/create/', views.create_split_release_royalty, name='create_split_release_royalty'),
    path('releases/split/<int:split_id>/update/', views.update_split_release_royalty, name='update_split_release_royalty'),
    path('releases/split/list/', views.list_split_release_royalties, name='list_split_release_royalties'),
    path('releases/split/<int:split_id>/delete/', views.delete_split_release_royalty, name='delete_split_release_royalty'),
    path('releases/split/', views.split_royalty_page, name='split_royalty_page'),
    path('releases/split/track_percentage/', views.get_track_split_percentage, name='get_track_split_percentage'),
    path('releases/split/tracks/', views.get_user_tracks, name='get_user_tracks'),
    path('releases/split/tracks_with_splits/', views.user_tracks_with_splits, name='user_tracks_with_splits'),
    path('releases/split/user_list/', views.user_split_royalties_list, name='user_split_royalties_list'),
    path('releases/split/update/<int:split_id>/', views.update_split_release_royalty, name='update_split_release_royalty'),
]