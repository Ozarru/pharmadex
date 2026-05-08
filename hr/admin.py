from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from hr.models import PayrollItem, PayrollTransaction, SalaryScale



#  ---------------------------------------------------------
# Staff Salary Models
#  ---------------------------------------------------------
@admin.register(SalaryScale)
class SalaryScaleAdmin(admin.ModelAdmin):
    search_fields = [
        "staff_group",
    ]

    list_filter = [
        "staff_group",
        "effective_from",
    ]

    list_display = [
        "display_staff_group",
        "base_salary",
        "gross_salary",
        "net_salary",
        "effective_from",
        "created_at",
    ]

    readonly_fields = [
        "gross_salary",
        "net_salary",
    ]

    @admin.display(description=_("Staff Category"))
    def display_staff_group(self, obj):
        return obj.get_staff_group_display()


@admin.register(PayrollItem)
class PayrollItemAdmin(admin.ModelAdmin):
    search_fields = [
        "staff__first_name",
        "staff__last_name",
        "staff__matric_number",
        "payroll_month",
        "payroll_year",
    ]

    list_filter = [
        "salary_scale",
        "payroll_month",
        "payroll_year",
    ]

    list_display = [
        "staff",
        "salary_scale",
        "amount",
        "total_paid",
        "balance",
        "status",
        "payroll_month",
        "payroll_year",
        "approved_on",
    ]

    readonly_fields = [
        "total_paid",
        "balance",
        "status",
    ]

    ordering = ("-payroll_year", "-payroll_month", "-created_at")

    @admin.display(description=_("Status"))
    def status(self, obj):
        return obj.status


@admin.register(PayrollTransaction)
class PayrollTransactionAdmin(admin.ModelAdmin):
    search_fields = [
        "payroll_item__staff__first_name",
        "payroll_item__staff__last_name",
        "payroll_item__staff__employee_id",
        "payroll_item__payroll_month",
        "payroll_item__payroll_year",
    ]

    list_filter = [
        "financial_account",
        "payment_date",
    ]

    list_display = [
        "get_staff",
        "payroll_item",
        "amount",
        "financial_account",
        "payment_date",
    ]

    readonly_fields = [
        "payment_date",
    ]

    fieldsets = (
        (_("Payroll Reference"), {
            "fields": (
                "payroll_item",
                "amount",
            )
        }),
        (_("Payment Details"), {
            "fields": (
                "financial_account",
                "cash_account",
                "bank_account",
                "payment_date",
                "proof_file",
            )
        }),
    )

    @admin.display(description=_("Staff"))
    def get_staff(self, obj):
        return obj.payroll_item.staff if obj.payroll_item else None
