

import csv
from io import TextIOWrapper
from phonenumber_field.phonenumber import to_python
from datetime import datetime
from utils import get_clean_csv_reader
from .models import *


def calculate_insurance_split(customer, product, price):
    policy = customer.active_insurance.policy

    # 1. find rule
    rule = (
        policy.rules.filter(product=product).first()
        or policy.rules.filter(category=product.category).first()
    )

    coverage_percent = (
        rule.coverage_percent if rule else policy.coverage_percent
    )

    max_amount = (
        rule.max_amount if rule else policy.max_coverage_amount
    )

    insurer_amount = (coverage_percent / 100) * price

    if max_amount:
        insurer_amount = min(insurer_amount, max_amount)

    customer_amount = price - insurer_amount

    return customer_amount, insurer_amount


def apply_insurance(customer, total):
    if not customer.insurance_policy:
        return total, 0

    coverage = customer.insurance_policy.coverage_percent / 100

    insurance_part = total * coverage
    customer_part = total - insurance_part

    return customer_part, insurance_part