from django.core.management.base import BaseCommand
from simple_history.utils import update_change_reason
# from accounts.models import  UserInvitation

class Command(BaseCommand):
    help = "Clean up historical records of a model"

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to clean up historical records...")

        # Clean up historical records for UserInvitation
        # self._clean_up_history(UserInvitation)

        self.stdout.write("Cleanup completed!")

    def _clean_up_history(self, model):
        """Remove historical records for deleted instances of a given model."""
        # Get all deleted records' historical entries
        historical_records = model.history.filter(history_user__isnull=True)

        # Iterate through all historical records and delete them
        deleted_count = historical_records.count()
        historical_records.delete()

        self.stdout.write(f"Deleted {deleted_count} historical records for {model.__name__}.")
