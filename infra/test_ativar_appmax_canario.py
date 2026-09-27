"""A chave do canário liga um site só, mostra antes de gravar e volta atrás inteira."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

CAMINHO = Path(__file__).with_name("ativar-appmax-canario.py")
SPEC = importlib.util.spec_from_file_location("canario_appmax", CAMINHO)
assert SPEC and SPEC.loader
canario = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(canario)

SITE = "3f2b6a1e-7c4d-4e8f-9a0b-1c2d3e4f5a6b"
OUTRO = "9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a"
EXTERNAL_ID = "11111111-2222-4333-8444-555555555555"
SEGREDO = "segredo-de-producao-de-teste"
PAGAMENTOS = (
    'APPMAX_INSTALACOES={"2001":{"alias":"Meshcraft","sites":["' + SITE + '"]}}\n'
    "APPMAX_AUTH_URL=https://auth.appmax.com.br/oauth2/token\n"
    "APPMAX_API_URL=https://api.appmax.com.br\n"
    "APPMAX_MERCHANT_CLIENT_ID=cliente-de-teste\n"
    f"APPMAX_MERCHANT_CLIENT_SECRET={SEGREDO}\n"
    "APPMAX_CARD_ENABLED_SITES=\n"
    "APPMAX_PIX_ENABLED_SITES=\n"
)
CHECKOUT = (
    "DEBUG=0\n"
    "APPMAX_PIX_ENABLED_SITES=\n"
    "APPMAX_CARD_ENABLED_SITES=\n"
    f"APPMAX_EXTERNAL_ID={EXTERNAL_ID}\n"
)


class Compose:
    """Docker Compose de mentira: responde como a VPS saudável e anota as chamadas."""

    def __init__(self) -> None:
        self.ativos = list(canario.SERVICOS)
        self.external_id = EXTERNAL_ID
        self.prova = 0
        self.recargas: list[bool] = []
        self.respostas_de_recarga: list[bool] = []

    def __call__(self, _raiz: Path, _ambiente: dict[str, str], *args: str):
        if args[0] == "ps":
            return subprocess.CompletedProcess(args, 0, "\n".join(self.ativos), "")
        if args[:5] == ("exec", "-T", "pagamentos", "python", "manage.py"):
            if not self.external_id:
                return subprocess.CompletedProcess(args, 1, "", "sem instalação")
            return subprocess.CompletedProcess(args, 0, self.external_id + "\n", "")
        if args[0] == "exec":
            return subprocess.CompletedProcess(args, self.prova, "", "")
        raise AssertionError(f"chamada inesperada ao Compose: {args}")

    def recarregar(self, _raiz: Path, _ambiente: dict[str, str]) -> bool:
        resposta = self.respostas_de_recarga.pop(0) if self.respostas_de_recarga else True
        self.recargas.append(resposta)
        return resposta


def preparar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pagamentos: str = PAGAMENTOS,
    checkout: str = CHECKOUT,
) -> tuple[Path, Compose]:
    (tmp_path / "env").mkdir()
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "env/pagamentos.env").write_text(pagamentos, encoding="utf-8")
    (tmp_path / "env/checkout.env").write_text(checkout, encoding="utf-8")
    (tmp_path / "env/admin.env").write_text(
        "ALUNOS_API_TOKEN=alunos-de-teste\nTOKEN_CATALOGO=catalogo-de-teste\n",
        encoding="utf-8",
    )
    compose = Compose()
    monkeypatch.setattr(canario, "compose", compose)
    monkeypatch.setattr(canario, "recarregar", compose.recarregar)
    return tmp_path, compose


def fotografar(raiz: Path) -> dict[str, bytes]:
    return {
        nome: (raiz / f"env/{nome}.env").read_bytes()
        for nome in ("pagamentos", "checkout")
    }


def copias(raiz: Path) -> list[Path]:
    return list((raiz / "env").glob("*.bak-*"))


def test_previa_mostra_a_troca_sem_gravar_nem_recarregar(tmp_path, monkeypatch, capsys):
    raiz, compose = preparar(tmp_path, monkeypatch)
    antes = fotografar(raiz)
    canario.executar(raiz, SITE, ligar=True, gravar=False)
    saida = capsys.readouterr().out
    assert fotografar(raiz) == antes
    assert not copias(raiz)
    assert compose.recargas == []
    assert f"pagamentos.env APPMAX_CARD_ENABLED_SITES: (vazia) -> {SITE}" in saida
    assert f"checkout.env APPMAX_CARD_ENABLED_SITES: (vazia) -> {SITE}" in saida
    assert "--executar" in saida
    assert SEGREDO not in saida


def test_ligar_e_desligar_devolvem_os_env_identicos(tmp_path, monkeypatch, capsys):
    raiz, compose = preparar(tmp_path, monkeypatch)
    antes = fotografar(raiz)
    canario.executar(raiz, SITE, ligar=True, gravar=True)
    for nome in ("pagamentos", "checkout"):
        texto = (raiz / f"env/{nome}.env").read_text(encoding="utf-8")
        assert f"APPMAX_CARD_ENABLED_SITES={SITE}\n" in texto
        assert "APPMAX_PIX_ENABLED_SITES=\n" in texto
    assert "APPMAX_CANARIO_LIGADO" in capsys.readouterr().out
    canario.executar(raiz, SITE, ligar=False, gravar=True)
    assert fotografar(raiz) == antes
    assert compose.recargas == [True, True]
    saida = capsys.readouterr().out
    assert "APPMAX_CANARIO_DESLIGADO" in saida
    assert SEGREDO not in saida


def _trocar(texto: str, de: str, para: str) -> str:
    assert de in texto
    return texto.replace(de, para)


RECUSAS = [
    (
        "api-no-sandbox",
        _trocar(PAGAMENTOS, "https://api.appmax.com.br", "https://api.sandboxappmax.com.br"),
        CHECKOUT,
        "produção",
    ),
    (
        "autenticacao-no-sandbox",
        _trocar(
            PAGAMENTOS,
            "https://auth.appmax.com.br/oauth2/token",
            "https://auth.sandboxappmax.com.br/oauth2/token",
        ),
        CHECKOUT,
        "produção",
    ),
    (
        "credencial-merchant-vazia",
        _trocar(PAGAMENTOS, f"CLIENT_SECRET={SEGREDO}", "CLIENT_SECRET="),
        CHECKOUT,
        "MERCHANT",
    ),
    (
        "site-fora-da-instalacao",
        _trocar(PAGAMENTOS, '"sites":["' + SITE, '"sites":["' + OUTRO),
        CHECKOUT,
        "não está vinculado",
    ),
    (
        "outro-site-ligado-em-pagamentos",
        _trocar(PAGAMENTOS, "CARD_ENABLED_SITES=\n", f"CARD_ENABLED_SITES={OUTRO}\n"),
        CHECKOUT,
        "outro site",
    ),
    (
        "outro-site-ligado-no-checkout",
        PAGAMENTOS,
        _trocar(CHECKOUT, "CARD_ENABLED_SITES=\n", f"CARD_ENABLED_SITES={OUTRO}\n"),
        "outro site",
    ),
    (
        "pix-appmax-ligado",
        PAGAMENTOS,
        _trocar(CHECKOUT, "PIX_ENABLED_SITES=\n", f"PIX_ENABLED_SITES={SITE}\n"),
        "Pix",
    ),
    (
        "identificador-externo-divergente",
        PAGAMENTOS,
        _trocar(CHECKOUT, EXTERNAL_ID, "22222222-3333-4444-8555-666666666666"),
        "identificador externo",
    ),
    (
        "identificador-externo-vazio",
        PAGAMENTOS,
        _trocar(CHECKOUT, f"EXTERNAL_ID={EXTERNAL_ID}", "EXTERNAL_ID="),
        "identificador externo",
    ),
    (
        "trava-ausente",
        _trocar(PAGAMENTOS, "APPMAX_CARD_ENABLED_SITES=\n", ""),
        CHECKOUT,
        "trava ausente",
    ),
    (
        "chave-repetida",
        PAGAMENTOS + "APPMAX_CARD_ENABLED_SITES=\n",
        CHECKOUT,
        "repetida",
    ),
]


@pytest.mark.parametrize(
    ("pagamentos", "checkout", "motivo"),
    [caso[1:] for caso in RECUSAS],
    ids=[caso[0] for caso in RECUSAS],
)
def test_recusa_antes_de_gravar(tmp_path, monkeypatch, pagamentos, checkout, motivo):
    raiz, compose = preparar(tmp_path, monkeypatch, pagamentos, checkout)
    antes = fotografar(raiz)
    for gravar in (False, True):
        with pytest.raises(canario.ParouPorSeguranca, match=motivo):
            canario.executar(raiz, SITE, ligar=True, gravar=gravar)
    assert fotografar(raiz) == antes
    assert not copias(raiz)
    assert compose.recargas == []


def test_recusa_servico_parado(tmp_path, monkeypatch):
    raiz, compose = preparar(tmp_path, monkeypatch)
    compose.ativos.remove("pagamentos-appmax")
    with pytest.raises(canario.ParouPorSeguranca, match="ativos"):
        canario.executar(raiz, SITE, ligar=True, gravar=True)
    assert not copias(raiz)
    assert compose.recargas == []


def test_recusa_instalacao_ausente_no_banco(tmp_path, monkeypatch):
    raiz, compose = preparar(tmp_path, monkeypatch)
    compose.external_id = ""
    with pytest.raises(canario.ParouPorSeguranca, match="banco"):
        canario.executar(raiz, SITE, ligar=True, gravar=True)
    assert not copias(raiz)
    assert compose.recargas == []


@pytest.mark.parametrize("falha", ["recarga", "prova"])
def test_falha_ao_ligar_restaura_os_dois_env(tmp_path, monkeypatch, falha):
    raiz, compose = preparar(tmp_path, monkeypatch)
    antes = fotografar(raiz)
    if falha == "recarga":
        compose.respostas_de_recarga = [False, True]
    else:
        compose.prova = 1
    with pytest.raises(canario.ParouPorSeguranca, match="restaurado"):
        canario.executar(raiz, SITE, ligar=True, gravar=True)
    assert fotografar(raiz) == antes
    assert compose.recargas[-1] is True


def test_falha_ao_desligar_mantem_a_trava_fechada(tmp_path, monkeypatch):
    ligado = _trocar(CHECKOUT, "CARD_ENABLED_SITES=\n", f"CARD_ENABLED_SITES={SITE}\n")
    raiz, compose = preparar(
        tmp_path,
        monkeypatch,
        _trocar(PAGAMENTOS, "CARD_ENABLED_SITES=\n", f"CARD_ENABLED_SITES={SITE}\n"),
        ligado,
    )
    compose.respostas_de_recarga = [False]
    with pytest.raises(canario.ParouPorSeguranca, match="continua fechada"):
        canario.executar(raiz, SITE, ligar=False, gravar=True)
    for nome in ("pagamentos", "checkout"):
        texto = (raiz / f"env/{nome}.env").read_text(encoding="utf-8")
        assert "APPMAX_CARD_ENABLED_SITES=\n" in texto
    assert compose.recargas == [False]


def test_desligar_funciona_mesmo_com_a_appmax_fora_da_producao(tmp_path, monkeypatch):
    pagamentos = _trocar(
        _trocar(PAGAMENTOS, "https://api.appmax.com.br", "https://api.sandboxappmax.com.br"),
        "CARD_ENABLED_SITES=\n",
        f"CARD_ENABLED_SITES={OUTRO},{SITE}\n",
    )
    raiz, compose = preparar(tmp_path, monkeypatch, pagamentos, CHECKOUT)
    compose.ativos = []
    compose.external_id = ""
    canario.executar(raiz, SITE, ligar=False, gravar=True)
    texto = (raiz / "env/pagamentos.env").read_text(encoding="utf-8")
    assert f"APPMAX_CARD_ENABLED_SITES={OUTRO}\n" in texto
    assert compose.recargas == [True]


@pytest.mark.parametrize("ligar", [True, False])
def test_estado_ja_alcancado_nao_grava_nem_recarrega(tmp_path, monkeypatch, capsys, ligar):
    valor = SITE if ligar else ""
    raiz, compose = preparar(
        tmp_path,
        monkeypatch,
        _trocar(PAGAMENTOS, "CARD_ENABLED_SITES=\n", f"CARD_ENABLED_SITES={valor}\n"),
        _trocar(CHECKOUT, "CARD_ENABLED_SITES=\n", f"CARD_ENABLED_SITES={valor}\n"),
    )
    antes = fotografar(raiz)
    canario.executar(raiz, SITE, ligar=ligar, gravar=True)
    assert fotografar(raiz) == antes
    assert not copias(raiz)
    assert compose.recargas == []
    assert "Nada a fazer" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argumentos",
    [
        [],
        ["--executar"],
        ["--site"],
        ["--site", "meshcraft.top"],
        ["--site", SITE, "--ligar"],
        ["--site", SITE, "--executar", "--executar"],
        ["--site", SITE, "--site", OUTRO],
    ],
)
def test_argumento_invalido_para_antes_de_ler_a_vps(argumentos, monkeypatch, capsys):
    monkeypatch.setattr(
        canario, "executar", lambda *_a, **_k: pytest.fail("não podia executar")
    )
    assert canario.main(argumentos) == 1
    assert "PAROU POR SEGURANÇA" in capsys.readouterr().out


def test_main_encaminha_site_sentido_e_gravacao(monkeypatch):
    chamadas = []
    monkeypatch.setenv("PLATAFORMA_DIR", "/opt/plataforma-de-teste")
    monkeypatch.setattr(
        canario, "executar", lambda raiz, site, **opcoes: chamadas.append((raiz, site, opcoes))
    )
    assert canario.main(["--site", SITE.upper()]) == 0
    assert canario.main(["--desligar", "--site", SITE, "--executar"]) == 0
    assert chamadas == [
        (Path("/opt/plataforma-de-teste"), SITE, {"ligar": True, "gravar": False}),
        (Path("/opt/plataforma-de-teste"), SITE, {"ligar": False, "gravar": True}),
    ]
