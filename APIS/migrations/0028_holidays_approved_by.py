from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('APIS', '0027_remove_holidays_teacher'),
    ]

    operations = [
        migrations.AddField(
            model_name='holidays',
            name='approved_by',
            field=models.IntegerField(blank=True, db_column='ApprovedBy', null=True),
        ),
    ]
