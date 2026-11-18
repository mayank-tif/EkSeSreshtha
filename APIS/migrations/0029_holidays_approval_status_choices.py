from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('APIS', '0028_holidays_approved_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='holidays',
            name='approval_status',
            field=models.CharField(blank=True, choices=[('approved', 'Approved'), ('pending', 'Pending'), ('rejected', 'Rejected')], db_column='ApprovalStatus', default='approved', max_length=20, null=True),
        ),
    ]
