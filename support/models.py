from django.db.models import Q, CheckConstraint
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from base.models import BaseModel, OrganizationModel
from django.contrib.auth import get_user_model

from pharmadex.tenant import TenantManager
User = get_user_model()

# --- Constants ---
TICKET_STATUSES = [
	('open', _("Open")),
	('ongoing', _("Ongoing")),
	('resolved', _("Resolved")),
	('closed', _("Closed")),
	('escalated', _("Escalated")),
	('cancelled', _("Cancelled")),
]

TICKET_PRIORITIES = [
	('low', _("Low")),
	('medium', _("Medium")),
	('high', _("High")),
	('urgent', _("Urgent")),
]

TICKET_TYPES = [
    ('technical', _("Technical Issue")),
    ('billing', _("Billing Issue")),
    ('account', _("Account Issue")),
    ('inventory', _("Inventory Issue")),
    ('sales', _("Sales/POS Issue")),
    ('prescription', _("Prescription Issue")),
    ('report', _("Report Issue")),
    ('feature_request', _("Feature Request")),
    ('other', _("Other")),
]
    
class SupportTicket(OrganizationModel):
	
	objects = TenantManager()
 
	author = models.ForeignKey(
		User, on_delete=models.CASCADE, related_name="support_tickets",
		verbose_name=_("Author")
	)
	ticket_type = models.CharField(
		max_length=50,
		choices=TICKET_TYPES,
		default='technical',
		verbose_name=_("Ticket Type")
	)
	subject = models.CharField(max_length=255, verbose_name=_("Subject"))
	description = models.TextField(verbose_name=_("Description"))

	status = models.CharField(
		max_length=50, choices=TICKET_STATUSES, default='open',
		verbose_name=_("Status")
	)
	priority = models.CharField(
		max_length=50, choices=TICKET_PRIORITIES, default='medium',
		verbose_name=_("Priority")
	)
	assigned_to = models.ForeignKey(
		User, null=True, blank=True, on_delete=models.SET_NULL,
		related_name='assigned_support_tickets',
		verbose_name=_("Assigned To")
	)
	is_escalated = models.BooleanField(default=False, verbose_name=_("Is Escalated"))
	is_archived = models.BooleanField(default=False, verbose_name=_("Is Archived"))

	proof_file = models.FileField(
		upload_to='support/support_tickets', blank=True, null=True,
		verbose_name=_("Proof File")
	)

	model_icon = 'fa-solid fa-headset'
 
	class Meta:
		ordering = ['-created_at', ]
		verbose_name = _("Support Ticket")
		verbose_name_plural = _("Support Tickets")
		permissions = [
            ("import_supportticket", "Can import user ticket"),
            ("export_supportticket", "Can export user ticket"),
            ("manage_supportticket", "Can manage all user tickets"),
		]

	def escalate(self):
		"""Escalate this user ticket to the platform"""
		if not self.is_escalated:
			self.is_escalated = True
			self.save()
		return None

	def __str__(self):
		return f"[{self.ticket_type}] {self.subject}"
	
	@property
	def is_resolved(self):
		return self.status in ['resolved', 'closed']


# --- Ticket Responses ---
class TicketResponse(BaseModel):
    
	objects = TenantManager()
    
	WRITTEN_BY_CHOICES = [
		('author', _("Author")),
		('organization_admin', _("Organization Admin")),
		('platform_admin', _("Platform Admin")),
	]

	written_by = models.CharField(
		max_length=20,
		choices=WRITTEN_BY_CHOICES,
		verbose_name=_("Written By")
	)

	author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Author"))

	support_ticket = models.ForeignKey(
		SupportTicket, null=True, blank=True, on_delete=models.CASCADE,
		related_name='responses',
		verbose_name=_("Support Ticket")
	)

	message = models.TextField(verbose_name=_("Message"))
	is_by_author = models.BooleanField(default=False, verbose_name=_("Written By Author"))
	is_by_organization_admin = models.BooleanField(default=False, verbose_name=_("Written By Campus Admin"))
	is_by_platform_admin = models.BooleanField(default=False, verbose_name=_("Written By Platform Admin"))

	model_icon = 'fa-solid fa-comment'
	default_url = 'support:support-ticket-list'
	class Meta:
		ordering = ['created_at', ]
		constraints = [
		]
		verbose_name = _("Ticket Response")
		verbose_name_plural = _("Ticket Responses")
		permissions = [
			("export_ticketresponse", "Can export ticket response"),
			("manage_ticketresponse", "Can manage all ticket responses"),
		]

	def __str__(self):
		return f"Response by {self.author.username} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"

	def get_ticket(self):
		return self.support_ticket
	
	@property
	def is_by_author(self):
		return self.written_by == 'author'

	@property
	def is_by_organization_admin(self):
		return self.written_by == 'organization_admin'

	@property
	def is_by_platform_admin(self):
		return self.written_by == 'platform_admin'


# --- Ticket Attachments ---
class TicketAttachment(BaseModel):
	author = models.ForeignKey(
		User, on_delete=models.CASCADE, related_name="ticket_attachements",
		verbose_name=_("Author")
	)
	file = models.FileField(upload_to='ticket_attachments/', verbose_name=_("File"))
	response = models.ForeignKey(
		TicketResponse, on_delete=models.CASCADE, related_name='attachments',
		verbose_name=_("Response")
	)
	uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Uploaded By"))
	uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Uploaded At"))

	model_icon = 'fa-solid fa-file'
	default_url = 'support:ticket-attachement-list'
	class Meta:
		ordering = ['-created_at', ]
		verbose_name = _("Ticket Attachment")
		verbose_name_plural = _("Ticket Attachments")
		permissions = [
			("export_ticketattachement", "Can export ticket attachement"),
			("manage_ticketattachement", "Can manage all ticket attachements"),
		]

	def __str__(self):
		return f"Attachment by {self.uploaded_by.username} on {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"

