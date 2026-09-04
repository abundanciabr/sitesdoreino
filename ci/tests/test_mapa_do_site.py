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
import re
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import mapa_do_site  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402


def _cenario(
    tmp_path: Path, mapa: dict | None = None, *, com_vistas: bool = False
) -> Path:
    """Uma raiz com as quatro fontes reais e o mapa que o teste quiser.

    As fontes são as DE VERDADE (roteamento, urlconfs, envs, celulas.yml)
    porque a régua do varredor é o site real: um cenário com rotas inventadas
    mediria o teste, não o varredor. Só o mapa é do teste — é ele o sabotado.

    `com_vistas` traz também o CÓDIGO das células (as `def` das views), que é o
    que a checagem 4 (gestos) lê para saber se uma rota só aceita POST. É
    opt-in porque são 408 arquivos e ~0,4 s por cenário, e a maioria dos testes
    daqui não fala de gesto — sem ele, aquela checagem simplesmente não decide
    nada, que é o comportamento honesto dela e não um verde falso.
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
    if com_vistas:
        for py in (RAIZ / "services").rglob("*.py"):
            relativo = py.relative_to(RAIZ)
            if {"tests", "migrations"} & set(relativo.parts):
                continue
            alvo = raiz / relativo
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(py, alvo)
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


# --------------------------------------------------------------------------
# A sonda — a luz de "está no ar?" que o navegador do DONO acende
# --------------------------------------------------------------------------


def test_sonda_num_gesto_reprova(tmp_path: Path):
    """A cerca que impede um DANO, não uma inconsistência.

    `/entrar/sair` é um gesto. Marcado com `sonda`, o navegador do dono o
    abriria sozinho ao carregar o mapa — e ele sairia da própria conta. Um
    `/…/apagar` seria pior.
    """
    mapa = _mapa_real()
    _entrada(mapa, "identidade", "entrar/sair")["sonda"] = True
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL
    assert "GESTO" in relatorio.render()


def test_sonda_em_endereco_interno_reprova(tmp_path: Path):
    """O navegador dele não alcança a rede do Docker: a luz mentiria vermelho."""
    mapa = _mapa_real()
    _entrada(mapa, "catalogo", "api/catalogo/")["sonda"] = True
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL
    assert "interno" in relatorio.render()


def test_sonda_num_molde_sem_exemplo_reprova(tmp_path: Path):
    """Pedir `/forum/t/<int:topico_id>` devolve 404 e pintaria de vermelho uma
    porta que está aberta."""
    mapa = _mapa_real()
    _entrada(mapa, "forum", "t/<int:topico_id>")["sonda"] = True
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa))
    assert relatorio.estado is Estado.FAIL
    assert "molde" in relatorio.render()


def test_as_portas_principais_estao_sondadas():
    """O mapa de hoje acende luz nas portas que o dono chamaria de 'o site'."""
    sondadas = {
        e.get("exemplo") or e["endereco"]
        for e in _mapa_real()["enderecos"]
        if e.get("sonda")
    }
    for porta in ("/", "/login", "/forum/", "/forms/sugestoes/", "/admin/"):
        assert porta in sondadas, f"a porta {porta} deveria ter luz"


# --------------------------------------------------------------------------
# A checagem 4: rota que só aceita POST não é página (armadilhas/330)
# --------------------------------------------------------------------------


def test_rota_so_post_sem_a_marca_de_gesto_reprova(tmp_path: Path):
    """O caso medido em 04/09/2026, e o motivo desta checagem existir.

    `gesto: true` é o que faz a tela NÃO oferecer link. Sem a marca, o dono
    clica no nome da linha e recebe 405 — e nada ficava vermelho: cinco
    endereços viveram assim com o portão verde e os 963 testes da célula
    `admin` passando.
    """
    mapa = _mapa_real()
    _entrada(mapa, "admin", "economia/mudar-conquista").pop("gesto", None)
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, mapa, com_vistas=True))
    assert relatorio.estado is Estado.FAIL
    saida = relatorio.render()
    assert "economia/mudar-conquista" in saida
    assert "economia_mudar_conquista" in saida, "a recusa diz QUAL view decidiu"
    assert "gesto" in saida, "a recusa entrega o conserto pronto"


def test_gesto_em_rota_que_aceita_leitura_nao_reprova(tmp_path: Path):
    """A recíproca é FALSA, e escrevê-la reprovaria quatro entradas corretas.

    `/entrar/google` é GET e é gesto legítimo: abrir esse endereço não mostra
    página nenhuma, dispara o vaivém do Google. Só-POST ⇒ gesto é verdade
    sempre; gesto ⇒ só-POST, não.
    """
    vistas = mapa_do_site.vistas_da_celula(RAIZ, "identidade")
    assert (
        vistas.get("entrar_google") is not True
    ), "se um dia esta view virar só-POST, este teste deixa de provar o que diz"
    assert _entrada(_mapa_real(), "identidade", "entrar/google")["gesto"] is True
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, com_vistas=True))
    assert relatorio.estado is Estado.PASS


def test_o_portao_de_hoje_decide_a_maioria_das_rotas(tmp_path: Path):
    """A checagem não pode virar decorativa por não decidir nada.

    Ela é fail-open por desenho — rota cuja view não se resolve não vira
    afirmação —, e é exatamente assim que ela morreria em silêncio: um dia
    decidindo zero e ainda dizendo PASS. Este guarda fixa o piso medido em
    04/09/2026 (149 de 183) com folga, e a conta aparece na tela do portão.
    """
    relatorio = mapa_do_site.verificar(_cenario(tmp_path, com_vistas=True))
    linha = next(r for r in relatorio.resultados if r.nome == "gestos")
    sem_veredito = int(re.search(r"\((\d+) rotas sem", linha.resumo).group(1))
    total = len(mapa_do_site.medir(RAIZ))
    assert sem_veredito < total // 2, (
        f"o portão deixou de decidir {sem_veredito} de {total} rotas — a "
        "checagem virou decoração"
    )


def test_nome_de_view_ambiguo_nao_vira_afirmacao(tmp_path: Path):
    """Dois `def` com o mesmo nome e vereditos opostos: o portão cala.

    A busca é pelo NOME (seguir a cadeia de imports daria mais formas de errar
    em silêncio do que de acertar). O preço dessa escolha é a homonímia — e o
    preço se paga calando, nunca afirmando sobre a rota de outra pessoa.
    """
    raiz = _cenario(tmp_path, com_vistas=True)
    sosia = raiz / "services" / "admin" / "apps" / "core" / "sosia_do_teste.py"
    sosia.write_text(
        "from django.views.decorators.http import require_GET\n\n\n"
        "@require_GET\ndef economia_mudar_conquista(request):\n    return None\n",
        encoding="utf-8",
    )
    vistas = mapa_do_site.vistas_da_celula(raiz, "admin")
    assert vistas["economia_mudar_conquista"] is None
    mapa = _mapa_real()
    _entrada(mapa, "admin", "economia/mudar-conquista").pop("gesto", None)
    (raiz / "painel" / "mapa-do-site.json").write_text(
        json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert mapa_do_site.verificar(raiz).estado is Estado.PASS
