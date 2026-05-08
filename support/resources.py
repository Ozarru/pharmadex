from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from base.resources import BaseResource
from organizations.models import Organization
from .models import (
    SupportTicket,
    TicketResponse,
    TicketAttachment
)

#  ------------------------------------
# User model import
#  ------------------------------------
from django.contrib.auth import get_user_model
User = get_user_model()

# -----------------------------
# Support Ticket Resource
# -----------------------------
class SupportTicketResource(BaseResource):
    author = fields.Field(
        column_name='author',
        attribute='author',
        widget=ForeignKeyWidget(User, 'username')
    )
    organization = fields.Field(
        column_name='organization',
        attribute='organization',
        widget=ForeignKeyWidget(Organization, 'name')
    )
    assigned_to = fields.Field(
        column_name='assigned_to',
        attribute='assigned_to',
        widget=ForeignKeyWidget(User, 'username')
    )

    class Meta:
        model = SupportTicket
        fields = (
            'id', 'author', 'organization', 'ticket_type', 'subject', 'description',
            'status', 'priority', 'assigned_to', 'is_escalated', 'is_archived',
            'created_at', 'updated_at'
        )
        import_id_fields = ('id',)


# -----------------------------
# Ticket Response Resource
# -----------------------------
class TicketResponseResource(resources.ModelResource):
    author = fields.Field(
        column_name='author',
        attribute='author',
        widget=ForeignKeyWidget(User, 'username')
    )
    support_ticket = fields.Field(
        column_name='support_ticket',
        attribute='support_ticket',
        widget=ForeignKeyWidget(SupportTicket, 'id')
    )

    class Meta:
        model = TicketResponse
        fields = (
            'id', 'written_by', 'author', 'support_ticket',
            'message', 'is_by_author', 'is_by_organization_admin', 'is_by_platform_admin',
            'created_at', 'updated_at'
        )
        import_id_fields = ('id',)


# -----------------------------
# Ticket Attachment Resource
# -----------------------------
class TicketAttachmentResource(resources.ModelResource):
    author = fields.Field(
        column_name='author',
        attribute='author',
        widget=ForeignKeyWidget(User, 'username')
    )
    response = fields.Field(
        column_name='response',
        attribute='response',
        widget=ForeignKeyWidget(TicketResponse, 'id')
    )
    uploaded_by = fields.Field(
        column_name='uploaded_by',
        attribute='uploaded_by',
        widget=ForeignKeyWidget(User, 'username')
    )

    class Meta:
        model = TicketAttachment
        fields = (
            'id', 'author', 'file', 'response', 'uploaded_by', 'uploaded_at', 'created_at', 'updated_at'
        )
        import_id_fields = ('id',)
