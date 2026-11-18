from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('APIS', '0025_remove_center_from_academic_holiday'),
    ]

    operations = [
        migrations.AddField(
            model_name='holidays',
            name='teacher',
            field=models.ForeignKey(blank=True, db_column='TeacherId', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='teacher_holidays', to='APIS.teacher'),
        ),
        migrations.AddField(
            model_name='holidays',
            name='approval_status',
            field=models.CharField(blank=True, db_column='ApprovalStatus', default='approved', max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='holidays',
            name='continuous_days',
            field=models.IntegerField(blank=True, db_column='ContinuousDays', null=True),
        ),
        migrations.AddIndex(
            model_name='holidays',
            index=models.Index(fields=['teacher'], name='idx_holidays_teacher'),
        ),
        migrations.AddIndex(
            model_name='holidays',
            index=models.Index(fields=['approval_status'], name='idx_holidays_approval'),
        ),
    ]
