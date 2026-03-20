from django.contrib.auth.models import AbstractBaseUser
from django.db import models
from django.utils import timezone

from .constants import COUNTRIES, LANGUAGES, GENRES, ARTIST_ROLES
from .managers import CDUserManager


class CDUser(AbstractBaseUser):
    # Static
    class ROLES(models.TextChoices):
        ADMIN = "admin", "Admin"
        INTERMEDIATE = "intermediate", "Intermediate"
        NORMAL = "normal", "Normal"
        MEMBER = "member", "Member"

    COUNTRY_CHOICES = [(country, country) for country in COUNTRIES]
    LANGUAGE_CHOICES = [(language, language) for language in LANGUAGES]

    # Fields
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    first_name = models.CharField("First Name", max_length=100)
    last_name = models.CharField("Last Name", max_length=100)
    role = models.CharField(
        max_length=20, choices=ROLES.choices, default=ROLES.NORMAL, null=False
    )
    country = models.CharField(
        "Country",
        max_length=255,
        choices=COUNTRY_CHOICES,
        null=False,
        default=COUNTRIES[0],
    )
    language = models.CharField(
        "Language", max_length=255, choices=LANGUAGE_CHOICES, default=LANGUAGES[0]
    )
    city = models.CharField("City", max_length=512, default="")
    street = models.CharField("Street", max_length=512, default="")
    postal_code = models.CharField("Postal Code", max_length=255, default="")
    contact_phone = models.CharField("Contact Phone", max_length=255, null=False)
    company = models.CharField("Company", max_length=255, default="")
    company_name = models.CharField("Company Name", max_length=255, default="")
    fiskal_id_number = models.CharField("Fiskal ID Number", max_length=255, default="")
    country_phone = models.CharField("Country Phone", max_length=255, default="")
    company_contact_phone = models.CharField(
        "Company Contact Phone", max_length=255, null=False
    )
    pan = models.CharField("PAN", max_length=255, null=False)
    gst_number = models.CharField("GST Number", max_length=255, default="")
    account_name = models.CharField("Account Name", max_length=255, default="")
    account_number = models.CharField("Account Number", max_length=255, default="")
    ifsc = models.CharField("IFSC", max_length=255, default="")
    sort_code = models.CharField("SORT Code", max_length=255, default="")
    swift_code = models.CharField("Swift Code", max_length=255, default="")
    iban = models.CharField("IBAN", max_length=255, default="")
    bank_country = models.CharField("Bank Country", max_length=255, default="")
    bank_name = models.CharField("Bank Name", max_length=255, default="")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, verbose_name="Parent")
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    objects = CDUserManager()
    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["email"]
        indexes = [
            models.Index(fields=["email"]),
        ]

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser


class Ratio(models.Model):
    # Static
    class STATUS(models.TextChoices):
        ACTIVE = "active", "Active"
        IN_ACTIVE = "inactive", "In Active"

    # Fields
    user = models.ForeignKey(
        CDUser, on_delete=models.CASCADE, null=False, related_name="ratios"
    )
    stores = models.IntegerField()
    youtube = models.IntegerField()
    sales_payout = models.IntegerField()
    sales_payout_threshold = models.IntegerField()
    status = models.CharField(
        max_length=255, choices=STATUS.choices, default=STATUS.ACTIVE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.email

    class Meta:
        verbose_name = "Ratio"
        verbose_name_plural = "Ratios"


class DueAmount(models.Model):
    # Fields
    user = models.ForeignKey(
        CDUser,
        on_delete=models.CASCADE,
        null=False,
        related_name="due_amounts",
        verbose_name="User",
        unique=True,
    )
    amount = models.FloatField("Amount Due")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.email

    class Meta:
        verbose_name = "Due Amount"
        verbose_name_plural = "Due Amounts"


class Request(models.Model):
    # Status
    class STATUS(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        IN_REVIEW = "IN REVIEW", "IN REVIEW"
        CLOSED = "CLOSED", "CLOSED"

    # Fields
    user = models.ForeignKey(
        CDUser,
        on_delete=models.CASCADE,
        null=False,
        related_name="requests",
        verbose_name="User",
    )
    title = models.CharField("Title", max_length=100, default="")
    description = models.CharField("Description", max_length=5000, default="")
    feedback = models.CharField("Admin Feedback", max_length=5000, default="")
    status = models.CharField(
        "Status", max_length=255, choices=STATUS.choices, default=STATUS.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.email

    class Meta:
        verbose_name = "Request"
        verbose_name_plural = "Requests"


class UniqueCode(models.Model):
    class TYPE(models.TextChoices):
        UPC = "upc", "UPC"
        ISRC = "isrc", "ISRC"

    type = models.CharField("Type", max_length=20, choices=TYPE.choices, null=False)
    code = models.CharField("Code", max_length=50, null=False, unique=True)
    assigned = models.BooleanField("Is Assigned", default=False, null=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "Unique Code"
        verbose_name_plural = "Unique Codes"


class Label(models.Model):
    user = models.ForeignKey(
        CDUser, on_delete=models.CASCADE, null=False, verbose_name="User"
    )
    label = models.CharField("Label", max_length=255, null=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.label

    class Meta:
        verbose_name = "Label"
        verbose_name_plural = "Labels"


class Release(models.Model):
    # Static
    class ALBUM_FORMAT(models.TextChoices):
        SINGLE = "single", "Single"
        EP = "ep", "EP"
        ALBUM = "album", "Album"

    class PRICE_CATEGORY(models.TextChoices):
        MID = "mid", "Mid"
        BUDGET = "budget", "Budget"
        FULL = "full", "Full"
        PREMIUM = "premium", "Premium"

    class LICENSE_TYPE(models.TextChoices):
        COPYRIGHT = "copyright", "Copyright"
        CREATIVE_COMMON = "creative_common", "Creative Common"

    # Fields
    title = models.CharField("Title", max_length=255, null=False)
    cover_art_url = models.CharField("Cover Art", max_length=1024, default="")
    remix_version = models.CharField("Remix Version", max_length=255, default="")
    primary_genre = models.CharField(
        "Primary Genre",
        max_length=512,
        choices=[(genre, genre) for genre in GENRES],
        null=False,
        default=GENRES[0],
    )
    secondary_genre = models.CharField(
        "Secondary Genre",
        max_length=512,
        choices=[(genre, genre) for genre in GENRES],
        default=""
    )
    language = models.CharField(
        "Language",
        max_length=512,
        choices=[(language, language) for language in LANGUAGES],
        null=False,
        default=LANGUAGES[0],
    )
    album_format = models.CharField(
        "Album Format",
        max_length=20,
        choices=ALBUM_FORMAT.choices,
        null=False,
        default=ALBUM_FORMAT.SINGLE,
    )
    upc = models.CharField("UPC", max_length=50, default="")
    reference_number = models.CharField("Reference Number", max_length=255, default="")
    grid = models.CharField("GRID", max_length=255, default="")
    description = models.TextField("Description", default="")
    created_by = models.ForeignKey(
        CDUser, on_delete=models.DO_NOTHING, null=False, verbose_name="Created by"
    )
    published = models.BooleanField("Is Published", default=False)
    takedown_requested = models.BooleanField("Is Takedown Requested", default=False)
    published_at = models.DateTimeField("Published At", null=True)
    # License fields
    price_category = models.CharField(
        "Price Category",
        max_length=100,
        choices=PRICE_CATEGORY.choices,
        default=PRICE_CATEGORY.BUDGET,
    )
    digital_release_date = models.DateField("Digital Release Date", null=True)
    original_release_date = models.DateField("Original Release Date", null=True)
    license_type = models.CharField(
        "License Type",
        max_length=50,
        choices=LICENSE_TYPE.choices,
        default=LICENSE_TYPE.COPYRIGHT,
    )
    license_holder_year = models.CharField("License Holder Year", max_length=4, default="")
    license_holder_name = models.CharField("License Holder Name", max_length=255, default="")
    copyright_recording_year = models.CharField(
        "Copyright Recording Year", max_length=255, default=""
    )
    copyright_recording_text = models.CharField(
        "Copyright Recording Text", max_length=255, default=""
    )
    territories = models.CharField(
        "Territories", max_length=255, default="Entire World"
    )
    label = models.ForeignKey(
        Label, on_delete=models.DO_NOTHING, max_length=255, verbose_name="Label", null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Release"
        verbose_name_plural = "Releases"


class Track(models.Model):
    # Static
    class EXPLICIT_LYRICS(models.TextChoices):
        NOT_EXPLICIT = "not_explicit", "Not Explicit"
        EXPLICIT = "explicit", "Explicit"
        CLEANED = "cleaned", "Cleaned"

    # Fields
    release = models.ForeignKey(
        Release, on_delete=models.CASCADE, null=False, verbose_name="Release"
    )
    remix_version = models.CharField("Remix Version", max_length=255)
    title = models.CharField("Title", max_length=1024, null=False)
    created_by = models.ForeignKey(
        CDUser, on_delete=models.DO_NOTHING, null=False, verbose_name="Created by"
    )
    audio_track_url = models.CharField("Audio Track", max_length=1024)
    primary_genre = models.CharField(
        "Primary Genre", max_length=512, choices=[(genre, genre) for genre in GENRES]
    )
    secondary_genre = models.CharField(
        "Secondary Genre", max_length=512, choices=[(genre, genre) for genre in GENRES], default="", null=True
    )
    isrc = models.CharField("ISRC", max_length=255)
    iswc = models.CharField("ISWC", max_length=255, default="")
    publishing_rights_owner = models.CharField(
        "Publishing Rights Owner", max_length=255, default=""
    )
    publishing_rights_year = models.CharField("Publishing Rights Year", max_length=4, default="")
    lyrics = models.TextField("Lyrics", null=True)
    explicit_lyrics = models.CharField(
        "Explicit Lyrics",
        max_length=20,
        choices=EXPLICIT_LYRICS.choices,
        default=EXPLICIT_LYRICS.NOT_EXPLICIT,
        null=False,
    )
    language = models.CharField(
        "Language",
        max_length=512,
        choices=[(language, language) for language in LANGUAGES],
        null=False,
    )
    available_separately = models.BooleanField("Is Available Separately", default=False)
    start_point = models.CharField("Start Point", max_length=10)
    notes = models.TextField("Notes")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Track"
        verbose_name_plural = "Tracks"


class Artist(models.Model):
    user = models.ForeignKey(
        CDUser, on_delete=models.DO_NOTHING, null=False, verbose_name="User"
    )
    name = models.CharField("Full Name", max_length=255)
    first_name = models.CharField("First Name", max_length=100, default="")
    last_name = models.CharField("Last Name", max_length=100, default="")
    apple_music_id = models.CharField("Apple Music ID", max_length=1024, default="")
    spotify_id = models.CharField("Spotify ID", max_length=1024, default="")
    youtube_username = models.CharField("Youtube Username", max_length=1024, default="")
    soundcloud_page = models.CharField("Soundcloud Page", max_length=1024, default="")
    facebook_page = models.CharField("Facebook Page", max_length=1024, default="")
    x_username = models.CharField("X Username", max_length=1024, default="")
    website = models.CharField("Website", max_length=1024, default="")
    biography = models.CharField("Biography", max_length=1024, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Artist"
        verbose_name_plural = "Artists"


class RelatedArtists(models.Model):
    release = models.ForeignKey(
        Release,
        on_delete=models.DO_NOTHING,
        related_name="release_artists",
        null=True,
        verbose_name="Release",
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.DO_NOTHING,
        related_name="track_artists",
        verbose_name="Track",
        null=True,
    )
    relation_key = models.CharField(
        "Relation Key",
        max_length=30,
        choices=[("release", "release"), ("track", "track")],
    )
    artist = models.ForeignKey(
        Artist,
        on_delete=models.DO_NOTHING,
        related_name="related_records",
        verbose_name="Artist",
    )
    role = models.CharField(
        "Role",
        choices=[(role, role) for role in ARTIST_ROLES],
        max_length=250,
        null=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.role} | {self.artist.name}"

    class Meta:
        verbose_name = "Related Artist"
        verbose_name_plural = "Related Artists"

class Announcement(models.Model):
    # Fields
    announcement_id = models.AutoField("Announcement ID", primary_key=True,unique=True)
    announcement = models.TextField("Announcement", null=False)
   
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
   

    class Meta:
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ['-created_at']
       

    def __str__(self):
        return self.announcement
    

class Payment(models.Model):
    
    username = models.CharField("Username", max_length=255)
    date_of_payment = models.DateField("Payment Date")
    amount_paid = models.FloatField("Amount Paid")
    tds = models.FloatField("TDS")
    tds_percentage = models.BigIntegerField("TDS Percentage")
    source_account = models.CharField("Source Account", max_length=400)
    sent_to_name = models.CharField("Recipient Name", max_length=400)
    sent_to_account_number = models.CharField("Account Number", max_length=400)
    sent_to_ifsc_code = models.CharField("IFSC Code", max_length=400)
    transfer_id = models.CharField("Transfer ID", max_length=400)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
   
        indexes = [
            models.Index(fields=['username'], name='idx_username'),
        ]

    def __str__(self):
        return f"{self.username} - {self.amount_paid} ({self.date_of_payment})"

class Royalties(models.Model):
    royalty_id = models.AutoField("Royalty ID", primary_key=True,unique=True)
    start_date = models.DateField("Start Date")
    end_date = models.DateField("End Date")
    country = models.TextField("Country")
    currency = models.TextField("Currency")
    type = models.TextField("Type")
    units = models.BigIntegerField("Units")
    unit_price = models.FloatField("Unit Price")
    gross_total = models.FloatField("Gross Total")
    channel_costs = models.FloatField("Channel Costs")
    taxes = models.FloatField("Taxes")
    net_total = models.FloatField("Net Total")
    currency_rate = models.FloatField("Currency Rate")
    net_total_INR = models.FloatField("Net Total INR")
    channel = models.TextField("Channel")
    isrc = models.CharField("ISRC", max_length=50)
    gross_total_INR = models.FloatField("Gross Total INR")
    other_costs_INR = models.FloatField("Other Costs INR")
    channel_costs_INR = models.FloatField("Channel Costs INR")
    taxes_INR = models.FloatField("Taxes INR")
    gross_total_client_currency = models.FloatField("Gross Total Client Currency")
    other_costs_client_currency = models.FloatField("Other Costs Client Currency")
    channel_costs_client_currency = models.FloatField("Channel Costs Client Currency")
    taxes_client_currency = models.FloatField("Taxes Client Currency")
    net_total_client_currency = models.FloatField("Net Total Client Currency")
    confirmed_date = models.DateField("Confirmed Date")

    class Meta:
        verbose_name = "Royalty"
        verbose_name_plural = "Royalties"
        indexes = [
            # The PRIMARY index is automatically created by Django for the primary_key field
            models.Index(fields=['isrc'], name='idx_royalties_isrc'),
        ]

    def __str__(self):
        return f"Royalty {self.royalty_id} - {self.isrc} ({self.start_date} to {self.end_date})"


class Sharing(models.Model):
    # Fields
    user = models.ForeignKey(
        CDUser,
        on_delete=models.CASCADE,
        null=False,
        related_name="shares",
        verbose_name="User"
    )
    store_ratio = models.DecimalField("Store Revenue Share (%)", max_digits=5, decimal_places=2, null=False)
    youtube_ratio = models.DecimalField("YouTube Revenue Share (%)", max_digits=5, decimal_places=2, null=False)
    payout_threshold = models.DecimalField("Payout Threshold (INR)", max_digits=10, decimal_places=2, null=False)
    is_active = models.BooleanField("Is Active", default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sharing"
        verbose_name_plural = "Shares"
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.email} - Store: {self.store_ratio}%, YT: {self.youtube_ratio}%"
