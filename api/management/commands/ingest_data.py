from django.core.management.base import BaseCommand
from api.tasks import ingest_customer_data, ingest_loan_data

class Command(BaseCommand):
    help = 'Ingest data from Excel files'

    def handle(self, *args, **options):
        # Call the ingestion functions directly (not as Celery tasks)
        ingest_customer_data('customer_data.xlsx')
        ingest_loan_data('loan_data.xlsx')
        self.stdout.write(self.style.SUCCESS('Data ingestion completed directly.')) 