from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.utils.translation import gettext_lazy as _
from base.mixins import TabBuilderMixin
from base.views import BaseDetailView, BaseListView, BaseModelView
from hr.models import PayrollItem, PayrollTransaction, Staff, SalaryScale


# -------------------------------------------------------------------------
# Staff
# -------------------------------------------------------------------------
class StaffListView(BaseListView):
    model = Staff
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'staff_page'
    title = _("Staff Page")
    subtitle = _("Manage your staff here")
    header_paragraph = _("""
        Manage and oversee all staff directly on the platform. Whether adding new staff, updating their profiles, or assigning roles and permissions, 
        the platform provides an intuitive interface to handle all staff-related tasks. Admins can easily view, update, and remove staff, 
        ensuring they have access to the right resources. his central hub allows for efficient staff management,
        promoting a streamlined experience for all involved.""")
    object_crud_link = "hr:staff-synchronise"
    object_crud_via_htmx = False

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.request
        user = request.user
        org = user.profile.current_organization

        queryset = queryset.filter(organization=org)

        full_name = request.GET.get('full_name')
        gender = request.GET.get('gender')
        phone_number = request.GET.get('phone_number')
        is_active = request.GET.get('is_active')

        if full_name:
            queryset = queryset.filter(
                Q(first_name__icontains=full_name) |
                Q(last_name__icontains=full_name)
            )

        if gender:
            queryset = queryset.filter(gender=gender)

        if phone_number:
            queryset = queryset.filter(phone_number__icontains=phone_number)

        if is_active == "true":
            queryset = queryset.filter(is_active=True)
        elif is_active == "false":
            queryset = queryset.filter(is_active=False)

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        GENDER_MAP = dict(Staff._meta.get_field('gender').choices)

        gender_counts = [
            {
                "name": label,
                "count": queryset.filter(gender=code).count()
            }
            for code, label in GENDER_MAP.items()
        ]

        context['data_groups'] = [
            (_("Staff by Gender"), gender_counts, "fa-user", "blue")
        ]

        return context


class StaffDetailView(TabBuilderMixin, BaseDetailView):
    model = Staff
    template_name = 'staff/detail.html'

    header_paragraph = _(
        """
        View staff profile details, including identity, contact information, and system access.
        Manage updates, roles, and linked records from this centralized view.
        """
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        staff = context["object"]
        user = self.request.user

        # Page metadata
        context.update({
            "active_page": "staff_page",
            "title": _("Staff Details"),
            "subtitle": _("View staff details"),
        })

        # Correct permission handling
        if hasattr(user, "get_permissions") and "change_staff" in user.get_permissions():
            context.update({
                "can_crud_object": True,
                "object_crud_link": "people:staff-update",
                "object_crud_via_htmx": True,
                "object_pk": staff.pk,
            })

        # Ownership check
        if getattr(staff, "user", None) == user:
            context["active_page"] = "staff_profile"

        # Basic stats (ONLY real fields)
        context["stats"] = [
            {"label": _("Has User Account"), "value": bool(staff.user)},
            {"label": _("Has Email"), "value": bool(staff.email)},
            {"label": _("Has Phone"), "value": bool(staff.phone_number)},
            {"label": _("Active"), "value": staff.is_active},
        ]

        # Safe payroll section (optional dependency)
        try:
            outstanding_payments = PayrollItem.objects.filter(staff=staff)
            total_outstanding = sum(
                item.amount - item.total_paid for item in outstanding_payments
            )
        except Exception:
            total_outstanding = 0

        context["outstanding_payments"] = total_outstanding

        # Tabs (ONLY keep what actually exists)
        context["tabs"] = [
            self.build_tab(
                PayrollTransaction,
                id="payouts_tab",
                title=_("Payroll"),
                icon=getattr(PayrollTransaction, "model_icon", "fa-money-bill"),
                model_container="payroll-transaction-list",
                model_list_url="finances:payroll-transaction-list",
                model_create_url="finances:payroll-transaction-create",
                permission="finances.add_payrolltransaction",
                url_query_string=f"?origin=partial&staff_id={staff.id}",
                show_add=True,
                crud_via_htmx=True,
            ),
        ]

        return context


class StaffCreateView(BaseModelView, CreateView):
    model = Staff
    fields = [
        'first_name', 'last_name', 'email', 'gender', 'phone_number', 'staff_id'
    ]
    success_url = reverse_lazy('hr:staff-list')
    title = _("Add Staff")
    subtitle = _("Fill the form to add a new staff")
    header_paragraph = _("Fill the form to add a new staff")


class StaffUpdateView(BaseModelView, UpdateView):
    model = Staff
    fields = [
        'first_name', 'last_name', 'email', 'gender', 'phone_number', 'staff_id'
    ]
    success_url = reverse_lazy('hr:staff-list')
    title = _("Edit Staff")
    subtitle = _("Edit Staff Info")
    header_paragraph = _("Edit a staff's info")


# @login_required(login_url='accounts:login')
# def sync_staff_view(request):
#     """
#     View that triggers staff sync and redirects to staff list.
#     """
#     try:
#         result = sync_staff_records()
#         created = result.get("created", 0)
#         updated = result.get("updated", 0)

#         messages.success(
#             request,
#             f"Staff sync completed successfully — {created} created, {updated} updated."
#         )

#     except Exception as e:
#         messages.error(request, f"Staff sync failed: {e}")

#     # Redirect to the staff list view
#     return redirect("hr:staff-list")


# ------------------------------------------------------------------------
# Salary Scale Views
# ------------------------------------------------------------------------
class SalaryScaleListView(BaseListView):
    model = SalaryScale
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Salary Scales")
    subtitle = _("Manage and review your organization's salary structures")
    header_paragraph = _(
        """Payroll management ensures accurate and timely compensation for staff,
        incorporating salary scales, approvals, and payment tracking — providing
        administrators with clear insight into staff costs, consistency in pay
        structures, and effective financial planning."""
    )

    object_crud_link = "finances:salary-scale-create"
    object_crud_via_htmx = True


class SalaryScaleDetailView(BaseDetailView):
    model = SalaryScale
    template_name = 'salaryscale/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salary_scale = self.object
        context["salary_scale"] = salary_scale
        context["title"] = _("Salary Scale Details")
        context["subtitle"] = _("Detailed overview of this salary scale")
        context["active_page"] = "finance_page"
        context["header_paragraph"] = """
            This page shows detailed information about a salary scale,
            including grade levels, step increments, and applicable allowances.
            Use this view to review salary structures or make updates as needed.
        """
        return context


class SalaryScaleCreateView(BaseModelView, CreateView):
    model = SalaryScale
    fields = ['staff_group', 'base_salary', 'housing_allowance',
              'transport_allowance', 'other_allowance', 'deductions', 'effective_from']
    success_url = reverse_lazy('finances:salary-scale-list')
    title = _("Add Salary Scale")
    subtitle = _("Create a new salary scale for staff payroll management")


class SalaryScaleUpdateView(BaseModelView, UpdateView):
    model = SalaryScale
    fields = ['staff_group', 'base_salary', 'housing_allowance',
              'transport_allowance', 'other_allowance', 'deductions', 'effective_from']
    success_url = reverse_lazy('finances:salary-scale-list')
    title = _("Edit Salary Scale")
    subtitle = _("Update details of this salary scale")


# ------------------------------------------------------------------------
# Payroll Item Views
# ------------------------------------------------------------------------
class PayrollItemListView(BaseListView):
    model = PayrollItem
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Payroll Items")
    subtitle = _("Track and manage all staff Payroll Items")
    header_paragraph = _(
        """Payroll management ensures accurate and timely compensation for staff,
        covering salary computation, approvals, and payment tracking — providing
        administrators with clear insight into staff costs, accountability,
        and effective financial planning."""
    )
    object_crud_link = "finances:payroll-item-create"
    object_crud_via_htmx = True


class PayrollItemDetailView(BaseDetailView):
    model = PayrollItem
    template_name = 'payroll/item/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payroll_item = self.object
        context["payroll_item"] = payroll_item
        context["title"] = _("Payroll Item Details")
        context["subtitle"] = _("View complete details of this Payroll Item")
        context["active_page"] = "finance_page"
        context["header_paragraph"] = """
            This page shows information about a staff Payroll Item,
            including the employee, gross pay, deductions, and payment status.
            You can confirm, update, or export payroll records from this section.
        """
        return context


class PayrollItemCreateView(BaseModelView, CreateView):
    model = PayrollItem
    fields = ['staff', 'salary_scale',
              'amount', 'approved_on', 'payroll_month', 'payroll_year', 'note']
    success_url = reverse_lazy('finances:payroll-item-list')
    title = _("Add Payroll Item")
    subtitle = _("Record a new staff Payroll Item")


class PayrollItemUpdateView(BaseModelView, UpdateView):
    model = PayrollItem
    fields = ['staff', 'salary_scale',
              'amount', 'approved_on', 'payroll_month', 'payroll_year', 'note']
    success_url = reverse_lazy('finances:payroll-item-list')
    title = _("Edit Payroll Item")
    subtitle = _("Update details of this Payroll Item")


# ------------------------------------------------------------------------
# Payroll Transaction Views
# ------------------------------------------------------------------------
class PayrollTransactionListView(BaseListView):
    model = PayrollTransaction
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Payroll Transactions")
    subtitle = _("View and manage all Payroll Transaction records")
    header_paragraph = _(
        """Payroll transactions record the actual disbursement of staff salaries,
        capturing payment dates, methods, and references — ensuring traceability,
        accountability, and accurate financial records for effective payroll
        auditing and reporting."""
    )
    object_crud_link = "finances:payroll-transaction-create"
    object_crud_via_htmx = True


class PayrollTransactionDetailView(BaseDetailView):
    model = PayrollTransaction
    template_name = 'payroll/transaction/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payroll_transaction = self.object
        context["payroll_transaction"] = payroll_transaction
        context["title"] = _("Payroll Transaction Details")
        context["subtitle"] = _(
            "Detailed information about this Payroll Transaction record")
        context["active_page"] = "finance_page"
        context["header_paragraph"] = """
            This page provides detailed information about a Payroll Transaction,
            including the staff member, total paid amount, deductions, and payout date.
            You can verify transactions or export payout details for reporting.
        """
        return context


class PayrollTransactionCreateView(BaseModelView, CreateView):
    model = PayrollTransaction
    fields = ['financial_account', 'cash_account', 'bank_account',
              'payroll_item', 'amount',]
    success_url = reverse_lazy('finances:payroll-transaction-list')
    title = _("Add Payroll Transaction")
    subtitle = _("Fill in the form to record a new Payroll Transaction")


class PayrollTransactionUpdateView(BaseModelView, UpdateView):
    model = PayrollTransaction
    fields = ['financial_account', 'cash_account', 'bank_account',
              'payroll_item', 'amount',]
    success_url = reverse_lazy('finances:payroll-transaction-list')
    title = _("Edit Payroll Transaction")
    subtitle = _("Update details for this Payroll Transaction record")
