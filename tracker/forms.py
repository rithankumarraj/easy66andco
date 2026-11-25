"""
Forms for Customer, Loan, and Staff Management.
"""
from django import forms
from django.contrib.auth.models import User
from .models import Customer, Loan, UserProfile


class CustomerForm(forms.ModelForm):
    """Form to add or edit a Customer profile with mandatory KYC documents."""
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'email', 'address', 'pan_card_doc', 'aadhaar_card_doc', 'utility_bill_doc']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name', 'data-i18n-ph': 'ph_name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number', 'data-i18n-ph': 'ph_phone'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address (optional)', 'data-i18n-ph': 'ph_email'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full address', 'data-i18n-ph': 'ph_address'}),
            'pan_card_doc': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
            'aadhaar_card_doc': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
            'utility_bill_doc': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
        }
        labels = {
            'pan_card_doc': 'PAN Card (Mandatory)',
            'aadhaar_card_doc': 'Aadhaar Card (Mandatory)',
            'utility_bill_doc': 'Recent Utility Bill (Electricity, water, or piped gas within 2–3 months)',
        }


class LoanForm(forms.ModelForm):
    """Form to create a loan for an EXISTING customer."""
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_customer_select'}),
        empty_label='— Select Existing Customer —'
    )

    class Meta:
        model = Loan
        fields = [
            'customer', 'gross_principal', 'net_proceeds', 'interest_rate',
            'frequency', 'installment_count', 'start_date', 'assigned_staff', 'status'
        ]
        widgets = {
            'gross_principal': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '100', 'step': '100',
                'id': 'id_gross_principal', 'placeholder': '10000',
                'oninput': 'calcThavanai()'
            }),
            'net_proceeds': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '100', 'step': '100',
                'id': 'id_net_proceeds', 'placeholder': '8000',
                'style': 'font-weight:700;color:var(--teal);',
                'oninput': 'calcThavanaiFromNet()'
            }),
            'interest_rate': forms.HiddenInput(attrs={'id': 'id_interest_rate'}),
            'frequency': forms.Select(attrs={'class': 'form-control', 'id': 'id_frequency', 'onchange': 'calcThavanai()'}),
            'installment_count': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'max': '365',
                'id': 'id_installment_count', 'placeholder': '100',
                'oninput': 'calcThavanai()'
            }),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'assigned_staff': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_staff'].queryset = User.objects.filter(profile__role='employee')
        self.fields['assigned_staff'].required = False
        self.fields['assigned_staff'].empty_label = 'None (Unassigned)'
        self.fields['net_proceeds'].required = True
        self.fields['interest_rate'].required = False
        if not self.instance.pk:
            self.fields.pop('status', None)

    def clean(self):
        cleaned_data = super().clean()
        gross = cleaned_data.get('gross_principal')
        net = cleaned_data.get('net_proceeds')

        if gross and net:
            if net > gross:
                self.add_error('net_proceeds', 'Cash Disbursed cannot exceed Gross Principal.')
            else:
                upfront = gross - net
                rate = round((float(upfront) / float(gross)) * 100.0, 2)
                cleaned_data['interest_rate'] = rate
        return cleaned_data


class StaffForm(forms.Form):
    """Form to add a new staff member."""
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name', 'data-i18n-ph': 'ph_staff_name'})
    )
    phone = forms.CharField(
        max_length=15, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number', 'data-i18n-ph': 'ph_phone'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address', 'data-i18n-ph': 'ph_email'})
    )
    username = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username for login', 'data-i18n-ph': 'ph_username'})
    )
    password = forms.CharField(
        min_length=4,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password', 'data-i18n-ph': 'ph_password'})
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username


class StaffEditForm(forms.Form):
    """Form to edit an existing staff member."""
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    username = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(required=False, min_length=4, widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to keep unchanged'}))

    def __init__(self, *args, user_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = user_id

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = User.objects.filter(username=username)
        if self.user_id:
            qs = qs.exclude(pk=self.user_id)
        if qs.exists():
            raise forms.ValidationError('This username is already taken.')
        return username
