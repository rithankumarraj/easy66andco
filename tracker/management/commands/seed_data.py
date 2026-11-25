"""
Seed data command for Customers, Thavanai Loans, and Installments.
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tracker.models import UserProfile, Customer, Loan, Installment


class Command(BaseCommand):
    help = 'Seeds database with default users, customers, and Thavanai loans'

    def handle(self, *args, **options):
        self.stdout.write('Seeding Thavanai Customers & Loans...')

        # Admin User
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={'first_name': 'Administrator', 'email': 'admin@easy66.com'}
        )
        admin_user.set_password('admin123')
        admin_user.save()
        UserProfile.objects.get_or_create(user=admin_user, defaults={'role': 'admin', 'phone': '9876543210'})

        # Employee Users
        staff_users = []
        staff_data = [
            ('staff1', 'staff123', 'Ravi Kumar', '9876543211', 'ravi@easy66.com'),
            ('staff2', 'staff123', 'Priya Sharma', '9876543212', 'priya@easy66.com'),
        ]
        for uname, pwd, name, phone, email in staff_data:
            user, _ = User.objects.get_or_create(
                username=uname,
                defaults={'first_name': name.split()[0], 'email': email}
            )
            user.set_password(pwd)
            user.save()
            UserProfile.objects.get_or_create(user=user, defaults={'role': 'employee', 'phone': phone})
            staff_users.append(user)

        # Clear existing data for clean re-seed
        Installment.objects.all().delete()
        Loan.objects.all().delete()
        Customer.objects.all().delete()

        customer_names = [
            ('Arun Pandian', '9871000001'),
            ('Karthik Raja', '9871000002'),
            ('Meena Devi', '9871000003'),
            ('Suresh Babu', '9871000004'),
            ('Lakshmi Narayanan', '9871000005'),
            ('Deepa Krishnan', '9871000006'),
            ('Ganesh Moorthy', '9871000007'),
            ('Revathi Sundaram', '9871000008'),
            ('Murugan Vel', '9871000009'),
            ('Anitha Rajan', '9871000010'),
        ]

        created_customers = []
        for name, phone in customer_names:
            c = Customer.objects.create(
                name=name, phone=phone,
                email=f'{name.lower().replace(" ", ".")}@gmail.com',
                address=f'{random.randint(1, 150)}, Main Road, Chennai - 600028',
            )
            created_customers.append(c)

        # Seed loans (some customers get 2 loans to showcase multiple loans per customer!)
        loan_cases = [
            (created_customers[0], 10000, 20.0, 'daily', 100, 30),
            (created_customers[0], 15000, 20.0, 'daily', 100, 10), # 2nd loan for Arun Pandian!
            (created_customers[1], 20000, 20.0, 'daily', 100, 45),
            (created_customers[2], 10000, 20.0, 'weekly', 10, 28),
            (created_customers[3], 50000, 20.0, 'weekly', 20, 60),
            (created_customers[4], 10000, 20.0, 'daily', 100, 15),
            (created_customers[5], 30000, 15.0, 'monthly', 10, 90),
            (created_customers[6], 15000, 20.0, 'daily', 100, 20),
            (created_customers[7], 10000, 20.0, 'weekly', 10, 35),
            (created_customers[8], 25000, 20.0, 'daily', 100, 10),
            (created_customers[9], 10000, 20.0, 'daily', 100, 5),
        ]

        today_date = date.today()

        for cust, gross, rate, freq, count, days_ago in loan_cases:
            start = today_date - timedelta(days=days_ago)
            staff = random.choice(staff_users)

            loan = Loan.objects.create(
                customer=cust,
                gross_principal=gross,
                interest_rate=rate,
                frequency=freq,
                installment_count=count,
                start_date=start,
                assigned_staff=staff,
            )

            emi = float(loan.installment_amount)
            all_paid = True

            for j in range(1, count + 1):
                if freq == 'daily':
                    due = start + timedelta(days=j)
                elif freq == 'weekly':
                    due = start + timedelta(weeks=j)
                else:
                    due = start + timedelta(days=j * 30)

                is_past = due < today_date
                paid = is_past and random.random() > 0.25

                Installment.objects.create(
                    loan=loan, num=j,
                    due_date=due, amount=emi,
                    status='paid' if paid else ('overdue' if is_past else 'pending'),
                    paid_date=due if paid else None,
                    paid_amount=emi if paid else 0,
                    collected_by=staff if paid else None,
                )
                if not paid:
                    all_paid = False

            if all_paid:
                loan.status = 'completed'
                loan.save()

            self.stdout.write(f'  ✓ Loan {loan.loan_id} for {cust.name}: Gross ₹{gross}, Net ₹{loan.net_proceeds}')

        self.stdout.write(self.style.SUCCESS('\nSeeding complete!'))
