from django.utils.translation import gettext_lazy as _


# ==========================================================
# CORE FUNCTION
# ==========================================================
def get_sidebar_links(user, current_organization=None):
    links = []

    def add_link(name, url, icon, active_class, url_args=None, get_params=None):
        links.append({
            "name": name,
            "url": url,
            "icon": icon,
            "active_class": active_class,
            "url_args": url_args or [],
            "get_params": get_params or "",
        })

    if not user.is_authenticated:
        return links

    # ==========================================================
    # ORGANIZATION CONTEXT
    # ==========================================================
    profile = getattr(user, "profile", None)
    current_org = getattr(profile, "current_organization",
                          None) if profile else None
    current_pharma = getattr(profile, "current_pharmacy",
                             None) if profile else None
    assignment = getattr(profile, "current_role", None) if profile else None
    current_role = assignment.role if assignment else None
    current_role_type = getattr(
        current_role, "user_type", None) if current_role else None

    # ==========================================================
    # HOME
    # ==========================================================
    add_link(_("Home"), "base:home", "fa-solid fa-house", "home_page")

    if current_org:
        add_link(
            _("Organization"),
            "organizations:organization-dashboard",
            "fa-solid fa-building",
            "organizations_page"
        )

        if current_pharma:
            add_link(
                _("Pharmacy"),
                "pharmacies:pharmacy-detail",
                "fa-solid fa-staff-snake",
                "pharmacies_page",
                url_args=[current_pharma.id]
            )
        else:
            add_link(
                _("Pharmacies"),
                "pharmacies:pharmacy-list",
                "fa-solid fa-staff-snake",
                "pharmacies_page"
            )

    # ==========================================================
    # 💊 PHARMACY CORE (WORKFLOW-BASED)
    # ==========================================================
    if current_role_type in [
        "vendor",
        "cashier",
        "pharmacist",
        "doctor",
        "inventory_manager",
        "pharmacy_manager",
        "platform_admin",
    ]:

        # ------------------------------
        # DISPENSING / POS
        # ------------------------------
        add_link(
            _("Point of Sale"),
            "pharmacies:point-of-sale",
            "fa-solid fa-store",
            "pos_page"
        )
        
        if current_pharma and current_pharma.requires_cashier_validation:
            add_link(
                _("Cashier Validation"),
                "pharmacies:cashier-validation",
                "fa-solid fa-cash-register",
                "cashier_validation_page"
            )

        add_link(
            _("Sales History"),
            "pharmacies:sale-list",
            "fa-solid fa-cart-shopping",
            "sales_page"
        )

        add_link(
            _("Prescriptions"),
            "pharmacies:prescription-list",
            "fa-solid fa-file-prescription",
            "prescriptions_page",
        )

        # ------------------------------
        # PRODUCT & BATCH INVENTORY
        # ------------------------------
        add_link(
            _("Stock Overview"),
            "pharmacies:product-stock-list",
            "fa-solid fa-boxes-stacked",
            "product_stocks_page"
        )

        # ------------------------------
        # INVENTORY OPERATIONS
        # ------------------------------
        add_link(
            _("Inventory Dashboard"),
            "pharmacies:inventory-dashboard",
            "fa-solid fa-up-down",
            "inventory_page"
        )
        
        if current_pharma:
            add_link(
                _("Stock Procurement"),
                "pharmacies:procurement-dashboard",
                "fa-solid fa-dolly",
                "procurement_page"
            )

        # ------------------------------
        # CLINIC LINKS
        # ------------------------------
        # if current_pharma and current_pharma.clinic_enabled:
        #     add_link(
        #         _("Clinic Dashboard"),
        #         "clinics:clinic-dashboard",
        #         "fa-solid fa-house-medical",
        #         "clinics_page"
        #     )

    # ==========================================================
    # ADMIN / BACKOFFICE
    # ==========================================================
    if user.is_superuser or user.is_platform_admin() or current_role_type == "platform_admin":

        add_link(
            _("Fiannce Dashboard"),
            "finances:finances-dashboard",
            "fa-solid fa-coins",
            "finances_page"
        )

        # add_link(
        #     _("Human Resources"),
        #     "hr:hr-dahboard",
        #     "fa-solid fa-users-rays",
        #     "staff_page"
        # )

        add_link(
            _("Users Management"),
            "accounts:user-list",
            "fa-solid fa-user-alt",
            "users_page"
        )

    # ==========================================================
    # SYSTEM SETTINGS (SUPERUSER ONLY)
    # ==========================================================
    if user.is_superuser:

        add_link(
            _("User Invitations"),
            "accounts:user-invitation-list",
            "fa-solid fa-envelope-circle-check",
            "user_invitations_page"
        )

        add_link(
            _("Accounts Settings"),
            "base:user-parameters",
            "fa-solid fa-user-gear",
            "user_parameters_page"
        )

        add_link(
            _("System Settings"),
            "base:system-parameters",
            "fa-solid fa-server",
            "system_parameters_page"
        )

    return links


# ==========================================================
# CONTEXT PROCESSOR
# ==========================================================

def sidebar_context(request):
    user = request.user
    sidebar_links = []

    if user.is_authenticated:
        profile = getattr(user, "profile", None)
        current_organization = getattr(
            profile, "current_organization", None) if profile else None

        sidebar_links = get_sidebar_links(user, current_organization)

    return {
        "sidebar_links": sidebar_links
    }
