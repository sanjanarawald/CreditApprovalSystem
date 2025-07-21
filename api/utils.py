from .models import Loan
from django.db.models import Sum
from datetime import datetime

def calculate_credit_score(customer):
    """
    Calculate the credit score for a customer based on:
    - Past loans paid on time (+1 per EMI, max 50)
    - Loan activity in current year (+5 per loan, max 15)
    - Loan approved volume (+1 per 100,000, max 20)
    - Number of loans taken in past (-2 per loan, max penalty -15)
    - If sum of current loans > approved limit, score = 0 (hard rule)
    Score is clamped between 0 and 100.
    """
    loans = Loan.objects.filter(customer=customer)
    total_emis_paid_on_time = loans.aggregate(Sum('emis_paid_on_time'))['emis_paid_on_time__sum'] or 0
    num_loans_taken = loans.count()
    current_year = datetime.now().year
    loans_in_current_year = loans.filter(start_date__year=current_year).count()
    loan_approved_volume = loans.aggregate(Sum('loan_amount'))['loan_amount__sum'] or 0
    
    # Hard rule: if sum of current loans > approved limit, score = 0
    current_loans = loans.filter(end_date__gte=datetime.now())
    current_loans_sum = current_loans.aggregate(Sum('loan_amount'))['loan_amount__sum'] or 0
    if current_loans_sum > customer.approved_limit:
        return 0

    # Point-based scoring
    score = 0
    score += min(total_emis_paid_on_time, 50)  # up to 50 points for EMIs paid on time
    score += min(loans_in_current_year * 5, 15)  # up to 15 points for current year activity
    score += min(loan_approved_volume // 100000, 20)  # up to 20 points for volume
    score -= min(num_loans_taken * 2, 15)  # penalty for too many loans
    score = max(0, min(100, score))  # Clamp between 0 and 100
    return score

# Compound interest EMI calculation
# P = principal, r = monthly rate, n = tenure (months)
def calculate_emi(principal, annual_rate, tenure):
    """
    Calculate the monthly EMI using the compound interest formula:
    EMI = [P * r * (1 + r)^n] / [(1 + r)^n - 1]
    Where:
      P = principal (loan amount)
      r = monthly interest rate (annual_rate / 12 / 100)
      n = tenure (months)
    """
    r = annual_rate / (12 * 100)
    if r == 0:
        return principal / tenure
    emi = principal * r * ((1 + r) ** tenure) / (((1 + r) ** tenure) - 1)
    return round(emi, 2) 