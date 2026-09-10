from django.db import migrations


class Migration(migrations.Migration):
    """
    Widen columns that overflow with real Excel data:
      - School.SchoolName    (data max 59 chars, was 50)
      - Student.FullName     (data max 71 chars, was 50)

    Uses raw SQL because migration 0015 was recorded as applied while its
    AlterField operations were rolled back by MySQL (DDL is not
    transactional). Django's state believes the fields are already widened,
    so a normal AlterField here would be a no-op.
    """

    dependencies = [
        ('APIS', '0015_remove_classdetail_center_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE `School` MODIFY COLUMN `SchoolName` varchar(100) NULL;"
                "ALTER TABLE `Student` MODIFY COLUMN `FullName` varchar(100) NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE `School` MODIFY COLUMN `SchoolName` varchar(50) NULL;"
                "ALTER TABLE `Student` MODIFY COLUMN `FullName` varchar(50) NULL;"
            ),
        ),
    ]
