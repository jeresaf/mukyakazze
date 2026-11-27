from django.core.management.base import BaseCommand
from accounts.services import provision_roles
class Command(BaseCommand):
    help = 'Create and reconcile baseline administrative roles after migration.'
    def handle(self, *args, **options):
        provision_roles()
        self.stdout.write(self.style.SUCCESS('Baseline roles provisioned.'))
