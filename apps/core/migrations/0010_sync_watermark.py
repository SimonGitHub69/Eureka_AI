from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_configurazioneprogramma_documenti_menu"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncWatermark",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "source_table",
                    models.CharField(db_index=True, max_length=120, unique=True),
                ),
                ("last_modifica", models.DateTimeField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Watermark sync 4D",
                "verbose_name_plural": "Watermark sync 4D",
                "ordering": ["source_table"],
            },
        ),
    ]
