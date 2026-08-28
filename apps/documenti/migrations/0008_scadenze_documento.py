from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0007_categoria_ddt"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="scadenza_1",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="testadocumento",
            name="scadenza_2",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="testadocumento",
            name="scadenza_3",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="testadocumento",
            name="scadenza_4",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="testadocumento",
            name="scadenza_5",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="testadocumento",
            name="scadenza_6",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="testadocumento",
            name="scadenza_7",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="testadocumento",
            name="scadenza_8",
            field=models.DateField(blank=True, null=True),
        ),
    ]
