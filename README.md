# Credit Approval System

A backend system for managing customer credit approvals, built with Django, Django REST Framework, PostgreSQL, Celery, and Docker.

---

## 🚀 Setup & Installation

### Prerequisites
- [Docker](https://www.docker.com/products/docker-desktop) installed on your machine
- Docker Compose (comes with Docker Desktop)

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd Credit Approval System
```

### 2. Add Data Files
Place `customer_data.xlsx` and `loan_data.xlsx` in the project root directory.

### 3. Build and Start the Services
```bash
docker-compose up --build -d
```

### 4. Ingest the Data
```bash
docker-compose run web python manage.py ingest_data
```

### 5. Create a Django Superuser (for admin access)
```bash
docker-compose run web python manage.py createsuperuser
```

### 6. Access the Admin Panel
Go to [http://localhost:8000/admin/](http://localhost:8000/admin/) and log in with your superuser credentials.

---

## 🛠️ API Endpoints
All endpoints are prefixed with `/api/`.

### 1. `/register/`  
**Add a new customer.**
- **Request (POST):**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "age": 30,
  "monthly_income": 50000,
  "phone_number": "9876543210"
}
```
- **Logic:**
  - `approved_limit = 36 * monthly_income` (rounded to the nearest lakh, i.e., 100,000)
- **Response:**
```json
{
  "customer_id": 301,
  "name": "John Doe",
  "age": 30,
  "monthly_income": 50000,
  "approved_limit": 1800000,
  "phone_number": "9876543210"
}
```

### 2. `/check-eligibility/`  
**Check if a customer is eligible for a new loan.**
- **Request (POST):**
```json
{
  "customer_id": 1,
  "loan_amount": 200000,
  "interest_rate": 14,
  "tenure": 12
}
```
- **Logic:**
  - Calculates a credit score (0-100) based on customer’s loan history.
  - **Credit Score Calculation:**
    - **Rule:** If sum of current loans > approved limit, score = 0 (hard rule).
    - **+1 point** for every on-time EMI paid (max 50).
    - **+5 points** for each loan in the current year (max 15).
    - **+1 point** for every 100,000 in total loan volume (max 20).
    - **-2 points** for every loan ever taken (max penalty -15).
    - Score is clamped between 0 and 100.
  - **Approval Rules:**
    - If credit_score > 50: approve loan
    - If 30 < credit_score ≤ 50: approve if interest_rate > 12%
    - If 10 < credit_score ≤ 30: approve if interest_rate > 16%
    - If credit_score ≤ 10: do not approve
    - If sum of all current EMIs > 50% of monthly salary: do not approve
    - If interest rate is too low for the slab, response includes `corrected_interest_rate`.
  - **EMI Calculation:** Uses the compound interest formula for monthly installment.
- **Response:**
```json
{
  "customer_id": 1,
  "approval": true,
  "interest_rate": 14.0,
  "corrected_interest_rate": 14.0,
  "tenure": 12,
  "monthly_installment": 17997.0
}
```

### 3. `/create-loan/`  
**Process a new loan for a customer.**
- **Request (POST):**
```json
{
  "customer_id": 1,
  "loan_amount": 200000,
  "interest_rate": 14,
  "tenure": 12
}
```
- **Logic:**
  - Uses the same eligibility logic as `/check-eligibility/`.
  - If approved, creates a new loan and updates the customer’s current debt.
- **Response (approved):**
```json
{
  "loan_id": 123,
  "customer_id": 1,
  "loan_approved": true,
  "message": "Loan approved and created.",
  "monthly_installment": 17997.0
}
```
- **Response (not approved):**
```json
{
  "loan_id": null,
  "customer_id": 1,
  "loan_approved": false,
  "message": "Sum of current EMIs exceeds 50% of monthly salary.",
  "monthly_installment": 17997.0
}
```

### 4. `/view-loan/<loan_id>/`  
**View details of a specific loan and its customer.**
- **Request (GET):**
  - No body required. Just provide the loan ID in the URL.
- **Response:**
```json
{
  "loan_id": 123,
  "customer": {
    "id": 1,
    "first_name": "John",
    "last_name": "Doe",
    "phone_number": "9876543210",
    "age": 30
  },
  "loan_amount": 200000,
  "interest_rate": 14.0,
  "monthly_installment": 17997.0,
  "tenure": 12
}
```

### 5. `/view-loans/<customer_id>/`  
**View all loans for a customer.**
- **Request (GET):**
  - No body required. Just provide the customer ID in the URL.
- **Response:**
```json
[
  {
    "loan_id": 123,
    "loan_amount": 200000,
    "interest_rate": 14.0,
    "monthly_installment": 17997.0,
    "repayments_left": 8
  },
  {
    "loan_id": 124,
    "loan_amount": 100000,
    "interest_rate": 12.0,
    "monthly_installment": 8888.0,
    "repayments_left": 4
  }
]
```

---

## 🧮 Math & Logic Details

### Credit Score Calculation
- **Rule:** If sum of current loans > approved limit, score = 0 (hard rule).
- **+1 point** for every on-time EMI paid (max 50).
- **+5 points** for each loan in the current year (max 15).
- **+1 point** for every 100,000 in total loan volume (max 20).
- **-2 points** for every loan ever taken (max penalty -15).
- Score is clamped between 0 and 100.

### EMI Calculation (Compound Interest)
- Formula:
  - `EMI = [P * r * (1 + r)^n] / [(1 + r)^n - 1]`
  - Where:
    - `P` = principal (loan amount)
    - `r` = monthly interest rate (annual_rate / 12 / 100)
    - `n` = tenure (months)

---

## 🧪 Running Unit Tests

To run all unit tests:
```bash
docker-compose run web python manage.py test
```

### What’s Tested?
- **/register:** Customer creation, response format, approved limit calculation.
- **/check-eligibility:** Credit score logic, approval rules, corrected interest, EMI calculation.
- **/create-loan:** Loan approval/rejection, loan creation, response format.
- **/view-loan/<loan_id>:** Correct loan and customer details returned.
- **/view-loans/<customer_id>:** List of loans, repayments left calculation.

Each test checks both typical and edge cases, ensuring the API is robust and reliable.

---

## 📋 Notes
- After testing, you can reset the database and re-import the Excel data for a clean state:
  ```bash
  docker-compose run web python manage.py flush --no-input
  docker-compose run web python manage.py migrate
  docker-compose run web python manage.py ingest_data
  ```
- For any questions, see the code comments or contact the project author.

---

Enjoy using the Credit Approval System!  