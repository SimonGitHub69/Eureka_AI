import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name="UUID",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creato il")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modificato il")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        verbose_name="Creato da",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
        verbose_name="Modificato da",
    )
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Eliminato il")
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_deleted",
        verbose_name="Eliminato da",
    )
    is_active = models.BooleanField(default=True, verbose_name="Attivo")
    note = models.TextField(blank=True, verbose_name="Note")

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=["is_active", "deleted_at", "deleted_by", "updated_at"])
