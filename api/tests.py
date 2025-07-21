from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Customer
from .models import Loan

# Create your tests here.

class RegisterAPITest(APITestCase):
    def test_register_customer(self):
        url = reverse('register')
        data = {
            "first_name": "Unit",
            "last_name": "Test",
            "age": 28,
            "monthly_income": 60000,
            "phone_number": "8888888888"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('customer_id', response.data)
        self.assertEqual(response.data['name'], 'Unit Test')
        self.assertEqual(response.data['age'], 28)
        self.assertEqual(response.data['monthly_income'], 60000)
        self.assertEqual(response.data['phone_number'], '8888888888')
        self.assertTrue('approved_limit' in response.data)

class CheckEligibilityAPITest(APITestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            first_name="Elig",
            last_name="Test",
            age=35,
            monthly_salary=100000,
            phone_number="7777777777",
            approved_limit=3600000,
            current_debt=0
        )
    def test_check_eligibility(self):
        url = reverse('check-eligibility')
        data = {
            "customer_id": self.customer.id,
            "loan_amount": 200000,
            "interest_rate": 14,
            "tenure": 12
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('customer_id', response.data)
        self.assertIn('approval', response.data)
        self.assertIn('interest_rate', response.data)
        self.assertIn('corrected_interest_rate', response.data)
        self.assertIn('tenure', response.data)
        self.assertIn('monthly_installment', response.data)
        self.assertEqual(response.data['customer_id'], self.customer.id)
        self.assertEqual(response.data['tenure'], 12)

class CreateLoanAPITest(APITestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            first_name="Loan",
            last_name="Test",
            age=40,
            monthly_salary=120000,
            phone_number="6666666666",
            approved_limit=4320000,
            current_debt=0
        )
    def test_create_loan(self):
        url = reverse('create-loan')
        data = {
            "customer_id": self.customer.id,
            "loan_amount": 200000,
            "interest_rate": 14,
            "tenure": 12
        }
        response = self.client.post(url, data, format='json')
        self.assertIn('loan_id', response.data)
        self.assertIn('customer_id', response.data)
        self.assertIn('loan_approved', response.data)
        self.assertIn('message', response.data)
        self.assertIn('monthly_installment', response.data)
        if response.data['loan_approved']:
            self.assertIsNotNone(response.data['loan_id'])
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        else:
            self.assertIsNone(response.data['loan_id'])
            self.assertEqual(response.status_code, status.HTTP_200_OK)

class ViewLoanAPITest(APITestCase):
    def setUp(self):
        from datetime import date, timedelta
        self.customer = Customer.objects.create(
            first_name="View",
            last_name="Loan",
            age=50,
            monthly_salary=90000,
            phone_number="5555555555",
            approved_limit=3240000,
            current_debt=0
        )
        self.loan = Loan.objects.create(
            customer=self.customer,
            loan_amount=500000,
            tenure=24,
            interest_rate=10.5,
            monthly_repayment=23000,
            emis_paid_on_time=12,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30*24)
        )
    def test_view_loan(self):
        url = reverse('view-loan', args=[self.loan.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['loan_id'], self.loan.id)
        self.assertIn('customer', response.data)
        self.assertEqual(response.data['customer']['id'], self.customer.id)
        self.assertEqual(response.data['customer']['first_name'], self.customer.first_name)
        self.assertEqual(response.data['customer']['last_name'], self.customer.last_name)
        self.assertEqual(response.data['customer']['phone_number'], self.customer.phone_number)
        self.assertEqual(response.data['customer']['age'], self.customer.age)
        self.assertEqual(response.data['loan_amount'], self.loan.loan_amount)
        self.assertEqual(response.data['interest_rate'], self.loan.interest_rate)
        self.assertEqual(response.data['monthly_installment'], self.loan.monthly_repayment)
        self.assertEqual(response.data['tenure'], self.loan.tenure)

class ViewLoansAPITest(APITestCase):
    def setUp(self):
        from datetime import date, timedelta
        self.customer = Customer.objects.create(
            first_name="Multi",
            last_name="Loan",
            age=45,
            monthly_salary=80000,
            phone_number="4444444444",
            approved_limit=2880000,
            current_debt=0
        )
        self.loan1 = Loan.objects.create(
            customer=self.customer,
            loan_amount=300000,
            tenure=12,
            interest_rate=11.0,
            monthly_repayment=27000,
            emis_paid_on_time=6,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30*12)
        )
        self.loan2 = Loan.objects.create(
            customer=self.customer,
            loan_amount=150000,
            tenure=6,
            interest_rate=10.0,
            monthly_repayment=26000,
            emis_paid_on_time=2,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30*6)
        )
    def test_view_loans(self):
        url = reverse('view-loans', args=[self.customer.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 2)
        loan_ids = [item['loan_id'] for item in response.data]
        self.assertIn(self.loan1.id, loan_ids)
        self.assertIn(self.loan2.id, loan_ids)
        for item in response.data:
            if item['loan_id'] == self.loan1.id:
                self.assertEqual(item['repayments_left'], self.loan1.tenure - self.loan1.emis_paid_on_time)
            if item['loan_id'] == self.loan2.id:
                self.assertEqual(item['repayments_left'], self.loan2.tenure - self.loan2.emis_paid_on_time)
