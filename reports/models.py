from django.db import models
from django.contrib.gis.db import models as gis_models
from django.db.models import JSONField
import uuid
from typing import Dict

from offers.models import Parcel

class Report(models.Model):
    """
    Report model linked to one or more parcels.
    """
    identifier = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now=True)
    parcels = models.ManyToManyField(Parcel, related_name="reports")  # New field

    mpoly = gis_models.MultiPolygonField()

    # Report area suitability
    area_m2 = models.PositiveIntegerField()
    usable_area_m2 = models.PositiveIntegerField()
    usable_area_solar_m2 = models.PositiveIntegerField()
    usable_area_wind_m2 = models.PositiveIntegerField()
    usable_area_battery_m2 = models.PositiveIntegerField()

    # General suitability infra
    energy_distance_midhigh_m = models.PositiveIntegerField()
    energy_distance_highhigh_m = models.PositiveIntegerField()
    energy_distance_tower_highest_m = models.PositiveIntegerField()
    energy_distance_tower_high_m = models.PositiveIntegerField()
    energy_distance_tower_mid_m = models.PositiveIntegerField()

    # Traffic distances
    distance_motorway_ramp_m = models.PositiveIntegerField()
    distance_motorway_m = models.PositiveIntegerField()
    distance_trunkprimary_m = models.PositiveIntegerField()
    distance_secondary_m = models.PositiveIntegerField()
    distance_traintracks_m = models.PositiveIntegerField()

    # General suitability
    distance_settlement_m = models.PositiveIntegerField()
    eeg_area_m2 = models.PositiveIntegerField()
    baugb_area_m2 = models.PositiveIntegerField()
    is_area_in_privilege_area = models.BooleanField()

    class ReportVisibility(models.TextChoices):
        ADMIN = "A"
        USER = "U"
        PUBLIC = "P"

    visible_for = models.CharField(
        max_length=1, choices=ReportVisibility.choices, default=ReportVisibility.USER
    )

    data = JSONField()

    
    def calculate_energy_metrics(mpoly: gis_models.MultiPolygonField, average_solar_irradiance: float, average_wind_speed: float, grid_distance: float) -> Dict[str, float]:
        """
        Calculate energy suitability metrics for a parcel.

        Args:
            mpoly (MultiPolygon): The geometry of the parcel.
            average_solar_irradiance (float): Average solar irradiance in kWh/m²/day.
            average_wind_speed (float): Average wind speed in m/s.
            grid_distance (float): Distance to the nearest grid infrastructure in meters.

        Returns:
            Dict[str, float]: A dictionary containing calculated metrics.
        """
        # Constants
        SOLAR_PANEL_EFFICIENCY = 0.15  # 15% efficiency
        WIND_TURBINE_EFFICIENCY = 0.4  # 40% efficiency
        AIR_DENSITY = 1.225  # kg/m³ (at sea level)
        BATTERY_SCALING_FACTOR = 0.01  # Adjust scaling factor for battery suitability

        # Calculate area
        total_area_m2 = mpoly.area  # Total area in square meters
        usable_area_solar = total_area_m2 * 0.5  # Assume 50% is usable for solar panels
        usable_area_wind = total_area_m2 * 0.1  # Assume 10% is usable for wind turbines

        # Solar energy potential
        solar_energy_potential = (
            usable_area_solar * average_solar_irradiance * 365 * SOLAR_PANEL_EFFICIENCY
        )

        # Wind energy potential
        wind_energy_potential = (
            0.5 * AIR_DENSITY * usable_area_wind * (average_wind_speed**3) * WIND_TURBINE_EFFICIENCY * 8760  # 8760 = hours in a year
        )

        # Battery suitability
        battery_suitability = (
            usable_area_solar / grid_distance * BATTERY_SCALING_FACTOR if grid_distance > 0 else 0
        )

        return {
            "total_area_m2": total_area_m2,
            "usable_area_solar_m2": usable_area_solar,
            "usable_area_wind_m2": usable_area_wind,
            "solar_energy_potential_kwh_per_year": solar_energy_potential,
            "wind_energy_potential_kwh_per_year": wind_energy_potential,
            "battery_suitability_score": battery_suitability,
        }
