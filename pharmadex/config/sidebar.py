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
            "get_params": get_params or [],
        })

    if not user.is_authenticated:
        return links

    # ==========================================================
    # ORGANIZATION CONTEXT
    # ==========================================================
    profile = getattr(user, "profile", None)
    current_org = getattr(profile, "current_organization",
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
            "fa-solid fa-table-list",
            "organization_page"
        )

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

        add_link(
            _("Prescriptions"),
            "pharmacies:prescription-list",
            "fa-solid fa-file-prescription",
            "prescription_page",
            get_params={"status": "pending"}
        )

        add_link(
            _("Sales History"),
            "pharmacies:sale-list",
            "fa-solid fa-cart-shopping",
            "sale_page"
        )

        # ------------------------------
        # PRODUCT & BATCH INVENTORY
        # ------------------------------
        add_link(
            _("Product Catalog"),
            "pharmacies:product-list",
            "fa-solid fa-prescription-bottle-medical",
            "product_page"
        )

        add_link(
            _("Stock Overview"),
            "pharmacies:product-stock-list",
            "fa-solid fa-boxes-stacked",
            "product_stock_page"
        )

        add_link(
            _("Batch Management"),
            "pharmacies:product-batch-list",
            "fa-solid fa-cart-flatbed",
            "batch_page"
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

        # ------------------------------
        # SAFETY / COMPLIANCE
        # ------------------------------
        add_link(
            _("Stock Alerts"),
            "pharmacies:product-batch-list",
            "fa-solid fa-bell",
            "stock_alert_page",
            get_params={"filter": "alerts"}
        )

    # ==========================================================
    # ADMIN / BACKOFFICE
    # ==========================================================
    if user.is_superuser or user.is_platform_admin() or current_role_type == "platform_admin":

        # add_link(
        #     _("Staff Management"),
        #     "hr:staff-list",
        #     "fa-solid fa-user-tie",
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
            "user_invitation_page"
        )

        add_link(
            _("Account Settings"),
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
