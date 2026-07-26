from django.db import migrations


DEFAULT_COMMANDS = [
    {
        "frase": "apri clienti",
        "azione": "navigate",
        "destinazione": "clienti",
        "query": "",
        "attivo": True,
        "ordine": 10,
        "match_mode": "contains",
    },
    {
        "frase": "apri dashboard",
        "azione": "navigate",
        "destinazione": "dashboard",
        "query": "",
        "attivo": True,
        "ordine": 20,
        "match_mode": "contains",
    },
    {
        "frase": "apri categorie",
        "azione": "navigate",
        "destinazione": "categorie",
        "query": "",
        "attivo": True,
        "ordine": 30,
        "match_mode": "contains",
    },
    {
        "frase": "cerca cliente",
        "azione": "search",
        "destinazione": "clienti",
        "query": "",
        "attivo": True,
        "ordine": 40,
        "match_mode": "starts_with",
    },
    {
        "frase": "cerca articolo",
        "azione": "search",
        "destinazione": "articoli",
        "query": "",
        "attivo": True,
        "ordine": 50,
        "match_mode": "starts_with",
    },
]


def seed_default_commands(apps, schema_editor):
    ComandoVocale = apps.get_model("core", "ComandoVocale")
    if ComandoVocale.objects.exists():
        return

    for item in DEFAULT_COMMANDS:
        ComandoVocale.objects.create(**item)


def unseed_default_commands(apps, schema_editor):
    ComandoVocale = apps.get_model("core", "ComandoVocale")
    phrases = [item["frase"] for item in DEFAULT_COMMANDS]
    ComandoVocale.objects.filter(frase__in=phrases).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_comando_vocale"),
    ]

    operations = [
        migrations.RunPython(seed_default_commands, unseed_default_commands),
    ]
