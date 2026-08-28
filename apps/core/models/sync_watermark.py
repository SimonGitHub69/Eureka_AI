from django.db import models


class SyncWatermark(models.Model):
    """Ultima data/ora modifica 4D importata per tabella sorgente ODBC."""

    source_table = models.CharField(max_length=120, unique=True, db_index=True)
    last_modifica = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Watermark sync 4D"
        verbose_name_plural = "Watermark sync 4D"
        ordering = ["source_table"]

    def __str__(self) -> str:
        return f"{self.source_table} @ {self.last_modifica:%Y-%m-%d %H:%M:%S}"
