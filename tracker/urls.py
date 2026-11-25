"""
URL patterns for Easy 66 & Co.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_add, name='customer_add'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),

    # Loans (Dedicated Page)
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/create/', views.loan_create, name='loan_create'),
    path('loans/<int:pk>/', views.loan_detail, name='loan_detail'),
    path('loans/<int:pk>/edit/', views.loan_edit, name='loan_edit'),
    path('loans/<int:pk>/delete/', views.loan_delete, name='loan_delete'),
    path('loans/<int:loan_pk>/collect/<int:inst_num>/', views.collect_installment, name='collect_installment'),
    path('loans/<int:pk>/settle-all/', views.settle_full_loan, name='settle_full_loan'),

    # Cashfree Subscriptions & AutoPay
    path('loans/<int:pk>/mandate/create/', views.create_loan_mandate, name='create_loan_mandate'),
    path('loans/<int:pk>/mandate/sync/', views.sync_loan_mandate, name='sync_loan_mandate'),
    path('loans/<int:pk>/mandate/charge-next/', views.charge_mandate_next, name='charge_mandate_next'),
    path('loans/<int:pk>/mandate/send-whatsapp/', views.send_loan_autopay_whatsapp, name='send_loan_autopay_whatsapp'),
    path('loans/<int:pk>/mandate/callback/', views.mandate_callback, name='mandate_callback'),
    path('subscriptions/simulator/<str:sub_id>/', views.subscription_simulator, name='subscription_simulator'),
    path('api/cashfree/webhook/', views.cashfree_webhook, name='cashfree_webhook'),
    path('settings/cashfree/', views.cashfree_settings, name='cashfree_settings'),

    # Collections (Dedicated Page)
    path('collections/', views.collection_list, name='collection_list'),

    # Public Loan Request & Borrowers
    path('loan-request/', views.loan_request_public, name='loan_request_public'),
    path('loan-requests/', views.loan_request_list, name='loan_request_list'),
    path('loan-requests/<int:pk>/status/', views.loan_request_status_update, name='loan_request_status_update'),
    path('loan-requests/<int:pk>/convert/', views.loan_request_convert, name='loan_request_convert'),

    # WhatsApp Cloud API Sandbox & Messenger
    path('whatsapp/', views.whatsapp_messenger, name='whatsapp_messenger'),
    path('whatsapp/settings/', views.whatsapp_settings, name='whatsapp_settings'),

    # Inquiries & Loan Estimation
    path('inquiries/', views.inquiries, name='inquiries'),
    path('inquiries/pdf/', views.inquiry_pdf, name='inquiry_pdf'),

    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/pdf/', views.report_pdf, name='report_pdf'),

    # Staff (admin only)
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_add, name='staff_add'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:pk>/delete/', views.staff_delete, name='staff_delete'),
]
