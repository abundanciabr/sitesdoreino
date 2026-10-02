from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
PAGAMENTOS_ENV_EXEMPLO = RAIZ / "infra" / "env" / "pagamentos.env.exemplo"


def _env_exemplo() -> dict[str, str]:
    valores = {}
    for linha in PAGAMENTOS_ENV_EXEMPLO.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip()
    return valores


def test_cartao_appmax_nasce_desligado():
    assert _env_exemplo()["APPMAX_CARD_ENABLED_SITES"] == ""
