from django.urls import path
from .views import *

urlpatterns = [
    path('', tickets_dashboard, name='tickets-dashboard'),
    # SupportTicket URLs
    path('support-tickets/list/', SupportTicketListView.as_view(), name='support-ticket-list'),
    path('support-tickets/create/', SupportTicketCreateView.as_view(), name='support-ticket-create'),
    path('support-tickets/<uuid:pk>/detail/', SupportTicketDetailView.as_view(), name='support-ticket-detail'),
    path('support-tickets/<uuid:pk>/update/', SupportTicketUpdateView.as_view(), name='support-ticket-update'),
    # Escalation URLs
    path('support-tickets/<uuid:pk>/escalate', escalate_ticket, name='support-ticket-escalate'),
    path('support-tickets/<uuid:pk>/deescalate', deescalate_ticket, name='support-ticket-deescalate'),
    # Escalation URLs
    path('support-tickets/<uuid:pk>/archive', archive_ticket, name='support-ticket-archive'),
    path('support-tickets/<uuid:pk>/unarchive', unarchive_ticket, name='support-ticket-unarchive'),
    # TicketPespone URLs
    path('ticket/<uuid:pk>/response/list/', ticket_response_list, name='ticket-response-list'),
    path('ticket/<uuid:pk>/response/create/', ticket_response_create, name='ticket-response-create'),
    path('ticket/response/<uuid:pk>/update/', ticket_response_update, name='ticket-response-update'),
    path('ticket/response/<uuid:pk>/delete/', ticket_response_delete, name='ticket-response-delete'),
    path('ticket/attachement/<uuid:pk>/delete/', ticket_attachment_delete, name='ticket-attachement-delete'),

]