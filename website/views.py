from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from datetime import datetime, timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.shortcuts import get_object_or_404, render
from website.models import ContentComment, ContentPost, NewsletterSubscriber, Testimonial

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

@require_POST
@csrf_exempt
def set_country(request):
    try:
        data = json.loads(request.body)
        country = data.get('country', 'SN')
        currency = data.get('currency', 'XOF')
        
        request.session['country_code'] = country
        request.session['currency_code'] = currency
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


def home(request):
    # user = request.user
    context = {
        "active_page": "home_page",
        "title": _("Home Page"),
    }

    return render(request, 'website/index.html', context)


def pricing(request):
    # user = request.user
    context = {
        "active_page": "pricing_page",
        "title": _("pricing Page"),
    }

    return render(request, 'website/pricing.html', context)


def contact(request):
    # user = request.user
    context = {
        "active_page": "contact_page",
        "title": _("contact Page"),
    }

    return render(request, 'website/contact.html', context)


def about(request):
    # user = request.user
    context = {
        "active_page": "about_page",
        "title": _("about Page"),
    }

    return render(request, 'website/about.html', context)


def get_started(request):
    # user = request.user
    context = {
        "active_page": "get_started_page",
        "title": _("Get Started Page"),
    }

    return render(request, 'website/get_started.html', context)


@login_required(login_url='accounts:login')
def not_found(request, exception):
    context = {
        "active_page": "not_found_page",
        "title": _("Page not found"),
        "subtitle": _("Error 404"),
        "header_paragraph": _(
            "The page you are trying to access does not exist, may have been moved, "
            "or you may not have the correct access rights."
        ),
    }
    return render(request, "website/error_400.html", context)


# ===========================================================
# COMMUNITY CONTENT VIEWS
# ===========================================================
@login_required
@user_passes_test(lambda u: u.is_staff)
def post_create(request):
    if request.method == "POST":
        post = ContentPost.objects.create(
            title=request.POST["title"],
            content=request.POST["content"],
            excerpt=request.POST.get("excerpt"),
            author=request.user,
            status=ContentPost.Status.PUBLISHED,
        )

        return JsonResponse({"success": True, "slug": post.slug})

    return render(request, "posts/form.html")


@login_required
@user_passes_test(lambda u: u.is_staff)
def post_update(request, pk):
    post = get_object_or_404(ContentPost, pk=pk)

    if request.method == "POST":
        post.title = request.POST["title"]
        post.content = request.POST["content"]
        post.excerpt = request.POST.get("excerpt")
        post.save()

        return JsonResponse({"success": True})

    return render(request, "posts/form.html", {"post": post})


@login_required
@user_passes_test(lambda u: u.is_staff)
def post_delete(request, pk):
    post = get_object_or_404(ContentPost, pk=pk)

    if request.method == "POST":
        post.delete()
        return JsonResponse({"success": True})

    return render(request, "posts/delete.html", {"post": post})


def post_list(request):
    query = request.GET.get("search", "")
    author_id = request.GET.get("author")

    posts = ContentPost.objects.filter(
        status=ContentPost.Status.PUBLISHED,
        published_at__lte=timezone.now()
    ).select_related("author")

    if query:
        posts = posts.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(excerpt__icontains=query)
        )

    if author_id:
        posts = posts.filter(author_id=author_id)

    posts = posts.order_by("-published_at")

    paginator = Paginator(posts, 10)
    page = request.GET.get("page", 1)
    posts = paginator.get_page(page)

    return render(request, "posts/list.html", {
        "posts": posts
    })


def post_detail(request, slug):
    post = get_object_or_404(
        ContentPost,
        slug=slug,
        status=ContentPost.Status.PUBLISHED
    )

    post.views_count += 1
    post.save(update_fields=["views_count"])

    comments = post.comments.filter(
        is_approved=True
    ).select_related("author").order_by("-created_at")

    paginator = Paginator(comments, 10)
    page = request.GET.get("page", 1)
    comments = paginator.get_page(page)

    user_has_liked = False
    if request.user.is_authenticated:
        user_has_liked = post.likes.filter(id=request.user.id).exists()

    return render(request, "posts/detail.html", {
        "post": post,
        "comments": comments,
        "user_has_liked": user_has_liked,
    })


@login_required
def toggle_like(request, pk):
    post = get_object_or_404(ContentPost, pk=pk)

    if post.likes.filter(id=request.user.id).exists():
        post.likes.remove(request.user)
        liked = False
    else:
        post.likes.add(request.user)
        liked = True

    return JsonResponse({
        "liked": liked,
        "total_likes": post.likes.count()
    })


@login_required
def add_comment(request, pk):
    post = get_object_or_404(ContentPost, pk=pk)

    content = request.POST.get("content")
    if not content:
        return JsonResponse({"error": "Empty comment"}, status=400)

    comment = ContentComment.objects.create(
        post=post,
        author=request.user,
        content=content,
        is_approved=request.user.is_staff
    )

    return JsonResponse({
        "success": True,
        "comment": {
            "id": comment.id,
            "content": comment.content,
            "author": comment.author.get_full_name() or comment.author.username,
        }
    })


@login_required
def delete_comment(request, pk):
    comment = get_object_or_404(ContentComment, pk=pk)

    if request.user != comment.author and not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    comment.delete()
    return JsonResponse({"success": True})


# ===========================================================
# CLIENT INSTRUCTION VIEWS 
# ===========================================================
def help_center(request):
    """Help Center - Main support hub"""
    context = {
        'title': _('Help Center'),
        'description': _('Find answers, guides, and support for Pharmadex'),
        'categories': [
            {
                'icon': 'fa-book',
                'title': _('Getting Started'),
                'description': _('Setup guides and onboarding resources'),
                'articles': 12
            },
            {
                'icon': 'fa-boxes',
                'title': _('Inventory Management'),
                'description': _('Stock tracking, batches, and audits'),
                'articles': 8
            },
            {
                'icon': 'fa-cash-register',
                'title': _('Sales & POS'),
                'description': _('Point of sale, receipts, and payments'),
                'articles': 10
            },
            {
                'icon': 'fa-file-prescription',
                'title': _('Prescriptions'),
                'description': _('Managing and dispensing prescriptions'),
                'articles': 6
            },
            {
                'icon': 'fa-chart-line',
                'title': _('Reports & Analytics'),
                'description': _('Financial and operational reports'),
                'articles': 7
            },
            {
                'icon': 'fa-users',
                'title': _('User Management'),
                'description': _('Roles, permissions, and staff'),
                'articles': 5
            },
        ]
    }
    return render(request, 'website/client/help_center.html', context)


def faq(request):
    """Frequently Asked Questions"""
    faqs = [
        {
            'category': _('General'),
            'questions': [
                {
                    'q': _('What is Pharmadex?'),
                    'a': _('Pharmadex is a comprehensive pharmacy management ERP platform that helps pharmacies manage inventory, sales, prescriptions, procurement, accounting, and compliance from one cloud-based solution.')
                },
                {
                    'q': _('Is Pharmadex suitable for small pharmacies?'),
                    'a': _('Yes! Pharmadex scales from single-location pharmacies to multi-branch chains. Our pricing and features adapt to your needs.')
                },
                {
                    'q': _('Can I access Pharmadex on mobile devices?'),
                    'a': _('Absolutely. Pharmadex is fully responsive and works on tablets, smartphones, and desktop computers.')
                },
            ]
        },
        {
            'category': _('Pricing & Billing'),
            'questions': [
                {
                    'q': _('How much does Pharmadex cost?'),
                    'a': _('We offer flexible pricing tiers based on pharmacy size and features needed. Contact our sales team for a customized quote.')
                },
                {
                    'q': _('Is there a free trial?'),
                    'a': _('Yes, we offer a 14-day free trial with full access to all features. No credit card required.')
                },
            ]
        },
        {
            'category': _('Security & Compliance'),
            'questions': [
                {
                    'q': _('Is my data secure?'),
                    'a': _('Yes. We use bank-grade encryption, regular backups, and comply with HIPAA and GDPR standards.')
                },
                {
                    'q': _('Where is my data stored?'),
                    'a': _('Data is stored in secure cloud servers with redundancy across multiple geographic locations.')
                },
            ]
        },
        {
            'category': _('Technical'),
            'questions': [
                {
                    'q': _('Do I need to install anything?'),
                    'a': _('No. Pharmadex is entirely cloud-based. Just open your browser and log in.')
                },
                {
                    'q': _('Can I import my existing data?'),
                    'a': _('Yes, we provide CSV import tools and can assist with data migration from most pharmacy software.')
                },
            ]
        },
    ]

    context = {
        'title': _('Frequently Asked Questions'),
        'faqs': faqs,
    }
    return render(request, 'website/client/faq.html', context)


def feedback(request):
    """User feedback form"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        feedback_type = request.POST.get('feedback_type')
        message = request.POST.get('message')

        # Send email to support
        try:
            send_mail(
                subject=f'Pharmadex Feedback: {feedback_type}',
                message=f'From: {name} ({email})\n\nType: {feedback_type}\n\n{message}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.SUPPORT_EMAIL],
                fail_silently=False,
            )
            messages.success(request, _(
                'Thank you for your feedback! We appreciate your input.'))
            return redirect('website:feedback')
        except Exception:
            messages.error(request, _(
                'Something went wrong. Please try again later.'))

    context = {
        'title': _('Feedback'),
        'feedback_types': [
            ('suggestion', _('Feature Suggestion')),
            ('bug', _('Bug Report')),
            ('experience', _('User Experience')),
            ('complaint', _('Complaint')),
            ('other', _('Other')),
        ]
    }
    return render(request, 'website/client/feedback.html', context)


def testimonials(request):
    """Customer testimonials"""
    testimonials_list = Testimonial.objects.filter(
        is_published=True).order_by('-created_at')

    context = {
        'title': _('What Our Customers Say'),
        'description': _('Trusted by pharmacies across Africa and beyond'),
        'testimonials': testimonials_list,
        'stats': {
            'pharmacies': '100+',
            'countries': '5+',
            'satisfaction': '98%',
        }
    }
    return render(request, 'website/client/testimonials.html', context)


# ===========================================================
# LEGAL VIEWS 
# ===========================================================
def terms_and_conditions(request):
    """Terms and Conditions"""
    context = {
        'title': _('Terms & Conditions'),
        'description': _('The rules governing your use of our platform.'),
        'last_updated': datetime(2026, 5, 18),
    }
    return render(request, 'website/legal/terms_and_conditions.html', context)


def privacy_policy(request):
    """Privacy Policy"""
    context = {
        'title': _('Privacy Policy'),
        'last_updated': datetime(2026, 5, 18),
    }
    return render(request, 'website/legal/privacy_policy.html', context)


def security_policy(request):
    """Security Policy"""
    context = {
        'title': _('Security Policy'),
        'last_updated': datetime(2026, 5, 18),
    }
    return render(request, 'website/legal/security_policy.html', context)


def cookies_policy(request):
    """Cookie Policy"""
    context = {
        'title': _('Cookie Policy'),
        'last_updated': datetime(2026, 5, 18),
    }
    return render(request, 'website/legal/cookies_policy.html', context)


# ===========================================================
# NEWSLETTER VIEWS 
# ===========================================================
@require_http_methods(["POST"])
def newsletter_subscribe(request):
    """Newsletter subscription"""
    email = request.POST.get('email', '').strip()

    if not email:
        messages.error(request, _('Please provide a valid email address.'))
        return redirect('website:index')

    try:
        subscriber, created = NewsletterSubscriber.objects.get_or_create(
            email=email,
            defaults={'is_active': True}
        )
        if created:
            messages.success(request, _(
                'Thank you for subscribing to our newsletter!'))
        else:
            if subscriber.is_active:
                messages.info(request, _(
                    'You are already subscribed to our newsletter.'))
            else:
                subscriber.is_active = True
                subscriber.save()
                messages.success(request, _(
                    'Welcome back! Your subscription has been reactivated.'))
    except Exception:
        messages.error(request, _('Something went wrong. Please try again.'))

    return redirect('website:index')
