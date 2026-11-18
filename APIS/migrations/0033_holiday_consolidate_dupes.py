# -*- coding: utf-8 -*-
# Consolidate duplicate Holidays (same name+dates) into single rows with multiple centers

from django.db import migrations, models
from collections import defaultdict


def consolidate_duplicates(apps, schema_editor):
    Holidays = apps.get_model('APIS', 'Holidays')
    HolidayCenter = apps.get_model('APIS', 'HolidayCenter')
    
    # Group center-specific holidays by (name, start_date, end_date, academic_holiday)
    groups = defaultdict(list)
    for h in Holidays.objects.filter(academic_holiday=False).order_by('id'):
        key = (h.name, h.start_date, h.end_date, h.academic_holiday)
        groups[key].append(h)
    
    for key, holidays in groups.items():
        if len(holidays) <= 1:
            continue
        
        # Keep the first (lowest id), merge others into it
        master = holidays[0]
        others = holidays[1:]
        
        # Collect all centers from all holidays in group
        all_center_ids = set()
        for h in holidays:
            all_center_ids.update(h.centers.values_list('center_id', flat=True))
        
        # Create HolidayCenter entries for master with all centers
        for cid in all_center_ids:
            HolidayCenter.objects.get_or_create(
                holiday=master,
                center_id=cid,
                defaults={'created_by': master.created_by, 'created_on': master.created_on}
            )
        
        # Delete other holidays (cascades to their HolidayCenter entries)
        for h in others:
            h.delete()


def reverse_consolidate(apps, schema_editor):
    # Not easily reversible - would need to recreate duplicates
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('APIS', '0032_holiday_remove_center_fk'),
    ]

    operations = [
        migrations.RunPython(consolidate_duplicates, reverse_consolidate),
    ]
