import uuid
from datetime import datetime

import pytz
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.validators import MinLengthValidator
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

# NOTE stefan The following models are missing:
# * Report: This is created outside of this app. I will share the structure soon, its mainly a json blob atm. Since i am refactoring this at the moment, i will share it after refactoring.
from website.models import Report


#
# Shared enums
#
class Currency(models.TextChoices):
    EUR = "EUR", _("Euro")


class Ternary(models.TextChoices):
    YES = "YES", _("Ja")
    NO = "NO", _("Nein")
    NOT_SPECIFIED = "NOT", _("Keine Angabe")


#
#
# market matching
#
#


class MarketUser(models.Model):
    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=50)

    surename = models.CharField(max_length=50)  # Nachname

    entity = models.CharField(
        max_length=50, blank=True, null=True
    )  # company or institution

    email = models.EmailField()

    # https://docs.djangoproject.com/en/5.1/ref/contrib/auth/
    user = models.ForeignKey(to=User, on_delete=models.SET_NULL)

    # Maximum phone number length is 15
    # https://en.wikipedia.org/wiki/E.164
    phonenumber = PhoneNumberField(region="DE", max_length=20, blank=True, null=True)

    town = models.CharField(max_length=50, null=True)

    street_housenumber = models.CharField(max_length=50, null=True)

    zipcode = models.CharField(max_length=5)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    confirmed_at = models.DateTimeField(null=True)

    signed_up_via = models.OneToOneField("InviteLink", on_delete=models.SET_NULL)

    # NOTE here the hubspot integration is missing, will include an id or model-reference here for tracking users pushed to hubspot


class Technology(models.Model):
    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=50, blank=False)


class Landowner(MarketUser):
    position = models.CharField(max_length=50)


class ProjectDeveloper(MarketUser):

    company_website = models.URLField()

    interest = models.ForeignKey(
        to="ProjectDeveloperInterest", on_delete=models.CASCADE
    )

    states_active = models.ManyToManyField(
        to="Region", on_delete=models.SET_NULL, null=True
    )


class Region(models.Model):

    name = models.CharField(max_length=64)

    # example 'DE-BW' or see https://en.wikipedia.org/wiki/ISO_3166
    iso3166 = models.CharField(
        max_length=5, validators=[MinLengthValidator(5)], null=True, blank=False
    )

    geom = models.MultiPolygonField()


class ProjectDeveloperInterest(models.Model):
    """Interest of the project developer"""

    wind = models.BooleanField()

    ground_mounted_solar = models.BooleanField()

    battery = models.BooleanField()

    heat = models.BooleanField()

    hydrogen = models.BooleanField()

    electromobility = models.BooleanField()

    ecological_upgrading = models.BooleanField()

    other = models.CharField(max_length=50)


#
#
# Areas and offers
#
#
class Landuse(models.TextChoices):
    WIND = "WIND", _("Windenergie")
    GROUND_MOUNTED_SOLAR = "SOLAR", _("Freiflächen-Solarenergie")
    ENERGY_STORAGE = "ENERGY_STORAGE", _("Energiespeicher")
    ECOLOGICAL_UPGRADING = "ECOLOGICAL", _("Ökologische Aufwertungsmaßnahmen")


class Landuse(models.Model):
    """Multiselect excluded landuse in area offer"""

    key = models.CharField(
        max_length=8, choices=Landuse.choices, unique_for_date="valid_from"
    )

    title = models.CharField(blank=False)

    valid_from = models.DateField()
    valid_to = models.DateField(default="9999-01-01")


# R1_v4, R1_V6
class Parcel(models.Model):
    """Defines the geometry of areas of land that landowners want to put on the marketplace"""

    geom = models.PolygonField()

    # We import this from cadastre / government sources
    # The last ones are very german specific and thus hav no english pendant
    state_name = models.CharField(max_length=64)
    district_name = models.CharField(max_length=64)
    municipal_name = models.CharField(max_length=64)
    gemarkung = models.CharField(max_length=64)
    flur = models.CharField(max_length=64)
    flurstueck_nr_nen = models.CharField(max_length=8, blank=False, null=True)
    flurstueck_nr_zae = models.CharField(max_length=8, blank=False, null=False)
    nutzung = models.CharField()

    area_m2 = models.DecimalField(decimal_places=2)

    appear_in_offer = models.ForeignKey(
        "AreaOffer", related_name="parcels", on_delete=models.SET_NULL
    )

    created_by = models.ForeignKey(User)

    created_at = models.DateTimeField(auto_now_add=True)


# R2_V6
class ProjectDeveloperWatchlist(models.Model):

    user = models.ForeignKey(ProjectDeveloper)
    parcel = models.ForeignKey(Parcel)

    created_at = models.DateTimeField(auto_now_add=True)


# R1_V10, R1_V13
class AreaOffer(models.Model):
    """
    Logical wraps multiple parcels and provides offer criteria by the landowner

    Note document_others relation via AreaOfferDocument
    """

    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # six digit field
    offer_number = models.PositiveIntegerField(auto_created=True)

    title = models.CharField()
    description = models.TextField()

    class OfferStatus(models.TextChoices):
        IN_PREPARATION = "V", _("In Vorbereitung")  # after creation
        PREPARED = "P", _("Vorprüfung abgeschlossen")
        ACTIVE = "A", _("Aktiv")
        INACTIVE = "I", _("Inaktiv")

    status = models.TextChoices(choices=OfferStatus, default=OfferStatus.IN_PREPERATION)

    hide_from_search = models.BooleanField(default=False)

    created_by = models.ForeignKey(Landowner, on_delete=models.SET_NULL)

    available_from = models.DateField()

    class AreaUtilization(models.TextChoices):
        NO_RESTRICTION = "NO", _("Keine Einschränkung")
        SALE = "SA", _("Verkauf")
        LEASE = "LE", _("Verpachtung")

    utilization = models.TextField(
        choices=AreaUtilization, default=AreaUtilization.NO_RESTRICTION
    )

    excluded_landuse = models.ManyToManyField(Landuse, related_name="offers")

    class DeveloperRegionality(models.TextChoices):
        NO_RESTRICTION = "NO", _("Keine Einschränkung")
        GERMANY = "DE", _("Firmensitz in Deutschland")
        FEDERAL_STATE = "BL", _("Firmensitz im Bundesland des Grundstücks")

    preferred_regionality = models.TextField(
        choices=DeveloperRegionality, default=DeveloperRegionality.NO_RESTRICTION
    )

    class ShareholderModel(models.TextChoices):
        NO_RESTRICTION = "NO", _("Keine Einschränkung")
        SHARES_INCOME = "IN", _("Beteiligungen am Erlös")
        SHARES_COMPANY = "CO", _("Beteiligungen an der Projektgesellschaft")
        BOTH = "BO", _("Beides")

    shareholder_model = models.TextField(
        choices=ShareholderModel, default=ShareholderModel.NO_RESTRICTION
    )

    important_remarks = models.TextField()

    document_land_register = models.FileField(help_text=_("Auszug Grundbuch"))
    document_assingement_landowner = models.FileField(
        help_text=_("Beauftragung des Eigentümers")
    )
    document_declaration_of_consent_network_request = models.FileField(
        help_text=_("Einverständniserklärung der Netzanfrage")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# R1_V10, R1_V13
class AreaOfferDocuments(models.Model):
    """Unspecified files that can be uploaded by registred users."""

    filename = models.CharField(max_length=64)

    file = models.FileField(unique=True)

    uploaded_by = models.ForeignKey(User)

    offer = models.ForeignKey(
        AreaOffer, related_name="document_other", on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# R2_V9
class AreaOfferConfirmation(models.Model):
    """Provides offer criteria by the projectdeveloper"""

    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class LandownerUtilization(models.TextChoices):
        SALE = "SA", _("Kauf des Gründstücks")
        LEASE = "LE", _("Anpachtung des Grundstücks")
        BOTH = "BO", _("Beides")

    confirms_offer = models.ForeignKey(AreaOffer)
    sent_by = models.ForeignKey(ProjectDeveloper, on_delete=models.SET_NULL)

    utilitization = models.CharField(choices=AreaOffer.AreaUtilization.choices)

    # if utilitization = SALE
    sale_amount = models.DecimalField(
        decimal_places=2, help_text=_("Angebotener Kaufpreis")
    )

    # if utilitization = LEASE
    lease_amount_single_payment = models.DecimalField(
        decimal_places=2,
        help_text=_("Einmalzahlung an Eigentümer bei Vertragsabschluss"),
    )
    lease_amount_yearly_lease_year_one = models.DecimalField(
        decimal_places=2, help_text=_("Jährliche Pacht in Jahr 1")
    )
    contracted_term_month = models.PositiveSmallIntegerField(
        null=True, help_text=_("Vertragslaufzeit")
    )
    staggered_lease = models.TextField(
        choices=Ternary.choices, null=True, help_text=_("Staffelpacht möglich?")
    )
    share_of_income = models.TextField(
        choices=Ternary.choices,
        help_text=_("Bieten Sie Beteiligungen an laufenden Erlösen?"),
    )
    shares_project_company = models.TextField(
        choices=Ternary.choices,
        help_text=_(
            "Im Falle der Gründung einer Projektgesellschaft: Bieten Sie Beteiligungen an der Projektgesellschaft an?"
        ),
    )

    message_to_landowner = models.TextField(
        max_length=500, help_text=_("Ihre Nachricht an den Eigentümer zu dem Gebot")
    )
    message_to_platform = models.TextField(
        max_length=500, help_text=_("Ihre Nachricht an Agrario Energy")
    )

    currency = models.CharField(choices=Currency.choices, default=Currency.EUR)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AreaOfferAdministration(models.Model):
    """Admin is able to assign information regarding transaction, this has no own view and is done via backend"""

    adminstrates = models.OneToOneField(AreaOffer)

    # if landuse WIND/SOLAR/STORAGE
    transaction_on_contractsigned_percent = models.DecimalField(decimal_places=2)
    transaction_on_authorization_percent = models.DecimalField(decimal_places=2)
    transaction_on_initial_operation_percent = models.DecimalField(decimal_places=2)

    # if landuse ECO
    lease_amount_single_payment = models.DecimalField(
        decimal_places=2
    )  # currency of the offer

    notes = models.TextField()
    admin_author = models.ForeignKey(User)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


#
# Parcel Reports and Analysis
#


# R1_V8, R1_v7
class ParcelAnalysis(models.Model):
    """Logically wraps the parcel items"""

    paid_by_transaction = models.ForeignKey(
        "PaymentTransaction", on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(auto_now_add=True)


class ParcelAnalysisItem(models.Model):
    """Relationship for the existing models"""

    report = models.ForeignKey(Report, on_delete=models.SET_NULL)
    parcel = models.ForeignKey(Parcel, on_delete=models.SET_NULL)
    analysis = models.ForeignKey(ParcelAnalysis, on_delete=models.SET_NULL)


class ReportShapefileZip(models.Model):
    """
    This represents report data as zipped Shape-file residing in a bucket storage
    This file is usually generated on/shortly after report creation.
    If not used it will be deleted and eventually re-created.
    """

    file_shape_zip = models.FileField(unique=True)

    report = models.ForeignKey(Report)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReportShapefileZipDownloadRequest(models.Model):
    """This helps keeping track of download requests"""

    shapefile = models.ForeignKey(ReportShapefileZip)

    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(User)


#
#
# Project dev Subscriptions
#
#


class PlatformSubscription(models.Model):
    """Instance of the available subscriptions"""

    class SubscriptionTier(models.TextChoices):
        FREE = "FREE", _("Free")
        PREMIUM = "PREM", _("Premium")
        ENTERPRISE = "ENTE", _("Enterprise")

    title = models.CharField()
    description = models.TextField()
    tier = models.CharField(
        max_length=4,
        choices=SubscriptionTier,
        default=SubscriptionTier.FREE,
        unique_for_date="valid_from",
    )

    valid_from = models.DateField()
    valid_to = models.DateField(default="9999-01-01")

    amount_paid_per_month = models.DecimalField(decimal_places=2)


class ProjectDeveloperSubscription(models.Model):
    """Instance of the choosen Subscription

    A user can have a specific tier, for a choosen timeframe.

    Timeframes will normally last forever.
    Timeframes are termined by setting valid_to to a date >= today()
    """

    class BillingMode(models.TextChoices):
        MONTHLY = "MON", _("Jährlich")
        YEARLY = "YEA", _("Monatlich")

    by_user = models.ForeignKey(
        to=ProjectDeveloper, on_delete=models.SET_NULL, unique_for_date="valid_from"
    )

    tier = models.ForeignKey(to=PlatformSubscription, on_delete=models.SET_NULL)

    valid_from = models.DateField()
    valid_to = models.DateField(default="9999-01-01")

    billing_mode = models.CharField(
        max_length=3,
        choices=BillingMode,
        default=BillingMode.MONTHLY,
    )

    payments = models.ForeignKey("PaymentTransaction", on_delete=models.SET_NULL)


class ProjectDeveloperSubscriptionDiscount(models.Model):
    """For timeframes of discounts for users, their subscription fee will be decreased."""

    discount_for_user = models.ForeignKey(
        ProjectDeveloper, on_delete=models.SET_NULL, unique_for_date="valid_from"
    )

    valid_from = models.DateField()
    valid_to = models.DateField()

    amount_percent = models.PositiveSmallIntegerField()


#
#
# Payment and promo
#


class PromoCode(models.Model):
    """Promotional redeem code which can be used in either purchasing parcel analysis or project developer subscriptions"""

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL)

    assigned_to = models.ForeignKey(MarketUser, on_delete=models.SET_NULL)

    redeemed_by = models.ForeignKey(MarketUser, on_delete=models.SET_NULL)

    # for landowner parcel analysis
    amount_percent = models.PositiveSmallIntegerField()

    # for project dev subscription tiers
    amount_month = models.PositiveSmallIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)


class PaymentTransaction(models.Model):
    """Object to store payment transactions"""

    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    amount = models.DecimalField(decimal_places=2)

    currency = models.CharField(choices=Currency.choices, default=Currency.EUR)

    promo_code = models.ForeignKey(to=PromoCode, on_delete=models.SET_NULL)

    stripe_id = models.CharField(max_length=512)

    by_user = models.ForeignKey(to=MarketUser, on_delete=models.SET_NULL)

    created_at = models.DateTimeField(auto_now_add=True)


class InviteLink(models.Model):

    uri_hash = models.CharField(max_length=16)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL)

    allow_more_than_one_invite = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)


NAIVE_DT_FOREVER = datetime(9999, 1, 1, 0, 0, 0)

timezone = pytz.UTC
DT_FOREVER = timezone.loclalize(NAIVE_DT_FOREVER)


class TokenAmount(models.Model):
    """
    Represent the token amount, a user has accumulates.

    Token can be used to perform different actions.
    """

    account_user = models.ForeignKey(User)

    requested_by = models.ForeignKey(User)

    amount = models.PositiveSmallIntegerField()

    valid_from = models.DateTimeField()

    valid_to = models.DateTimeField(default=DT_FOREVER)

    created_at = models.DateTimeField(auto_now_add=True)


#
# Messaging
#


class Message(models.Model):
    """Messages are composed in a thread and are displayed in order of creation."""

    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sender = models.ForeignKey(User)
    recipient = models.ForeignKey(User)
    subject = models.CharField(max_length=64)
    body = models.TextField(max_length=500)

    thread = models.UUIDField(default=uuid.uuid4)

    created_at = models.DateTimeField(auto_now_add=True)


#
# FAQ
#


class FaqItem(models.Model):

    class FaqCategory(models.TextChoices):
        GENERAL = "G", _("Allgemein")
        GENERAL = "E", _("Eigentümer")
        GENERAL = "P", _("Projektentwickler")

    category = models.CharField(
        choices=FaqCategory.choices, default=FaqCategory.GENERAL
    )

    question = models.TextField()
    answer = models.TextField()
    is_active = models.BooleanField()
