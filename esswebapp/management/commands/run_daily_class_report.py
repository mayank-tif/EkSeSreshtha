from django.core.management.base import BaseCommand
from esswebapp.views import send_daily_class_report

class Command(BaseCommand):
    help = 'Run the Daily Class Attendance Report scheduler'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting Daily Class Attendance Report generation...'))
        send_daily_class_report()
        self.stdout.write(self.style.SUCCESS('Daily Class Attendance Report sent successfully!'))
        