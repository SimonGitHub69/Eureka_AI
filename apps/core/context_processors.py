import json

from apps.core.models import ComandoVocale


def voice_commands(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"eureka_voice_commands_json": "[]"}

    commands = (
        ComandoVocale.objects.filter(attivo=True, is_active=True)
        .order_by("ordine", "frase")
        .values("frase", "azione", "destinazione", "query", "match_mode", "ordine")
    )
    return {"eureka_voice_commands_json": json.dumps(list(commands), ensure_ascii=False)}
