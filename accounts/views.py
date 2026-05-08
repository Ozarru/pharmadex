from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth import update_session_auth_hash
from collections import Counter
from django.conf import settings
import smtplib
import uuid
from django.core.exceptions import PermissionDenied
import random
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.views import View
from base.views import BaseDetailView, BaseListView, BaseModelView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Sum, Q
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from organizations.models import Organization
from base.models import *
from pharmacies.models import Pharmacy
from .forms import *
from .models import *
# from accounts.utils import assign_user_role_from_invitation
from django.contrib.auth.models import Permission

#  ------------------------------------
# User model import
#  ------------------------------------
from django.contrib.auth import get_user_model
User = get_user_model()

# P@ss1234


# Validate token as UUID before querying
def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError):
        return False


# ------------------------------------------------- Auth views -------------------------------------------------
@csrf_protect
def signupView(request):
    if request.user.is_authenticated:
        return redirect('base:home')

    referer = request.META.get('HTTP_REFERER', reverse('accounts:signup'))
    token = request.GET.get('token') or request.POST.get('token')
    invitation = None
    organization = None

    if token and is_valid_uuid(token):
        invitation = UserInvitation.objects.select_related(
            "organization").filter(token=token).first()
        if invitation and invitation.is_expired():
            messages.error(request, _("Invalid or expired invitation token."))
            return redirect(referer)
        organization = invitation.organization if invitation else None

    # Prevent duplicate signups
    if invitation:
        existing_user = User.objects.filter(
            email=invitation.receiver_email).first()
        if existing_user:
            # assign_user_role_from_invitation(existing_user, token)
            messages.success(request, _(
                "Your role or organization access has been updated. Please log in."))
            return redirect('accounts:login')

    form = CreateUserForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            profile = getattr(
                user, "profile", None) or Profile.objects.create(user=user)
            profile.gender = request.POST.get("gender") or profile.gender

            if invitation:
                if organization:
                    profile.current_organization = organization
                    profile.allowed_organizations.add(organization)

                if invitation.user_type:
                    role = Role.objects.filter(
                        user_type=invitation.user_type).first()
                    if not role:
                        role = Role.objects.create(
                            name=invitation.user_type.replace(
                                "_", " ").title(),
                            user_type=invitation.user_type,
                        )

                    assignment, _ = UserRole.objects.get_or_create(
                        user=user,
                        role=role,
                        organization=organization,
                    )
                    profile.current_role = assignment

                invitation.receiver = user
                invitation.save()

            profile.save()
            messages.success(request, _("Account created successfully."))
            return redirect('accounts:login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    context = {
        "active_page": "signup_page",
        "title": 'Signup',
        'form': form,
        'token': token,
    }

    return render(request, 'accounts/signup.html', context)


@csrf_protect
def loginView(request):
    if request.user.is_authenticated:
        return redirect('base:home')

    if request.method == 'POST':
        # This is the generic identifier
        email_or_phone_number = request.POST.get('email_or_phone_number')
        password = request.POST.get('password')

        user = authenticate(
            request, email_or_phone_number=email_or_phone_number, password=password)

        if user is not None:
            login(request, user)
            user.is_online = True
            user.last_login = timezone.now()
            user.save()
            next_url = request.GET.get('next', None)
            if next_url in request.POST:
                messages.success(
                    request, f'Hello! Welcome back, {user.first_name}.')
                return redirect(next_url)
            else:
                return redirect('base:home')  # Fallback redirect to home
        else:
            messages.error(request, 'Invalid credentials. Please try again.')

    context = {
        "active_page": "login_page",
        "title": 'accounts:Login'
    }
    return render(request, 'accounts/login.html', context)


@login_required
def change_password_view(request):
    user = request.user

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            # user.has_changed_password= True
            user.save()

            # keep user logged in
            update_session_auth_hash(request, user)

            messages.success(request, _("Password changed successfully."))
            return redirect("base:home")
        else:
            messages.error(request, _("Please fix the errors below."))
    else:
        form = SetPasswordForm(user)

    return render(request, "accounts/change_password.html", {
        "form": form,
        "title": _("Change Password")
    })


class VerifyOtpView(View):
    template_name = 'accounts/otp-verify.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')

        if 'pending_user_id' not in request.session:
            messages.warning(request, _(
                "Session expired. Please login again."))
            return redirect('accounts:login')

        return render(request, self.template_name)

    def post(self, request):
        otp_input = request.POST.get('otp')
        session_otp = request.session.get('otp_code')
        user_id = request.session.get('pending_user_id')

        if not all([otp_input, session_otp, user_id]):
            messages.error(request, _(
                "Session expired or invalid. Please login again."))
            return redirect('accounts:login')

        if otp_input == session_otp:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                messages.error(request, _("User not found."))
                return redirect('accounts:login')

            # Login the user
            login(request, user)

            # Clear session OTP data
            request.session.pop('otp_code', None)
            request.session.pop('pending_user_id', None)

            messages.success(request, _("Successfully logged in."))
            return redirect('home')

        messages.error(request, _("Invalid OTP. Please try again."))
        return render(request, self.template_name)


class ResendOtpView(View):
    def post(self, request):
        user_id = request.session.get('pending_user_id')
        if not user_id:
            messages.error(request, _("Session expired. Please login again."))
            return redirect('accounts:login')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, _("User not found."))
            return redirect('accounts:login')

        # Generate new OTP and update session
        otp_code = f'{random.randint(0, 999999):06d}'
        request.session['otp_code'] = otp_code

        # Send OTP email
        send_otp_email(user, otp_code)

        messages.success(request, _("A new verification code has been sent."))
        return redirect('accounts:otp-verify')


def send_otp_email(user, otp_code):
    subject = _("Your Login Verification Code")
    context = {'otp_code': otp_code}
    html = render_to_string("emails/otp.html", context)
    text = strip_tags(html)

    email = EmailMultiAlternatives(subject, text, to=[user.email])
    email.attach_alternative(html, "text/html")
    email.send()


@login_required(login_url='accounts:login')
def logoutUser(request):
    user = request.user
    logout(request)
    user.is_online = False
    user.last_logout = timezone.now()
    user.save()
    return redirect('accounts:login')


# ------------------------------------------------- Context views -------------------------------------------------
@login_required(login_url='accounts:login')
def switch_organization(request, pk):
    organization = get_object_or_404(Organization, id=pk)
    user = request.user
    profile = user.profile

    # Permission check
    if not (user.is_staff or user.is_superuser):
        allowed = (
            profile.allowed_organizations.filter(id=organization.id).exists()
            or user.user_roles.filter(organization=organization).exists()
        )
        if not allowed:
            messages.error(request, "Unauthorized organization switch.")
            return HttpResponseForbidden("Unauthorized organization switch.")

    # Pharmacy in session
    request.session["current_organization_id"] = str(organization.id)

    # Optional: still persist in DB
    profile.current_organization = organization
    profile.allowed_organizations.add(organization)

    if profile.current_pharmacy_id and profile.current_pharmacy.organization_id != organization.id:
        profile.current_pharmacy = None
        request.session.pop("current_pharmacy_id", None)

    current_role = profile.current_role

    if current_role:
        if current_role.organization and current_role.organization != organization:
            # role no longer valid → pick a new one
            role = (
                UserRole.objects
                .filter(user=user)
                .filter(Q(organization=organization) | Q(organization__isnull=True))
                .order_by('-organization')
                .first()
            )
            profile.current_role = role
    profile.save()

    messages.success(request, f"Switched to {organization.name}")
    return redirect('base:home')


@login_required(login_url='accounts:login')
def switch_pharmacy(request, pk):
    pharmacy = get_object_or_404(Pharmacy, id=pk)
    user = request.user
    profile = user.profile

    current_org = profile.current_organization
    if not current_org or pharmacy.organization_id != current_org.id:
        return HttpResponseForbidden("Unauthorized pharmacy switch.")

    if not (user.is_staff or user.is_superuser):
        allowed_qs = profile.allowed_pharmacies.filter(
            organization=current_org)
        if allowed_qs.exists() and not allowed_qs.filter(id=pharmacy.id).exists():
            return HttpResponseForbidden("Unauthorized pharmacy switch.")

    request.session["current_pharmacy_id"] = str(pharmacy.id)
    profile.current_pharmacy = pharmacy
    profile.allowed_pharmacies.add(pharmacy)
    profile.save(update_fields=["current_pharmacy"])

    messages.success(request, f"Switched to {pharmacy.name}")
    return redirect('base:home')


@login_required(login_url='accounts:login')
def switch_role(request, role_id):
    try:
        role = UserRole.objects.select_related("organization", "role").get(
            id=role_id, user=request.user
        )
    except UserRole.DoesNotExist:
        messages.error(request, "Invalid or unauthorized role switch.")
        return redirect('base:home')

    profile = request.user.profile
    profile.current_role = role

    # ✅ ONLY update organization if role has one
    if role.organization:
        profile.current_organization = role.organization
        request.session["current_organization_id"] = str(role.organization.id)
    else:
        # global role → keep current organization
        request.session["current_organization_id"] = request.session.get(
            "current_organization_id")

    profile.save()

    messages.success(
        request,
        f"Switched role to: {role.role.name}" +
        (f" @ {role.organization.name}" if role.organization else " (Global)")
    )

    return redirect('base:home')


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def toggle_tenancy(request):
    if not (request.user.is_superuser or request.user.is_platform_admin()):
        return HttpResponseForbidden("Unauthorized")

    current = bool(request.session.get("pharmacy_scope_disabled", False))
    request.session["pharmacy_scope_disabled"] = not current

    if request.headers.get("HX-Request") == "true":
        return HttpResponse(
            "",
            status=204,
            headers={"HX-Refresh": "true"},
        )

    return redirect(request.META.get("HTTP_REFERER", reverse("base:home")))


# ------------------------------------------------- CustomUser views -------------------------------------------------
@login_required(login_url='accounts:login')
def user_preview(request, pk):
    user = request.user
    curr_obj = get_object_or_404(CustomUser, id=pk)
    is_self = True if user == curr_obj else False

    context = {
        "active_page": "user_page",
        'title': 'user',
        'curr_obj': curr_obj,
        'is_self': is_self,
    }
    return render(request, 'accounts/user/_preview.html', context)


@login_required(login_url='accounts:login')
def update_profile(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)

    if request.user != user:
        return HttpResponseForbidden("You do not have the permission to edit this profil.")

    profile = get_object_or_404(Profile, user=user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(
                request, 'Your profile has been updated successfully.')
            return redirect('accounts:user-detail', pk=profile.user.id)
    else:
        form = UserProfileForm(instance=profile)

    context = {
        'form': form,
        'user': user,
        'title': 'Edit my profile',
        'subtitle': 'Profil update'
    }
    return render(request, 'accounts/user/profile_form.html', context)


# -------------------------------------------------------------------------
# CustomUser
# -------------------------------------------------------------------------
class CustomUserListView(BaseListView):
    model = CustomUser
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'users_page'
    title = _("Users Page")
    subtitle = _("Manage the users on the platform")
    header_paragraph = _("""Manage and oversee users directly on the platform. Whether adding new users, updating their profiles, or assigning roles and permissions, the platform provides an intuitive interface to handle all user-related tasks.
                                             Admins can easily view, update, and remove users, ensuring the right people have access to the right resources.
                                             This central hub allows for efficient user management, promoting a streamlined experience for everyone involved in the platform.""")

    def get_queryset(self):
        # Start with the base queryset
        queryset = super().get_queryset()

        # Get the user_type from GET parameters
        user_type = self.request.GET.get('user_type')

        # Filter by user_type if provided
        if user_type:
            queryset = queryset.filter(
                user_roles__role__user_type=user_type).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Determine object creation link
        context['object_crud_link'] = 'accounts:user-invitation-create'

        # Extract user_type from query string
        user_type = self.request.GET.get('user_type', '')
        context['selected_user_type'] = user_type

        # Map account type to readable title (you can customize or translate as needed)
        user_type_names = {
            'vendor': _('Vendors'),
            'cashier': _('Cashiers'),
            'pharmacist': _('Pharmacists'),
            'doctor': _('Doctors'),
            'inventory_manager': _('Inventory Managers'),
            'pharmacy_manager': _('Pharmacy Managers'),
            'platform_admin': _('Platform Administrator'),
        }
        # Set dynamic title, subtitle, and active page
        if user_type in user_type_names:
            context['title'] = _("Users Page — %(type)s Accounts") % {
                'type': user_type_names[user_type]}
            context['subtitle'] = _("Manage the users with %(type)s accounts on the platform") % {
                'type': user_type_names[user_type]}
            context['active_page'] = f"{user_type}_accounts_page"

        # Get the counts for each subject domain dynamically
        vendors_count = CustomUser.objects.filter(
            user_roles__role__user_type='vendor'
        ).distinct().count()
        cashiers_count = CustomUser.objects.filter(
            user_roles__role__user_type='cashier'
        ).distinct().count()
        pharmacists_count = CustomUser.objects.filter(
            user_roles__role__user_type='pharmacist'
        ).distinct().count()
        doctors_count = CustomUser.objects.filter(
            user_roles__role__user_type='doctor'
        ).distinct().count()
        inventory_managers_count = CustomUser.objects.filter(
            user_roles__role__user_type='inventory_manager'
        ).distinct().count()
        pharmacy_managers_count = CustomUser.objects.filter(
            user_roles__role__user_type='pharmacy_manager'
        ).distinct().count()
        platform_admins_count = CustomUser.objects.filter(
            user_roles__role__user_type='platform_admin'
        ).distinct().count()

        # List of subjects and their counts, icons, and colors
        data_groups = [
            (_("Vendors"), vendors_count, "fa-user-tag", "green"),
            (_("Cashiers"), cashiers_count, "fa-cash-register", "teal"),
            (_("Pharmacists"), pharmacists_count, "fa-user-nurse", "blue"),
            (_("Doctors"), doctors_count, "fa-user-doctor", "orange"),
            (_("Inventory Managers"), inventory_managers_count,
             "fa-boxes-stacked", "purple"),
            (_("Pharmacy Managers"), pharmacy_managers_count, "fa-store", "indigo"),
            (_("Platform Administrators"),
             platform_admins_count, "fa-shield", "red"),
        ]

        # Add the data_groups list to context
        context['data_groups'] = data_groups
        context['pagination_url '] = "accounts:user-list"

        return context

    def get_search_fields(self):
        # List of fields to be used for searching
        return ['email', 'first_name', 'last_name', 'username', 'phone_number']


class CustomUserDetailView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'accounts/user/detail.html'
    # This will give you access to `curr_obj` in the template
    context_object_name = 'curr_obj'

    def get_object(self):
        # Override the get_object method to customize how the object is fetched
        obj = super().get_object()  # Get the default object
        # Ensure the object is only accessible if the user is either viewing their own profile or an admin
        if self.request.user != obj and not self.request.user.is_staff:
            raise PermissionDenied("You are not allowed to view this profile.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        curr_obj = self.get_object()
        user = self.request.user
        is_self = user == curr_obj

        profile = getattr(curr_obj, 'profile', None)
        user_type = curr_obj.get_current_user_type()
        current_organization = getattr(
            profile, "current_organization", None) if profile else None
        current_role = getattr(profile, "current_role",
                               None) if profile else None

        # Add context data
        context.update({
            "active_page": "user_page",
            'title': 'user',
            'is_self': is_self,
            'profile': profile,
            'user_type': user_type,
            'current_organization': current_organization,
            'current_role': current_role,
            'title': _("User Detail Page"),
            'subtitle': _("View user's detail on the platform"),
        })

        return context


# class CustomUserCreateView(BaseModelView, CreateView):
#     model = CustomUser
#     fields = ['email', 'phone_number', 'username',
#               'first_name', 'last_name', 'user_type']
#     success_url = reverse_lazy('accounts:user-list')
#     title = _("Add a new user account")
#     subtitle = _("Fill the form to add a new user account")


class CustomUserUpdateView(BaseModelView, UpdateView):
    model = CustomUser
    fields = ['email', 'phone_number', 'username', 'first_name', 'last_name']
    # success_url = reverse_lazy('accounts:user-list')
    title = _("Edit a user account")
    subtitle = _("Update the user account info")


class ProfileUpdateView(BaseModelView, UpdateView):
    model = Profile
    fields = ['gender', 'bio', 'image',]
    # success_url = reverse_lazy('accounts:user-detail')
    title = _("Edit User Profile")
    subtitle = _("Update the user profile info")


# -------------------------------------------------------------------------
# UserInvitation
# -------------------------------------------------------------------------
class UserInvitationListView(BaseListView):
    model = UserInvitation
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'user_invitation_page'
    title = _("Organization Invitations")
    subtitle = _("Manage organization invitations")
    object_crud_link = 'accounts:user-invitation-create'
    header_paragraph = """Manage and oversee organization user invitations directly from the platform.
    Whether you’re adding new invitations, updating user profiles, or assigning roles and permissions,
    the platform offers an intuitive interface for seamless invitation management"""

    def get_search_fields(self):
        return ['receiver_email', 'user_type', 'organization__name']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        invitations = self.get_queryset()

        # Map user_type codes to labels and icons/colors
        USER_TYPE_INFO = {
            'vendor': {'label': _("Vendor Invitations"), 'icon': "fa-user-tag", 'color': "green"},
            'cashier': {'label': _("Cashier Invitations"), 'icon': "fa-cash-register", 'color': "teal"},
            'pharmacist': {'label': _("Pharmacist Invitations"), 'icon': "fa-user-nurse", 'color': "blue"},
            'doctor': {'label': _("Doctor Invitations"), 'icon': "fa-user-doctor", 'color': "orange"},
            'inventory_manager': {'label': _("Inventory Manager Invitations"), 'icon': "fa-boxes-stacked", 'color': "purple"},
            'pharmacy_manager': {'label': _("Pharmacy Manager Invitations"), 'icon': "fa-user-tie", 'color': "indigo"},
        }

        data_groups = []

        for user_type, info in USER_TYPE_INFO.items():
            acc_invitations = invitations.filter(user_type=user_type)

            total_sent = acc_invitations.count()
            responded = sum(1 for inv in acc_invitations if inv.is_used())
            expired = sum(1 for inv in acc_invitations if inv.is_expired())
            unanswered = total_sent - responded - expired

            data_groups.append((
                info['label'],
                [
                    {"name": _("Total Sent"), "count": total_sent},
                    {"name": _("Responded"), "count": responded},
                    {"name": _("Unanswered"), "count": unanswered},
                    {"name": _("Expired"), "count": expired},
                ],
                info['icon'],
                info['color']
            ))

        # print(data_groups)

        context['data_groups'] = data_groups
        context['model_detail_url'] = None
        context['model_update_url'] = None
        return context


class UserInvitationCreateView(BaseModelView, CreateView):
    model = UserInvitation
    fields = ['receiver_email', 'user_type']
    success_url = reverse_lazy('accounts:user-invitation-list')
    title = _("Create a new user invitation")
    subtitle = _("Fill out the form to invite a new user to the organization")

    def form_valid(self, form):
        # Set the sender as the current user
        form.instance.sender = self.request.user

        # Set the organization to the user's current organization
        form.instance.organization = self.request.user.profile.current_organization

        # Optional: Check if the combination of organization, sender, and receiver_email already exists
        if UserInvitation.objects.filter(
                organization=form.instance.organization,
                receiver_email=form.instance.receiver_email,
                user_type=form.instance.user_type
        ).exists():
            # If exists, show an error and return form_invalid
            messages.error(self.request, _(
                "An invitation with this email already exists for this organization, receiver email and user type."))
            return self.form_invalid(form)

        # If the combination doesn't exist, proceed to save the invitation
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _(
            "There were errors with your submission. Please check and try again."))
        return super().form_invalid(form)


# -------------------------------------------------------------------------
# User Parameters
# -------------------------------------------------------------------------
@login_required(login_url='accounts:login')
def user_parameters(request):
    user = request.user
    user_type = user.get_current_user_type()
    header_paragraph = """"""
    context = {
        "active_page": "user_parameters_page",
        "title": _("Platform User Parameters Page"),
        "subtitle": _("Manage the platform's user parameters"),
        "user_type": user_type,
        "header_paragraph": header_paragraph,
        "model_icon": 'fa-solid fa-user-gear',

    }

    return render(request, 'accounts/parameters/index.html', context)


@login_required(login_url='accounts:login')
def user_analytics(request):
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    last_7_days = now - timedelta(days=7)
    last_24h = now - timedelta(hours=24)

    users = CustomUser.objects.all()

    # --------------------------
    # BASIC USER COUNTS
    # --------------------------
    total_users = users.count()
    active_users = users.filter(is_active=True).count()
    staff_users = users.filter(is_staff=True).count()
    online_users = users.filter(is_online=True).count()
    offline_users = users.filter(is_online=False).count()

    # --------------------------
    # LOGIN STATISTICS
    # --------------------------
    logins_last_24h = users.filter(last_login__gte=last_24h).count()
    logins_last_7d = users.filter(last_login__gte=last_7_days).count()
    logins_last_30d = users.filter(last_login__gte=last_30_days).count()

    # Login timeline for graph
    login_timeline_labels = []
    login_timeline_values = []

    for i in range(30):
        day = now - timedelta(days=i)
        login_timeline_labels.append(day.strftime("%b %d"))
        login_timeline_values.append(
            users.filter(last_login__date=day.date()).count()
        )

    login_timeline_labels.reverse()
    login_timeline_values.reverse()

    # --------------------------
    # LOGOUT STATISTICS
    # --------------------------
    logouts_last_24h = users.filter(last_logout__gte=last_24h).count()
    logouts_last_7d = users.filter(last_logout__gte=last_7_days).count()
    logouts_last_30d = users.filter(last_logout__gte=last_30_days).count()

    # Login timeline for graph
    logout_timeline_labels = []
    logout_timeline_values = []

    for i in range(30):
        day = now - timedelta(days=i)
        logout_timeline_labels.append(day.strftime("%b %d"))
        logout_timeline_values.append(
            users.filter(last_logout__date=day.date()).count()
        )

    logout_timeline_labels.reverse()
    logout_timeline_values.reverse()

    # --------------------------
    # 24-HOUR LOGIN / LOGOUT VOLUME (HOURLY)
    # --------------------------

    hourly_labels = []
    hourly_logins = []
    hourly_logouts = []

    for i in range(24):
        hour_start = now - timedelta(hours=23 - i)
        hour_end = hour_start + timedelta(hours=1)

        hourly_labels.append(hour_start.strftime("%H:%M"))

        hourly_logins.append(
            users.filter(
                last_login__gte=hour_start,
                last_login__lt=hour_end
            ).count()
        )

        hourly_logouts.append(
            users.filter(
                last_logout__gte=hour_start,
                last_logout__lt=hour_end
            ).count()
        )

    # --------------------------
    # GENDER DISTRIBUTION
    # --------------------------
    gender_counts = {
        "male": Profile.objects.filter(gender="male").count(),
        "female": Profile.objects.filter(gender="female").count(),
        "unknown": Profile.objects.filter(gender__isnull=True).count()
    }

    # --------------------------
    # USER TYPE DISTRIBUTION
    # --------------------------
    user_types = [
        (user.get_current_user_type() or "unknown")
        for user in users
    ]

    user_type_counter = Counter(user_types)
    user_type_labels = list(user_type_counter.keys())
    user_type_values = list(user_type_counter.values())

    # --------------------------
    # CAMPUS DISTRIBUTION
    # --------------------------
    organization_names = Profile.objects.filter(
        current_organization__isnull=False
    ).values_list("current_organization__name", flat=True)

    organization_counter = Counter(organization_names)
    organization_labels = list(organization_counter.keys())
    organization_values = list(organization_counter.values())

    # --------------------------
    # PACKAGE DATA
    # --------------------------
    context = {
        "total_users": total_users,
        "active_users": active_users,
        "staff_users": staff_users,
        "online_users": online_users,
        "offline_users": offline_users,

        "logins": {
            "last_24h": logins_last_24h,
            "last_7d": logins_last_7d,
            "last_30d": logins_last_30d,
            "timeline_labels": login_timeline_labels,
            "timeline_data": login_timeline_values,
        },

        "logouts": {
            "last_24h": logouts_last_24h,
            "last_7d": logouts_last_7d,
            "last_30d": logouts_last_30d,
            "timeline_labels": logout_timeline_labels,
            "timeline_data": logout_timeline_values,
        },

        "activity_24h": {
            "labels": hourly_labels,
            "logins": hourly_logins,
            "logouts": hourly_logouts,
        },

        "gender": gender_counts,

        "user_types": user_type_counter,
        "user_type_labels": user_type_labels,
        "user_type_values": user_type_values,

        "organizations": organization_counter,
        "organization_labels": organization_labels,
        "organization_values": organization_values,

        "model_icon": "fa-solid fa-chart-line",
        "title": "Platform User Analytics",
        "subtitle": "Platform User Analytics",
        "header_paragraph": "Platform User Analytics",
    }

    return render(request, "accounts/user/analytics.html", context)


# -------------------------------------------------------------------------
# Permission
# -------------------------------------------------------------------------
class PermissionListView(BaseListView):
    model = PermissionProxy
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'user_parameters_page'
    title = _("User Permissions Page")
    subtitle = _("View and manage user permissions here")
    subtitle = _("View and manage user permissions here")
    header_paragraph = """Manage and oversee user permissions directly from the platform.
Whether you’re assigning access levels, updating roles, or controlling feature permissions,
the platform offers an intuitive interface for seamless permission management."""

    def get_search_fields(self):
        return ['name', 'codename',]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_icon'] = 'fa-solid fa-id-badge'
        context['pagination_url'] = 'accounts:user-permission-list'
        context['pagination_target'] = 'user-permission-list'
        context['object_is_actionable'] = False
        context['model_detail_url'] = None
        context['model_update_url'] = None
        return context


class PermissionUpdateView(BaseModelView, UpdateView):
    model = PermissionProxy
    fields = ['name', 'codename']
    success_url = reverse_lazy('accounts:user-permission-list')
    title = _("Edit User Permission")
    subtitle = _("Update the permission details")


# -------------------------------------------------------------------------
# Role
# -------------------------------------------------------------------------
class RoleListView(BaseListView):
    model = Role
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'user_role_page'
    title = _("User Roles Page")
    subtitle = _("View and manage user roles here")
    header_paragraph = _(
        """Manage and oversee the platform's user roles.
		This page helps administrators maintain clear and consistent access control."""
    )

    def get_search_fields(self):
        return ['name', 'user_type']


class RoleDetailView(BaseDetailView):
    model = Role
    template_name = 'accounts/user_role/detail.html'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        form = RolePermissionForm(
            request.POST,
            instance=self.object
        )

        if form.is_valid():
            form.save()
            messages.success(request, "Permissions updated successfully.")
        else:
            messages.error(request, "Failed to update permissions.")

        return redirect(request.path)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_role = context["object"]
        form = RolePermissionForm(instance=user_role)

        context.update({
            'form': form,
            'user_role': user_role,
            'user_permissions': user_role.permissions.all(),
            'paginate_by': 50,
            'pagination_url': 'accounts:user-permission-list',
            'pagination_target': 'user-permission-list',
            'active_page': 'app_parameters_page',
            'title': f'{user_role.name} User Role Details',
            'subtitle': 'View user role details',
            'header_paragraph': """
                        The User Role Details section provides a centralized view of each role’s access
                        and responsibilities within the system.
                """
        })
        return context


class RoleUpdateView(BaseModelView, UpdateView):
    model = Role
    fields = ['name', 'user_type', 'permissions']
    success_url = reverse_lazy('accounts:grading-system-list')
    title = _("Edit User Role")
    subtitle = _("Update the role details")


# -------------------------------------------------------------------------
# UserRole
# -------------------------------------------------------------------------
class UserRoleListView(BaseListView):
    model = UserRole
    template_name = 'accounts/user_organization_role/index.html'
    partial_parent_directory = 'accounts'
    partial_nested_directory = 'user_organization_role'
    context_object_name = 'user_user_roles'
    active_page = 'user_organization_role_page'
    title = _("User Role Assignments Page")
    subtitle = _("View and manage user user roles here")
    header_paragraph = _(
        """Manage and oversee your platform users' roles.
		This page helps administrators maintain an organized and transparent education ecosystem."""
    )

    def get_search_fields(self):
        return ['name', 'codename',]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_crud_object'] = ""
        context['object_crud_link'] = ""
        return context


class UserRoleCreateView(BaseModelView, CreateView):
    model = UserRole
    fields = ['name', 'user_type', 'permissions']
    success_url = reverse_lazy('accounts:grading-system-list')
    title = _("Add User Organization Role")
    subtitle = _("Create a user admin role")


class UserRoleUpdateView(BaseModelView, UpdateView):
    model = UserRole
    fields = ['name', 'user_type', 'permissions']
    success_url = reverse_lazy('accounts:grading-system-list')
    title = _("Edit User Role")
    subtitle = _("Update the role details")
