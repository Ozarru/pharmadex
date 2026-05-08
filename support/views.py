from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, View
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from accounts.utils import user_has_permission
from base.views import BaseListView, BaseModelView
from django.contrib.auth.mixins import LoginRequiredMixin

from support.forms import TicketResponseForm
from .models import TicketAttachment, TicketResponse, SupportTicket
from django.contrib import messages


def tickets_dashboard():
    print('Tickets dashboard')


# SupportTicket-------------------------------------------------------------------------
class SupportTicketListView(BaseListView):
    model = SupportTicket
    template_name = 'support/ticket/index.html'
    partial_parent_directory = 'support'
    partial_nested_directory = 'ticket'
    context_object_name = 'tickets'
    active_page = 'support_page'
    title = _("Support Ticket Page")
    subtitle = _("Manage your user tickets here")
    header_paragraph = _(
        """
        Manage and oversee user tickets directly on the platform. Whether adding new user tickets, updating their profiles, or assigning roles and permissions, 
        the platform provides an intuitive interface to handle all user ticket-related tasks. Admins can easily view, update, and remove user tickets, 
        ensuring they have access to the right resources. This central hub allows for efficient user ticket management,
        promoting a streamlined experience for all involved.
        """
    )
    object_crud_link = "support:support-ticket-create"
    object_crud_via_htmx = True

    def get_search_fields(self):
        return ['subject', 'author__first_name', 'author__last_name', 'organization__name']

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_organization = self.request.user.profile.current_organization

        open_tickets = SupportTicket.objects.filter(
            organization=current_organization, status='open', is_archived=False).count()
        ongoing_tickets = SupportTicket.objects.filter(
            organization=current_organization, status='ongoing', is_archived=False).count()
        closed_tickets = SupportTicket.objects.filter(
            organization=current_organization, status='closed', is_archived=False).count()
        escalated_tickets = SupportTicket.objects.filter(
            organization=current_organization, is_escalated=True, is_archived=False).count()

        data_groups = [
            (_("Open Tickets"), open_tickets, "fa-folder-open", "blue"),
            (_("Ongoing Tickets"), ongoing_tickets, "fa-hourglass-half", "orange"),
            (_("Closed Tickets"), closed_tickets, "fa-lock", "gray"),
            (_("Escalated"), escalated_tickets, "fa-code", "red"),
        ]

        context['data_groups'] = data_groups
        context['partial_parent_directory'] = 'support'
        context['partial_nested_directory'] = 'ticket'
        return context


class SupportTicketDetailView(LoginRequiredMixin, DetailView):
    model = SupportTicket
    template_name = 'support/ticket/detail.html'

    def get_template_names(self):
        if self.request.headers.get('HX-Request') == 'true':
            return ['support/ticket/detail_htmx.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ticket = self.get_object()

        # Get all responses related to this ticket
        responses = ticket.responses.select_related(
            'author').prefetch_related('attachments')

        context['responses'] = responses

        if self.request.user.has_perm('tickets.change_supportticket'):
            context['can_crud_object'] = True
            context['object_crud_link'] = "support:support-ticket-update"
            context['object_crud_via_htmx'] = True
            context['object_pk'] = self.kwargs['pk']

        context['active_page'] = 'support_page'
        context['ticket'] = ticket
        context['title'] = _('Support Ticket Details')
        context['subtitle'] = _('View user ticket details')

        return context


class SupportTicketCreateView(BaseModelView, CreateView):
    model = SupportTicket
    fields = ['ticket_type', 'subject', 'description', 'proof_file']
    success_url = reverse_lazy('support:support-ticket-list')
    title = _("Add Support Ticket")
    subtitle = _("Fill the form to add a new user ticket")

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.organization = self.request.user.profile.current_organization
        return super().form_valid(form)


class SupportTicketUpdateView(BaseModelView, UpdateView):
    model = SupportTicket
    fields = ['ticket_type', 'subject', 'description', 'proof_file']
    success_url = reverse_lazy('support:support-ticket-list')
    title = _("Edit Support Ticket")
    subtitle = _("Edit the support ticket info")


@login_required
def escalate_ticket(request, pk):
    ticket = get_object_or_404(
        SupportTicket,
        id=pk,
        organization=request.user.profile.current_organization
    )

    if ticket.is_escalated:
        messages.info(request, _("This ticket has already been escalated."))
    else:
        ticket.status = 'escalated'
        ticket.is_escalated = True
        ticket.save()

        messages.success(
            request,
            _("Ticket escalated and sent to platform support.")
        )

    return redirect('support:support-ticket-detail', pk=ticket.id)


@login_required
def deescalate_ticket(request, pk):
    ticket = get_object_or_404(
        SupportTicket,
        id=pk,
        organization=request.user.profile.current_organization
    )

    if not ticket.is_escalated:
        messages.info(request, _("This ticket has not been escalated."))
    else:
        ticket.status = 'open'  # or whatever your default is
        ticket.is_escalated = False
        ticket.save(update_fields=['status', 'is_escalated'])

        messages.success(request, _("Ticket de-escalated successfully."))

    return redirect('support:support-ticket-detail', pk=ticket.id)


@login_required
def archive_ticket(request, pk):
    ticket = get_object_or_404(
        SupportTicket,
        id=pk,
        organization=request.user.profile.current_organization
    )

    if ticket.is_archived:
        messages.info(request, _("This ticket is already archived."))
    else:
        ticket.is_archived = True
        ticket.save(update_fields=['is_archived'])

        messages.success(request, _("Ticket archived successfully."))

    # Redirect back to the referring page, fallback to ticket detail
    return redirect(request.META.get('HTTP_REFERER', f'/support/ticket/{ticket.id}/'))


@login_required
def unarchive_ticket(request, pk):
    ticket = get_object_or_404(
        SupportTicket,
        id=pk,
        organization=request.user.profile.current_organization
    )

    if not ticket.is_archived:
        messages.info(request, _("This ticket is not archived."))
    else:
        ticket.is_archived = False
        ticket.save(update_fields=['is_archived'])

        messages.success(request, _("Ticket unarchived successfully."))

    # Redirect back to the referring page, fallback to ticket detail
    return redirect(request.META.get('HTTP_REFERER', f'/support/ticket/{ticket.id}/'))


# TicketResponse-------------------------------------------------------------------------
@login_required
def ticket_response_list(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk)
    responses = TicketResponse.objects.filter(support_ticket=ticket).order_by("created_at")
    
    template = "support/response/_list.html"
    
    return render(request, template, {
        "ticket": ticket,
        "responses": responses,
    })


@login_required
def ticket_response_create(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk)
    user = request.user

    # Determine responder type
    user_type = user.get_current_user_type()
    if user_type == 'platform_admin':
        responder = 'platform_admin'
    elif user_type == 'organization_admin':
        responder = 'organization_admin'
    else:
        responder = 'author'

    message = request.POST.get("message")
    if not message:
        return HttpResponseBadRequest("Message is required")

    new_response = TicketResponse.objects.create(
        organization=user.profile.current_organization,
        author=user,
        written_by=responder,
        support_ticket=ticket,
        message=message,
    )

    # Handle multiple attachments
    for f in request.FILES.getlist("attachments"):
        TicketAttachment.objects.create(
            organization=user.profile.current_organization,
            author=user,
            uploaded_by=user,
            response=new_response,
            file=f
        )

    # Check if this is the first response
    is_first = ticket.responses.count() == 1

    if is_first:
        return HttpResponse(
            "",
            status=204,
            headers={"HX-Trigger": "obj_changed"}
        )
    else:
        html = render_to_string(
            "support/response/_item.html",
            {"response": new_response, "user": user},
            request=request,
        )
        return HttpResponse(html)


@login_required
def ticket_response_update(request, pk):
    response = get_object_or_404(TicketResponse, pk=pk)
    user = request.user

    if request.method == "GET":
        form = TicketResponseForm(instance=response)
        return render(request, "generic/htmx_form.html", {
            "form": form,
            "form_title": "Edit Response",
            "form_subtitle": "Update the message below"
        })

    elif request.method == "POST":
        form = TicketResponseForm(request.POST, instance=response)
        if form.is_valid():
            form.save()

            # Handle additional attachments
            for f in request.FILES.getlist("attachments"):
                TicketAttachment.objects.create(
                    organization=user.profile.current_organization,
                    author=user,
                    uploaded_by=user,
                    response=response,
                    file=f
                )

            return HttpResponse(
                "",
                status=204,
                headers={"HX-Trigger": "obj_changed"}
            )
        else:
            return render(request, "generic/htmx_form.html", {
                "form": form,
                "form_title": "Edit Response",
                "form_subtitle": "Update the message below"
            })


@login_required
def ticket_response_delete(request, pk):
    """
    HTMX-only delete endpoint for TicketResponse objects.
    Fires `obj_changed` trigger instead of generic `db_changed`.
    """
    if request.method != "POST":
        return HttpResponseForbidden("POST requests only")

    if request.headers.get("HX-Request") != "true":
        return HttpResponseForbidden("HTMX requests only")

    response = get_object_or_404(TicketResponse, pk=pk)

    # Permission check
    if not user_has_permission("delete", request.user, response.__class__):
        return HttpResponse(
            "",
            status=403,
            headers={
                "HX-Trigger": "obj_changed",
                "htmx_response_status": "403",
                "message_type": "error",
            },
        )

    response.delete()

    # Trigger HTMX event
    return HttpResponse(
        "",
        status=204,
        headers={
            "HX-Trigger": "obj_changed",
            "htmx_response_status": "204",
            "message_type": "success",
        },
    )


@login_required
def ticket_attachment_delete(request, pk):
    """
    HTMX-only delete endpoint for TicketAttachment objects.
    Fires `obj_changed` trigger to refresh the response list.
    """
    if request.method != "POST":
        return HttpResponseForbidden("POST requests only")

    if request.headers.get("HX-Request") != "true":
        return HttpResponseForbidden("HTMX requests only")

    attachment = get_object_or_404(TicketAttachment, pk=pk)

    # Permission check
    if not user_has_permission("delete", request.user, attachment.__class__):
        return HttpResponse(
            "",
            status=403,
            headers={
                "HX-Trigger": "obj_changed",
                "htmx_response_status": "403",
                "message_type": "error",
            },
        )

    attachment.delete()

    return HttpResponse(
        "",
        status=204,
        headers={
            "HX-Trigger": "obj_changed",
            "htmx_response_status": "204",
            "message_type": "success",
        },
    )

