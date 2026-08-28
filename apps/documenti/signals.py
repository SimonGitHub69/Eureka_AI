from django.db import transaction
from django.db.models.signals import post_save
from django.db.utils import OperationalError, ProgrammingError
from django.dispatch import receiver

from apps.documenti.layout import seed_colonne_riga_default
from apps.documenti.models import TipoDocumento


@receiver(post_save, sender=TipoDocumento)
def seed_colonne_riga_on_create(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        with transaction.atomic():
            seed_colonne_riga_default(instance)
    except (ProgrammingError, OperationalError):
        pass

