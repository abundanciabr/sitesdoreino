"""TESTAR O TESTADOR — a área do registro, conferida EM SOMBRA no pouso.

O campo `area` do registro (`painel/LEIA-ME.md`) alimenta a aba "Prioridades"
do painel do dono, e campo que nasce sem portão nasce vazio ou errado. O portão
do pouso é o único instante em que ainda existe alguém para consertar com um
commit (`armadilhas/185`, `248`).

A regra nasce em SOMBRA (a lei do Sistema Imunológico, no cabeçalho de
`ci/muralha_das_armadilhas.py`): ela DIZ o que teria feito e NUNCA muda o
veredito. Por isso o teste que mais importa aqui é o que prova que um registro
sem área, e um com área errada, continuam pousando.

Todos os testes são offline: alimentam as funções com a resposta que o `gh`
devolveria.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import divida_do_livro
import mergear
from _nucleo import Estado

# O arquivo de mentira tem a forma de `painel/areas.json`: um nome é
# reconhecido se estiver em QUALQUER lista `celulas`.
AREAS_DE_MENTIRA = {
    "areas": [
        {
            "id": "fabrica",
            "nome": "Infra e fabrica",
            "diz": "o que faz a casa andar",
            "celulas": ["ci", "infra", ".github"],
        },
        {
            "id": "painel",
            "nome": "Seu painel",
            "diz": "o que voce olha",
            "celulas": ["admin", "painel"],
        },
    ]
}


def _remessa(caminho: str, *linhas: str) -> dict[str, Any]:
    """Uma entrada do `gh api .../pulls/N/files`, com o patch já em linhas `+`."""
    return {
        "filename": caminho,
        "patch": "@@ -0,0 +1 @@\n" + "\n".join(linhas),
    }


def _registro(area: str | None, *, aspas: bool = False) -> list[str]:
    if area is None:
        corpo = ""
    elif aspas:
        corpo = f'+  "area": "{area}",'
    else:
        corpo = f'+  area: "{area}",'
    return ['+  tipo: "entrega",'] + ([corpo] if corpo else []) + ['+  frente: "fabrica"']


# ---------------------------------------------------------------------------
# As duas funções puras
# ---------------------------------------------------------------------------


def test_le_a_area_nas_duas_grafias_que_o_livro_aceita() -> None:
    """`armadilhas/379`: um regex que só casava UMA grafia deixou de contar
    registro honesto, e o Python passou a dizer 6 onde o painel dizia 7."""
    sem_aspas = _remessa("painel/registros/20260907-001-a.js", *_registro("ci"))
    com_aspas = _remessa(
        "painel/registros/20260907-002-b.js", *_registro("admin", aspas=True)
    )
    assert divida_do_livro.areas_dos_registros_embarcados([sem_aspas, com_aspas]) == [
        ("painel/registros/20260907-001-a.js", "ci"),
        ("painel/registros/20260907-002-b.js", "admin"),
    ]


def test_campo_parecido_nao_passa_por_declaracao_de_area() -> None:
    """O revisor do PR #1337: `"sub-area"` casava como SUFIXO de `area`, e como
    vem antes no molde o falso positivo vencia o campo verdadeiro. O campo é
    sempre o primeiro token da linha, então a leitura ancora no começo dela."""
    remessa = _remessa(
        "painel/registros/20260907-006-f.js",
        '+  "sub-area": "vendas",',
        '+  area: "ci",',
    )
    assert divida_do_livro.areas_dos_registros_embarcados([remessa]) == [
        ("painel/registros/20260907-006-f.js", "ci")
    ]


def test_registro_sem_o_campo_e_com_null_contam_como_nao_declarado() -> None:
    """`area: null` é o molde não preenchido — não vale como declaração."""
    sem = _remessa("painel/registros/20260907-003-c.js", *_registro(None))
    nulo = _remessa("painel/registros/20260907-004-d.js", "+  area: null,")
    assert divida_do_livro.areas_dos_registros_embarcados([sem, nulo]) == [
        ("painel/registros/20260907-003-c.js", None),
        ("painel/registros/20260907-004-d.js", None),
    ]


def test_area_em_linha_removida_nao_conta() -> None:
    """Registro não se apaga (`painel/LEIA-ME.md`): linha `-` não é declaração."""
    remessa = {
        "filename": "painel/registros/20260907-005-e.js",
        "patch": '@@ -1 +1 @@\n-  area: "ci",\n+  tipo: "entrega",',
    }
    assert divida_do_livro.areas_dos_registros_embarcados([remessa]) == [
        ("painel/registros/20260907-005-e.js", None)
    ]


def test_arquivo_fora_da_pasta_do_livro_nao_e_registro() -> None:
    fora = _remessa("ci/mergear.py", '+  area: "ci",')
    assert divida_do_livro.areas_dos_registros_embarcados([fora]) == []


def test_area_do_ramo_le_o_nome_da_celula() -> None:
    assert divida_do_livro.area_do_ramo("agent/ci/area-do-registro") == "ci"
    assert divida_do_livro.area_do_ramo("agent/admin/degrau-17") == "admin"


def test_ramo_fora_do_padrao_nao_tem_area() -> None:
    """Ramo que não é `agent/<area>/<tarefa>` não diz área nenhuma."""
    assert divida_do_livro.area_do_ramo("main") is None
    assert divida_do_livro.area_do_ramo("agent/ci") is None
    assert divida_do_livro.area_do_ramo("agent/ci/") is None
    assert divida_do_livro.area_do_ramo("") is None
    assert divida_do_livro.area_do_ramo(None) is None


# ---------------------------------------------------------------------------
# A sombra, no pouso
# ---------------------------------------------------------------------------


def _raiz_com_areas(tmp_path: Path, areas: dict | None = None) -> Path:
    (tmp_path / "painel").mkdir(parents=True, exist_ok=True)
    if areas is not None:
        (tmp_path / "painel" / "areas.json").write_text(
            json.dumps(areas, ensure_ascii=False), encoding="utf-8"
        )
    return tmp_path


def _pr_com_registro(ramo: str = "agent/ci/area-do-registro") -> dict[str, Any]:
    return {
        "number": 99,
        "title": "ci: um PR de mentira",
        "body": "",
        "url": "https://example.invalid/pr/99",
        "headRefName": ramo,
        "headRefOid": "a" * 40,
        "files": [
            {"path": "ci/mergear.py"},
            {"path": "painel/registros/20260907-001-a.js"},
        ],
    }


class _DiffDeMentira:
    """O diff que as sombras leem, sem rede."""

    def __init__(self, remessas: list[dict]) -> None:
        self.remessas = remessas

    def ler(self, _quem: str) -> list[dict]:
        return self.remessas


def _sombra(raiz: Path, pr: dict, remessas: list[dict], capsys) -> str:
    mergear.sombra_da_area_do_registro(raiz, pr, _DiffDeMentira(remessas))
    return capsys.readouterr().out


def test_sem_areas_json_na_main_a_sombra_diz_que_nao_mediu(tmp_path, capsys) -> None:
    """Fail-open: se o arquivo faltar na main, a sombra não mede e cala."""
    raiz = _raiz_com_areas(tmp_path, areas=None)
    remessas = [_remessa("painel/registros/20260907-001-a.js", *_registro("ci"))]
    saida = _sombra(raiz, _pr_com_registro(), remessas, capsys)
    assert "não medi, painel/areas.json não existe na main." in saida
    assert "bate com o ramo" not in saida


def test_registro_sem_area_diria_o_que_escrever(tmp_path, capsys) -> None:
    """O ramo é `agent/ci/...` e `ci` é célula conhecida: aí sim o nome do ramo
    vira sugestão, porque é um valor que o painel aceita."""
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)
    remessas = [_remessa("painel/registros/20260907-001-a.js", *_registro(None))]
    saida = _sombra(raiz, _pr_com_registro(), remessas, capsys)
    assert "não declara área" in saida
    assert 'Escreva area: "ci"' in saida
    assert "não corresponde a nenhuma área" not in saida


def test_ramo_fora_das_areas_conhecidas_nao_sugere_o_nome_do_ramo(
    tmp_path, capsys
) -> None:
    """Sugerir o nome do ramo cru ensinaria um valor que `painel/logica.js`
    recusa e que mata o build do painel na muralha. Num ramo cujo nome não
    está em `painel/areas.json`, a sombra manda usar uma célula conhecida."""
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)
    remessas = [_remessa("painel/registros/20260907-001-a.js", *_registro(None))]
    pr = _pr_com_registro("agent/xyz/uma-tarefa")
    saida = _sombra(raiz, pr, remessas, capsys)
    assert 'Escreva area: "xyz"' not in saida
    assert (
        "O ramo agent/xyz/ não corresponde a nenhuma área de painel/areas.json"
        in saida
    )
    assert 'por exemplo: "admin", "ci", "infra".' in saida


def test_area_diferente_do_ramo_teria_reprovado(tmp_path, capsys) -> None:
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)
    remessas = [_remessa("painel/registros/20260907-001-a.js", *_registro("admin"))]
    saida = _sombra(raiz, _pr_com_registro(), remessas, capsys)
    assert 'declara "admin" e o ramo é agent/ci/...: teria reprovado.' in saida


def test_area_conferida_diz_que_bate(tmp_path, capsys) -> None:
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)
    remessas = [_remessa("painel/registros/20260907-001-a.js", *_registro("ci"))]
    saida = _sombra(raiz, _pr_com_registro(), remessas, capsys)
    assert 'painel/registros/20260907-001-a.js: área "ci" bate com o ramo.' in saida
    assert "reprovado" not in saida


def test_ramo_fora_do_padrao_a_sombra_nao_mede(tmp_path, capsys) -> None:
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)
    remessas = [_remessa("painel/registros/20260907-001-a.js", *_registro("ci"))]
    pr = _pr_com_registro("conserto-rapido")
    saida = _sombra(raiz, pr, remessas, capsys)
    assert (
        "não medi, o ramo conserto-rapido não segue agent/<area>/<tarefa>." in saida
    )


def test_pr_isento_e_pr_sem_registro_a_bordo_calam(tmp_path, capsys) -> None:
    """Esses dois casos já têm dono em `checar_registro_embarcado`; a sombra
    falar de novo só faria barulho — e nem o diff ela precisa buscar."""
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)

    class _DiffProibido:
        def ler(self, _quem):
            raise AssertionError("a sombra não pode consultar o diff nestes casos")

    isento = _pr_com_registro()
    isento["files"] = [{"path": "painel/registros/20260907-001-a.js"}]
    mergear.sombra_da_area_do_registro(raiz, isento, _DiffProibido())
    sem_registro = _pr_com_registro()
    sem_registro["files"] = [{"path": "ci/mergear.py"}]
    mergear.sombra_da_area_do_registro(raiz, sem_registro, _DiffProibido())
    assert "SOMBRA (área do registro)" not in capsys.readouterr().out


def test_diff_ilegivel_nao_derruba_o_pouso_ja_consumado(tmp_path, capsys) -> None:
    """Sombra é fail-open de ponta a ponta: ela roda DEPOIS do merge, e uma
    exceção aqui transformaria um pouso bem-sucedido em ERROR."""
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)

    class _DiffQueQuebra:
        def ler(self, _quem):
            raise mergear.ErroDeInstrumentacao("o gh caiu", "sem rede")

    mergear.sombra_da_area_do_registro(raiz, _pr_com_registro(), _DiffQueQuebra())
    saida = capsys.readouterr().out
    assert "não mediu" in saida
    assert "teria reprovado" not in saida


def test_falha_de_leitura_na_sombra_da_area_nomeia_a_sombra_da_area(
    monkeypatch, tmp_path, capsys
) -> None:
    """A descrição da leitura era fixa no nome da sombra irmã, então uma falha
    de rede aqui acusava a outra sombra a quem fosse ler o log.

    Este teste passa pelo `DiffDoPR` de verdade de propósito: um duplo com
    `ler` próprio não executaria a linha que monta a descrição, e a sabotagem
    dela passaria verde (`armadilhas/391`)."""
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)

    def _gh_que_cai(_argumentos, _raiz, descricao, **_kwargs):
        # A mesma forma que `_nucleo.executar` dá ao erro: a descrição abre o
        # resumo, e é por ela que quem lê o log sabe quem estava medindo.
        raise mergear.ErroDeInstrumentacao(f"{descricao}: exit code 1")

    monkeypatch.setattr(mergear, "_gh", _gh_que_cai)
    mergear.sombra_da_area_do_registro(
        raiz, _pr_com_registro(), mergear.DiffDoPR(raiz, 99)
    )
    saida = capsys.readouterr().out
    assert "não mediu" in saida
    assert "para a sombra da área do registro" in saida
    assert "sombra do evento da fila" not in saida


def test_um_tropeco_isolado_do_gh_nao_custa_mais_a_leitura(
    monkeypatch, tmp_path, capsys
) -> None:
    """Desde 12/09/2026 a leitura tenta três vezes antes de desistir.

    Nos 52 pousos medidos em sombra, TODOS os 13 silêncios vieram daqui: o
    `gh` caiu ao ler o diff. Agora que a porta FECHA a tarefa, uma queda
    isolada de rede não pode mais custar o fechamento.
    """
    descricoes: list[str] = []
    remessas = [_remessa("painel/registros/20260907-001-a.js")]

    def _gh_que_cai_so_na_primeira_leitura(_argumentos, _raiz, descricao, **_kwargs):
        descricoes.append(descricao)
        if len(descricoes) == 1:
            raise mergear.ErroDeInstrumentacao("o gh caiu", "sem rede")
        return json.dumps(remessas)

    monkeypatch.setattr(mergear, "_gh", _gh_que_cai_so_na_primeira_leitura)
    diff = mergear.DiffDoPR(tmp_path, 99)
    assert diff.ler("o fechamento da tarefa") == remessas
    assert len(descricoes) == 2
    assert "falhou na tentativa 1 de 3" in capsys.readouterr().out


def test_falha_de_leitura_nao_fica_guardada_e_a_leitora_seguinte_rele(
    monkeypatch, tmp_path
) -> None:
    """Um tropeço não pode virar diff vazio reaproveitado pela segunda leitora.

    Aqui o `gh` cai nas TRÊS tentativas da primeira leitora — só então ela
    desiste —, e a segunda ainda assim tenta por conta própria, com o nome
    dela na descrição.
    """
    descricoes: list[str] = []
    remessas = [_remessa("painel/registros/20260907-001-a.js")]

    def _gh_que_cai_nas_tres_primeiras(_argumentos, _raiz, descricao, **_kwargs):
        descricoes.append(descricao)
        if len(descricoes) <= mergear.TENTATIVAS_DE_LEITURA_DO_DIFF:
            raise mergear.ErroDeInstrumentacao("o gh caiu", "sem rede")
        return json.dumps(remessas)

    monkeypatch.setattr(mergear, "_gh", _gh_que_cai_nas_tres_primeiras)
    diff = mergear.DiffDoPR(tmp_path, 99)
    with pytest.raises(mergear.ErroDeInstrumentacao):
        diff.ler("o fechamento da tarefa")
    assert diff.ler("a sombra da área do registro") == remessas
    assert descricoes == [
        *["ler o diff do PR #99 para o fechamento da tarefa"]
        * mergear.TENTATIVAS_DE_LEITURA_DO_DIFF,
        "ler o diff do PR #99 para a sombra da área do registro",
    ]


def test_o_diff_e_lido_uma_vez_por_pouso_e_quem_le_diz_o_proprio_nome(
    monkeypatch, tmp_path
) -> None:
    """Duas sombras, um endpoint: a segunda reaproveita o que a primeira leu."""
    descricoes: list[str] = []

    def _gh_falso(_argumentos, _raiz, descricao, **_kwargs):
        descricoes.append(descricao)
        return json.dumps([_remessa("painel/registros/20260907-001-a.js")])

    monkeypatch.setattr(mergear, "_gh", _gh_falso)
    diff = mergear.DiffDoPR(tmp_path, 99)
    primeira = diff.ler("a sombra do evento da fila")
    segunda = diff.ler("a sombra da área do registro")
    assert primeira == segunda
    assert descricoes == ["ler o diff do PR #99 para a sombra do evento da fila"]


# ---------------------------------------------------------------------------
# O que faz a sombra ser sombra: o veredito do pouso NÃO muda
# ---------------------------------------------------------------------------


def _pousar_com(monkeypatch, raiz: Path, pr: dict, remessas: list[dict]) -> int:
    chamadas: list = []

    def _gh_falso(argumentos, _raiz, _descricao, **_kwargs):
        chamadas.append(list(argumentos))
        if argumentos and argumentos[0] == "api":
            return json.dumps(remessas)
        if argumentos[:2] == ["pr", "view"]:
            return json.dumps(
                {
                    "state": "MERGED",
                    "mergedBy": {"login": "robo"},
                    "mergeCommit": {"oid": "a" * 40},
                }
            )
        return ""

    relatorio = mergear.Relatorio("teste")
    relatorio.registrar(mergear.Resultado("tudo", Estado.PASS, "verde"))
    monkeypatch.setenv(mergear.VARIAVEL_DA_PISTA, "sim")
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: raiz)
    monkeypatch.setattr(mergear, "conferir", lambda _n: (relatorio, pr))
    monkeypatch.setattr(mergear, "_gh", _gh_falso)
    return mergear.main(["99", "--confirmo", "99"])


def test_registro_sem_area_continua_pousando(monkeypatch, tmp_path, capsys) -> None:
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)
    remessas = [_remessa("painel/registros/20260907-001-a.js", *_registro(None))]
    assert _pousar_com(monkeypatch, raiz, _pr_com_registro(), remessas) == 0
    assert "não declara área" in capsys.readouterr().out


def test_area_errada_continua_pousando(monkeypatch, tmp_path, capsys) -> None:
    raiz = _raiz_com_areas(tmp_path, AREAS_DE_MENTIRA)
    remessas = [_remessa("painel/registros/20260907-001-a.js", *_registro("admin"))]
    assert _pousar_com(monkeypatch, raiz, _pr_com_registro(), remessas) == 0
    assert "teria reprovado" in capsys.readouterr().out
