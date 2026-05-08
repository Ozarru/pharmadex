# finances/management/commands/sync_permissions.py
import sys
from django.core.management.base import BaseCommand
from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = "Syncs model permissions: adds missing, deletes obsolete, includes default Django perms."

    def handle(self, *args, **kwargs):
        self.stdout.write("📌 Scanning models for permissions...")

        declared_permissions = {}

        # --- Collect all declared permissions in models ---
        for model in apps.get_models():
            opts = model._meta
            ct = ContentType.objects.get_for_model(model)

            # 1️⃣ Default Django permissions
            default_perms = [
                (f'add_{opts.model_name}', f'Can add {opts.verbose_name}'),
                (f'change_{opts.model_name}', f'Can change {opts.verbose_name}'),
                (f'delete_{opts.model_name}', f'Can delete {opts.verbose_name}'),
                (f'view_{opts.model_name}', f'Can view {opts.verbose_name}'),
                # (f'import_{opts.model_name}', f'Can import {opts.verbose_name}'),
                (f'export_{opts.model_name}', f'Can export {opts.verbose_name}'),
                (f'manage_{opts.model_name}', f'Can manage {opts.verbose_name_plural}'),
                # (f'toggle_{opts.model_name}', f'Can toggle {opts.verbose_name}'),
            ]

            # 2️⃣ Static Meta.permissions
            static_perms = getattr(opts, 'permissions', [])

            # 3️⃣ Dynamic permissions via get_permissions
            dynamic_perms = []
            if hasattr(model, 'get_permissions') and callable(getattr(model, 'get_permissions')):
                dynamic_perms = model.get_permissions()

            # Merge all permissions for this content type
            declared_permissions.setdefault(ct, set()).update(default_perms + list(static_perms) + list(dynamic_perms))

        # --- Collect all existing permissions in DB ---
        existing_permissions = Permission.objects.all()
        delete_count = 0

        # --- Delete permissions that are obsolete ---
        for perm in existing_permissions:
            ct = perm.content_type
            if ct not in declared_permissions or (perm.codename, perm.name) not in declared_permissions[ct]:
                self.stdout.write(f"🗑 Deleting obsolete permission: {perm.codename} ({perm.name})")
                perm.delete()
                delete_count += 1

        # --- Create missing permissions ---
        create_count = 0
        for ct, perms in declared_permissions.items():
            for codename, name in perms:
                if not Permission.objects.filter(content_type=ct, codename=codename).exists():
                    Permission.objects.create(
                        content_type=ct,
                        codename=codename,
                        name=name
                    )
                    self.stdout.write(f"✅ Created permission: {codename} ({name})")
                    create_count += 1

        self.stdout.write(self.style.SUCCESS(f"✔ Permissions sync complete!"))
        self.stdout.write(self.style.SUCCESS(f"✔ Created: {create_count}, Deleted: {delete_count}"))
        self.stdout.write(self.style.SUCCESS("🎉 Permission sync complete!"))
