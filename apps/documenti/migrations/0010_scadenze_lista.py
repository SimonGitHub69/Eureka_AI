from django.db import migrations, models


def copy_scadenze_columns(apps, schema_editor):
    TestaDocumento = apps.get_model("documenti", "TestaDocumento")
    for obj in TestaDocumento.objects.iterator():
        dates = []
        for i in range(1, 9):
            value = getattr(obj, f"scadenza_{i}", None)
            if value:
                dates.append(value.isoformat())
        if dates:
            obj.scadenze = dates
            obj.save(update_fields=["scadenze"])


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0009_tipodocumento_scadenze"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="scadenze",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(copy_scadenze_columns, migrations.RunPython.noop),
        migrations.RemoveField(model_name="testadocumento", name="scadenza_1"),
        migrations.RemoveField(model_name="testadocumento", name="scadenza_2"),
        migrations.RemoveField(model_name="testadocumento", name="scadenza_3"),
        migrations.RemoveField(model_name="testadocumento", name="scadenza_4"),
        migrations.RemoveField(model_name="testadocumento", name="scadenza_5"),
        migrations.RemoveField(model_name="testadocumento", name="scadenza_6"),
        migrations.RemoveField(model_name="testadocumento", name="scadenza_7"),
        migrations.RemoveField(model_name="testadocumento", name="scadenza_8"),
    ]
