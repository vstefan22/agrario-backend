# Generated by Django 5.1.4 on 2025-01-14 16:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invites', '0002_alter_invitelink_uri_hash'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invitelink',
            name='uri_hash',
            field=models.CharField(default='94dd2f433b9b41c7', max_length=16, unique=True),
        ),
    ]