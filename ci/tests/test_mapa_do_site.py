"""O MAPA DO SITE e o varredor que o impede de mentir (30/08/2026).

O mapa de `/admin/mapa/` é lido com confiança — é para isso que ele existe. Por
isso o perigo dele não é estar errado: é estar errado **em silêncio**. Nada
quebra visivelmente quando uma página nova nasce fora do mapa; o dono
simplesmente deixa de saber que ela existe, e continua consultando uma planta
que já não é a da casa. É a Classe 8 (mapa velho), a mesma doença que
`celulas.yml` cura do outro lado.

Daí a forma destes testes: cada um SABOTA o mapa (ou o código) de um jeito
diferente e exige vermelho. Um teste que só rodasse o varredor contra o
repositório são provaria que ele roda — não que ele morde.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import mapa_do_site  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402


def _cenario(tmp_path: Path, mapa: dict | None = None) -> Path:
    """Uma raiz com as quatro fontes reais e o mapa que o teste quiser.

    As fontes são as DE VERDADE (roteamento, urlconfs, envs, celulas.yml)
    porque a régua do varredor é o site real: um cenário com rotas inventadas
    mediria o teste, não o varredor. Só o mapa é do teste — é ele o sabotado.
    """
    raiz = tmp_path / "repo"
    # Um teste pode montar DOIS cenários (sabotagem e a sabotagem oposta) no
    # mesmo `tmp_path`: sem esta limpeza o segundo estouraria em `mkdir`.
    shutil.rmtree(raiz, ignore_errors=True)
    (raiz / "painel").mkdir(parents=True)
    (raiz / "infra" / "traefik" / "dynamic").mkdir(parents=True)
    (raiz / "infra" / "env").mkdir(parents=True)
    shutil.copy(RAIZ / "celulas.yml", raiz / "celulas.yml")
    shutil.copy(
        RAIZ / "infra" / "traefik" / "dynamic" / "plataforma.yml",
        raiz / "infra" / "traefik" / "dynamic" / "plataforma.yml",
    )
    for env in (RAIZ / "infra" / "env").glob("*.env.exemplo"):
        shutil.copy(env, raiz / "infra" / "env" / env.name)
    for urls in (RAIZ / "services").glob("*/config/urls.py"):
        destino = raiz / "services" / urls.parents[1].name / "config"
        destino.mkdir(parents=True)
        shutil.copy(urls, destino / "urls.py")
    if mapa is None:
        mapa = json.loads(
            (RAIZ / "painel" / "mapa-do-site.json").read_text(encoding="utf-8")
        )
    (raiz / "painel" / "mapa-do-site.json").write_text(
        json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return raiz


def _mapa_real() -> dict:
    return json.loads(
        (RAIZ / "painel" / "mapa-do-site.json").read_text(encoding="utf-8")
    )


def _entrada(mapa: dict, celula: str, rota: str) -> dict:
    for entrada in mapa["enderecos"]:
        if entrada["celula"] == celula and entrada["rota"] == rota:
            return entrada
    raise AssertionError(f"o mapa real não tem {celula} → {rota!r}")


# --------------------------------------------------------------------------
# O repositório real: o mapa diz a verdade HOJE
# --------------------------------------------------------------------------


def test_o_mapa_do_site_diz_a_verdade_sobre_o_roteamento():
    relatorio = mapa_do_site.verificar(RAIZ)
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_toda_rota_do_site_tem_texto_para_uma_pessoa():
    """Título e descrição existem e não são enfeite — a tela é para um leigo.

    Sem esta régua, uma entrada com `descricao: "-"` passaria no portão (o
    campo está preenchido) e chegaria à tela do dono sem dizer nada.
    """
    curtas = [
        f"{e['celula']}:{e['rota']!r}"
        for e in _mapa_real()["enderecos"]
        if len(e.get("descricao", "")) < 30 or len(e.get("titulo", "")) < 5
    ]
    assert not curtas, f"descrição de enfeite em: {curtas}"


def test_o_endereco_duplo_da_biblioteca_e_medido_como_duplo():
    """`/docs/` e `/admin/docs/` são a MESMA rota, e as duas respondem.

    Medido na internet pública em 30/08/2026 (200 nas duas). Se um dia o
    varredor deixar de enxergar o segundo endereço, o mapa passará a oferecer
    só o caminho de dentro da área — e a biblioteca pública sumiria da vista.
    """
    medido = mapa_do_site.medir(RAIZ)
    _, alcance = medido[("admin", "docs/")]
    assert alcance.enderecos == ["/admin/docs/", "/docs/"]


def test_o_prefixo_dobrado_do_quiz_nao_vira_endereco_curto():
    """`/quiz/<slug>/` NÃO é oferecido: sob SCRIPT_NAME o prefixo é removido.

    A rota do quiz é `quiz/<slug>/` e a célula vive sob `/quiz`, então o
    endereço real dobra o prefixo. Oferecer o caminho curto seria mandar o dono
    para um 404 — e é o tipo de erro que só aparece em produção.
    """
    medido = mapa_do_site.medir(RAIZ)
    _, alcance = medido[("quiz", "quiz/<slug:slug>/")]
    assert alcance.enderecos == ["/quiz/quiz/<slug:slug>/"]


def test_o_que_a_internet_nao_alcanca_e_medido_como_interno():
    medido = mapa_do_site.medir(RAIZ)
    _, catalogo = medido[("catalogo", "api/catalogo/")]
    _, forum = medido[("forum", "interno/")]
    assert not catalogo.publico, "o catálogo não tem rota no Traefik"
    assert forum.publico, "a porta de máquina do fórum mora sob o /forum público"


# --------------------------------------------------------------------------
# As sabotagens — uma por forma de mentir
# --------------------------------------------------------------------------


def test_rota_nova_sem_entrada_no_mapa_reprova(tmp_path: Path):
    """O caso que mais vai acontecer: alguém cria uma página e esquece o mapa."""
    raiz = _cenario(tmp_path)
    urls = raiz / "services" / "forum" / "config" / "urls.py"
    urls.write_text(
        urls.read_text(encoding="utf-8").replace(
            'path("", home, name="home"),',
            'path("", home, name="home"),\n    path("novidades", home, name="novidades"),',
        ),
        encoding="utf-8",
    )
    relatorio = mapa_do_site.verificar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "novidades" in relatorio.render()


def test_entrada_fantasma_reprova(tmp_path: Path):
    """Linha que sobreviveu à página: link quebrado na tela do dono."""
    mapa = _mapa_real()
    mapa["enderecos"].append(
        {
            "celula": "forum",
            "rota": "pagina-que-nao-existe",
            "endereco": "/forum/pagina-que-nao-existe",
            "alcance": "publico",
            "para_quem": "visitante",
            "titulo": "Uma página inventada",
            "descricao": "Não existe no código, e por isso este teste exige vermelho.",
        }
    )
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL
    assert "FANTASMA" in relatorio.render()


def test_endereco_errado_reprova(tmp_path: Path):
    """O mapa diz um caminho, a rota responde em outro."""
    mapa = _mapa_real()
    _entrada(mapa, "forum", "")["endereco"] = "/forum-da-escola/"
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL
    assert "/forum-da-escola/" in relatorio.render()


def test_dizer_publico_o_que_a_internet_nao_alcanca_reprova(tmp_path: Path):
    """Prometer porta aberta onde não há porta assusta à toa — e o contrário
    esconde uma porta que existe. Os dois sentidos reprovam."""
    mapa = _mapa_real()
    _entrada(mapa, "catalogo", "api/catalogo/")["alcance"] = "publico"
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL

    mapa = _mapa_real()
    _entrada(mapa, "forum", "")["alcance"] = "interno"
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL


def test_publico_fora_do_vocabulario_reprova(tmp_path: Path):
    """Valor novo em `para_quem` cairia num grupo que a tela não desenha."""
    mapa = _mapa_real()
    _entrada(mapa, "forum", "")["para_quem"] = "professores"
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL
    assert "para_quem" in relatorio.render()


def test_exemplo_que_nao_cabe_no_molde_reprova(tmp_path: Path):
    """O exemplo é o link que o dono clica: fora do molde, ele dá 404."""
    mapa = _mapa_real()
    _entrada(mapa, "forum", "a/<slug:slug>")["exemplo"] = "/forum/areas/avisos"
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL
    assert "exemplo" in relatorio.render()


def test_entrada_repetida_reprova(tmp_path: Path):
    mapa = _mapa_real()
    mapa["enderecos"].append(dict(_entrada(mapa, "forum", "")))
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL
    assert "duas vezes" in relatorio.render()


# --------------------------------------------------------------------------
# Não consegui medir NUNCA vira PASS (INV-CI01)
# --------------------------------------------------------------------------


def test_mapa_ausente_e_ERROR_e_nunca_mapa_vazio(tmp_path: Path):
    raiz = _cenario(tmp_path)
    (raiz / "painel" / "mapa-do-site.json").unlink()
    with pytest.raises(ErroDeInstrumentacao):
        mapa_do_site.verificar(raiz)


def test_mapa_vazio_e_ERROR(tmp_path: Path):
    """Lista vazia passaria em qualquer comparação de conjuntos vazios."""
    raiz = _cenario(tmp_path, {"enderecos": []})
    with pytest.raises(ErroDeInstrumentacao):
        mapa_do_site.verificar(raiz)


def test_roteamento_ausente_e_ERROR(tmp_path: Path):
    raiz = _cenario(tmp_path)
    (raiz / "infra" / "traefik" / "dynamic" / "plataforma.yml").unlink()
    with pytest.raises(ErroDeInstrumentacao):
        mapa_do_site.verificar(raiz)


def test_urlpatterns_por_concatenacao_e_ERROR(tmp_path: Path):
    """Forma que este varredor não sabe ler vira ERROR, nunca "medi menos".

    Um `urlpatterns += [...]` deixaria as rotas acrescentadas invisíveis para o
    mapa — e o portão ficaria verde medindo metade do site. É o falso-verde do
    padrão 1 da RETROSPECTIVA-FASE-D, e por isso é ERROR e não FAIL: o
    instrumento não sabe medir aquilo.
    """
    raiz = _cenario(tmp_path)
    urls = raiz / "services" / "forum" / "config" / "urls.py"
    urls.write_text(
        urls.read_text(encoding="utf-8") + "\nurlpatterns += []\n", encoding="utf-8"
    )
    with pytest.raises(ErroDeInstrumentacao):
        mapa_do_site.verificar(raiz)


def test_celula_sem_urlconf_e_ERROR(tmp_path: Path):
    raiz = _cenario(tmp_path)
    (raiz / "services" / "forum" / "config" / "urls.py").unlink()
    with pytest.raises(ErroDeInstrumentacao):
        mapa_do_site.verificar(raiz)
