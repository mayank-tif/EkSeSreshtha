# -*- coding: utf-8 -*-
# Remove center FK from Holidays (now in HolidayCenter junction table)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('APIS', '0031_holidaycenter_normalize'),
    ]

    operations = [
        # Remove the center FK from Holidays - data already migrated in 0031
        # Note: model already updated to remove 'center' field; DB column
        # removal handled by Django's RemoveField. Index was on the FK
        # column which is being dropped, so no separate RemoveIndex needed.
        migrations.RemoveField(
            model_name='holidays',
            name='center',
        ),
    ]
