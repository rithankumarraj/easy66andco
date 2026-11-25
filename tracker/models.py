"""
Models for Easy 66 & Co — Thavanai Loan Management System.

Architecture:
- UserProfile: Extends User for Role (Admin / Employee) and Phone
- Customer: Stores borrower identity (Name, Phone, Email, Address)
- Loan: Represents each Thavanai loan contract (one customer can have MULTIPLE loans!)
- Installment: Individual daily/weekly/monthly repayment entries for a loan
"""
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum


class UserProfile(models.Model):
    """Extra profile info for users."""
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('employee', 'Employee'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=15, blank=True, default='')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='employee')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"


class Customer(models.Model):
    """Borrower / Customer Profile."""
    customer_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, default='')
    address = models.TextField(blank=True, default='')
    
    # Mandatory KYC Documents
    pan_card_doc = models.FileField(upload_to='customer_docs/pan/%Y/%m/', blank=True, null=True, help_text='PAN Card copy')
    aadhaar_card_doc = models.FileField(upload_to='customer_docs/aadhaar/%Y/%m/', blank=True, null=True, help_text='Aadhaar Card copy')
    utility_bill_doc = models.FileField(upload_to='customer_docs/utility/%Y/%m/', blank=True, null=True, help_text='Recent Utility Bill copy')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.phone})"

    def save(self, *args, **kwargs):
        if not self.customer_id:
            last = Customer.objects.order_by('-id').first()
            num = (last.id + 1) if last else 1
            self.customer_id = f'C{1000 + num}'
        super().save(*args, **kwargs)

    def total_loans_count(self):
        return self.loans.count()

    def active_loans_count(self):
        return self.loans.filter(status='active').count()

    def total_borrowed(self):
        return self.loans.aggregate(t=Sum('gross_principal'))['t'] or 0

    def total_paid(self):
        return Installment.objects.filter(
            loan__customer=self, status='paid'
        ).aggregate(t=Sum('paid_amount'))['t'] or 0

    def total_outstanding(self):
        return float(self.total_borrowed()) - float(self.total_paid())


class Loan(models.Model):
    """Thavanai Loan Contract — One customer can have multiple loans."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
    ]

    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    loan_id = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loans')

    # Thavanai Financials
    gross_principal = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Gross Principal (e.g. ₹10,000)'
    )
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.0,
        help_text='Upfront Interest % (e.g. 20%)'
    )
    upfront_interest = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Interest deducted upfront'
    )
    net_proceeds = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Net Disbursed Cash (e.g. ₹8,000)'
    )

    frequency = models.CharField(
        max_length=10, choices=FREQUENCY_CHOICES, default='daily',
        help_text='Collection Frequency'
    )
    installment_count = models.PositiveIntegerField(
        default=100,
        help_text='Total number of installments'
    )
    installment_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Amount per installment'
    )
    start_date = models.DateField()

    assigned_staff = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_loans',
        limit_choices_to={'profile__role': 'employee'},
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    
    # Cashfree Subscriptions & AutoPay Mandate
    payment_mode = models.CharField(
        max_length=20,
        choices=[('manual', 'Manual / Cash'), ('cashfree_auto', 'Cashfree AutoPay')],
        default='manual'
    )
    cashfree_subscription_id = models.CharField(max_length=100, blank=True, default='')
    cashfree_sub_status = models.CharField(
        max_length=50, blank=True, default='',
        help_text='INITIALIZED, ACTIVE, ON_HOLD, COMPLETED, CANCELLED'
    )
    cashfree_auth_link = models.URLField(max_length=500, blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.loan_id} — {self.customer.name} (₹{self.gross_principal:,.0f})"

    def save(self, *args, **kwargs):
        if not self.loan_id:
            last = Loan.objects.order_by('-id').first()
            num = (last.id + 1) if last else 1
            self.loan_id = f'LN{1000 + num}'

        gross = float(self.gross_principal)
        rate = float(self.interest_rate)
        count = int(self.installment_count) if self.installment_count else 1

        self.upfront_interest = round(gross * (rate / 100.0), 2)
        self.net_proceeds = round(gross - float(self.upfront_interest), 2)
        self.installment_amount = round(gross / count, 2)

        super().save(*args, **kwargs)

    # ---- Financial Summary Properties ----
    def paid_total(self):
        return self.installments.filter(status='paid').aggregate(
            total=Sum('paid_amount'))['total'] or 0

    def outstanding(self):
        return float(self.gross_principal) - float(self.paid_total())

    def paid_count(self):
        return self.installments.filter(status='paid').count()

    def pending_count(self):
        return self.installments.filter(status='pending').count()

    def overdue_count(self):
        return self.installments.filter(status='overdue').count()


class Installment(models.Model):
    """Single installment in a loan schedule."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='installments')
    num = models.PositiveIntegerField(help_text='Installment number (1, 2, 3…)')
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    paid_date = models.DateField(null=True, blank=True)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(
        max_length=25,
        choices=[('cash', 'Cash'), ('cashfree_auto', 'Cashfree AutoPay'), ('upi', 'UPI / Online')],
        default='cash'
    )
    cashfree_reference_id = models.CharField(max_length=100, blank=True, default='')
    collected_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='collections_made'
    )

    class Meta:
        ordering = ['due_date', 'num']
        unique_together = ['loan', 'num']

    def __str__(self):
        return f"{self.loan.loan_id} — #{self.num} ({self.status})"

    @property
    def customer(self):
        return self.loan.customer


class CashfreeConfig(models.Model):
    """Cashfree Subscriptions API Configuration for Sandbox / Test & Production."""
    ENV_CHOICES = [
        ('TEST', 'Sandbox / Test Environment'),
        ('PROD', 'Production Environment'),
    ]

    app_id = models.CharField(max_length=100, blank=True, default='', help_text='Cashfree Client/App ID')
    secret_key = models.CharField(max_length=150, blank=True, default='', help_text='Cashfree Secret Key')
    environment = models.CharField(max_length=10, choices=ENV_CHOICES, default='TEST')
    webhook_secret = models.CharField(max_length=150, blank=True, default='', help_text='Optional Webhook Secret')
    is_enabled = models.BooleanField(default=True, help_text='Enable Cashfree AutoPay Subscriptions')
    auto_debit = models.BooleanField(default=True, help_text='Auto-debit installments on due date')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cashfree Configuration'
        verbose_name_plural = 'Cashfree Configuration'

    def __str__(self):
        status = 'Configured' if (self.app_id and self.secret_key) else 'Simulator Mode'
        return f"Cashfree ({self.environment}) — {status}"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class WhatsAppConfig(models.Model):
    """Meta WhatsApp Cloud API Sandbox Configuration."""
    phone_number_id = models.CharField(max_length=50, blank=True, default='', help_text='Meta Phone Number ID')
    access_token = models.TextField(blank=True, default='', help_text='Meta User or System Access Token')
    business_account_id = models.CharField(max_length=50, blank=True, default='', help_text='WhatsApp Business Account ID')
    test_recipient_number = models.CharField(max_length=20, blank=True, default='', help_text='Sandbox verified recipient phone number (e.g. 919876543210)')
    is_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'WhatsApp Configuration'

    def __str__(self):
        status = 'Configured' if (self.phone_number_id and self.access_token) else 'Pending Credentials'
        return f"WhatsApp Cloud API Sandbox — {status}"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class LoanRequest(models.Model):
    """Borrower Loan Requests submitted via public request link."""
    EMPLOYMENT_CHOICES = [
        ('salaried', 'Salaried Employee'),
        ('self_employed', 'Self-Employed / Freelancer'),
        ('business', 'Business Owner / Trader'),
        ('daily_wage', 'Daily Wage / Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    request_id = models.CharField(max_length=20, unique=True, editable=False)
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.TextField()
    employment_type = models.CharField(max_length=25, choices=EMPLOYMENT_CHOICES, default='salaried')
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2, default=10000)
    frequency = models.CharField(max_length=10, choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='daily')

    # Mandatory Upload Documents (Only these 3 for all loans)
    pan_card_doc = models.FileField(upload_to='loan_docs/pan/%Y/%m/', blank=True, null=True, help_text='PAN Card file')
    aadhaar_card_doc = models.FileField(upload_to='loan_docs/aadhaar/%Y/%m/', blank=True, null=True, help_text='Aadhaar Card file')
    utility_bill_doc = models.FileField(upload_to='loan_docs/utility/%Y/%m/', blank=True, null=True, help_text='Recent Utility Bill (electricity, water, or piped gas bill within last 2-3 months)')

    # Document Status Flags
    has_pan_card = models.BooleanField(default=False)
    has_aadhaar_card = models.BooleanField(default=False)
    has_utility_bill = models.BooleanField(default=False)

    # Legacy fields
    has_rent_agreement = models.BooleanField(default=False)
    has_salary_slips = models.BooleanField(default=False)
    has_bank_statements = models.BooleanField(default=False)
    has_form16_itr = models.BooleanField(default=False)
    has_employment_proof = models.BooleanField(default=False)
    has_business_itr = models.BooleanField(default=False)
    has_business_bank_stmt = models.BooleanField(default=False)
    has_pnl_balance_sheet = models.BooleanField(default=False)

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.request_id} — {self.customer_name} (₹{self.requested_amount:,.0f})"

    def save(self, *args, **kwargs):
        if not self.request_id:
            last = LoanRequest.objects.order_by('-id').first()
            num = (last.id + 1) if last else 1
            self.request_id = f"REQ{1000 + num}"
        if self.pan_card_doc:
            self.has_pan_card = True
        if self.aadhaar_card_doc:
            self.has_aadhaar_card = True
        if self.utility_bill_doc:
            self.has_utility_bill = True
        super().save(*args, **kwargs)
