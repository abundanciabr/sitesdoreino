"""O ensaio de rollback desliga o cartão só da Meshcraft sandbox, prova e religa sempre."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

CAMINHO = Path(__file__).with_name("drill-appmax-rollback-sandbox.py")
SPEC = importlib.util.spec_from_file_location("drill_appmax", CAMINHO)
assert SPEC and SPEC.loader
drill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drill)

RAIZ = Path(__file__).resolve().parents[1]
WORKFLOW = RAIZ / ".github/workflows/appmax-drill-rollback.yml"
SITE = "cc06b8c3-043b-4c06-92c5-5ea624e00586"
OUTRO = "9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a"
SEGREDO = "segredo-do-sandbox-de-teste"
PAGAMENTOS = (
    'APPMAX_INSTALACOES={"1888":{"alias":"Meshcraft","sites":["' + SITE + '"]}}\n'
    "APPMAX_AUTH_URL=https://auth.sandboxappmax.com.br/oauth2/token\n"
    "APPMAX_API_URL=https://api.sandboxappmax.com.br\n"
    "APPMAX_MERCHANT_CLIENT_ID=cliente-de-teste\n"
    f"APPMAX_MERCHANT_CLIENT_SECRET={SEGREDO}\n"
    f"APPMAX_CARD_ENABLED_SITES={SITE}\n"
    f"APPMAX_PIX_ENABLED_SITES={SITE}\n"
)
CHECKOUT = (
    "DEBUG=0\n"
    f"APPMAX_PIX_ENABLED_SITES={SITE}\n"
    f"APPMAX_CARD_ENABLED_SITES={SITE}\n"
    "APPMAX_EXTERNAL_ID=11111111-2222-4333-8444-555555555555\n"
)


def pagina(*, cartao: bool, pix_na_appmax: bool, pix: bool = True, explicacao: bool = True) -> str:
    """A página de dados do checkout como o Django a entrega (json_script e Alpine)."""
    return (
        "<main>"
        f'<script id="appmax-pix-enabled" type="application/json">{json.dumps(pix_na_appmax)}</script>'
        f'<script id="appmax-card-enabled" type="application/json">{json.dumps(cartao)}</script>'
        + (
            '<button type="button" :aria-pressed="method === \'pix\'" '
            "@click=\"method = 'pix'\">Pix</button>"
            if pix
            else ""
        )
        + '<button type="button" x-show="appmaxCard">Cartão</button>'
        + (
            '<button type="button" x-show="!appmaxCard" disabled aria-disabled="true">'
            "Cartão indisponível</button>"
            '<p x-show="!appmaxCard">O cartão ainda não pode ser concluído neste site.</p>'
            if explicacao
            else ""
        )
        + "</main>"
    )


class VPS:
    """Compose e página pública de mentira: o checkout serve o que os serviços leram."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.ativos = list(drill.canario.SERVICOS)
        self.recargas: list[bool] = []
        self.respostas_de_recarga: list[bool] = []
        self.recargas_sem_efeito: list[bool] = []
        try:
            self.lido = self._ler()
        except drill.canario.ParouPorSeguranca:
            self.lido = {"pagamentos": {}, "checkout": {}}
        self.pagina_congelada: str | None = None
        self.sem_pix_quando_desligado = False
        self.sem_explicacao = False
        self.http = "200"
        self.sondas = 0

    def _ler(self) -> dict[str, dict[str, str]]:
        return {
            nome: drill.canario.ler_env(self.raiz / f"env/{nome}.env", escrever=False)
            for nome in ("pagamentos", "checkout")
        }

    def compose(self, _raiz: Path, _ambiente: dict[str, str], *args: str):
        if args[0] == "ps":
            return subprocess.CompletedProcess(args, 0, "\n".join(self.ativos), "")
        if args[:2] == ("exec", "-T") and args[3:5] == ("python", "-c"):
            esperado = re.search(r"== '([^']*)'", args[5]).group(1)
            codigo = 0 if self.lido[args[2]].get(drill.TRAVA, "") == esperado else 1
            return subprocess.CompletedProcess(args, codigo, "", "")
        raise AssertionError(f"chamada inesperada ao Compose: {args}")

    def recarregar(self, _raiz: Path, _ambiente: dict[str, str]) -> bool:
        resposta = self.respostas_de_recarga.pop(0) if self.respostas_de_recarga else True
        self.recargas.append(resposta)
        sem_efeito = self.recargas_sem_efeito.pop(0) if self.recargas_sem_efeito else False
        if resposta and not sem_efeito:
            self.lido = self._ler()
        return resposta

    def buscar_pagina(self) -> tuple[str, str]:
        self.sondas += 1
        if self.pagina_congelada is not None:
            return self.pagina_congelada, self.http
        checkout = self.lido["checkout"]
        cartao = SITE in drill.canario.lista(checkout.get(drill.TRAVA, ""))
        return (
            pagina(
                cartao=cartao,
                pix_na_appmax=SITE in drill.canario.lista(checkout.get("APPMAX_PIX_ENABLED_SITES", "")),
                pix=not (self.sem_pix_quando_desligado and not cartao),
                explicacao=not self.sem_explicacao,
            ),
            self.http,
        )


def preparar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pagamentos: str = PAGAMENTOS,
    checkout: str = CHECKOUT,
) -> tuple[Path, VPS]:
    (tmp_path / "env").mkdir()
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "env/pagamentos.env").write_text(pagamentos, encoding="utf-8")
    (tmp_path / "env/checkout.env").write_text(checkout, encoding="utf-8")
    (tmp_path / "env/admin.env").write_text(
        "ALUNOS_API_TOKEN=alunos-de-teste\nTOKEN_CATALOGO=catalogo-de-teste\n",
        encoding="utf-8",
    )
    vps = VPS(tmp_path)
    monkeypatch.setattr(drill.canario, "compose", vps.compose)
    monkeypatch.setattr(drill.canario, "recarregar", vps.recarregar)
    monkeypatch.setattr(drill, "buscar_pagina", vps.buscar_pagina)
    monkeypatch.setattr(drill, "ESPERA_SEGUNDOS", 0)
    return tmp_path, vps


def fotografar(raiz: Path) -> dict[str, bytes]:
    return {nome: (raiz / f"env/{nome}.env").read_bytes() for nome in ("pagamentos", "checkout")}


def copias(raiz: Path) -> list[Path]:
    return list((raiz / "env").glob("*.bak-*"))


def _trocar(texto: str, de: str, para: str) -> str:
    assert de in texto
    return texto.replace(de, para)


LIGADO = {
    "http": 200,
    "pix_oferecido": True,
    "pix_na_appmax": True,
    "cartao_ligado": True,
    "explicacao_ao_comprador": True,
}


def test_ensaio_inteiro_prova_o_bloqueio_religa_e_devolve_os_env_identicos(tmp_path, monkeypatch):
    # guarda: infra/drill-appmax-rollback-sandbox.py:254
    # guarda: infra/drill-appmax-rollback-sandbox.py:270
    raiz, vps = preparar(tmp_path, monkeypatch)
    antes = fotografar(raiz)
    evidencia = drill.executar(raiz)
    assert evidencia["resultado"] == "PASS", evidencia
    assert evidencia["sondas"] == {
        "antes": LIGADO,
        "desligado": {**LIGADO, "cartao_ligado": False},
        "religado": LIGADO,
    }
    assert evidencia["alterou_a_vps"] is True
    assert evidencia["env_devolvido_identico"] is True
    assert fotografar(raiz) == antes
    assert not copias(raiz)
    assert vps.recargas == [True, True]
    assert SEGREDO not in json.dumps(evidencia)
    assert SITE not in json.dumps(evidencia)


RECUSAS = [
    (
        "api-na-producao",
        _trocar(PAGAMENTOS, "https://api.sandboxappmax.com.br", "https://api.appmax.com.br"),
        CHECKOUT,
        "sandbox",
    ),
    (
        "autenticacao-na-producao",
        _trocar(
            PAGAMENTOS,
            "https://auth.sandboxappmax.com.br/oauth2/token",
            "https://auth.appmax.com.br/oauth2/token",
        ),
        CHECKOUT,
        "sandbox",
    ),
    (
        "instalacao-de-outro-site",
        _trocar(PAGAMENTOS, '"sites":["' + SITE, '"sites":["' + OUTRO),
        CHECKOUT,
        "Meshcraft",
    ),
    (
        "instalacao-com-dois-sites",
        _trocar(PAGAMENTOS, '"sites":["' + SITE + '"', '"sites":["' + SITE + '","' + OUTRO + '"'),
        CHECKOUT,
        "Meshcraft",
    ),
    (
        "outra-instalacao",
        _trocar(PAGAMENTOS, '"1888"', '"2001"'),
        CHECKOUT,
        "Meshcraft",
    ),
    (
        "outro-site-na-trava-de-pagamentos",
        _trocar(PAGAMENTOS, f"CARD_ENABLED_SITES={SITE}", f"CARD_ENABLED_SITES={SITE},{OUTRO}"),
        CHECKOUT,
        "só a Meshcraft",
    ),
    (
        "outro-site-na-trava-do-checkout",
        PAGAMENTOS,
        _trocar(CHECKOUT, f"CARD_ENABLED_SITES={SITE}", f"CARD_ENABLED_SITES={OUTRO}"),
        "só a Meshcraft",
    ),
    (
        "cartao-ja-desligado",
        PAGAMENTOS,
        _trocar(CHECKOUT, f"CARD_ENABLED_SITES={SITE}", "CARD_ENABLED_SITES="),
        "só a Meshcraft",
    ),
    (
        "trava-ausente",
        _trocar(PAGAMENTOS, f"APPMAX_CARD_ENABLED_SITES={SITE}\n", ""),
        CHECKOUT,
        "só a Meshcraft",
    ),
    (
        "chave-repetida",
        PAGAMENTOS + f"APPMAX_CARD_ENABLED_SITES={SITE}\n",
        CHECKOUT,
        "repetida",
    ),
]


@pytest.mark.parametrize(
    ("pagamentos", "checkout", "motivo"),
    [caso[1:] for caso in RECUSAS],
    ids=[caso[0] for caso in RECUSAS],
)
def test_recusa_antes_de_gravar_fora_do_sandbox_da_meshcraft(
    tmp_path, monkeypatch, pagamentos, checkout, motivo
):
    raiz, vps = preparar(tmp_path, monkeypatch, pagamentos, checkout)
    antes = fotografar(raiz)
    with pytest.raises(drill.canario.ParouPorSeguranca, match=motivo):
        drill.executar(raiz)
    assert fotografar(raiz) == antes
    assert not copias(raiz)
    assert vps.recargas == []
    assert vps.sondas == 0


def test_recusa_servico_parado_antes_de_gravar(tmp_path, monkeypatch):
    # guarda: infra/drill-appmax-rollback-sandbox.py:218
    raiz, vps = preparar(tmp_path, monkeypatch)
    vps.ativos.remove("checkout")
    with pytest.raises(drill.canario.ParouPorSeguranca, match="ativos"):
        drill.executar(raiz)
    assert not copias(raiz)
    assert vps.recargas == []


def test_recusa_tokens_do_compose_ausentes(tmp_path, monkeypatch):
    raiz, vps = preparar(tmp_path, monkeypatch)
    (raiz / "env/admin.env").write_text("ALUNOS_API_TOKEN=\n", encoding="utf-8")
    with pytest.raises(drill.canario.ParouPorSeguranca, match="admin.env"):
        drill.executar(raiz)
    assert vps.recargas == []


@pytest.mark.parametrize(
    ("estrago", "motivo"),
    [
        ("cartao-desligado", "cartão ligado"),
        ("sem-pix", "Pix"),
        ("fora-do-ar", "cartão ligado"),
    ],
)
def test_recusa_quando_a_pagina_publica_nao_parte_do_cartao_ligado(
    tmp_path, monkeypatch, estrago, motivo
):
    raiz, vps = preparar(tmp_path, monkeypatch)
    if estrago == "cartao-desligado":
        vps.pagina_congelada = pagina(cartao=False, pix_na_appmax=True)
    elif estrago == "sem-pix":
        vps.pagina_congelada = pagina(cartao=True, pix_na_appmax=True, pix=False)
    else:
        vps.http = "502"
    antes = fotografar(raiz)
    with pytest.raises(drill.canario.ParouPorSeguranca, match=motivo):
        drill.executar(raiz)
    assert fotografar(raiz) == antes
    assert not copias(raiz)
    assert vps.recargas == []


@pytest.mark.parametrize(
    ("estrago", "motivo"),
    [
        ("cartao-continua-oferecido", "cartão continuou"),
        ("pix-sumiu", "Pix"),
        ("sem-explicacao", "explicação"),
        ("recarga-falhou", "desligar"),
    ],
)
def test_falha_no_meio_religa_e_devolve_os_env(tmp_path, monkeypatch, estrago, motivo):
    raiz, vps = preparar(tmp_path, monkeypatch)
    antes = fotografar(raiz)
    if estrago == "cartao-continua-oferecido":
        vps.pagina_congelada = pagina(cartao=True, pix_na_appmax=True)
    elif estrago == "pix-sumiu":
        vps.sem_pix_quando_desligado = True
    elif estrago == "sem-explicacao":
        vps.sem_explicacao = True
    else:
        vps.respostas_de_recarga = [False, True]
    evidencia = drill.executar(raiz)
    assert evidencia["resultado"] == "FAIL", evidencia
    assert motivo in evidencia["motivo"]
    assert evidencia["env_devolvido_identico"] is True
    assert fotografar(raiz) == antes
    assert not copias(raiz)
    assert vps.recargas[-1] is True


def test_religacao_que_falha_vira_error_e_guarda_a_copia(tmp_path, monkeypatch):
    raiz, vps = preparar(tmp_path, monkeypatch)
    antes = fotografar(raiz)
    vps.respostas_de_recarga = [True, False]
    evidencia = drill.executar(raiz)
    assert evidencia["resultado"] == "ERROR"
    assert "religar" in evidencia["motivo"]
    assert ".bak-" in evidencia["acao"]
    assert evidencia["env_devolvido_identico"] is True
    assert fotografar(raiz) == antes
    assert len(copias(raiz)) == 2


def test_servico_que_nao_le_a_trava_desligada_reprova_sem_sondar(tmp_path, monkeypatch):
    # guarda: infra/drill-appmax-rollback-sandbox.py:248
    raiz, vps = preparar(tmp_path, monkeypatch)
    antes = fotografar(raiz)
    vps.recargas_sem_efeito = [True, False]
    evidencia = drill.executar(raiz)
    assert evidencia["resultado"] == "FAIL"
    assert "não leu a trava" in evidencia["motivo"]
    assert "desligado" not in evidencia["sondas"]
    assert fotografar(raiz) == antes


def test_servico_que_nao_le_a_trava_religada_vira_error(tmp_path, monkeypatch):
    # guarda: infra/drill-appmax-rollback-sandbox.py:188
    raiz, vps = preparar(tmp_path, monkeypatch)
    vps.recargas_sem_efeito = [False, True]
    evidencia = drill.executar(raiz)
    assert evidencia["resultado"] == "ERROR"
    assert "religar" in evidencia["motivo"] and "não leu a trava" in evidencia["motivo"]
    assert len(copias(raiz)) == 2


def test_pagina_que_nao_volta_depois_de_religar_reprova(tmp_path, monkeypatch):
    raiz, _ = preparar(tmp_path, monkeypatch)
    antes = fotografar(raiz)
    leituras = iter(
        [pagina(cartao=True, pix_na_appmax=True)]
        + [pagina(cartao=False, pix_na_appmax=True)] * 20
    )
    monkeypatch.setattr(drill, "buscar_pagina", lambda: (next(leituras), "200"))
    evidencia = drill.executar(raiz)
    assert evidencia["resultado"] == "FAIL"
    assert "não voltou" in evidencia["motivo"]
    assert fotografar(raiz) == antes
    assert not copias(raiz)


def test_sonda_espera_o_cartao_mudar_antes_de_julgar(tmp_path, monkeypatch):
    leituras = iter(
        [
            (pagina(cartao=True, pix_na_appmax=False), "200"),
            (pagina(cartao=True, pix_na_appmax=False), "200"),
            (pagina(cartao=False, pix_na_appmax=False), "200"),
        ]
    )
    monkeypatch.setattr(drill, "buscar_pagina", lambda: next(leituras))
    monkeypatch.setattr(drill, "ESPERA_SEGUNDOS", 0)
    assert drill.sondar_ate(cartao_ligado=False)["cartao_ligado"] is False


def test_leitura_da_pagina_so_confia_na_declaracao_do_checkout():
    assert drill.ler_pagina(pagina(cartao=True, pix_na_appmax=False), "200") == {
        **LIGADO,
        "pix_na_appmax": False,
    }
    assert drill.ler_pagina("<p>manutenção</p>", "503") == {
        "http": 503,
        "pix_oferecido": False,
        "pix_na_appmax": None,
        "cartao_ligado": None,
        "explicacao_ao_comprador": False,
    }
    assert drill.ler_pagina("", "sem resposta")["http"] == 0


def test_o_checkout_real_entrega_o_que_a_sonda_le():
    """Se o checkout mudar a declaração ou a explicação, o ensaio precisa saber."""
    modelo = (RAIZ / "services/checkout/templates/checkout/dados.html").read_text(encoding="utf-8")
    assert 'json_script:"appmax-card-enabled"' in modelo
    assert 'json_script:"appmax-pix-enabled"' in modelo
    assert ">Pix</button>" in modelo
    assert ">Cartão indisponível</button>" in modelo
    assert drill.EXPLICACAO in modelo


# ------------------------------------------------------------- esteira


def _saida(evidencia: dict) -> str:
    return (
        "docker compose falou algo\n"
        + json.dumps(evidencia, ensure_ascii=False)
        + "\n"
        + "=" * 47
        + "\n✅ Successfully executed commands to all hosts.\n"
        + "=" * 47
    )


def _evidencia(tmp_path, monkeypatch) -> dict:
    raiz, _ = preparar(tmp_path, monkeypatch)
    return drill.executar(raiz)


@pytest.mark.parametrize(("resultado", "codigo"), [("PASS", 0), ("FAIL", 1), ("ERROR", 2)])
def test_conferir_publica_o_resumo_e_devolve_o_estado(
    tmp_path, monkeypatch, capsys, resultado, codigo
):
    evidencia = {**_evidencia(tmp_path, monkeypatch), "resultado": resultado}
    resumo = tmp_path / "resumo.md"
    monkeypatch.setenv("SAIDA", _saida(evidencia))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumo))
    assert drill.main(["conferir"]) == codigo
    texto = resumo.read_text(encoding="utf-8")
    assert f"Resultado: {resultado}" in texto
    assert "| desligado | 200 | sim | sim | não | sim |" in texto
    assert "\u2014" not in texto and "\u2013" not in texto
    assert resultado in capsys.readouterr().out


@pytest.mark.parametrize(
    "estrago",
    ["vazia", "texto", "chave-a-mais", "valor-fora-do-tipo", "resultado-inventado"],
)
def test_conferir_recusa_saida_que_nao_e_a_evidencia(tmp_path, monkeypatch, estrago):
    evidencia = _evidencia(tmp_path, monkeypatch)
    if estrago == "vazia":
        saida = ""
    elif estrago == "texto":
        saida = "APPMAX_MERCHANT_CLIENT_SECRET=" + SEGREDO
    elif estrago == "chave-a-mais":
        saida = _saida({**evidencia, "segredo": SEGREDO})
    elif estrago == "valor-fora-do-tipo":
        evidencia["sondas"]["antes"]["http"] = SEGREDO
        saida = _saida(evidencia)
    else:
        saida = _saida({**evidencia, "resultado": "OK"})
    resumo = tmp_path / "resumo.md"
    monkeypatch.setenv("SAIDA", saida)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumo))
    assert drill.main(["conferir"]) == 2
    assert not resumo.exists() or SEGREDO not in resumo.read_text(encoding="utf-8")


def test_preparar_leva_o_ensaio_e_a_chave_do_canario_para_a_vps(tmp_path, monkeypatch):
    saida = tmp_path / "github_output"
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(saida))
    assert drill.main(["preparar"]) == 0
    script = tmp_path / "drill-appmax-rollback-sandbox.sh"
    assert saida.read_text(encoding="utf-8") == f"script={script}\n"
    texto = script.read_text(encoding="utf-8")
    assert texto.startswith("#!/bin/sh\nset -eu\n")
    assert CAMINHO.read_text(encoding="utf-8") in texto
    assert (RAIZ / "infra/ativar-appmax-canario.py").read_text(encoding="utf-8") in texto
    assert texto.rstrip().endswith('python3 "$DIR/drill-appmax-rollback-sandbox.py" executar')
    assert "\r" not in texto


@pytest.mark.parametrize("argumentos", [[], ["executar", "--agora"], ["ligar"]])
def test_argumento_invalido_para_sem_tocar_nada(argumentos, monkeypatch, capsys):
    monkeypatch.setattr(drill, "executar", lambda *_a: pytest.fail("não podia executar"))
    assert drill.main(argumentos) == 2
    assert "preparar" in capsys.readouterr().out


def test_executar_pela_linha_de_comando_imprime_uma_linha_de_evidencia(
    tmp_path, monkeypatch, capsys
):
    raiz, _ = preparar(tmp_path, monkeypatch)
    monkeypatch.setenv("PLATAFORMA_DIR", str(raiz))
    assert drill.main(["executar"]) == 0
    linhas = capsys.readouterr().out.strip().splitlines()
    assert len(linhas) == 1
    assert json.loads(linhas[0])["resultado"] == "PASS"


def test_executar_recusado_informa_que_nada_mudou(tmp_path, monkeypatch, capsys):
    raiz, _ = preparar(
        tmp_path,
        monkeypatch,
        _trocar(PAGAMENTOS, "https://api.sandboxappmax.com.br", "https://api.appmax.com.br"),
    )
    monkeypatch.setenv("PLATAFORMA_DIR", str(raiz))
    assert drill.main(["executar"]) == 2
    evidencia = json.loads(capsys.readouterr().out)
    assert evidencia["resultado"] == "ERROR"
    assert evidencia["alterou_a_vps"] is False


def test_workflow_roda_so_da_main_no_ambiente_protegido_e_publica_a_evidencia():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert set(doc[True]) == {"workflow_dispatch"}
    assert doc["concurrency"] == {"group": "deploy", "cancel-in-progress": False, "queue": "max"}
    (job,) = doc["jobs"].values()
    assert job["environment"] == "vps"
    passos = job["steps"]
    assert "exit 1" in passos[0]["run"] and passos[0]["if"] == "github.ref != 'refs/heads/main'"
    checkout = next(p for p in passos if p.get("uses", "").startswith("actions/checkout"))
    assert checkout["with"] == {"ref": "${{ github.sha }}", "persist-credentials": False}
    conferir = next(p for p in passos if p.get("id") == "conferir")
    assert "python infra/drill-appmax-rollback-sandbox.py preparar" in conferir["run"]
    assert 'if [ ! -f "$SCRIPT" ]' in conferir["run"]
    remoto = next(p for p in passos if p.get("id") == "remoto")
    assert remoto["with"]["script_path"] == "${{ steps.conferir.outputs.script }}"
    ultimo = passos[-1]
    assert ultimo["if"] == "always() && steps.remoto.outcome != 'skipped'"
    assert ultimo["run"] == "python infra/drill-appmax-rollback-sandbox.py conferir"
