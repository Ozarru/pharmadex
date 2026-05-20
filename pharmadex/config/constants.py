"""
Project-wide constants for West African markets.
Import anywhere: models, views, templates via context processor, API serializers, website.
"""

from django.utils.translation import gettext_lazy as _


class CountryPreset:
    """ISO 3166-1 alpha-2 codes for West & Central Africa + key trade partners."""

    # --- UEMOA / West African CFA (XOF) ---
    BENIN = "BJ", _("Benin")
    BURKINA_FASO = "BF", _("Burkina Faso")
    COTE_DIVOIRE = "CI", _("Côte d'Ivoire")
    GUINEA_BISSAU = "GW", _("Guinea-Bissau")
    MALI = "ML", _("Mali")
    NIGER = "NE", _("Niger")
    SENEGAL = "SN", _("Senegal")
    TOGO = "TG", _("Togo")

    # --- CEMAC / Central African CFA (XAF) ---
    CAMEROON = "CM", _("Cameroon")
    CENTRAL_AFRICAN_REPUBLIC = "CF", _("Central African Republic")
    CHAD = "TD", _("Chad")
    CONGO = "CG", _("Congo")
    EQUATORIAL_GUINEA = "GQ", _("Equatorial Guinea")
    GABON = "GA", _("Gabon")

    # --- Other Key Markets ---
    GHANA = "GH", _("Ghana")
    NIGERIA = "NG", _("Nigeria")

    # --- Regional / International ---
    OTHER = "XX", _("Other / Regional")

    _ALL = [
        BENIN, BURKINA_FASO, COTE_DIVOIRE, GUINEA_BISSAU,
        MALI, NIGER, SENEGAL, TOGO,  # XOF zone
        CAMEROON, CENTRAL_AFRICAN_REPUBLIC, CHAD, CONGO,
        EQUATORIAL_GUINEA, GABON,  # XAF zone
        GHANA, NIGERIA,  # Independent currencies
        OTHER,
    ]

    @classmethod
    def choices(cls):
        return cls._ALL

    @classmethod
    def get_currency_for_country(cls, country_code):
        """Default currency preset for a given country."""
        mapping = {
            # XOF zone
            "BJ": "XOF", "BF": "XOF", "CI": "XOF", "GW": "XOF",
            "ML": "XOF", "NE": "XOF", "SN": "XOF", "TG": "XOF",
            # XAF zone
            "CM": "XAF", "CF": "XAF", "TD": "XAF", "CG": "XAF",
            "GQ": "XAF", "GA": "XAF",
            # Independent
            "GH": "GHS",
            "NG": "NGN",
        }
        return mapping.get(country_code, "XOF")

    @classmethod
    def get_display_name(cls, code):
        for c in cls._ALL:
            if c[0] == code:
                return c[1]
        return code


class CurrencyPreset:
    """ISO 4217 currencies with regional context."""

    XOF = "XOF", _("West African CFA Franc"), "₣", 0
    XAF = "XAF", _("Central African CFA Franc"), "₣", 0
    NGN = "NGN", _("Nigerian Naira"), "₦", 2
    GHS = "GHS", _("Ghanaian Cedi"), "₵", 2
    EUR = "EUR", _("Euro"), "€", 2
    USD = "USD", _("US Dollar"), "$", 2
    GBP = "GBP", _("British Pound"), "£", 2

    _ALL = [XOF, XAF, NGN, GHS, EUR, USD, GBP]

    @classmethod
    def choices(cls):
        return [(c[0], c[1]) for c in cls._ALL]

    @classmethod
    def get_data(cls, code):
        """Return full tuple for a currency code."""
        for c in cls._ALL:
            if c[0] == code:
                return {
                    "code": c[0],
                    "name": c[1],
                    "symbol": c[2],
                    "decimal_places": c[3],
                }
        return None

    @classmethod
    def format_amount(cls, code, amount):
        """Static formatting without model instance."""
        data = cls.get_data(code)
        if not data:
            return str(amount)
        symbol = data["symbol"]
        if data["decimal_places"] == 0:
            return f"{symbol}{int(amount):,}"
        return f"{symbol}{amount:,.{data['decimal_places']}f}"

    @classmethod
    def get_countries(cls, code):
        """Which countries typically use this currency."""
        country_currency_map = {
            "XOF": ["BJ", "BF", "CI", "GW", "ML", "NE", "SN", "TG"],
            "XAF": ["CM", "CF", "TD", "CG", "GQ", "GA"],
            "NGN": ["NG"],
            "GHS": ["GH"],
            "EUR": [],
            "USD": [],
            "GBP": [],
        }
        return country_currency_map.get(code, [])


class MobileOperatorPreset:
    """Major mobile money operators in West & Central Africa."""

    # --- Francophone West Africa ---
    ORANGE_MONEY = "OM", _("Orange Money"), ["SN", "ML", "BF", "CI", "GN", "NE", "TG"]
    MOOV_MONEY = "MM", _("Moov Money"), ["BJ", "BF", "CI", "GA", "ML", "NE", "TG"]
    MTN_MOMO = "MTN", _("MTN Mobile Money"), ["BJ", "CI", "GH", "NE", "TG"]
    WAVE = "WV", _("Wave"), ["SN", "CI", "BF", "ML", "UG"]
    FREE_MONEY = "FM", _("Free Money"), ["SN"]

    # --- Anglophone West Africa ---
    MTN_MOMO_NG = "MTN_NG", _("MTN MoMo Nigeria"), ["NG"]
    AIRTEL_MONEY = "AM", _("Airtel Money"), ["NG", "GH"]
    OPAY = "OP", _("OPay"), ["NG"]
    PALMPAY = "PP", _("PalmPay"), ["NG"]
    KUDA = "KD", _("Kuda"), ["NG"]

    # --- Central Africa ---
    AFRICELL_MONEY = "AF", _("Africell Money"), ["CD", "GA", "UG", "SL"]

    _ALL = [
        ORANGE_MONEY, MOOV_MONEY, MTN_MOMO, WAVE, FREE_MONEY,
        MTN_MOMO_NG, AIRTEL_MONEY, OPAY, PALMPAY, KUDA,
        AFRICELL_MONEY,
    ]

    @classmethod
    def choices(cls):
        return [(c[0], c[1]) for c in cls._ALL]

    @classmethod
    def for_country(cls, country_code):
        """Operators available in a specific country."""
        return [
            (c[0], c[1]) for c in cls._ALL
            if country_code.upper() in c[2]
        ]

    @classmethod
    def get_data(cls, code):
        for c in cls._ALL:
            if c[0] == code:
                return {
                    "code": c[0],
                    "name": c[1],
                    "countries": c[2],
                }
        return None