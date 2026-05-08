# accounts/signals.py
from django.db import transaction
from django.utils.text import capfirst
from accounts.models import CustomUser,  Role, Permission, UserRole #, UserInvitation, UserRole
from django.dispatch import receiver
from django.db.models.signals import post_migrate, post_save, post_delete
from django.contrib.auth.signals import user_logged_in
from accounts.models import Profile
# from accounts.utils import send_invitation_email
from django.contrib.auth import get_user_model
from django.apps import apps

User = get_user_model()

# Create or update profile after user creation
@receiver(post_save, sender=CustomUser)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Ensure every user has a Profile with a sensible current_organization.
    """

    if created:
        # Create profile when user is created
        Profile.objects.create(
            user=instance,
            current_organization=None
        )
    else:
        # Ensure profile exists
        profile, _boolean = Profile.objects.get_or_create(user=instance)

        # Update organization if missing
        # if not profile.current_organization:
        #     organizationes = instance.user_roles.all()
        #     if organizationes.exists():
        #         profile.current_organization = organizationes.first()
        #         profile.save(update_fields=["current_organization"])


# Assign platform admin role after superuser creation
@receiver(post_save, sender=CustomUser)
def assign_platform_admin_role(sender, instance, created, **kwargs):
    """
    Assign Platform Admin role to superusers and set it as current_role.
    """

    if not instance.is_superuser:
        return

    # Get or create the Platform Admin role
    role, _ = Role.objects.get_or_create(
        name="Platform Administrator",
        user_type="platform_admin",
    )

    # Create user role (global → organization=None)
    assignment, _ = UserRole.objects.get_or_create(
        user=instance,
        role=role,
        organization=None
    )

    # Ensure profile exists
    profile, _ = Profile.objects.get_or_create(user=instance)

    # Assign current role correctly ✅
    if profile.current_role_id != assignment.id:
        profile.current_role = assignment
        profile.save(update_fields=["current_role"])


