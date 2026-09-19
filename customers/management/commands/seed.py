"""Fake data for local development (ADR-0013). Never real customers."""
import random
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import User
from customers.models import (
    Customer, Gender, HouseholdMember, ImmigrationStatus, Language, PublicCoverage, Relationship,
)

VI_LAST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ"]
VI_FIRST_F = ["Thị Lan", "Ngọc Anh", "Thu Hà", "Mai", "Kim Chi", "Hồng Nhung", "Bích Ngọc"]
VI_FIRST_M = ["Văn Minh", "Quốc Bảo", "Đức Anh", "Hoàng Nam", "Thanh Tùng", "Minh Khoa"]
EN_LAST = ["Johnson", "Williams", "Brown", "Garcia", "Martinez", "Davis", "Lopez", "Wilson", "Hernandez"]
EN_FIRST_F = ["Maria", "Jennifer", "Linda", "Sofia", "Ashley", "Guadalupe"]
EN_FIRST_M = ["James", "Robert", "Jose", "Michael", "Carlos", "David"]
STREETS = ["Texas Pkwy", "Cartwright Rd", "Murphy Rd", "Sienna Pkwy", "Hampton Dr", "Lexington Blvd"]
CITIES = [("Missouri City", "77459"), ("Sugar Land", "77478"), ("Houston", "77072"), ("Stafford", "77477")]
DEV_PASSWORD = "dev-password-change-me"


class Command(BaseCommand):
    help = "Create ~200 fake Customers and two dev users. Development only."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=200)

    def handle(self, *args, count, **options):
        if not settings.DEBUG:
            raise CommandError("Refusing to seed: DEBUG is off. Seed data never goes to production.")
        rng = random.Random(2026)
        self._users()
        created = []
        for _ in range(count):
            created.append(self._customer(rng))
        for original in rng.sample(created, 10):
            self._near_duplicate(rng, original)
        for customer in rng.sample(created, 5):
            customer.sms_opt_out = True
            customer.sms_opt_out_at = timezone.now()
            customer.save()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {count + 10} customers. Log in as admin@example.com or staff@example.com / {DEV_PASSWORD}"
        ))

    def _users(self):
        for email, group, is_staff in [("admin@example.com", "Admin", True), ("staff@example.com", "Staff", False)]:
            user, made = User.objects.get_or_create(email=email, defaults={"is_staff": is_staff})
            if made:
                user.set_password(DEV_PASSWORD)
                user.save()
            user.groups.add(Group.objects.get(name=group))

    def _messy_phone(self, rng):
        area = rng.choice(["281", "832", "713", "346"])
        n = f"{area}{rng.randint(2000000, 9999999)}"
        return rng.choice([
            n, f"({n[:3]}) {n[3:6]}-{n[6:]}", f"{n[:3]}.{n[3:6]}.{n[6:]}", f"+1 {n[:3]}-{n[3:6]}-{n[6:]}",
            f"{n[3:6]}-{n[6:]}",  # missing area code: flagged by the checklist
        ])

    def _person(self, rng, vietnamese, female):
        if vietnamese:
            return rng.choice(VI_LAST), rng.choice(VI_FIRST_F if female else VI_FIRST_M)
        return rng.choice(EN_LAST), rng.choice(EN_FIRST_F if female else EN_FIRST_M)

    def _customer(self, rng):
        vietnamese = rng.random() < 0.6
        female = rng.random() < 0.5
        last, first = self._person(rng, vietnamese, female)
        city, zip_code = rng.choice(CITIES)
        language = Language.VI if vietnamese and rng.random() < 0.8 else rng.choice([Language.EN, Language.ES])
        customer = Customer.objects.create(
            first_name=first, last_name=last,
            gender=Gender.FEMALE if female else Gender.MALE,
            date_of_birth=None if rng.random() < 0.15 else date(1950, 1, 1) + timedelta(days=rng.randint(0, 20000)),
            email="" if rng.random() < 0.4 else f"{first.split()[0].lower()}{rng.randint(1, 99)}@example.com",
            res_street=f"{rng.randint(100, 9999)} {rng.choice(STREETS)}", res_city=city, res_zip=zip_code,
            phone_primary="" if rng.random() < 0.05 else self._messy_phone(rng),
            phone_secondary=self._messy_phone(rng) if rng.random() < 0.3 else "",
            preferred_language="" if rng.random() < 0.1 else language,
            immigration_status=rng.choice([c for c, _ in ImmigrationStatus.choices] + [""]),
            household_income=None if rng.random() < 0.2 else rng.randrange(18000, 95000, 500),
        )
        if rng.random() < 0.45:
            s_last, s_first = self._person(rng, vietnamese, not female)
            HouseholdMember.objects.create(
                customer=customer, relationship=Relationship.SPOUSE, first_name=s_first, last_name=s_last,
                immigration_status=rng.choice([c for c, _ in ImmigrationStatus.choices]),
            )
        for _ in range(rng.choice([0, 0, 1, 2, 3])):
            d_first = self._person(rng, vietnamese, rng.random() < 0.5)[1]
            HouseholdMember.objects.create(
                customer=customer, relationship=Relationship.DEPENDENT, first_name=d_first, last_name=last,
                date_of_birth=date(2008, 1, 1) + timedelta(days=rng.randint(0, 6000)),
                public_coverage=rng.choice([PublicCoverage.NONE, PublicCoverage.CHIP, PublicCoverage.MEDICAID]),
            )
        if rng.random() < 0.05:
            HouseholdMember.objects.create(
                customer=customer, relationship=Relationship.DEPENDENT, first_name="Văn Hùng", last_name=last,
                date_of_birth=date(1948, 3, 9), public_coverage=PublicCoverage.MEDICARE,
            )
        return customer

    def _near_duplicate(self, rng, original):
        """Same person entered twice by two staff: name without diacritics, same phone."""
        plain = original.last_name.replace("ễ", "e").replace("ầ", "a").replace("ạ", "a").replace("à", "a")
        Customer.objects.create(
            first_name=original.first_name, last_name=plain,
            date_of_birth=original.date_of_birth, phone_primary=original.phone_primary,
        )
