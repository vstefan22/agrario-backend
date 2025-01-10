from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management.base import BaseCommand
from offers.models import Region

class Command(BaseCommand):
    help = "Preloads the Region model with predefined data"

    def handle(self, *args, **kwargs):
        regions = [
            {"name": "Berlin", "iso3166": "DE-BE"},
            {"name": "Hamburg", "iso3166": "DE-HH"},
            {"name": "Bavaria", "iso3166": "DE-BY"},
            {"name": "Saxony", "iso3166": "DE-SN"},
        ]

        # Define a placeholder geometry (example: a bounding box)
        placeholder_geom = MultiPolygon(Polygon.from_bbox((0.0, 0.0, 1.0, 1.0)))

        for region_data in regions:
            region, created = Region.objects.get_or_create(
                name=region_data["name"],
                iso3166=region_data["iso3166"],
                defaults={"geom": placeholder_geom},  # Add a default geometry
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Region {region.name} added."))
            else:
                self.stdout.write(self.style.WARNING(f"Region {region.name} already exists."))
