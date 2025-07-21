import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Customer
from .serializers import CustomerSerializer
from .utils import calculate_credit_score, calculate_emi
from .models import Loan
from django.db.models import Sum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def round_to_nearest_lakh(amount):
    """Round the given amount to the nearest lakh (100,000)."""
    return int(round(amount / 100000.0) * 100000)

class RegisterView(APIView):
    """API endpoint to register a new customer."""
    def post(self, request):
        data = request.data
        monthly_income = data.get('monthly_income')
        if not monthly_income:
            logger.warning("Registration failed: monthly_income is required.")
            return Response({'error': 'monthly_income is required'}, status=status.HTTP_400_BAD_REQUEST)
        approved_limit = round_to_nearest_lakh(36 * int(monthly_income))
        customer_data = {
            'first_name': data.get('first_name'),
            'last_name': data.get('last_name'),
            'age': data.get('age'),
            'monthly_salary': monthly_income,
            'phone_number': data.get('phone_number'),
            'approved_limit': approved_limit
        }
        serializer = CustomerSerializer(data=customer_data)
        if serializer.is_valid():
            customer = serializer.save()
            logger.info(f"Registered new customer: {customer.id} - {customer.first_name} {customer.last_name}")
            response_data = {
                'customer_id': customer.id,
                'name': f"{customer.first_name} {customer.last_name}",
                'age': customer.age,
                'monthly_income': customer.monthly_salary,
                'approved_limit': customer.approved_limit,
                'phone_number': customer.phone_number
            }
            return Response(response_data, status=status.HTTP_201_CREATED)
        logger.warning(f"Registration failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CheckEligibilityView(APIView):
    """API endpoint to check loan eligibility for a customer."""
    def post(self, request):
        customer_id = request.data.get('customer_id')
        loan_amount = float(request.data.get('loan_amount', 0))
        interest_rate = float(request.data.get('interest_rate', 0))
        tenure = int(request.data.get('tenure', 0))

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            logger.error(f"Eligibility check failed: Customer {customer_id} not found.")
            return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

        credit_score = calculate_credit_score(customer)
        approval = False
        corrected_interest_rate = interest_rate

        # Approval logic based on credit score
        if credit_score > 50:
            approval = True
            min_rate = 0
        elif 30 < credit_score <= 50:
            min_rate = 12
            if interest_rate > 12:
                approval = True
            else:
                corrected_interest_rate = 12
        elif 10 < credit_score <= 30:
            min_rate = 16
            if interest_rate > 16:
                approval = True
            else:
                corrected_interest_rate = 16
        else:
            min_rate = 100  # Not eligible
            approval = False
            corrected_interest_rate = 16

        # If sum of all current EMIs > 50% of monthly salary, don’t approve any loans
        current_loans = customer.loan_set.filter(end_date__gte=datetime.now())
        sum_of_current_emis = current_loans.aggregate(Sum('monthly_repayment'))['monthly_repayment__sum'] or 0
        if sum_of_current_emis > 0.5 * customer.monthly_salary:
            approval = False

        # If the interest rate does not match as per credit limit, correct it in the response
        if interest_rate < min_rate:
            corrected_interest_rate = min_rate

        monthly_installment = calculate_emi(loan_amount, corrected_interest_rate, tenure)

        logger.info(f"Eligibility checked for customer {customer_id}: approval={approval}, credit_score={credit_score}")
        response = {
            'customer_id': customer.id,
            'approval': approval,
            'interest_rate': interest_rate,
            'corrected_interest_rate': corrected_interest_rate,
            'tenure': tenure,
            'monthly_installment': monthly_installment
        }
        return Response(response, status=status.HTTP_200_OK)

class CreateLoanView(APIView):
    """API endpoint to create a new loan for a customer if eligible."""
    def post(self, request):
        customer_id = request.data.get('customer_id')
        loan_amount = float(request.data.get('loan_amount', 0))
        interest_rate = float(request.data.get('interest_rate', 0))
        tenure = int(request.data.get('tenure', 0))

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            logger.error(f"Loan creation failed: Customer {customer_id} not found.")
            return Response({'loan_id': None, 'customer_id': customer_id, 'loan_approved': False, 'message': 'Customer not found', 'monthly_installment': 0}, status=status.HTTP_404_NOT_FOUND)

        # Reuse eligibility logic
        credit_score = calculate_credit_score(customer)
        approval = False
        corrected_interest_rate = interest_rate
        message = ''

        if credit_score > 50:
            approval = True
            min_rate = 0
        elif 30 < credit_score <= 50:
            min_rate = 12
            if interest_rate > 12:
                approval = True
            else:
                corrected_interest_rate = 12
        elif 10 < credit_score <= 30:
            min_rate = 16
            if interest_rate > 16:
                approval = True
            else:
                corrected_interest_rate = 16
        else:
            min_rate = 100
            approval = False
            corrected_interest_rate = 16
            message = 'Credit score too low for loan approval.'

        # If sum of all current EMIs > 50% of monthly salary, don’t approve any loans
        current_loans = customer.loan_set.filter(end_date__gte=datetime.now())
        sum_of_current_emis = current_loans.aggregate(Sum('monthly_repayment'))['monthly_repayment__sum'] or 0
        if sum_of_current_emis > 0.5 * customer.monthly_salary:
            approval = False
            message = 'Sum of current EMIs exceeds 50% of monthly salary.'

        # If the interest rate does not match as per credit limit, correct it in the response
        if interest_rate < min_rate:
            corrected_interest_rate = min_rate
            message = f'Interest rate too low for credit score. Minimum required: {min_rate}%.'

        monthly_installment = calculate_emi(loan_amount, corrected_interest_rate, tenure)

        if approval:
            # Create the loan
            from datetime import date
            start_date = date.today()
            end_date = start_date + timedelta(days=30*tenure)
            loan = Loan.objects.create(
                customer=customer,
                loan_amount=loan_amount,
                tenure=tenure,
                interest_rate=corrected_interest_rate,
                monthly_repayment=monthly_installment,
                emis_paid_on_time=0,
                start_date=start_date,
                end_date=end_date
            )
            # Update current_debt
            current_loans = customer.loan_set.filter(end_date__gte=datetime.now())
            total_debt = current_loans.aggregate(Sum('loan_amount'))['loan_amount__sum'] or 0
            customer.current_debt = total_debt
            customer.save()
            logger.info(f"Loan {loan.id} created for customer {customer.id}.")
            return Response({
                'loan_id': loan.id,
                'customer_id': customer.id,
                'loan_approved': True,
                'message': 'Loan approved and created.',
                'monthly_installment': monthly_installment
            }, status=status.HTTP_201_CREATED)
        else:
            logger.info(f"Loan not approved for customer {customer.id}: {message or 'Loan not approved.'}")
            return Response({
                'loan_id': None,
                'customer_id': customer.id,
                'loan_approved': False,
                'message': message or 'Loan not approved.',
                'monthly_installment': monthly_installment
            }, status=status.HTTP_200_OK)

class ViewLoanView(APIView):
    """API endpoint to view details of a specific loan and its customer."""
    def get(self, request, loan_id):
        try:
            loan = Loan.objects.get(id=loan_id)
        except Loan.DoesNotExist:
            logger.error(f"View loan failed: Loan {loan_id} not found.")
            return Response({'error': 'Loan not found'}, status=status.HTTP_404_NOT_FOUND)

        customer = loan.customer
        customer_data = {
            'id': customer.id,
            'first_name': customer.first_name,
            'last_name': customer.last_name,
            'phone_number': customer.phone_number,
            'age': customer.age
        }

        response_data = {
            'loan_id': loan.id,
            'customer': customer_data,
            'loan_amount': loan.loan_amount,
            'interest_rate': loan.interest_rate,
            'monthly_installment': loan.monthly_repayment,
            'tenure': loan.tenure
        }
        logger.info(f"Viewed loan {loan.id} for customer {customer.id}.")
        return Response(response_data, status=status.HTTP_200_OK)

class ViewLoansView(APIView):
    """API endpoint to view all loans for a customer."""
    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            logger.error(f"View loans failed: Customer {customer_id} not found.")
            return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

        loans = Loan.objects.filter(customer=customer)
        response_data = []
        for loan in loans:
            repayments_left = loan.tenure - loan.emis_paid_on_time
            loan_item = {
                'loan_id': loan.id,
                'loan_amount': loan.loan_amount,
                'interest_rate': loan.interest_rate,
                'monthly_installment': loan.monthly_repayment,
                'repayments_left': repayments_left
            }
            response_data.append(loan_item)
        logger.info(f"Viewed {len(response_data)} loans for customer {customer.id}.")
        return Response(response_data, status=status.HTTP_200_OK)
