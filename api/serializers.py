# api/serializers.py
from rest_framework import serializers
from pharmadex.config.constants import MobileOperatorPreset,CountryPreset, CurrencyPreset


class MarketInfoSerializer(serializers.Serializer):
    countries = serializers.SerializerMethodField()
    currencies = serializers.SerializerMethodField()
    operators = serializers.SerializerMethodField()

    def get_countries(self, obj):
        return [
            {"code": c[0], "name": str(c[1]), "default_currency": CountryPreset.get_currency_for_country(c[0])}
            for c in CountryPreset.choices()
        ]

    def get_currencies(self, obj):
        return [
            {
                "code": c[0],
                "name": str(c[1]),
                "symbol": CurrencyPreset.get_data(c[0])["symbol"],
                "decimal_places": CurrencyPreset.get_data(c[0])["decimal_places"],
                "countries": CurrencyPreset.get_countries(c[0]),
            }
            for c in CurrencyPreset.choices()
        ]

    def get_operators(self, obj):
        return [
            {"code": c[0], "name": str(c[1]), "countries": c[2]}
            for c in MobileOperatorPreset._ALL
        ]