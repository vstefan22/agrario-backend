class Report(models.Model):

    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now=True)

    mpoly = models.MultiPolygonField()

    bound_to = models.ForeignKey(Lead, on_delete=models.PROTECT, null=True)

    # Report area suitability (filter criteria for search views)
    area_m2 = models.PositiveIntegerField()
    usable_area_m2 = models.PositiveIntegerField()
    usable_area_solar_m2 = models.PositiveIntegerField()
    usable_area_wind_m2 = models.PositiveIntegerField()
    usable_area_battery_m2 = models.PositiveIntegerField()
    # General suitability infra
    ## Energy
    energy_networkprovider = models.ForeignKey(
        'GridOperator'
    )
    energy_distance_midhigh_m = models.PositiveIntegerField()
    energy_distance_highhigh_m = models.PositiveIntegerField()
    energy_distance_tower_highest_m = models.PositiveIntegerField()
    energy_distance_tower_high_m = models.PositiveIntegerField()
    energy_distance_tower_mid_m = models.PositiveIntegerField()
    ## Traffic: see https://wiki.openstreetmap.org/wiki/DE:Key:highway
    distance_motorway_ramp_m = models.PositiveIntegerField()
    # de: Autobahn
    distance_motorway_m = models.PositiveIntegerField()
    # de: Kraftfahrt u. Bundestraßen
    distance_trunkprimary_m = models.PositiveIntegerField()
    # de: Kreistraßen
    distance_secondary_m = models.PositiveIntegerField()
    # de: Schienenwege
    distance_traintracks_m = models.PositiveIntegerField()

    # General suitability
    distance_settlement_m = models.PositiveIntegerField()
    eeg_area_m2 = models.PositiveIntegerField()
    baugb_area_m2 = models.PositiveIntegerField()
    is_area_in_privilege_area = models.BooleanField()



    class ReportVisibility(models.TextChoices):
        ADMIN   = 'A'
        USER    = 'U'
        PUBLIC  = 'P'


    visible_for = models.CharField(
        max_length=1,
        choices=ReportVisibility,
        default=ReportVisibility.USER
    )


    data = models.JSONField()

    def __repr__(self) -> str:
        return self.identifier

class GridOperator(models.Model):
    name = models.CharField(unique=True)
    mpoly = models.MultiPolygonField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
