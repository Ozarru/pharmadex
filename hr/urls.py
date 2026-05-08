from django.urls import path
from .views import *

urlpatterns = [
    
    # Staff URLs
    path('staff/list/', StaffListView.as_view(), name='staff-list'),
    path('staff/create/', StaffCreateView.as_view(), name='staff-create'),
    path('staff/<uuid:pk>/detail/', StaffDetailView.as_view(), name='staff-detail'),
    path('staff/<uuid:pk>/update/', StaffUpdateView.as_view(), name='staff-update'),
    # path("staff/synchronize/", sync_staff_view, name="staff-synchronise"),
    
    
    # Salary Scale URLs
    path('salary-scales/list/', SalaryScaleListView.as_view(), name='salary-scale-list'),
    path('salary-scales/create/', SalaryScaleCreateView.as_view(), name='salary-scale-create'),
    path('salary-scales/<uuid:pk>/detail/', SalaryScaleDetailView.as_view(), name='salary-scale-detail'),
    path('salary-scales/<uuid:pk>/update/', SalaryScaleUpdateView.as_view(), name='salary-scale-update'),
    
    # Payro llItem URLs
    path('payroll-items/list/', PayrollItemListView.as_view(), name='payroll-item-list'),
    path('payroll-items/create/', PayrollItemCreateView.as_view(), name='payroll-item-create'),
    path('payroll-items/<uuid:pk>/detail/', PayrollItemDetailView.as_view(), name='payroll-item-detail'),
    path('payroll-items/<uuid:pk>/update/', PayrollItemUpdateView.as_view(), name='payroll-item-update'),
    
    # Payroll Transaction URLs
    path('payroll-transactions/list/', PayrollTransactionListView.as_view(), name='payroll-transaction-list'),
    path('payroll-transactions/create/', PayrollTransactionCreateView.as_view(), name='payroll-transaction-create'),
    path('payroll-transactions/<uuid:pk>/detail/', PayrollTransactionDetailView.as_view(), name='payroll-transaction-detail'),
    path('payroll-transactions/<uuid:pk>/update/', PayrollTransactionUpdateView.as_view(), name='payroll-transaction-update'),
]