from django.urls import path
from .views import *

urlpatterns = [

    # Pharmacy Finances URLs -----------------------------------------------------------------------------
    path('dashboard/', finances_dashboard, name='finances-dashboard'),
    path('reports/', financial_reports, name='financial-reports'),

    # Currency URLs
    path('currencies/list/', CurrencyListView.as_view(), name='currency-list'),
    path('currencies/create/', CurrencyCreateView.as_view(), name='currency-create'),
    path('currencies/<uuid:pk>/detail/',
         CurrencyDetailView.as_view(), name='currency-detail'),
    path('currencies/<uuid:pk>/update/',
         CurrencyUpdateView.as_view(), name='currency-update'),

    # BankAccount URLs
    path('bank-accounts/list/', BankAccountListView.as_view(),
         name='bank-account-list'),
    path('bank-accounts/create/', BankAccountCreateView.as_view(),
         name='bank-account-create'),
    path('bank-accounts/<uuid:pk>/detail/',
         BankAccountDetailView.as_view(), name='bank-account-detail'),
    path('bank-accounts/<uuid:pk>/update/',
         BankAccountUpdateView.as_view(), name='bank-account-update'),

    # CashAccount URLs
    path('cash_accounts/list/', CashAccountListView.as_view(), name='cash-account-list'),
    path('cash_accounts/create/', CashAccountCreateView.as_view(), name='cash-account-create'),
    path('cash_accounts/<uuid:pk>/detail/',
         CashAccountDetailView.as_view(), name='cash-account-detail'),
    path('cash_accounts/<uuid:pk>/update/',
         CashAccountUpdateView.as_view(), name='cash-account-update'),

    # MobileOperator URLs
    path('mobile-operators/list/', MobileOperatorListView.as_view(),
         name='mobile-operator-list'),
    path('mobile-operators/create/', MobileOperatorCreateView.as_view(),
         name='mobile-operator-create'),
    path('mobile-operators/<uuid:pk>/detail/',
         MobileOperatorDetailView.as_view(), name='mobile-operator-detail'),
    path('mobile-operators/<uuid:pk>/update/',
         MobileOperatorUpdateView.as_view(), name='mobile-operator-update'),

    # Invoice URLs
    path('invoices/list/', InvoiceListView.as_view(), name='invoice-list'),
    path('invoices/create/', InvoiceCreateView.as_view(), name='invoice-create'),
    path('invoices/<uuid:pk>/detail/',
         InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoices/<uuid:pk>/update/',
         InvoiceUpdateView.as_view(), name='invoice-update'),

    # Bill URLs
    path('bills/list/', BillListView.as_view(), name='bill-list'),
    path('bills/create/', BillCreateView.as_view(), name='bill-create'),
    path('bills/<uuid:pk>/detail/', BillDetailView.as_view(), name='bill-detail'),
    path('bills/<uuid:pk>/update/', BillUpdateView.as_view(), name='bill-update'),

    # Payment URLs
    # path('payments/list/', PaymentListView.as_view(), name='payment-list'),
    # path('payments/create/', PaymentCreateView.as_view(), name='payment-create'),
    # path('payments/<uuid:pk>/detail/', PaymentDetailView.as_view(), name='payment-detail'),
    # path('payments/<uuid:pk>/update/', PaymentUpdateView.as_view(), name='payment-update'),

    # FinancialOperation URLs
    path('financial-operations/create', FinancialOperationCreateView.as_view(),
         name='financial-operation-create'),
    path('financial-operations/list/', FinancialOperationListView.as_view(),
         name='financial-operation-list'),
    path('financial-operations/<uuid:pk>/detail/',
         FinancialOperationDetailView.as_view(), name='financial-operation-detail'),
    path('financial-operations/<uuid:pk>/update/',
         FinancialOperationUpdateView.as_view(), name='financial-operation-update'),


    # Cash Closing
    path('cash-closing/list/', CashClosingListView.as_view(),
         name='cash-closing-list'),
    path('cash-closing/<uuid:pk>/detail/',
         CashClosingDetailView.as_view(), name='cash-closing-detail'),
    path("cash-closing/create/", CashClosingUpsertView.as_view(),
         name="cash-closing-create"),
    path("cash-closing/<uuid:pk>/update/",
         CashClosingUpsertView.as_view(), name="cash-closing-update"),
    path("cash-closing/analytics/", cash_closing_analytics,
         name="cash-closing-analytics"),

]
