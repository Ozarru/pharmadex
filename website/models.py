from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from base.models import BaseModel

User = get_user_model()


class ContentPost(BaseModel):
    """
    Unified system for:
    - Blog articles (SEO content)
    - Product updates (newsfeed)
    - Announcements (critical info)
    """

    class PostType(models.TextChoices):
        BLOG = "blog", _("Blog")
        UPDATE = "update", _("Update")
        ANNOUNCEMENT = "announcement", _("Announcement")

    title = models.CharField(_("Title"), max_length=255)
    slug = models.SlugField(_("Slug"), max_length=255, unique=True)
    excerpt = models.TextField(_("Excerpt"), blank=True, null=True)
    content = models.TextField(_("Content"))

    post_type = models.CharField(
        _("Type"),
        max_length=20,
        choices=PostType.choices,
        default=PostType.BLOG
    )

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="content_posts",
        verbose_name=_("Author")
    )

    featured_image = models.ImageField(
        _("Featured Image"),
        upload_to="content/images/",
        blank=True,
        null=True
    )

    is_published = models.BooleanField(_("Published"), default=False)

    views_count = models.PositiveIntegerField(_("Views"), default=0)

    likes = models.ManyToManyField(
        User,
        related_name="liked_content_posts",
        blank=True,
        verbose_name=_("Likes")
    )

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    published_at = models.DateTimeField(_("Published At"), blank=True, null=True)

    class Meta:
        verbose_name = _("Content Post")
        verbose_name_plural = _("Content Posts")
        ordering = ["-published_at", "-created_at"]

    def save(self, *args, **kwargs):
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ContentComment(BaseModel):
    """
    Unified comments system for blog + updates
    """

    post = models.ForeignKey(
        ContentPost,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("Post")
    )

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="content_comments",
        verbose_name=_("Author")
    )

    content = models.TextField(_("Content"))

    is_approved = models.BooleanField(_("Approved"), default=False)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Comment")
        verbose_name_plural = _("Comments")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.post.title}"
    

class NewsletterSubscriber(BaseModel):
    email = models.EmailField(_('Email'), unique=True)
    is_active = models.BooleanField(_('Is Active'), default=True)
    subscribed_at = models.DateTimeField(_('Subscribed At'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Newsletter Subscriber')
        verbose_name_plural = _('Newsletter Subscribers')
    
    def __str__(self):
        return self.email


class Testimonial(BaseModel):
    name = models.CharField(_('Name'), max_length=100)
    role = models.CharField(_('Role'), max_length=100)
    organization = models.CharField(_('Organization/Pharmacy'), max_length=200)
    content = models.TextField(_('Testimonial Content'))
    avatar = models.ImageField(_('Avatar'), upload_to='testimonials/', blank=True, null=True)
    rating = models.PositiveSmallIntegerField(_('Rating'), default=5)
    is_published = models.BooleanField(_('Is Published'), default=False)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Testimonial')
        verbose_name_plural = _('Testimonials')
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.name} - {self.organization}'