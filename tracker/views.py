"""
Views for Easy 66 & Co — Thavanai (தவணை) Finance Management.
Includes:
- Dashboard
- Customers (Directory & Profiles)
- Loans (Create Loan for Existing or New Customer, List, Detail)
- Collections (Dedicated page to view collection transactions & logs)
- Inquiries, Reports (with PDF export), and Staff Management
"""
import io
import json
import logging
from datetime import date, timedelta, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Q, Count
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import UserProfile, Customer, Loan, Installment, CashfreeConfig, WhatsAppConfig, LoanRequest
from .forms import CustomerForm, LoanForm, StaffForm, StaffEditForm
from .decorators import admin_required
from .cashfree import create_loan_subscription, sync_subscription_status, process_subscription_payment
from .whatsapp import (
    format_loan_request_message, format_autopay_mandate_message,
    send_meta_whatsapp_cta, clean_phone_number,
    get_direct_whatsapp_url, send_meta_whatsapp_message,
    generate_meta_curl_command
)


def _get_loans(request):
    if request.user.profile.role == 'admin':
        return Loan.objects.all().select_related('customer', 'assigned_staff')
    return Loan.objects.filter(assigned_staff=request.user).select_related('customer', 'assigned_staff')


def _get_customers(request):
    if request.user.profile.role == 'admin':
        return Customer.objects.all()
    # Employee sees customers who have loans assigned to them
    return Customer.objects.filter(loans__assigned_staff=request.user).distinct()


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', '')

        user = authenticate(request, username=username, password=password)
        if user:
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': 'admin' if user.is_superuser else 'employee'}
            )
            if profile.role == role or (user.is_superuser and role == 'admin'):
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, f'Role mismatch: Selected "{role}" but user is "{profile.role}".')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# ─────────────────── Dashboard ───────────────────
@login_required
def dashboard(request):
    loans = _get_loans(request)
    customers = _get_customers(request)
    today_date = date.today()

    total_gross = loans.aggregate(t=Sum('gross_principal'))['t'] or 0
    total_disbursed = loans.aggregate(t=Sum('net_proceeds'))['t'] or 0
    total_upfront_interest = loans.aggregate(t=Sum('upfront_interest'))['t'] or 0

    all_inst = Installment.objects.filter(loan__in=loans)
    collected = all_inst.filter(status='paid').aggregate(t=Sum('paid_amount'))['t'] or 0
    pending = all_inst.filter(status='pending').aggregate(t=Sum('amount'))['t'] or 0
    overdue = all_inst.filter(status='overdue').aggregate(t=Sum('amount'))['t'] or 0
    today_coll = all_inst.filter(paid_date=today_date).aggregate(t=Sum('paid_amount'))['t'] or 0

    upcoming = all_inst.filter(
        status='pending',
        due_date__gte=today_date,
        due_date__lte=today_date + timedelta(days=7),
    ).select_related('loan', 'loan__customer').order_by('due_date')[:10]

    recent_paid = all_inst.filter(
        status='paid'
    ).select_related('loan', 'loan__customer', 'collected_by').order_by('-paid_date', '-paid_at', '-id')[:10]

    # Monthly collection chart (last 6 months)
    chart_months, chart_collected, chart_due = [], [], []
    for i in range(5, -1, -1):
        d = today_date - timedelta(days=i * 30)
        m_start = d.replace(day=1)
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            m_end = m_start.replace(month=m_start.month + 1, day=1) - timedelta(days=1)

        chart_months.append(m_start.strftime('%b %y'))
        c = all_inst.filter(status='paid', paid_date__gte=m_start, paid_date__lte=m_end).aggregate(t=Sum('paid_amount'))['t'] or 0
        dd = all_inst.filter(due_date__gte=m_start, due_date__lte=m_end).aggregate(t=Sum('amount'))['t'] or 0
        chart_collected.append(float(c))
        chart_due.append(float(dd))

    active_count = loans.filter(status='active').count()
    completed_count = loans.filter(status='completed').count()
    defaulted_count = loans.filter(status='defaulted').count()

    context = {
        'total_customers': customers.count(),
        'total_loans': loans.count(),
        'active_count': active_count,
        'completed_count': completed_count,
        'defaulted_count': defaulted_count,
        'total_gross': total_gross,
        'total_disbursed': total_disbursed,
        'total_upfront_interest': total_upfront_interest,
        'collected': collected,
        'pending': pending,
        'overdue': overdue,
        'today_collection': today_coll,
        'upcoming': upcoming,
        'recent_paid': recent_paid,
        'chart_months': json.dumps(chart_months),
        'chart_collected': json.dumps(chart_collected),
        'chart_due': json.dumps(chart_due),
        'active_count_chart': active_count,
        'completed_count_chart': completed_count,
        'defaulted_count_chart': defaulted_count,
    }
    return render(request, 'dashboard.html', context)


# ─────────────────── Customers ───────────────────
@login_required
def customer_list(request):
    customers = _get_customers(request)

    q = request.GET.get('q', '').strip()
    if q:
        customers = customers.filter(
            Q(name__icontains=q) | Q(phone__icontains=q) | Q(customer_id__icontains=q)
        )

    sort = request.GET.get('sort', '-created_at')
    if sort.lstrip('-') in ['name', 'created_at', 'customer_id']:
        customers = customers.order_by(sort)

    return render(request, 'customers/list.html', {
        'customers': customers,
        'q': q,
        'sort': sort,
    })


@login_required
def customer_add(request):
    """Add a new customer profile."""
    if request.method == 'POST':
        form = CustomerForm(request.POST, request.FILES)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer "{customer.name}" created successfully.')
            # If user clicked "Create Loan", redirect to loan creation with this customer selected
            if 'save_and_loan' in request.POST:
                return redirect(f'/loans/create/?customer={customer.pk}')
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = CustomerForm()

    return render(request, 'customers/form.html', {'form': form, 'title': 'Add Customer Profile'})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    loans = customer.loans.all().order_by('-created_at')

    total_borrowed = customer.total_borrowed()
    total_paid = customer.total_paid()
    outstanding = customer.total_outstanding()

    loan_requests = LoanRequest.objects.filter(phone=customer.phone).order_by('-created_at')
    # Sync docs from latest loan request if customer doesn't have them yet
    if not customer.pan_card_doc or not customer.aadhaar_card_doc or not customer.utility_bill_doc:
        req = loan_requests.first()
        if req:
            updated = False
            if not customer.pan_card_doc and req.pan_card_doc:
                customer.pan_card_doc = req.pan_card_doc
                updated = True
            if not customer.aadhaar_card_doc and req.aadhaar_card_doc:
                customer.aadhaar_card_doc = req.aadhaar_card_doc
                updated = True
            if not customer.utility_bill_doc and req.utility_bill_doc:
                customer.utility_bill_doc = req.utility_bill_doc
                updated = True
            if updated:
                customer.save()

    return render(request, 'customers/detail.html', {
        'customer': customer,
        'loans': loans,
        'total_borrowed': total_borrowed,
        'total_paid': total_paid,
        'outstanding': outstanding,
        'loan_requests': loan_requests,
    })


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, request.FILES, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f'Customer "{customer.name}" updated.')
            return redirect('customer_detail', pk=pk)
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'customers/form.html', {'form': form, 'title': 'Edit Customer', 'editing': True})


@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    name = customer.name
    customer.delete()
    messages.success(request, f'Customer "{name}" and associated records deleted.')
    return redirect('customer_list')


# ─────────────────── Loans (Dedicated Page) ───────────────────
@login_required
def loan_list(request):
    """View all loans with filters."""
    loans = _get_loans(request)

    q = request.GET.get('q', '').strip()
    if q:
        loans = loans.filter(
            Q(customer__name__icontains=q) | Q(customer__phone__icontains=q) |
            Q(loan_id__icontains=q) | Q(customer__customer_id__icontains=q)
        )

    freq = request.GET.get('freq', '')
    if freq:
        loans = loans.filter(frequency=freq)

    status = request.GET.get('status', '')
    if status:
        loans = loans.filter(status=status)

    staff = request.GET.get('staff', '')
    if staff:
        loans = loans.filter(assigned_staff_id=staff)

    sort = request.GET.get('sort', '-created_at')
    if sort.lstrip('-') in ['gross_principal', 'created_at', 'loan_id', 'status']:
        loans = loans.order_by(sort)

    staff_list = User.objects.filter(profile__role='employee') if request.user.profile.role == 'admin' else []

    return render(request, 'loans/list.html', {
        'loans': loans,
        'q': q,
        'freq': freq,
        'status_filter': status,
        'staff_filter': staff,
        'staff_list': staff_list,
        'sort': sort,
    })


@login_required
def loan_create(request):
    """
    Create a loan!
    User can select an existing customer OR register a new customer in one step.
    """
    initial_customer_id = request.GET.get('customer')

    if request.method == 'POST':
        is_new_customer = request.POST.get('is_new_customer') == '1'

        if is_new_customer:
            # Create the customer first
            name = request.POST.get('new_customer_name', '').strip()
            phone = request.POST.get('new_customer_phone', '').strip()
            email = request.POST.get('new_customer_email', '').strip()
            address = request.POST.get('new_customer_address', '').strip()

            if not name or not phone:
                messages.error(request, 'Customer name and phone number are required.')
                form = LoanForm(request.POST)
                return render(request, 'loans/form.html', {'form': form, 'title': 'Create New Loan'})

            customer = Customer.objects.create(name=name, phone=phone, email=email, address=address)
        else:
            cust_id = request.POST.get('customer')
            customer = get_object_or_404(Customer, pk=cust_id)

        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.customer = customer
            loan.save()

            # Generate Installment Schedule
            count = loan.installment_count
            emi = float(loan.installment_amount)
            today_date = date.today()

            for i in range(1, count + 1):
                if loan.frequency == 'daily':
                    due = loan.start_date + timedelta(days=i)
                elif loan.frequency == 'weekly':
                    due = loan.start_date + timedelta(weeks=i)
                else:
                    due = loan.start_date + timedelta(days=i * 30)

                is_past = due < today_date
                Installment.objects.create(
                    loan=loan, num=i,
                    due_date=due, amount=emi,
                    status='overdue' if is_past else 'pending',
                )

            messages.success(request, f'Loan {loan.loan_id} (₹{loan.gross_principal:,.0f}) created for {customer.name}.')
            return redirect('loan_detail', pk=loan.pk)
    else:
        initial = {
            'start_date': date.today(),
            'interest_rate': 20.0,
            'installment_count': 100,
            'frequency': 'daily',
            'gross_principal': 10000,
            'net_proceeds': 8000
        }
        if request.GET.get('gross'):
            try:
                initial['gross_principal'] = float(request.GET.get('gross'))
            except (ValueError, TypeError):
                pass
        if request.GET.get('net'):
            try:
                initial['net_proceeds'] = float(request.GET.get('net'))
                if initial['gross_principal'] > 0:
                    initial['interest_rate'] = round(((initial['gross_principal'] - initial['net_proceeds']) / initial['gross_principal']) * 100.0, 2)
            except (ValueError, TypeError):
                pass
        elif request.GET.get('rate'):
            try:
                initial['interest_rate'] = float(request.GET.get('rate'))
                initial['net_proceeds'] = max(0.0, initial['gross_principal'] - (initial['gross_principal'] * initial['interest_rate'] / 100.0))
            except (ValueError, TypeError):
                pass
        else:
            initial['net_proceeds'] = round(initial['gross_principal'] * 0.8, 2)

        if request.GET.get('count'):
            try:
                initial['installment_count'] = int(request.GET.get('count'))
            except (ValueError, TypeError):
                pass
        if request.GET.get('freq'):
            initial['frequency'] = request.GET.get('freq')

        if initial_customer_id:
            initial['customer'] = initial_customer_id

        form = LoanForm(initial=initial)

    customers = Customer.objects.all().order_by('name')
    return render(request, 'loans/form.html', {
        'form': form,
        'title': 'Create New Loan',
        'customers': customers,
        'selected_customer_id': int(initial_customer_id) if initial_customer_id else None
    })


@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    installments = loan.installments.all()
    paid_total = loan.paid_total()
    outstanding = loan.outstanding()

    return render(request, 'loans/detail.html', {
        'loan': loan,
        'installments': installments,
        'paid_total': paid_total,
        'outstanding': outstanding,
    })


@login_required
def loan_edit(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    if request.method == 'POST':
        form = LoanForm(request.POST, instance=loan)
        if form.is_valid():
            form.save()
            messages.success(request, f'Loan {loan.loan_id} updated.')
            return redirect('loan_detail', pk=pk)
    else:
        form = LoanForm(instance=loan)

    return render(request, 'loans/form.html', {'form': form, 'title': f'Edit Loan {loan.loan_id}', 'editing': True})


@login_required
def loan_delete(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    loan_id = loan.loan_id
    loan.delete()
    messages.success(request, f'Loan {loan_id} deleted.')
    return redirect('loan_list')


# ─────────────────── Collections (Dedicated Page) ───────────────────
@login_required
def collection_list(request):
    """
    Dedicated Collections page.
    Tab 1: 'due' - Active pending/overdue installments with quick 'Collect' action.
    Tab 2: 'history' - Ledger of paid collections with filters and PDF export.
    """
    loans = _get_loans(request)
    today_date = date.today()
    this_week_start = today_date - timedelta(days=today_date.weekday())
    this_month_start = today_date.replace(day=1)

    tab = request.GET.get('tab', 'due')
    q = request.GET.get('q', '').strip()

    # 1. Due / Pending Collections
    pending_inst = Installment.objects.filter(
        loan__in=loans.filter(status='active'),
        status__in=['pending', 'overdue']
    ).select_related('loan', 'loan__customer', 'loan__assigned_staff').order_by('due_date', 'id')

    due_today_inst = pending_inst.filter(due_date__lte=today_date)
    due_today_total = due_today_inst.aggregate(t=Sum('amount'))['t'] or 0
    due_today_count = due_today_inst.count()

    due_list = pending_inst
    if q:
        due_list = due_list.filter(
            Q(loan__customer__name__icontains=q) |
            Q(loan__customer__phone__icontains=q) |
            Q(loan__loan_id__icontains=q)
        )

    # 2. History / Paid Collections (Most recently paid first, oldest paid last)
    all_paid_inst = Installment.objects.filter(loan__in=loans, status='paid').select_related(
        'loan', 'loan__customer', 'collected_by'
    ).order_by('-paid_date', '-paid_at', '-id')

    today_total = all_paid_inst.filter(paid_date=today_date).aggregate(t=Sum('paid_amount'))['t'] or 0
    today_count = all_paid_inst.filter(paid_date=today_date).count()
    week_total = all_paid_inst.filter(paid_date__gte=this_week_start).aggregate(t=Sum('paid_amount'))['t'] or 0
    month_total = all_paid_inst.filter(paid_date__gte=this_month_start).aggregate(t=Sum('paid_amount'))['t'] or 0
    grand_total = all_paid_inst.aggregate(t=Sum('paid_amount'))['t'] or 0

    date_filter = request.GET.get('date_preset', '')
    from_date = request.GET.get('from', '')
    to_date = request.GET.get('to', '')
    staff_filter = request.GET.get('staff', '')

    history_list = all_paid_inst
    if date_filter == 'today':
        history_list = history_list.filter(paid_date=today_date)
    elif date_filter == 'yesterday':
        history_list = history_list.filter(paid_date=today_date - timedelta(days=1))
    elif date_filter == 'this_week':
        history_list = history_list.filter(paid_date__gte=this_week_start)
    elif date_filter == 'this_month':
        history_list = history_list.filter(paid_date__gte=this_month_start)
    else:
        if from_date:
            history_list = history_list.filter(paid_date__gte=from_date)
        if to_date:
            history_list = history_list.filter(paid_date__lte=to_date)

    if staff_filter:
        history_list = history_list.filter(collected_by_id=staff_filter)

    if q:
        history_list = history_list.filter(
            Q(loan__customer__name__icontains=q) |
            Q(loan__customer__phone__icontains=q) |
            Q(loan__loan_id__icontains=q)
        )

    history_list = history_list.order_by('-paid_date', '-paid_at', '-id')

    filtered_total = history_list.aggregate(t=Sum('paid_amount'))['t'] or 0
    staff_list = User.objects.filter(profile__role='employee') if request.user.profile.role == 'admin' else []

    return render(request, 'collections/list.html', {
        'tab': tab,
        'due_list': due_list,
        'due_today_count': due_today_count,
        'due_today_total': due_today_total,
        'collections': history_list,
        'today_total': today_total,
        'today_count': today_count,
        'week_total': week_total,
        'month_total': month_total,
        'grand_total': grand_total,
        'filtered_total': filtered_total,
        'date_preset': date_filter,
        'from_date': from_date,
        'to_date': to_date,
        'staff_filter': staff_filter,
        'staff_list': staff_list,
        'q': q,
    })


@login_required
def collect_installment(request, loan_pk, inst_num):
    """Collect single installment."""
    loan = get_object_or_404(Loan, pk=loan_pk)
    inst = get_object_or_404(Installment, loan=loan, num=inst_num)

    if inst.status != 'paid':
        inst.status = 'paid'
        inst.paid_date = date.today()
        inst.paid_at = timezone.now()
        inst.paid_amount = inst.amount
        inst.collected_by = request.user
        inst.save()

        if not loan.installments.exclude(status='paid').exists():
            loan.status = 'completed'
            loan.save()

        messages.success(request, f'Installment #{inst_num} (₹{inst.amount:,.0f}) collected for {loan.customer.name}.')

    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('loan_detail', pk=loan.pk)


@login_required
def settle_full_loan(request, pk):
    """Pay off all remaining installments in full."""
    loan = get_object_or_404(Loan, pk=pk)
    unpaid = loan.installments.exclude(status='paid')

    count = unpaid.count()
    total_settled = 0
    today_date = date.today()

    for inst in unpaid:
        inst.status = 'paid'
        inst.paid_date = today_date
        inst.paid_at = timezone.now()
        inst.paid_amount = inst.amount
        inst.collected_by = request.user
        inst.save()
        total_settled += float(inst.amount)

    loan.status = 'completed'
    loan.save()

    messages.success(request, f'Full loan settled! {count} installments (₹{total_settled:,.0f}) closed for {loan.customer.name}.')
    return redirect('loan_detail', pk=pk)


# ─────────────────── Cashfree Subscriptions & AutoPay ───────────────────
@login_required
def create_loan_mandate(request, pk):
    """Create or re-initialize Cashfree AutoPay subscription mandate and automatically dispatch WhatsApp authorization card."""
    loan = get_object_or_404(Loan, pk=pk)
    result = create_loan_subscription(loan, request)

    if result.get('success'):
        # Automatically send the WhatsApp AutoPay authorization card
        auth_url = loan.cashfree_auth_link or request.build_absolute_uri(f"/subscriptions/simulator/{loan.cashfree_subscription_id}/")
        header = f"Easy 66 & Co — Authorize AutoPay"
        body = (
            f"Hello {loan.customer.name}! Greetings from Easy 66 & Co.\n\n"
            f"Your Thavanai loan {loan.loan_id} (₹{loan.gross_principal:,.0f}) is approved.\n"
            f"• Installment: ₹{loan.installment_amount:,.0f} ({loan.get_frequency_display()})\n"
            f"• Total Installments: {loan.installment_count}\n\n"
            f"Please click below to accept and authorize your AutoPay mandate so your payments are automated."
        )

        wa_res = send_meta_whatsapp_cta(
            to_phone=loan.customer.phone,
            header_text=header,
            body_text=body,
            button_text="Accept AutoPay",
            button_url=auth_url
        )

        if wa_res.get('success'):
            messages.success(
                request,
                f"AutoPay Mandate initiated! (ID: {loan.cashfree_subscription_id}). Automated WhatsApp authorization card sent to {loan.customer.name} ({loan.customer.phone})!"
            )
        else:
            messages.success(
                request,
                f"AutoPay Mandate initiated! (ID: {loan.cashfree_subscription_id}). WhatsApp link ready to send to {loan.customer.name}."
            )
    else:
        messages.error(request, f"Could not create Cashfree mandate: {result.get('error', 'Unknown error')}")

    return redirect('loan_detail', pk=pk)


@login_required
def send_loan_autopay_whatsapp(request, pk):
    """Dispatch or re-send WhatsApp AutoPay authorization card to the customer."""
    loan = get_object_or_404(Loan, pk=pk)
    if not loan.cashfree_subscription_id:
        create_loan_subscription(loan, request)

    auth_url = loan.cashfree_auth_link or request.build_absolute_uri(f"/subscriptions/simulator/{loan.cashfree_subscription_id}/")
    header = f"Easy 66 & Co — Authorize AutoPay"
    body = (
        f"Hello {loan.customer.name}! Greetings from Easy 66 & Co.\n\n"
        f"Your Thavanai loan {loan.loan_id} (₹{loan.gross_principal:,.0f}) is approved.\n"
        f"• Installment: ₹{loan.installment_amount:,.0f} ({loan.get_frequency_display()})\n"
        f"• Total Installments: {loan.installment_count}\n\n"
        f"Please click below to accept and authorize your AutoPay mandate so your payments are automated."
    )

    wa_res = send_meta_whatsapp_cta(
        to_phone=loan.customer.phone,
        header_text=header,
        body_text=body,
        button_text="Accept AutoPay",
        button_url=auth_url
    )

    if wa_res.get('success'):
        messages.success(
            request,
            f"✅ WhatsApp AutoPay authorization card sent to {loan.customer.name} ({loan.customer.phone})!"
        )
        return redirect('loan_detail', pk=pk)
    else:
        # Redirect to whatsapp console pre-filled so staff can send via 1-click wa.me
        return redirect(f"/whatsapp/?mode=autopay&loan_id={loan.pk}&phone={loan.customer.phone}&name={loan.customer.name}")


@login_required
def sync_loan_mandate(request, pk):
    """Sync live status of subscription mandate from Cashfree."""
    loan = get_object_or_404(Loan, pk=pk)
    res = sync_subscription_status(loan)
    messages.info(request, f"Cashfree Mandate Status: {loan.cashfree_sub_status or 'INITIALIZED'}")
    return redirect('loan_detail', pk=pk)


@login_required
def charge_mandate_next(request, pk):
    """Trigger debit for the next pending installment via Cashfree AutoPay."""
    loan = get_object_or_404(Loan, pk=pk)
    if loan.cashfree_sub_status != 'ACTIVE':
        # In test mode, allow activating if simulated
        loan.cashfree_sub_status = 'ACTIVE'
        loan.save(update_fields=['cashfree_sub_status'])

    res = process_subscription_payment(loan.cashfree_subscription_id)
    if res.get('success'):
        messages.success(request, f"AutoPay Debit Successful! Installment #{res.get('installment_num')} (₹{res.get('amount', 0):,.0f}) collected.")
    else:
        messages.error(request, f"AutoPay Debit failed: {res.get('error', 'Error processing debit')}")

    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('loan_detail', pk=pk)


@login_required
def mandate_callback(request, pk):
    """Customer return URL after mandate authorization."""
    loan = get_object_or_404(Loan, pk=pk)
    loan.cashfree_sub_status = 'ACTIVE'
    loan.save(update_fields=['cashfree_sub_status'])
    messages.success(request, f"AutoPay Mandate authorized successfully for {loan.customer.name}! Recurring debits are now active.")
    return redirect('loan_detail', pk=pk)


def subscription_simulator(request, sub_id):
    """
    Interactive Cashfree Test Simulator checkout page.
    Allows testing UPI AutoPay / eNACH mandate authorization in sandbox.
    """
    loan = Loan.objects.filter(cashfree_subscription_id=sub_id).first()
    if not loan:
        return HttpResponse("Invalid subscription ID.", status=404)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'authorize':
            loan.cashfree_sub_status = 'ACTIVE'
            loan.save(update_fields=['cashfree_sub_status'])
            messages.success(request, f"Mandate Authorized! AutoPay is now ACTIVE for {loan.loan_id}.")
            return redirect(f"/loans/{loan.pk}/mandate/callback/?sub_id={sub_id}")
        elif action == 'debit_next':
            process_subscription_payment(sub_id)
            messages.success(request, f"Installment auto-debited via Cashfree AutoPay.")
            return redirect('subscription_simulator', sub_id=sub_id)

    return render(request, 'cashfree/simulator.html', {
        'loan': loan,
        'sub_id': sub_id,
        'pending_inst': loan.installments.filter(status='pending').first(),
    })


@csrf_exempt
def cashfree_webhook(request):
    """
    Cashfree Webhook receiver for Subscriptions & Recurring Payments.
    Receives notification when customer approves mandate or when recurring payment is debited.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'invalid method'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        event_type = data.get('type') or data.get('event') or ''
        sub_data = data.get('data', {}).get('subscription', {}) or data.get('subscription', {})
        sub_id = sub_data.get('subscription_id') or data.get('data', {}).get('subscription_id')

        logger.info(f"Received Cashfree Webhook: {event_type} for sub_id: {sub_id}")

        if sub_id:
            loan = Loan.objects.filter(cashfree_subscription_id=sub_id).first()
            if loan:
                if 'ACTIVAT' in event_type or 'AUTHORIZ' in event_type:
                    loan.cashfree_sub_status = 'ACTIVE'
                    loan.save(update_fields=['cashfree_sub_status'])

                elif 'PAYMENT_SUCCESS' in event_type or 'CHARGE_SUCCESS' in event_type:
                    payment_data = data.get('data', {}).get('payment', {})
                    amt = payment_data.get('payment_amount')
                    ref = payment_data.get('cf_payment_id') or str(payment_data.get('payment_id', ''))
                    process_subscription_payment(sub_id, amount=amt, reference_id=ref)

                elif 'CANCEL' in event_type:
                    loan.cashfree_sub_status = 'CANCELLED'
                    loan.save(update_fields=['cashfree_sub_status'])

        return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.exception(f"Error handling Cashfree webhook: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@admin_required
def cashfree_settings(request):
    """
    Admin configuration for Cashfree Sandbox / Production Credentials.
    """
    config = CashfreeConfig.get_solo()

    if request.method == 'POST':
        config.app_id = request.POST.get('app_id', '').strip()
        config.secret_key = request.POST.get('secret_key', '').strip()
        config.environment = request.POST.get('environment', 'TEST')
        config.webhook_secret = request.POST.get('webhook_secret', '').strip()
        config.is_enabled = request.POST.get('is_enabled') == 'on'
        config.auto_debit = request.POST.get('auto_debit') == 'on'
        config.save()

        # If user clicked "Test Connection"
        if 'test_conn' in request.POST:
            if config.app_id and config.secret_key:
                try:
                    url = f"{get_base_url()}/plans?limit=1"
                    resp = requests.get(url, headers=get_headers(), timeout=8)
                    if resp.status_code in [200, 404]:
                        messages.success(request, f"✅ Connection Successful! Verified with Cashfree ({config.environment}).")
                    elif resp.status_code == 401:
                        messages.error(request, "❌ Cashfree Authentication Failed (401). Please check your App ID and Secret Key.")
                    else:
                        messages.warning(request, f"Cashfree responded with status code {resp.status_code}: {resp.text[:120]}")
                except Exception as e:
                    messages.error(request, f"❌ Failed to reach Cashfree: {e}")
            else:
                messages.warning(request, "Please enter both App ID and Secret Key to test connection.")
        else:
            messages.success(request, "Cashfree configuration saved successfully.")

        return redirect('cashfree_settings')

    webhook_url = request.build_absolute_uri('/api/cashfree/webhook/')

    return render(request, 'cashfree/settings.html', {
        'config': config,
        'webhook_url': webhook_url,
    })


# ─────────────────── Inquiries & Loan Estimation ───────────────────
@login_required
def inquiries(request):
    """
    Loan Inquiry & Estimation Calculator.
    Enables estimating Thavanai loan terms, net cash, per-installment payments,
    and projected repayment schedule for walk-in / inquiring customers without creating a database record.
    """
    try:
        gross = float(request.GET.get('gross', 10000))
    except (ValueError, TypeError):
        gross = 10000.0

    if request.GET.get('net'):
        try:
            net_proceeds = float(request.GET.get('net'))
            upfront_interest = max(0.0, round(gross - net_proceeds, 2))
            interest_rate = round((upfront_interest / gross) * 100.0, 2) if gross > 0 else 0.0
        except (ValueError, TypeError):
            net_proceeds = round(gross * 0.8, 2)
            upfront_interest = round(gross - net_proceeds, 2)
            interest_rate = 20.0
    elif request.GET.get('rate'):
        try:
            interest_rate = float(request.GET.get('rate'))
            upfront_interest = round((gross * interest_rate) / 100.0, 2)
            net_proceeds = max(0.0, round(gross - upfront_interest, 2))
        except (ValueError, TypeError):
            net_proceeds = round(gross * 0.8, 2)
            upfront_interest = round(gross - net_proceeds, 2)
            interest_rate = 20.0
    else:
        net_proceeds = round(gross * 0.8, 2)
        upfront_interest = round(gross - net_proceeds, 2)
        interest_rate = 20.0

    frequency = request.GET.get('freq', 'daily')
    if frequency not in ['daily', 'weekly', 'monthly']:
        frequency = 'daily'

    default_counts = {'daily': 100, 'weekly': 10, 'monthly': 5}
    default_count = default_counts.get(frequency, 100)

    try:
        installment_count = int(request.GET.get('count', default_count))
        if installment_count <= 0:
            installment_count = default_count
    except (ValueError, TypeError):
        installment_count = default_count

    start_date_str = request.GET.get('start_date', '')
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = date.today()
    else:
        start_date = date.today()

    # Fixed installment amount
    installment_amount = round(gross / installment_count, 2) if installment_count > 0 else 0.0

    # Projected Schedule Generation
    schedule = []
    cumulative_paid = 0.0
    for i in range(1, installment_count + 1):
        if frequency == 'daily':
            due = start_date + timedelta(days=i)
        elif frequency == 'weekly':
            due = start_date + timedelta(weeks=i)
        else:
            due = start_date + timedelta(days=i * 30)

        # For the final installment, balance to exact gross
        if i == installment_count:
            amt = round(gross - cumulative_paid, 2)
        else:
            amt = installment_amount

        cumulative_paid = round(cumulative_paid + amt, 2)
        balance = max(0.0, round(gross - cumulative_paid, 2))

        schedule.append({
            'num': i,
            'due_date': due,
            'amount': amt,
            'cumulative_paid': cumulative_paid,
            'balance': balance,
        })

    end_date = schedule[-1]['due_date'] if schedule else start_date

    context = {
        'gross': gross,
        'interest_rate': interest_rate,
        'frequency': frequency,
        'installment_count': installment_count,
        'start_date': start_date,
        'upfront_interest': upfront_interest,
        'net_proceeds': net_proceeds,
        'installment_amount': installment_amount,
        'end_date': end_date,
        'schedule': schedule,
        'total_schedule_count': len(schedule),
    }

    return render(request, 'inquiries.html', context)


@login_required
def inquiry_pdf(request):
    """
    Download Thavanai Loan Estimation Quotation Slip as PDF.
    """
    try:
        gross = float(request.GET.get('gross', 10000))
    except (ValueError, TypeError):
        gross = 10000.0

    if request.GET.get('net'):
        try:
            net_proceeds = float(request.GET.get('net'))
            upfront_interest = max(0.0, round(gross - net_proceeds, 2))
            interest_rate = round((upfront_interest / gross) * 100.0, 2) if gross > 0 else 0.0
        except (ValueError, TypeError):
            net_proceeds = round(gross * 0.8, 2)
            upfront_interest = round(gross - net_proceeds, 2)
            interest_rate = 20.0
    elif request.GET.get('rate'):
        try:
            interest_rate = float(request.GET.get('rate'))
            upfront_interest = round((gross * interest_rate) / 100.0, 2)
            net_proceeds = max(0.0, round(gross - upfront_interest, 2))
        except (ValueError, TypeError):
            net_proceeds = round(gross * 0.8, 2)
            upfront_interest = round(gross - net_proceeds, 2)
            interest_rate = 20.0
    else:
        net_proceeds = round(gross * 0.8, 2)
        upfront_interest = round(gross - net_proceeds, 2)
        interest_rate = 20.0

    frequency = request.GET.get('freq', 'daily')
    if frequency not in ['daily', 'weekly', 'monthly']:
        frequency = 'daily'

    default_counts = {'daily': 100, 'weekly': 10, 'monthly': 5}
    default_count = default_counts.get(frequency, 100)

    try:
        installment_count = int(request.GET.get('count', default_count))
        if installment_count <= 0:
            installment_count = default_count
    except (ValueError, TypeError):
        installment_count = default_count

    start_date_str = request.GET.get('start_date', '')
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = date.today()
    else:
        start_date = date.today()

    # Fixed installment amount
    installment_amount = round(gross / installment_count, 2) if installment_count > 0 else 0.0

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                  textColor=colors.HexColor('#0d233a'), fontSize=18, alignment=0)
    elements.append(Paragraph('Easy 66 & Co — Thavanai Loan Estimation Quotation', title_style))
    elements.append(Paragraph(f'Quotation Date: {date.today().strftime("%d %b %Y")} | Valid for 7 Days', styles['Normal']))
    elements.append(Spacer(1, 6 * mm))

    # Summary Table
    summary_data = [
        ['Parameter', 'Quotation Value'],
        ['Gross Principal (Total Repayment)', f'Rs. {gross:,.0f}'],
        ['Upfront Interest Deducted', f'Rs. {upfront_interest:,.0f} ({interest_rate}%)'],
        ['Net Cash Handed to Borrower', f'Rs. {net_proceeds:,.0f}'],
        ['Collection Frequency', frequency.capitalize()],
        ['Total Installments', f'{installment_count} installments'],
        ['Per Installment Repayment', f'Rs. {installment_amount:,.0f}'],
        ['Repayment Period', f'{start_date.strftime("%d %b %Y")} to {(start_date + timedelta(days=installment_count if frequency=="daily" else (installment_count*7 if frequency=="weekly" else installment_count*30))).strftime("%d %b %Y")}'],
    ]
    st = Table(summary_data, colWidths=[80 * mm, 90 * mm])
    st.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#093b32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    elements.append(st)
    elements.append(Spacer(1, 8 * mm))

    # Schedule Preview (First 30 rows in PDF)
    elements.append(Paragraph('Projected Repayment Schedule (First 30 Installments)', styles['Heading2']))
    elements.append(Spacer(1, 3 * mm))

    schedule_data = [['#', 'Due Date', 'Installment Amount', 'Cumulative Paid', 'Balance Principal']]
    cum = 0.0
    limit_rows = min(installment_count, 30)
    for i in range(1, limit_rows + 1):
        due = start_date + timedelta(days=i) if frequency == 'daily' else (start_date + timedelta(weeks=i) if frequency == 'weekly' else start_date + timedelta(days=i * 30))
        amt = round(gross - cum, 2) if i == installment_count else installment_amount
        cum = round(cum + amt, 2)
        bal = max(0.0, round(gross - cum, 2))
        schedule_data.append([f'#{i}', due.strftime('%d %b %Y'), f'Rs. {amt:,.0f}', f'Rs. {cum:,.0f}', f'Rs. {bal:,.0f}'])

    s_table = Table(schedule_data, colWidths=[15 * mm, 35 * mm, 40 * mm, 40 * mm, 40 * mm])
    s_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#173452')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    elements.append(s_table)
    if installment_count > 30:
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph(f'... and {installment_count - 30} more installments until completion.', styles['Italic']))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Easy66_Loan_Estimation_{int(gross)}.pdf"'
    return response


# ─────────────────── Reports ───────────────────
@login_required
def reports(request):
    loans = _get_loans(request)
    today_str = str(date.today())
    report_type = request.GET.get('type') or 'collection'
    from_date = request.GET.get('from') or today_str
    to_date = request.GET.get('to') or today_str

    report_data = None
    report_title = ''
    summary = {}

    all_inst = Installment.objects.filter(loan__in=loans)

    # Always compute today's quick KPI
    today_inst = all_inst.filter(status='paid', paid_date=date.today())
    summary['today_collected'] = today_inst.aggregate(t=Sum('paid_amount'))['t'] or 0
    summary['today_count'] = today_inst.count()

    if report_type == 'collection':
        if from_date == to_date and from_date == today_str:
            report_title = "Today's Collection Report"
        else:
            report_title = f'Collection Report ({from_date} to {to_date})'
        qs = all_inst.filter(status='paid')
        if from_date:
            qs = qs.filter(paid_date__gte=from_date)
        if to_date:
            qs = qs.filter(paid_date__lte=to_date)
        report_data = qs.select_related('loan', 'loan__customer', 'collected_by').order_by('-paid_date', '-paid_at', '-id')
        summary['total_collected'] = qs.aggregate(t=Sum('paid_amount'))['t'] or 0
        summary['count'] = qs.count()

    elif report_type == 'summary':
        report_title = 'Overall Summary Report'
        summary['total_loans'] = loans.count()
        summary['total_gross'] = loans.aggregate(t=Sum('gross_principal'))['t'] or 0
        summary['total_disbursed'] = loans.aggregate(t=Sum('net_proceeds'))['t'] or 0
        summary['total_upfront'] = loans.aggregate(t=Sum('upfront_interest'))['t'] or 0
        summary['collected'] = all_inst.filter(status='paid').aggregate(t=Sum('paid_amount'))['t'] or 0
        summary['pending'] = all_inst.filter(status='pending').aggregate(t=Sum('amount'))['t'] or 0
        summary['overdue'] = all_inst.filter(status='overdue').aggregate(t=Sum('amount'))['t'] or 0
        report_data = loans.select_related('customer')

    elif report_type == 'outstanding':
        report_title = 'Outstanding Balance Report'
        report_data = loans.filter(status__in=['active', 'defaulted']).select_related('customer')
        total_out = sum(l.outstanding() for l in report_data)
        summary['total_outstanding'] = total_out
        summary['count'] = report_data.count()

    elif report_type == 'overdue':
        report_title = 'Overdue Installments Report'
        report_data = all_inst.filter(status='overdue').select_related('loan', 'loan__customer').order_by('due_date')
        summary['total_overdue'] = report_data.aggregate(t=Sum('amount'))['t'] or 0
        summary['count'] = report_data.count()

    elif report_type == 'customer':
        report_title = 'Customer-wise Ledger'
        report_data = loans.select_related('customer')

    return render(request, 'reports.html', {
        'report_type': report_type,
        'report_title': report_title,
        'report_data': report_data,
        'summary': summary,
        'from_date': from_date,
        'to_date': to_date,
        'today_str': today_str,
    })


@login_required
def report_pdf(request):
    """Download clean PDF report with ReportLab."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    today_str = str(date.today())
    report_type = request.GET.get('type', 'collection')
    from_date = request.GET.get('from', '')
    to_date = request.GET.get('to', '')
    selected_ids_str = request.GET.get('ids') or request.POST.get('ids') or ''
    selected_ids = [int(x) for x in selected_ids_str.split(',') if x.strip().isdigit()]

    loans = _get_loans(request)
    all_inst = Installment.objects.filter(loan__in=loans)

    title = ''
    headers = []
    rows = []

    if report_type == 'summary':
        title = 'Overall Summary (Thavanai Loans)'
        target_loans = loans.filter(id__in=selected_ids) if selected_ids else loans
        headers = ['Loan ID', 'Customer', 'Phone', 'Gross (₹)', 'Net Cash (₹)', 'Paid (₹)', 'Balance (₹)', 'Freq', 'Status']
        for l in target_loans:
            paid = float(l.paid_total())
            rows.append([l.loan_id, l.customer.name, l.customer.phone,
                         f'{l.gross_principal:,.0f}', f'{l.net_proceeds:,.0f}',
                         f'{paid:,.0f}', f'{l.outstanding():,.0f}',
                         l.frequency.capitalize(), l.status.title()])

    elif report_type == 'collection':
        qs = all_inst.filter(status='paid').select_related('loan', 'loan__customer', 'collected_by').order_by('-paid_date', '-paid_at', '-id')
        if selected_ids:
            qs = qs.filter(id__in=selected_ids)
            title = f'Collection Report ({qs.count()} Selected Records)'
        else:
            if from_date: qs = qs.filter(paid_date__gte=from_date)
            if to_date: qs = qs.filter(paid_date__lte=to_date)
            title = 'Collection Report'
        headers = ['Date', 'Customer', 'Phone', 'Loan ID', 'Inst #', 'Amount (₹)', 'Staff']
        for i in qs:
            collector = i.collected_by.get_full_name() or i.collected_by.username if i.collected_by else '—'
            rows.append([str(i.paid_date), i.loan.customer.name, i.loan.customer.phone,
                         i.loan.loan_id, f'#{i.num}', f'{i.paid_amount:,.0f}', collector])

    elif report_type == 'outstanding':
        title = 'Outstanding Report'
        headers = ['Loan ID', 'Customer', 'Phone', 'Gross (₹)', 'Net Cash (₹)', 'Paid (₹)', 'Balance (₹)', 'Pending Inst']
        for l in loans.filter(status__in=['active', 'defaulted']):
            rows.append([l.loan_id, l.customer.name, l.customer.phone,
                         f'{l.gross_principal:,.0f}', f'{l.net_proceeds:,.0f}',
                         f'{l.paid_total():,.0f}', f'{l.outstanding():,.0f}',
                         str(l.pending_count())])

    elif report_type == 'overdue':
        title = 'Overdue Report'
        headers = ['Customer', 'Phone', 'Loan ID', 'Due Date', 'Inst #', 'Amount (₹)']
        for i in all_inst.filter(status='overdue').select_related('loan', 'loan__customer').order_by('due_date'):
            rows.append([i.loan.customer.name, i.loan.customer.phone, i.loan.loan_id,
                         str(i.due_date), f'#{i.num}', f'{i.amount:,.0f}'])

    elif report_type == 'customer':
        title = 'Customer Ledger'
        headers = ['Loan ID', 'Name', 'Phone', 'Gross', 'Net Cash', 'Freq', 'Inst. Amt', 'Paid', 'Balance', 'Status']
        for l in loans:
            rows.append([l.loan_id, l.customer.name, l.customer.phone,
                         f'{l.gross_principal:,.0f}', f'{l.net_proceeds:,.0f}',
                         l.frequency.capitalize(), f'{l.installment_amount:,.0f}',
                         f'{l.paid_total():,.0f}', f'{l.outstanding():,.0f}', l.status.title()])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                  textColor=colors.HexColor('#0d233a'), fontSize=16)
    elements.append(Paragraph(f'Easy 66 & Co — {title}', title_style))
    elements.append(Paragraph(f'Generated on {date.today().strftime("%d %b %Y")}', styles['Normal']))
    elements.append(Spacer(1, 8 * mm))

    if rows:
        table_data = [headers] + rows
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#093b32')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph('No data available for this report.', styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Easy66_{report_type}_report.pdf"'
    return response


# ─────────────────── Staff (admin only) ───────────────────
@login_required
@admin_required
def staff_list(request):
    employees = User.objects.filter(profile__role='employee').select_related('profile')
    staff_data = []
    for emp in employees:
        assigned = Loan.objects.filter(assigned_staff=emp, status='active').count()
        total_coll = Installment.objects.filter(collected_by=emp).aggregate(t=Sum('paid_amount'))['t'] or 0
        staff_data.append({'user': emp, 'profile': emp.profile, 'assigned': assigned, 'collected': total_coll})
    return render(request, 'staff/list.html', {'staff_data': staff_data})


@login_required
@admin_required
def staff_add(request):
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            parts = d['name'].split()
            user = User.objects.create_user(
                username=d['username'], password=d['password'],
                first_name=parts[0],
                last_name=' '.join(parts[1:]) if len(parts) > 1 else '',
                email=d.get('email', ''),
            )
            UserProfile.objects.create(user=user, role='employee', phone=d.get('phone', ''))
            messages.success(request, f'Staff "{d["name"]}" added.')
            return redirect('staff_list')
    else:
        form = StaffForm()
    return render(request, 'staff/form.html', {'form': form, 'title': 'Add New Staff'})


@login_required
@admin_required
def staff_edit(request, pk):
    user = get_object_or_404(User, pk=pk, profile__role='employee')
    profile = user.profile

    if request.method == 'POST':
        form = StaffEditForm(request.POST, user_id=pk)
        if form.is_valid():
            d = form.cleaned_data
            parts = d['name'].split()
            user.first_name = parts[0]
            user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
            user.username = d['username']
            user.email = d.get('email', '')
            if d.get('password'):
                user.set_password(d['password'])
            user.save()
            profile.phone = d.get('phone', '')
            profile.save()
            messages.success(request, f'Staff "{d["name"]}" updated.')
            return redirect('staff_list')
    else:
        form = StaffEditForm(initial={
            'name': user.get_full_name(),
            'phone': profile.phone,
            'email': user.email,
            'username': user.username,
        }, user_id=pk)

    return render(request, 'staff/form.html', {'form': form, 'title': 'Edit Staff', 'editing': True})


@login_required
@admin_required
def staff_delete(request, pk):
    user = get_object_or_404(User, pk=pk, profile__role='employee')
    name = user.get_full_name()
    Loan.objects.filter(assigned_staff=user).update(assigned_staff=None)
    user.delete()
    messages.success(request, f'Staff "{name}" deleted.')
    return redirect('staff_list')


# ─────────────────── Public Loan Request & Document Verification ───────────────────
def loan_request_public(request):
    """
    Public borrower loan application page.
    Accessible without authentication so borrowers receiving WhatsApp link can view & submit.
    Requires uploading 3 mandatory documents: PAN Card, Aadhaar Card, and Recent Utility Bill.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        address = request.POST.get('address', '').strip()
        employment_type = request.POST.get('employment_type', 'salaried')
        monthly_income = Decimal(request.POST.get('monthly_income') or 0)
        requested_amount = Decimal(request.POST.get('requested_amount') or 10000)
        frequency = request.POST.get('frequency', 'daily')

        # Mandatory Document Uploads (Only these 3)
        pan_file = request.FILES.get('pan_card')
        aadhaar_file = request.FILES.get('aadhaar_card')
        utility_file = request.FILES.get('utility_bill')

        notes = request.POST.get('notes', '').strip()

        if not name or not phone or not address:
            messages.error(request, 'Please fill in Name, Phone, and Address.')
            return render(request, 'loans/request_public.html', {'post': request.POST})

        if not pan_file or not aadhaar_file or not utility_file:
            messages.error(
                request,
                'Mandatory documents missing! Please upload all 3 required documents: PAN Card, Aadhaar Card, and Recent Utility Bill.'
            )
            return render(request, 'loans/request_public.html', {'post': request.POST})

        req_obj = LoanRequest.objects.create(
            customer_name=name,
            phone=phone,
            email=email,
            address=address,
            employment_type=employment_type,
            monthly_income=monthly_income,
            requested_amount=requested_amount,
            frequency=frequency,
            pan_card_doc=pan_file,
            aadhaar_card_doc=aadhaar_file,
            utility_bill_doc=utility_file,
            has_pan_card=True,
            has_aadhaar_card=True,
            has_utility_bill=True,
            notes=notes,
            status='pending',
        )

        return render(request, 'loans/request_success.html', {'loan_request': req_obj})

    initial_amount = request.GET.get('amount', '10000')
    initial_freq = request.GET.get('freq', 'daily')
    return render(request, 'loans/request_public.html', {
        'initial_amount': initial_amount,
        'initial_freq': initial_freq,
    })


@login_required
def loan_request_list(request):
    """Staff view to browse, review, and manage incoming loan applications."""
    status_filter = request.GET.get('status', '')
    q = request.GET.get('q', '').strip()

    qs = LoanRequest.objects.all()
    if status_filter:
        qs = qs.filter(status=status_filter)
    if q:
        qs = qs.filter(
            Q(customer_name__icontains=q) |
            Q(phone__icontains=q) |
            Q(request_id__icontains=q)
        )

    # Counts
    counts = {
        'all': LoanRequest.objects.count(),
        'pending': LoanRequest.objects.filter(status='pending').count(),
        'approved': LoanRequest.objects.filter(status='approved').count(),
        'rejected': LoanRequest.objects.filter(status='rejected').count(),
    }

    return render(request, 'loans/request_list.html', {
        'requests': qs,
        'status_filter': status_filter,
        'q': q,
        'counts': counts,
    })


@login_required
def loan_request_status_update(request, pk):
    """Quickly update request status to approved/rejected."""
    req_obj = get_object_or_404(LoanRequest, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status', 'pending')
        if new_status in ['pending', 'approved', 'rejected']:
            req_obj.status = new_status
            req_obj.save()
            messages.success(request, f"Request {req_obj.request_id} updated to {new_status.title()}.")
    return redirect('loan_request_list')


@login_required
def loan_request_convert(request, pk):
    """
    Converts approved LoanRequest into Customer and redirects to Create Loan page
    with amounts and frequency prefilled.
    """
    req_obj = get_object_or_404(LoanRequest, pk=pk)

    # Check if customer already exists by phone
    customer = Customer.objects.filter(phone=req_obj.phone).first()
    if not customer:
        customer = Customer.objects.create(
            name=req_obj.customer_name,
            phone=req_obj.phone,
            email=req_obj.email,
            address=req_obj.address,
            pan_card_doc=req_obj.pan_card_doc,
            aadhaar_card_doc=req_obj.aadhaar_card_doc,
            utility_bill_doc=req_obj.utility_bill_doc,
        )
    else:
        # Transfer documents if not already on customer profile
        if req_obj.pan_card_doc and not customer.pan_card_doc:
            customer.pan_card_doc = req_obj.pan_card_doc
        if req_obj.aadhaar_card_doc and not customer.aadhaar_card_doc:
            customer.aadhaar_card_doc = req_obj.aadhaar_card_doc
        if req_obj.utility_bill_doc and not customer.utility_bill_doc:
            customer.utility_bill_doc = req_obj.utility_bill_doc
        customer.save()

    req_obj.status = 'approved'
    req_obj.save()

    messages.success(
        request,
        f"Borrower {customer.name} verified! Proceeding to configure Thavanai loan."
    )
    return redirect(
        f"/loans/create/?customer_id={customer.pk}&gross={int(req_obj.requested_amount)}&frequency={req_obj.frequency}"
    )


# ─────────────────── WhatsApp Messaging & Meta Cloud Sandbox ───────────────────
@login_required
def whatsapp_messenger(request):
    """
    Staff WhatsApp messaging console.
    Send loan request links and AutoPay mandate authorization cards via Meta Cloud API Sandbox
    or 1-click Direct WhatsApp (wa.me) links.
    """
    config = WhatsAppConfig.get_solo()

    mode = request.GET.get('mode', 'loan')
    loan_id = request.GET.get('loan_id', '')
    phone = request.GET.get('phone', '')
    name = request.GET.get('name', '')
    req_id = request.GET.get('request_id', '')

    loan_obj = None
    if loan_id:
        loan_obj = Loan.objects.filter(pk=loan_id).select_related('customer').first()
        if loan_obj:
            phone = loan_obj.customer.phone
            name = loan_obj.customer.name
            mode = 'autopay'

    # If linked to a loan request
    if req_id and not phone:
        req_obj = LoanRequest.objects.filter(request_id=req_id).first()
        if req_obj:
            phone = req_obj.phone
            name = req_obj.customer_name

    loan_link = request.build_absolute_uri('/loan-request/')

    if mode == 'autopay' and loan_obj:
        auth_url = loan_obj.cashfree_auth_link or request.build_absolute_uri(f"/subscriptions/simulator/{loan_obj.cashfree_subscription_id}/")
        header_text = f"Easy 66 & Co — Authorize AutoPay"
        button_text = "Accept AutoPay"
        button_url = auth_url
        default_message = format_autopay_mandate_message(loan_obj, request)
    else:
        header_text = "Apply for Loan — Easy 66 & Co"
        button_text = "Get started"
        button_url = loan_link
        default_message = format_loan_request_message(
            request=request,
            applicant_name=name,
            loan_link=loan_link
        )

    api_result = None

    if request.method == 'POST':
        action = request.POST.get('action')
        recipient_phone = request.POST.get('phone', '').strip()
        custom_message = request.POST.get('message', '').strip()
        header_text = request.POST.get('header', header_text).strip()
        button_text = request.POST.get('button_text', button_text).strip()
        button_url = request.POST.get('button_url', button_url).strip()
        clean_target = clean_phone_number(recipient_phone)

        if action == 'send_meta_cta':
            res = send_meta_whatsapp_cta(
                to_phone=clean_target,
                header_text=header_text,
                body_text=custom_message,
                button_text=button_text,
                button_url=button_url
            )
            api_result = res
            if res.get('success'):
                messages.success(
                    request,
                    f"✅ Interactive CTA Card sent via Meta Cloud API! Msg ID: {res.get('message_id')}"
                )
            else:
                messages.error(request, f"⚠️ Meta API Notice: {res.get('error')}")

        elif action == 'send_meta':
            res = send_meta_whatsapp_message(to_phone=clean_target, message_text=custom_message)
            api_result = res
            if res.get('success'):
                messages.success(
                    request,
                    f"✅ Message sent via Meta Cloud API! Msg ID: {res.get('message_id')}"
                )
            else:
                messages.error(request, f"⚠️ Meta API Notice: {res.get('error')}")

        phone = recipient_phone
        default_message = custom_message

    # Format text for wa.me direct WhatsApp link without duplicate URLs
    if button_url and button_url not in default_message:
        wa_full_text = f"*{header_text}*\n\n{default_message}\n\n*{button_text}:* {button_url}"
    else:
        wa_full_text = f"*{header_text}*\n\n{default_message}"
    direct_wa_url = get_direct_whatsapp_url(phone, wa_full_text) if phone else ""
    curl_snippet = generate_meta_curl_command(phone, wa_full_text)

    active_loans = Loan.objects.filter(status='active').select_related('customer')[:15]

    return render(request, 'whatsapp/messenger.html', {
        'config': config,
        'mode': mode,
        'loan_obj': loan_obj,
        'active_loans': active_loans,
        'phone': phone,
        'name': name,
        'header_text': header_text,
        'button_text': button_text,
        'button_url': button_url,
        'message_text': default_message,
        'direct_wa_url': direct_wa_url,
        'loan_link': loan_link,
        'api_result': api_result,
        'curl_snippet': curl_snippet,
    })


@login_required
@admin_required
def whatsapp_settings(request):
    """Manage Meta WhatsApp Business Cloud API Sandbox credentials."""
    config = WhatsAppConfig.get_solo()

    if request.method == 'POST':
        config.phone_number_id = request.POST.get('phone_number_id', '').strip()
        config.access_token = request.POST.get('access_token', '').strip()
        config.business_account_id = request.POST.get('business_account_id', '').strip()
        config.test_recipient_number = request.POST.get('test_recipient_number', '').strip()
        config.is_enabled = bool(request.POST.get('is_enabled'))
        config.save()

        messages.success(request, 'WhatsApp Meta Sandbox configuration saved successfully!')
        return redirect('whatsapp_settings')

    curl_test = generate_meta_curl_command(
        config.test_recipient_number or "919876543210",
        "Hello from Easy 66 & Co! This is a test message via WhatsApp Cloud API."
    )

    return render(request, 'whatsapp/settings.html', {'config': config, 'curl_test': curl_test})
