# Generated by Django 5.1.4 on 2025-01-14 22:00

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(max_length=255)),
                ('tier', models.CharField(choices=[('FREE', 'Free'), ('PREM', 'Premium'), ('ENTE', 'Enterprise')], default='FREE', max_length=4, unique_for_date='valid_from')),
                ('valid_from', models.DateField()),
                ('valid_to', models.DateField(default='9999-01-01')),
                ('amount_paid_per_month', models.DecimalField(decimal_places=2, max_digits=10)),
            ],
        ),
        migrations.CreateModel(
            name='ProjectDeveloperSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valid_from', models.DateField()),
                ('valid_to', models.DateField(default='9999-01-01')),
                ('billing_mode', models.CharField(choices=[('MON', 'Jährlich'), ('YEA', 'Monatlich')], default='MON', max_length=3)),
                ('by_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.projectdeveloper', unique_for_date='valid_from')),
                ('payments', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='payments.paymenttransaction')),
                ('tier', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='subscriptions.platformsubscription')),
            ],
        ),
        migrations.CreateModel(
            name='ProjectDeveloperSubscriptionDiscount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valid_from', models.DateField()),
                ('valid_to', models.DateField()),
                ('amount_percent', models.PositiveSmallIntegerField()),
                ('discount_for_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.projectdeveloper', unique_for_date='valid_from')),
            ],
        ),
    ]
