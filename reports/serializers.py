from rest_framework import serializers
from .models import Report

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "identifier",
            "area_m2",
            "usable_area_solar_m2",
            "usable_area_wind_m2",
            "visible_for",
            "data",  # Include all calculated metrics
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        analyse_plus = self.context.get("analyse_plus", False)

        # Add required fields from the client's request
        metrics = instance.data
        data.update({
            "possible_yearly_lease": metrics.get("total_area_m2") * 1.57,  # Example logic for lease calculation
            "sum_of_lease_25_years": metrics.get("total_area_m2") * 1.57 * 25,
            "possible_yearly_power": metrics.get("solar_energy_potential_kwh_per_year") + metrics.get("wind_energy_potential_kwh_per_year"),
            "sum_of_power_25_years": (metrics.get("solar_energy_potential_kwh_per_year", 0) + metrics.get("wind_energy_potential_kwh_per_year", 0)) * 25,
            "financial_shares_6EEG": metrics.get("total_area_m2") * 1.0,  # Example financial share logic
            "financial_shares_6EEG_25_years": metrics.get("total_area_m2") * 1.0 * 25,
            "green_energy_supplied_housholds": metrics.get("solar_energy_potential_kwh_per_year", 0) / 4500,  # Example: 4500 kWh/year per household
            "tons_of_co2_saving_per_year": metrics.get("solar_energy_potential_kwh_per_year", 0) * 0.5 / 1000,
            "tons_of_co2_saving_25_year": (metrics.get("solar_energy_potential_kwh_per_year", 0) * 0.5 / 1000) * 25,
            "tabular_data": [
                {
                    "name": "Lage und Nutzung",
                    "desc": "Hier finden Sie Informationen zur Lage, Größe und verzeichneten Nutzung ihres Flurstücks...",
                    "rows": [
                        {"type": "head", "key": "Bezeichnung", "val": "Wert"},
                        {"type": "value", "key": "Bundesland [-]", "val": "Hessen"},
                    ],
                }
            ],
        })

        # Blur fields if Analyse Plus is not purchased
        if not analyse_plus:
            for field in [
                "usable_area_solar_m2",
                "usable_area_wind_m2",
                "possible_yearly_power",
                "sum_of_power_25_years",
            ]:
                data[field] = "Blurred"

        return data
