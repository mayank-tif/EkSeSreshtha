from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('APIS', '0026_holidays_teacher_leave_approval'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='holidays',
            name='idx_holidays_teacher',
        ),
        migrations.RemoveField(
            model_name='holidays',
            name='teacher',
        ),
    ]
