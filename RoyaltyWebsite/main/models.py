from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
from main.consts import COUNTRIES, LANGUAGES
# Manager
class CDUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("parent_id", 1)
        extra_fields.setdefault("role", "admin")
        return self.create_user(email, password, **extra_fields)


# Models
class CDUser(AbstractBaseUser):
    # Static
    class ROLES(models.TextChoices):
        ADMIN = "admin", "Admin"
        INTERMEDIATE = "intermediate", "Intermediate"
        NORMAL = "normal", "Normal"
        MEMBER = "member", "Member"
        SPLIT_RECIPIENT = "split_recipient", "Split Recipient"

    COUNTRY_CHOICES = [(country, country) for country in COUNTRIES]
    LANGUAGE_CHOICES = [(language, language) for language in LANGUAGES]

    # Fields
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    split_royalties_enabled = models.BooleanField("Split Royalties", default=False)

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
    parent = models.ForeignKey("self", on_delete=models.CASCADE, verbose_name="Parent", null=True, blank=True)
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
            models.Index(fields=["email"], name="email_index"),
            models.Index(fields=["role"], name="role_index"),
            models.Index(fields=["is_active"], name="is_active_index"),
            models.Index(fields=["is_superuser"], name="is_superuser_index"),
            models.Index(fields=["is_staff"], name="is_staff_index"),
            models.Index(fields=["split_royalties_enabled"], name="split_royalties_enabled_index"),
            models.Index(fields=["country"], name="country_index"),
            models.Index(fields=["language"], name="language_index"),
            # Analytics optimization indexes
            models.Index(fields=["parent"]),
            models.Index(fields=["date_joined"]),
            models.Index(fields=["role", "is_active"]),
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
        indexes = [
            models.Index(fields=["stores"]),
            models.Index(fields=["youtube"]),
            models.Index(fields=["sales_payout"]),
            models.Index(fields=["sales_payout_threshold"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
            # Analytics optimization indexes
            models.Index(fields=["user"]),
        ]


class DueAmount(models.Model):
    # Fields
    user = models.OneToOneField(
        CDUser,
        on_delete=models.CASCADE,
        null=False,
        related_name="due_amounts",
        verbose_name="User",
    )
    amount = models.FloatField("Amount Due")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.email

    class Meta:
        verbose_name = "Due Amount"
        verbose_name_plural = "Due Amounts"
        indexes = [
            models.Index(fields=["amount"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
            # Analytics optimization indexes
            models.Index(fields=["user"]),
        ]

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
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
            # Analytics optimization indexes
            models.Index(fields=["user"]),
        ]

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

    def __str__(self):
        return f"{self.user.email} - Store: {self.store_ratio}% | YouTube: {self.youtube_ratio}%"

    class Meta:
        verbose_name = "Sharing"
        verbose_name_plural = "Shares"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
        ]


class Announcement(models.Model):
    # Fields
    announcement_id = models.AutoField("Announcement ID", primary_key=True, unique=True)
    announcement = models.TextField("Announcement", null=False,max_length=1024)
   
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ['-created_at']

    def __str__(self):
        return f"Announcement {self.announcement_id}"


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
            models.Index(fields=["username"]),
            models.Index(fields=["date_of_payment"]),
            models.Index(fields=["amount_paid"]),
            models.Index(fields=["tds"]),
            models.Index(fields=["tds_percentage"]),
            models.Index(fields=["transfer_id"]),
        ]

    def __str__(self):
        return f"{self.username} - {self.amount_paid} on {self.date_of_payment}"
