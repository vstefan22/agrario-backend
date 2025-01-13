# offers/management/commands/import_flurstueck.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry
from lxml import etree
from offers.models import Parcel


class Command(BaseCommand):
    help = "Imports parcels from a WFS XML file (GML)."

    def add_arguments(self, parser):
        parser.add_argument(
            'xml_path',
            type=str,
            help='Path to the WFS GML XML file to import'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        xml_path = options['xml_path']
        self.parse_wfs_featurecollection(xml_path)

    def parse_wfs_featurecollection(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        namespaces = root.nsmap
        fs = []

        for member in root.findall('.//wfs:member', namespaces=namespaces):
            flurstueck = member.find('.//Flurstueck', namespaces=namespaces)
            if flurstueck is not None:
                feature_id = flurstueck.get(
                    '{http://www.opengis.net/gml/3.2}id')
                land = flurstueck.find('./land', namespaces=namespaces).text
                gemeinde = flurstueck.find(
                    './gemeinde', namespaces=namespaces).text
                flaeche = flurstueck.find(
                    './flaeche', namespaces=namespaces).text
                kreis = flurstueck.find('./kreis', namespaces=namespaces).text
                gemarkung = flurstueck.find(
                    './gemarkung', namespaces=namespaces).text
                flur = flurstueck.find('./flur', namespaces=namespaces).text

                geom_element = flurstueck.find(
                    './/gml:MultiSurface', namespaces=namespaces)

                flurstnrzae = flurstueck.find(
                    './flstnrzae', namespaces=namespaces).text

                flstnrnen = flurstueck.find(
                    './flstnrnen', namespaces=namespaces)

                if flstnrnen:  # If flstnrnen is not null or empty
                    cadastral_parcel = f"{flurstnrzae}/{flstnrnen.text}"
                else:  # If flstnrnen is null or empty
                    cadastral_parcel = flurstnrzae

                if geom_element is not None:
                    geom_gml = etree.tostring(geom_element)
                    geom = GEOSGeometry.from_gml(geom_gml)

                    # NOTE: "create_or_update" is not a built-in method. Possibly you want "update_or_create"?
                    parcel, created = Parcel.objects.update_or_create(
                        alkis_feature_id=feature_id,
                        defaults={
                            "polygon": geom,
                            "state_name": land,
                            "district_name": kreis,
                            "communal_district": gemarkung,
                            "municipality_name": gemeinde,
                            "cadastral_area": flur,
                            "cadastral_parcel": cadastral_parcel,
                            "area_square_meters": int(float(flaeche)),

                            "zipcode": None,
                            "land_use": None,

                        }
                    )
                    fs.append(parcel)
                else:
                    print(f"No geometry found for feature {feature_id}")

        for p in Parcel.objects.all():
            geom = p.polygon
            geom.srid = 25832
            geom.transform(4326)
            p.polygon = geom
            p.save()

        self.stdout.write(self.style.SUCCESS(
            f"Successfully imported {len(fs)} features."))
