from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('pricing/', pricing, name='pricing'),
    path('contact/', contact, name='contact'),
    path('about/', about, name='about'),
    
path('api/set-country/', set_country, name='set-country'),

# Posts (Unified Blog/News/Feed system)
path("posts/", post_list, name="post-list"),
path("posts/create/", post_create, name="post-create"),

path("posts/<slug:slug>/", post_detail, name="post-detail"),
path("posts/<int:pk>/edit/", post_update, name="post-edit"),
path("posts/<int:pk>/delete/", post_delete, name="post-delete"),

# interactions
path("posts/<int:pk>/like/", toggle_like, name="post-like"),
path("posts/<int:pk>/comment/", add_comment, name="post-comment"),
path("comments/<int:pk>/delete/", delete_comment, name="comment-delete"),

# legal views
path('help-center/', help_center, name='help_center'),
path('faq/', faq, name='faq'),
path('feedback/', feedback, name='feedback'),
path('testimonials/', testimonials, name='testimonials'),
path('terms_and_conditions/', terms_and_conditions, name='terms_and_conditions'),
path('privacy_policy/', privacy_policy, name='privacy_policy'),
path('security_policy/', security_policy, name='security_policy'),
path('cookies_policy/', cookies_policy, name='cookies_policy'),
path('newsletter/subscribe/', newsletter_subscribe, name='newsletter_subscribe'),

path('error-404-page/', not_found, name='not-found'),
]