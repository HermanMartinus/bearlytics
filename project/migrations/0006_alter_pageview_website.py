# Generated by Django 5.1.2 on 2024-11-04 06:55

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0005_pageview_website'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pageview',
            name='website',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='project.website'),
        ),
    ]
