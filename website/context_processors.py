def country_currency(request):
    return {
        'COUNTRY_CODE': request.session.get('country_code', 'SN'),
        'CURRENCY_CODE': request.session.get('currency_code', 'XOF'),
    }