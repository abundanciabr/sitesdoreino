"""Testes da célula pagamentos: conexão local sem a espera do IPv6.

No Windows, "localhost" resolve primeiro para ::1. O Postgres e o Redis de
teste (Docker) só escutam em 127.0.0.1, então cada conexão nova esperava
cerca de 2 s pela recusa do ::1 antes de tentar o IPv4. A suíte tem muitos
testes com threads (conexão nova por thread) e um relay que abre um cliente
Redis a cada chamada: a soma deixava a suíte de 90 s com mais de 10 minutos,
e ela parecia travada. As configurações já foram lidas quando este arquivo
carrega (o pytest-django sobe o Django antes dos conftest), por isso a troca
é feita direto nelas, antes da primeira conexão.
"""

from __future__ import annotations

from django.conf import settings


def _sem_localhost(url: str) -> str:
    return url.replace("@localhost:", "@127.0.0.1:").replace("//localhost:", "//127.0.0.1:")


for _banco in settings.DATABASES.values():
    if _banco.get("HOST") == "localhost":
        _banco["HOST"] = "127.0.0.1"

for _nome in ("REDIS_STREAMS_URL", "SITE_ERRORS_REDIS_URL"):
    _valor = getattr(settings, _nome, "")
    if _valor:
        setattr(settings, _nome, _sem_localhost(_valor))
