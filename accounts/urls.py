from django.urls import path
from .views import *
from django.contrib.auth import views as auth_views

app_name = 'accounts'

urlpatterns = [
    # Auth and Registration URLs-----------------------------------------------------------
    path('signup/', signupView, name='signup'),
    path('login/', loginView, name='login'),
    path('logout/', logoutUser, name='logout'),

    
    # OTP URLs----------------------------------------------------------------------------
    path('otp/verify/', VerifyOtpView.as_view(), name='otp-verify'),
    path('otp/resend/', ResendOtpView.as_view(), name='otp-resend'),
    
    
    # PASSWORD CHANGE/RESET URLs----------------------------------------------------------------------------
    # Password change
    path('password-change/', change_password_view, name='password-change'),
    # Password reset: form to request email
    path(
        'password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset/request.html',
            email_template_name='accounts/emails/password_reset.txt',  # plain text fallback
            html_email_template_name='accounts/emails/password_reset.html',  # HTML version
            subject_template_name='accounts/password_reset/subject.txt',
            success_url=reverse_lazy('accounts:password-reset-done')
        ),
        name='password-reset'
    ),

    # Password reset done page
    path(
        'password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset/done.html'
        ),
        name='password-reset-done'
    ),

    # Password reset confirm (link in email)
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset/confirm.html',
            success_url='/accounts/password_reset/complete/'
        ),
        name='password-reset-confirm'
    ),

    # Password reset complete page
    path(
        'password_reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset/complete.html'
        ),
        name='password-reset-complete'
    ),
    
    # Organization Context URLs----------------------------------------------------------------------------
    path('switch-organization/<uuid:pk>/', switch_organization, name='organization-switch'),
    path('switch-pharmacy/<uuid:pk>/', switch_pharmacy, name='pharmacy-switch'),
    path('switch-role/<uuid:role_id>/', switch_role, name='switch-role'),
    path('toggle-pharmacy-scope/', toggle_tenancy, name='pharmacy-scope-toggle'),
    
    # User analytics URLs-------------------------------------------------------------------------
    path('user-analytics/', user_analytics, name='user-analytics'),
    # Permission ----------------------------
    path('user-permissions/list/', PermissionListView.as_view(), name='user-permission-list'),
    path('user-permissions/<uuid:pk>/update/', PermissionUpdateView.as_view(), name='user-permission-update'),
    
    # Role ----------------------------
    path('user-roles/list/', RoleListView.as_view(), name='user-role-list'),
    path('user-roles/<uuid:pk>/detail/', RoleDetailView.as_view(), name='user-role-detail'),
    path('user-roles/<uuid:pk>/update/', RoleUpdateView.as_view(), name='user-role-update'),
    
    # UserRole ----------------------------
    # path('user-role-assignments/list/', UserRoleListView.as_view(), name='user-role-assignment-list'),
    # path('user-role-assignments/create/', UserRoleCreateView.as_view(), name='user-role-assignment-create'),
    # path('user-role-assignments/<uuid:pk>/update/', UserRoleUpdateView.as_view(), name='user-role-assignment-update'),

    # User and Profile URLs-------------------------------------------------------------------------
    path('users/list/', CustomUserListView.as_view(), name='user-list'),
    # path('users/create/', CustomUserCreateView.as_view(), name='user-create'),
    path('users/detail/<uuid:pk>/', CustomUserDetailView.as_view(), name='user-detail'),
    path('users/<uuid:pk>/update/', CustomUserUpdateView.as_view(), name='user-update'),
    path('users/<uuid:pk>/preview/', user_preview, name='user-preview'),
    path('users/profiles/<uuid:pk>/update/', ProfileUpdateView.as_view(), name='user-profile-update'),
    path("account/archive/", ArchiveAccountView.as_view(), name="archive-account"),

    # User invitations URLs --------------------------------------------------------------
    path('users/user-invitations/list/', UserInvitationListView.as_view(), name='user-invitation-list'),
    path('users/user-invitations/create/', UserInvitationCreateView.as_view(), name='user-invitation-create'),

]
