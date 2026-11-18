# -*- coding: utf-8 -*-
# Generated migration to normalize Holidays with HolidayCenter junction table

from django.db import migrations, models
import django.db.models.deletion


def create_holiday_center(apps, schema_editor):
    """Migrate existing center-specific holidays to HolidayCenter junction table."""
    Holidays = apps.get_model('APIS', 'Holidays')
    Center = apps.get_model('APIS', 'Center')
    HolidayCenter = apps.get_model('APIS', 'HolidayCenter')
    
    # For each center-specific holiday (academic_holiday=False) with a center_id,
    # create a HolidayCenter entry and clear the center_id on Holidays
    for holiday in Holidays.objects.filter(academic_holiday=False).exclude(center__isnull=True):
        HolidayCenter.objects.create(
            holiday=holiday,
            center=holiday.center,
            created_by=holiday.created_by,
            created_on=holiday.created_on,
        )
        # Clear center_id on Holidays - will be removed in next migration
        holiday.center = None
        holiday.save(update_fields=['center'])


def reverse_holiday_center(apps, schema_editor):
    """Reverse: restore center_id on Holidays from HolidayCenter (first center only)."""
    Holidays = apps.get_model('APIS', 'Holidays')
    HolidayCenter = apps.get_model('APIS', 'HolidayCenter')
    
    for hc in HolidayCenter.objects.all():
        # Only restore if holiday doesn't already have a center
        holiday = hc.holiday
        if holiday.center_id is None:
            holiday.center = hc.center
            holiday.save(update_fields=['center'])


class Migration(migrations.Migration):

    dependencies = [
        ('APIS', '0030_teacherleaves_delete_academicholiday_and_more'),
    ]

    operations = [
        # 1. Create HolidayCenter junction table
        migrations.CreateModel(
            name='HolidayCenter',
            fields=[
                ('id', models.AutoField(db_column='Id', primary_key=True, serialize=False)),
                ('created_by', models.IntegerField(db_column='CreatedBy', blank=True, null=True)),
                ('created_on', models.DateTimeField(db_column='CreatedOn', blank=True, null=True)),
                ('center', models.ForeignKey(db_column='CenterId', on_delete=django.db.models.deletion.CASCADE, related_name='holiday_centers', to='APIS.center')),
                ('holiday', models.ForeignKey(db_column='HolidayId', on_delete=django.db.models.deletion.CASCADE, related_name='centers', to='APIS.holidays')),
            ],
            options={
                'db_table': 'HolidayCenter',
            },
        ),
        # Add unique constraint to prevent duplicate holiday-center pairs
        migrations.AddConstraint(
            model_name='holidaycenter',
            constraint=models.UniqueConstraint(fields=('holiday', 'center'), name='uniq_holiday_center'),
        ),
        # Index for common queries
        migrations.AddIndex(
            model_name='holidaycenter',
            index=models.Index(fields=['center'], name='idx_holidaycenter_center'),
        ),
        migrations.AddIndex(
            model_name='holidaycenter',
            index=models.Index(fields=['holiday'], name='idx_holidaycenter_holiday'),
        ),
        
        # 2. Migrate existing data
        migrations.RunPython(create_holiday_center, reverse_holiday_center),
    ]
