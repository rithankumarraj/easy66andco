"""
Django built-in admin configuration.
"""
from django.contrib import admin
from .models import UserProfile, Customer, Loan, Installment


class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0


class LoanInline(admin.TabularInline):
    model = Loan
    extra = 0
    show_change_link = True


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone']
    list_filter = ['role']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_id', 'name', 'phone', 'total_loans_count', 'created_at']
    search_fields = ['name', 'phone', 'customer_id']
    inlines = [LoanInline]


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = [
        'loan_id', 'customer', 'gross_principal', 'net_proceeds',
        'frequency', 'installment_amount', 'status', 'assigned_staff'
    ]
    list_filter = ['status', 'frequency']
    search_fields = ['loan_id', 'customer__name', 'customer__phone']
    inlines = [InstallmentInline]


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ['loan', 'num', 'due_date', 'amount', 'status', 'paid_date', 'collected_by']
    list_filter = ['status']
