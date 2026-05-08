from django.contrib import admin
from .models import SupportTicket, TicketResponse, TicketAttachment


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        "subject",
        "ticket_type",
        "status",
        "priority",
        "author",
        "assigned_to",
        "is_escalated",
        "is_archived",
        "created_at",
    ]
    search_fields = [
        "subject",
        "description",
        "author__username",
        "author__first_name",
        "author__last_name",
        "assigned_to__username",
        "assigned_to__first_name",
        "assigned_to__last_name",
    ]
    list_filter = [
        "status",
        "priority",
        "ticket_type",
        "is_escalated",
        "is_archived",
        "created_at",
    ]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(TicketResponse)
class TicketResponseAdmin(admin.ModelAdmin):
    list_display = [
        "support_ticket",
        "author",
        "written_by",
        "message_snippet",
        "created_at",
    ]
    search_fields = [
        "message",
        "author__username",
        "support_ticket__subject",
    ]
    list_filter = [
        "written_by",
        "created_at",
    ]

    def message_snippet(self, obj):
        return obj.message[:50] + ("..." if len(obj.message) > 50 else "")
    message_snippet.short_description = "Message"


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        "response",
        "uploaded_by",
        "file",
        "uploaded_at",
    ]
    search_fields = [
        "file",
        "uploaded_by__username",
        "response__message",
    ]
    list_filter = [
        "uploaded_at",
    ]
