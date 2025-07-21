import logging
from celery import shared_task
import pandas as pd
from .models import Customer, Loan
from django.db.models import Sum
from datetime import datetime

logger = logging.getLogger(__name__)

@shared_task
def ingest_customer_data(file_path):
    """Ingest customer data from the provided Excel file."""
    df = pd.read_excel(file_path)
    for _, row in df.iterrows():
        Customer.objects.create(
            first_name=row['First Name'],
            last_name=row['Last Name'],
            age=row['Age'],
            monthly_salary=row['Monthly Salary'],
            phone_number=row['Phone Number'],
            approved_limit=row['Approved Limit'],
            current_debt=0  # Set to 0 initially
        )
    logger.info(f"Ingested {len(df)} customers from {file_path}.")

@shared_task
def ingest_loan_data(file_path):
    """Ingest loan data from the provided Excel file and update current_debt for each customer."""
    df = pd.read_excel(file_path)
    missing_customers = 0
    for _, row in df.iterrows():
        try:
            customer = Customer.objects.get(id=row['Customer ID'])
            Loan.objects.create(
                customer=customer,
                loan_amount=row['Loan Amount'],
                tenure=row['Tenure'],
                interest_rate=row['Interest Rate'],
                monthly_repayment=row['Monthly payment'],
                emis_paid_on_time=row['EMIs paid on Time'],  # Corrected column name
                start_date=row['Date of Approval'],
                end_date=row['End Date']
            )
        except Customer.DoesNotExist:
            logger.warning(f"Customer with ID {row['Customer ID']} not found for loan ingestion.")
            missing_customers += 1
    logger.info(f"Ingested {len(df) - missing_customers} loans from {file_path}. {missing_customers} loans skipped due to missing customers.")
    # After all loans are created, update current_debt for each customer
    for customer in Customer.objects.all():
        current_loans = Loan.objects.filter(customer=customer, end_date__gte=datetime.now())
        total_debt = current_loans.aggregate(Sum('loan_amount'))['loan_amount__sum'] or 0
        customer.current_debt = total_debt
        customer.save()
    logger.info("Updated current_debt for all customers after loan ingestion.") 