# Generated by Django 5.1.4 on 2025-01-14 22:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invites', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invitelink',
            name='uri_hash',
            field=models.CharField(default='18337ecd2c2f480b', max_length=16, unique=True),
        ),
    ]