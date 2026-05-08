import smtplib

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.contrib import messages
from django.utils.translation import gettext as _  # For translation


# -------------------------------------------------------------------------
# User Permission Checker
# -------------------------------------------------------------------------
def user_has_permission(action, user, model):
	"""
	Generic permission checker.

	Rules:
	- Superuser: always allowed
	- Everyone else (including staff): must have explicit permission
	"""

	if not user or not user.is_authenticated:
		return False

	# Superuser override
	if user.is_superuser:
		return True

	if (
		model._meta.app_label == "organizations"
		and model._meta.model_name == "organization"
		and action in ["view", "add"]
	):
		return True

	model_name = model._meta.model_name
	perm = f"{action}_{model_name}"

	if hasattr(user, "get_all_permissions"):
		return perm in user.get_all_permissions()

	return False


def can_user_access_object(user, obj, organization=None, pharmacy=None):
	"""
	Determine if a user can access a given object (view, update, delete)
	based on zero-trust rules.

	Rules:
	1. Superusers: always allowed
	2. Users: must be connected via role/profile/relationship
	"""

	if not user or not user.is_authenticated:
		return False

	# Superuser override
	if user.is_superuser:
		return True

	# AdministrativeStaff with explicit permission
	if user.is_staff:
		model_name = obj._meta.model_name
		perm = f"change_{model_name}"
		if hasattr(user, "get_all_permissions") and perm in user.get_all_permissions():
			return True

	# Step 1: Direct ownership / connection
	if hasattr(obj, "users") and user in obj.users.all():
		return True

	if hasattr(obj, "user_profiles") and getattr(user, "profile", None) in obj.user_profiles.all():
		return True

	# Step 2: Tenant scoping
	if hasattr(obj, "organization_id"):
		curr_org_id = getattr(getattr(user, "profile", None), "current_organization_id", None)
		if organization and obj.organization_id != organization.id:
			return False
		if curr_org_id and obj.organization_id != curr_org_id:
			return False

	if hasattr(obj, "pharmacy_id"):
		curr_pharmacy_id = getattr(getattr(user, "profile", None), "current_pharmacy_id", None)
		if pharmacy and obj.pharmacy_id != pharmacy.id:
			return False
		if curr_pharmacy_id and obj.pharmacy_id != curr_pharmacy_id:
			return False

	# Step 3: Model-defined connected users
	if hasattr(obj, "get_connected_users"):
		if user in obj.get_connected_users():
			return True

	# Deny by default
	return False


# -------------------------------------------------------------------------
# Email Sender
# -------------------------------------------------------------------------
def send_invitation_email(invitation, request=None):
    """
    Sends a pharmacy/organization invitation email.
    """

    try:
        # -------------------- BASE URL --------------------
        base_url = getattr(settings, "SITE_URL")

        # -------------------- ORGANIZATION --------------------
        organization = getattr(invitation, "organization", None)

        # -------------------- INVITE URL --------------------
        invite_url = f"{base_url}{reverse('accounts:signup')}?token={invitation.token}"

        # -------------------- ROLE LABEL --------------------
        role_label = (
            dict(invitation.ROLE_TYPE_CHOICES).get(invitation.role_type)
            if hasattr(invitation, "ROLE_TYPE_CHOICES")
            else invitation.role_type
        )

        # -------------------- CONTEXT --------------------
        context = {
            "email": invitation.receiver_email,
            "role": role_label,
            "organization_name": organization.name if organization else _("Pharmacy"),
            "organization_logo": (
                f"{base_url}{organization.logo.url}"
                if organization and getattr(organization, "logo", None)
                else None
            ),
            "platform_logo": f"{base_url}/static/imgs/brand/logo.png",
            "invite_url": invite_url,
        }

        # -------------------- EMAIL CONTENT --------------------
        subject = _(
            "You have been invited to join {org} on Pharmadex"
        ).format(org=context["organization_name"])

        template_name = "accounts/emails/organization_invitation.html"

        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)

        # -------------------- SEND EMAIL --------------------
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@pharmadex.com"),
            recipient_list=[invitation.receiver_email],
            html_message=html_message,
        )

        # -------------------- SUCCESS --------------------
        if request:
            messages.success(
                request,
                _("Invitation email sent to {}.").format(invitation.receiver_email),
            )

        print(f"✅ Invitation sent to {invitation.receiver_email}")

    except Exception as e:
        # -------------------- ERROR --------------------
        if request:
            messages.error(
                request,
                _("Failed to send invitation email."),
            )

        print(f"❌ Invitation error: {str(e)}")


def send_test_email():
    try:
        # Connect to the Outlook SMTP server
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        server.starttls()  # Start TLS encryption
        # Login with your email and app password
        server.login(settings.DEFAULT_FROM_EMAIL, settings.EMAIL_HOST_PASSWORD)

        # Send a test email
        server.sendmail(
            from_addr=settings.DEFAULT_FROM_EMAIL,
            to_addrs=settings.TEST_RECIPIENT_EMAIL,  # Replace with a valid recipient email
            msg="Subject: Test Email\n\nThis is a test email."
        )
        print("Test email sent successfully.")
        server.quit()  # Close the connection
    except Exception as e:
        print(f"Error: {e}")

