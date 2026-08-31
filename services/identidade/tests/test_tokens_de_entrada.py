"""`apps/core/tokens_de_entrada.py` — a defesa de CSRF do login por senha,
isolada do HTTP (`test_login_por_senha.py` cobre o uso real, via view)."""

from django.core.signing import TimestampSigner

from apps.core import tokens_de_entrada as tokens


def test_token_emitido_confere():
    assert tokens.confere(tokens.emitir()) is True


def test_token_vazio_nao_confere():
    assert tokens.confere("") is False


def test_token_forjado_nao_confere():
    assert tokens.confere("qualquer-coisa-que-nao-foi-assinada-aqui") is False


def test_token_de_outro_assunto_nao_confere():
    outro = TimestampSigner().sign("outro-assunto")
    assert tokens.confere(outro) is False


def test_token_vencido_nao_confere(monkeypatch):
    import time

    token = tokens.emitir()
    # Avança o relógio além da validade sem esperar de verdade — mesma
    # técnica que qualquer teste de expiração baseado em tempo usa.
    agora_real = time.time
    monkeypatch.setattr(
        time, "time", lambda: agora_real() + tokens.VALIDADE_SEGUNDOS + 1
    )
    assert tokens.confere(token) is False
