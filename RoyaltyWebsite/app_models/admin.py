from django.contrib import admin
from django.contrib.admin.filters import DateFieldListFilter
from RoyaltyWebsite.admin import royalties_admin

from .models import (
    Artist,
    CDUser,
    DueAmount,
    Label,
    Ratio,
    RelatedArtists,
    Release,
    Request,
    Track,
    UniqueCode,
    Payment,
    Announcement,
    Royalties,
    Sharing,
)


class CDUserAdmin(admin.ModelAdmin):
    list_display = [
        "email",
        "role",
        "parent",
        "created_at",
    ]
    list_filter = (
        "email",
        "role",
        ("created_at", DateFieldListFilter),
    )
    search_fields = ("email",)
    ordering = ("-created_at",)


class RatioAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "stores",
        "youtube",
        "status",
        "created_at",
    ]
    list_filter = (
        "user",
        "status",
    )
    search_fields = ("user",)
    ordering = ("-created_at",)


class DueAmountAdmin(admin.ModelAdmin):
    list_display = ["user", "amount", "updated_at"]
    list_filter = ("user",)
    search_fields = ("user",)
    ordering = ("-updated_at",)


class RequestAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "title",
        "status",
        "created_at",
    ]
    list_filter = (
        "user",
        "status",
    )
    search_fields = ("user", "title", "description", "status")
    ordering = ("-created_at",)


class ArtistAdmin(admin.ModelAdmin):
    list_display = ["user", "name", "created_at"]
    list_filter = ("user", "name")
    search_fields = ("user", "name")
    ordering = ("-created_at",)


class RelatedArtistAdmin(admin.ModelAdmin):
    list_display = ["artist", "role", "release", "track", "created_at"]
    list_filter = ("role",)
    search_fields = ("artist", "role", "release", "track")
    ordering = ("-created_at",)


class ReleaseAdmin(admin.ModelAdmin):
    list_display = ["title", "created_by", "upc", "published", "created_at"]
    list_filter = ("created_by", "published")
    search_fields = ("title", "created_by", "upc")
    ordering = ("-created_at",)


class TrackAdmin(admin.ModelAdmin):
    list_display = ["title", "created_by", "isrc", "created_at"]
    list_filter = ("created_by",)
    search_fields = ("title", "created_by", "isrc")
    ordering = ("-created_at",)


class LabelAdmin(admin.ModelAdmin):
    list_display = ["label", "user", "created_at"]
    list_filter = ("user",)
    search_fields = ("label", "user")
    ordering = ("-created_at",)


class UniqueCodeAdmin(admin.ModelAdmin):
    list_display = ["code", "type", "assigned", "created_at"]
    list_filter = ("type", "assigned")
    search_fields = ("code",)
    ordering = ("-created_at",)


class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "username",
        "date_of_payment",
        "amount_paid",
        "tds",
        "tds_percentage",
        "sent_to_name",
        "transfer_id",
    ]
    list_filter = (
        "username",
        ("date_of_payment", DateFieldListFilter),
        "source_account",
    )
    search_fields = ("username", "sent_to_name", "transfer_id", "sent_to_account_number")
    ordering = ("-date_of_payment",)


class AnnouncementAdmin(admin.ModelAdmin):
    list_display = [
        "announcement_id",
        "announcement",
        "created_at",
    ]
    search_fields = ("announcement",)
    ordering = ("-created_at",)


class RoyaltiesAdmin(admin.ModelAdmin):
    list_display = [
        "royalty_id",
        "start_date",
        "end_date",
        "country",
        "type",
        "channel",
        "isrc",
        "net_total_INR",
    ]
    list_filter = (
        ("start_date", DateFieldListFilter),
        ("end_date", DateFieldListFilter),
        "country",
        "type",
        "channel",
    )
    search_fields = ("isrc", "country", "channel")
    ordering = ("-confirmed_date",)


class SharingAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "store_ratio",
        "youtube_ratio",
        "payout_threshold",
        "is_active",
        "created_at",
    ]
    list_filter = (
        "user",
        "is_active",
    )
    search_fields = ("user__email",)
    ordering = ("-created_at",)


royalties_admin.register(CDUser, CDUserAdmin)
royalties_admin.register(Ratio, RatioAdmin)
royalties_admin.register(DueAmount, DueAmountAdmin)
royalties_admin.register(Request, RequestAdmin)
royalties_admin.register(Artist, ArtistAdmin)
royalties_admin.register(RelatedArtists, RelatedArtistAdmin)
royalties_admin.register(Release, ReleaseAdmin)
royalties_admin.register(Track, TrackAdmin)
royalties_admin.register(Label, LabelAdmin)
royalties_admin.register(UniqueCode, UniqueCodeAdmin)
royalties_admin.register(Payment, PaymentAdmin)
royalties_admin.register(Announcement, AnnouncementAdmin)
royalties_admin.register(Royalties, RoyaltiesAdmin)
royalties_admin.register(Sharing, SharingAdmin)
