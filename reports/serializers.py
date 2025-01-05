from rest_framework import serializers
from .models import Report
from offers.serializers import ParcelSerializer

class ReportSerializer(serializers.ModelSerializer):
    parcels = ParcelSerializer(many=True, read_only=True)  # Include parcels

    class Meta:
        model = Report
        fields = [
            "identifier",
            "created",
            "parcels",  # Include parcels field
            "mpoly",
            "area_m2",
            "usable_area_m2",
            "usable_area_solar_m2",
            "usable_area_wind_m2",
            "usable_area_battery_m2",
            "energy_distance_midhigh_m",
            "energy_distance_highhigh_m",
            "energy_distance_tower_highest_m",
            "energy_distance_tower_high_m",
            "energy_distance_tower_mid_m",
            "distance_motorway_ramp_m",
            "distance_motorway_m",
            "distance_trunkprimary_m",
            "distance_secondary_m",
            "distance_traintracks_m",
            "distance_settlement_m",
            "eeg_area_m2",
            "baugb_area_m2",
            "is_area_in_privilege_area",
            "visible_for",
            "data",
        ]