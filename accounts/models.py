from functools import lru_cache
from django.db.models import Q
import uuid
from datetime import timedelta
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from phonenumber_field.modelfields import PhoneNumberField
from base.models import ArchivableModel, BaseModel, OptimizedImageMixin
from django.contrib.auth.models import Permission


class PermissionProxy(Permission):
    default_url = "accounts:user-permission-list"
    detail_url = "accounts:user-permission-detail"
    update_url = "accounts:user-permission-update"
    create_url = None

    class Meta:
        proxy = True
        verbose_name = _("Permission")
        verbose_name_plural = _("Permissions")

    @classmethod
    def get_default_url(cls):
        return cls.default_url

    @classmethod
    def get_detail_url(cls):
        return cls.detail_url

    @classmethod
    def get_update_url(cls):
        return cls.update_url

    @classmethod
    def get_create_url(cls):
        return cls.create_url


class CustomUserManager(BaseUserManager):
    def _create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('Email address is required'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_active', True)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if not extra_fields.get('is_staff'):
            raise ValueError(_('Superuser must have is_staff=True.'))
        if not extra_fields.get('is_superuser'):
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self._create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin, BaseModel):
    email = models.EmailField(unique=True, verbose_name=_("Email"))
    first_name = models.CharField(max_length=100, verbose_name=_("First name"))
    last_name = models.CharField(max_length=100, verbose_name=_("Last name"))
    username = models.CharField(
        unique=True,
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Username")
    )
    
    unique_identifier = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Unique identifier"),
        help_text=_(
            "Optional identifier used for login instead of email or phone."),
    )
    phone_number = PhoneNumberField(
        blank=True, null=True, verbose_name=_("Phone number"))

    first_login = models.DateTimeField(
        blank=True, null=True, verbose_name=_("first login"))
    first_logout = models.DateTimeField(
        blank=True, null=True, verbose_name=_("first logout"))
    last_login = models.DateTimeField(
        blank=True, null=True, verbose_name=_("Last login"))
    last_logout = models.DateTimeField(
        blank=True, null=True, verbose_name=_("Last logout"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    is_staff = models.BooleanField(default=False, verbose_name=_("Is Staff"))
    is_superuser = models.BooleanField(default=False, verbose_name=_("Is Superuser"))
    is_online = models.BooleanField(default=False, verbose_name=_("Is Online"))

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    model_icon = "fa-solid fa-user"

    objects = CustomUserManager()

    default_url = "accounts:user-list"
    detail_url = "accounts:user-detail"
    update_url = "accounts:user-update"
    create_url = "accounts:user-create"

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return f'{self.first_name} {self.last_name} - {self.email}'

    @property
    def alias(self):
        return f'@_{self.username}' if self.username else None

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def get_profile(self):
        return self.profile

    # ---------------------------------
    # ROLE HELPERS
    # ---------------------------------

    def get_roles(self, organization=None):
        """
        Returns roles scoped to a organization.
        If organization is None → returns global roles only.
        """
        return self.user_roles.filter(organization=organization)

    def get_effective_roles(self, organization):
        """
        Returns both:
        - global roles
        - roles for the given organization
        """
        return self.user_roles.filter(
            Q(organization=organization) | Q(organization__isnull=True)
        )

    def has_role(self, role_name, organization=None):
        """
        Generic role checker (DON'T hardcode everywhere else)
        """
        return self.user_roles.filter(
            role__name=role_name,
            organization=organization
        ).exists()

    def has_global_role(self, role_name):
        return self.has_role(role_name, organization=None)

    def has_organization_role(self, role_name, organization):
        return self.has_role(role_name, organization=organization)

    # ---------------------------------
    # HIGH-LEVEL CHECKS (SAFE WRAPPERS)
    # ---------------------------------

    def is_platform_admin(self):
        return self.has_global_role("Platform Administrator")

    def is_organization_admin(self, organization):
        return self.has_organization_role("Organization Administrator", organization)

    def get_current_user_type(self):
        # Use current_role if set or default to none
        current_role = getattr(self.profile, 'current_role', None)
        if current_role and current_role.role and current_role.role.user_type:
            return current_role.role.user_type

        return None

    def get_current_profile(self, user_type=None, organization=None):
        return getattr(self, "profile", None)


class Profile(OptimizedImageMixin, BaseModel):
    image_fields = ['image',]

    GENDER_CHOICES = (
        ('male', _('Masculin')),
        ('female', _('Feminin')),
    )
    user = models.OneToOneField(
        CustomUser, on_delete=models.PROTECT, related_name='profile', verbose_name=_("User")
    )
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES,
                              blank=True, null=True, verbose_name=_("Gender"))
    image = models.ImageField(
        upload_to='users/profiles', blank=True, null=True, verbose_name=_("Profile Picture")
    )
    bio = models.TextField(blank=True, null=True, verbose_name=_("Bio"))
    current_role = models.ForeignKey('UserRole', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='active_roles', verbose_name=_("Current Role"))
    current_organization = models.ForeignKey('organizations.Organization', on_delete=models.SET_NULL, null=True, blank=True,
                                             related_name='active_profiles', verbose_name=_("Current Organization"))
    allowed_organizations = models.ManyToManyField(
        'organizations.Organization', related_name='allowed_organizations', blank=True, verbose_name=_("Allowed organizations"))
    current_pharmacy = models.ForeignKey('pharmacies.Pharmacy', on_delete=models.SET_NULL, null=True, blank=True,
                                             related_name='active_profiles', verbose_name=_("Current Pharmacy"))
    allowed_pharmacies = models.ManyToManyField(
        "pharmacies.Pharmacy", blank=True, verbose_name=_("Allowed pharmacies"))

    model_icon = 'fa-solid fa-id-card'

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("Users Profiles")

    def __str__(self):
        return f'{self.user.full_name} User profile'


class Role(BaseModel):
    USER_TYPE_CHOICES = (
        ('vendor', _('Vendor')),
        ('cashier', _('Cashier')),
        ('pharmacist', _('Pharmacist')),
        ('doctor', _('Doctor')),
        ('inventory_manager', _('Inventory Manager')),
        ('pharmacy_manager', _('Pharmacy Manager')),
        ('platform_admin', _('Platform Administrator')),
    )

    name = models.CharField(max_length=255)
    user_type = models.CharField(
        max_length=24,
        choices=USER_TYPE_CHOICES,
        verbose_name=_("User Type")
    )
    permissions = models.ManyToManyField(
        Permission, related_name="roles", blank=True)
    
    model_icon = 'fa-solid fa-id-badge'

    class Meta:
        unique_together = ('name', 'user_type')  # better constraint
        verbose_name = _("User Role")
        verbose_name_plural = _("User Roles")

    def __str__(self):
        return self.name


class UserRole(BaseModel):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="user_roles"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="assigned_users"
    )
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_roles"
    )
    
    model_icon = 'fa-solid fa-user-tag'

    class Meta:
        unique_together = ('user', 'role', 'organization')

    def __str__(self):
        scope = self.organization.name if self.organization else "Global"
        return f"{self.user.email} → {self.role.name} ({scope})"


def get_default_invitation_expiration():
    return timezone.now() + timedelta(days=3)


class UserInvitation(BaseModel):
    USER_TYPE_CHOICES = [
        ('vendor', _('Vendor')),
        ('cashier', _('Cashier')),
        ('pharmacist', _('Pharmacist')),
        ('doctor', _('Doctor')),
        ('inventory_manager', _('Inventory Manager')),
        ('pharmacy_manager', _('Pharmacy Manager')),
        ('platform_admin', _('Platform Administrator')),
    ]

    organization = models.ForeignKey('organizations.Organization', blank=True, null=True,
                                     on_delete=models.CASCADE, related_name="user_invitations")
    sender = models.ForeignKey(CustomUser, on_delete=models.PROTECT,
                               related_name='invitations_sent', verbose_name=_("Invitation Sender"))
    receiver = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='invitations_received',
                                 blank=True, null=True, verbose_name=_("Invitation Receiver"))
    receiver_email = models.EmailField(verbose_name=_("Receiver Email"))
    user_type = models.CharField(
        max_length=24, choices=USER_TYPE_CHOICES, blank=True, null=True, verbose_name=_("User Type"))
    token = models.UUIDField(default=uuid.uuid4, unique=True,
                             editable=False, verbose_name=_("Invitation Token"))

    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Created At"))
    expiration_date = models.DateTimeField(
        blank=True, null=True,
        default=get_default_invitation_expiration,
        verbose_name=_("Expiration Date")
    )
    
    model_icon = 'fa-solid fa-envelope-circle-check'

    def is_expired(self):
        return timezone.now() > self.expiration_date

    def is_used(self):
        return self.receiver is not None

    def __str__(self):
        return f'{self.receiver_email} invited as {self.user_type}'

    class Meta:
        verbose_name = _("User Invitation")
        verbose_name_plural = _("User Invitations")
        constraints = [
            models.UniqueConstraint(
                fields=['receiver_email', 'user_type', 'organization'],
                name='unique_invitation'
            )
        ]
