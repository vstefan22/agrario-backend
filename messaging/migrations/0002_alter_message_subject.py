# Generated by Django 5.1.4 on 2025-01-15 13:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="subject",
            field=models.CharField(
                choices=[
                    ("Flurstücksanalyse PLUS", "Flurstücksanalyse PLUS"),
                    ("Angebot erstellen", "Angebot erstellen"),
                    ("Sonstiges", "Sonstiges"),
                ],
                default="General Inquiry",
                max_length=64,
            ),
        ),
    ]