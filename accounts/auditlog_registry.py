from auditlog.registry import auditlog
from .models import *

auditlog.register(Role)
auditlog.register(Permission)
auditlog.register(CustomUser)
auditlog.register(Profile)
# auditlog.register(UserRole)
# auditlog.register(UserInvitation)