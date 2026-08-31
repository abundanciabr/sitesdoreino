"""A Caixa DIZ o que cada etapa quer dizer, e diz a mesma coisa nas duas telas.

Pedido do mantenedor em 31/08/2026. Ele abriu a linha do tempo de uma ideia, viu
"Em análise" e perguntou se aquilo não deveria se chamar "Em votação", para
incentivar os alunos a votar. A pergunta destapou o buraco real: a Caixa
desenhava quatro etapas em DUAS telas (a linha do tempo da ideia e a faixa de
roadmap do quadro) e **nenhuma das duas dizia o que elas significam**. Decisão
dele, no mesmo dia: o nome continua "Em análise", o voto continua aberto em
qualquer etapa, e a Caixa passa a explicar.

Os quatro guardas daqui, e o que cada um impede:

1. **Nenhuma situação nasce muda** — status novo no model sem texto reprova AQUI,
   e não em silêncio na tela de um aluno.
2. **As duas telas explicam** — e a lista das telas é DERIVADA dos templates que
   desenham etapas, não escrita à mão: tela nova que desenhe o caminho entra
   sozinha na varredura. Mapa mantido à mão envelhece em silêncio (Classe 8 do
   `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`), e é o erro que `armadilhas/242` conta.
3. **O texto não é copiado no template** — a lei anti-duplicação do `CLAUDE.md`
   aplicada a texto. Uma frase escrita à mão no HTML passaria nos dois primeiros
   guardas e envelheceria sozinha no primeiro ajuste de redação.
4. **A frase do voto chega ao aluno** — é a que descreve o código de verdade
   (`votar()` não olha status), e sem ela o nome da primeira etapa ensina o
   contrário: que a votação fecha quando a ideia anda.

Toda asserção olha o HTML que o navegador receberia. As duas exceções são o
guarda 1 (que é sobre o model) e o 3 (que é sobre o arquivo no disco, porque é
justamente a ausência no HTML que ele NÃO consegue medir).
"""

from pathlib import Path

import pytest
from django.urls import reverse

from apps.core.participacao import (
    ETAPAS,
    EXPLICACAO_DAS_ETAPAS,
    VOTAR_NUNCA_FECHA,
    legenda_das_etapas,
)
from apps.sugestoes.models import Sugestao

pytestmark = pytest.mark.django_db

TEMPLATES = Path(__file__).resolve().parents[1] / "apps/core/templates/sugestoes"
LEGENDA = "sugestoes/_legenda_das_etapas.html"

# O que faz um template ser "tela que desenha o caminho": ele percorre a linha
# do tempo de uma ideia ou as zonas da faixa. É por estas duas marcas que a
# varredura acha as telas, e não por uma lista de nomes — o dia em que nascer
# uma terceira superfície do caminho, ela cai neste guarda sem ninguém lembrar.
MARCAS_DE_ETAPA = ("in linha_do_tempo", "in faixa")


def _corpo(pessoa, endereco: str) -> str:
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


def _telas_que_desenham_etapas() -> list[Path]:
    achadas = [
        arquivo
        for arquivo in sorted(TEMPLATES.glob("*.html"))
        if any(
            marca in arquivo.read_text(encoding="utf-8") for marca in MARCAS_DE_ETAPA
        )
    ]
    # Fail-closed: uma varredura que não acha nada passaria vazia e diria que
    # está tudo certo. É o falso-verde do padrão 1 da RETROSPECTIVA-FASE-D.
    assert len(achadas) >= 2, f"a varredura achou {len(achadas)} tela(s): {achadas}"
    return achadas


def test_nenhuma_situacao_da_ideia_nasce_muda():
    """Toda situação do model tem a frase dela — inclusive as duas saídas.

    Este é o degrau que impede o buraco de voltar: quem acrescentar um status
    novo em `Sugestao.Status` fica vermelho aqui, antes de um aluno topar com
    um selo que ninguém explica.
    """
    sem_texto = {s.value for s in Sugestao.Status} - set(EXPLICACAO_DAS_ETAPAS)
    assert not sem_texto, f"situação sem explicação para o aluno: {sorted(sem_texto)}"


def test_toda_tela_que_desenha_o_caminho_traz_a_legenda():
    """A legenda é do CAMINHO, não de uma página — quem desenha etapa, explica."""
    for tela in _telas_que_desenham_etapas():
        assert LEGENDA in tela.read_text(
            encoding="utf-8"
        ), f"{tela.name} desenha as etapas e não inclui a legenda"


def test_a_pagina_da_ideia_explica_as_quatro_etapas(dentro, sugestao):
    corpo = _corpo(dentro, reverse("sugestao", args=[sugestao.id]))
    for etapa in legenda_das_etapas():
        assert etapa["explicacao"] in corpo, etapa["chave"]
    assert VOTAR_NUNCA_FECHA in corpo


def test_o_quadro_explica_as_quatro_etapas(dentro, sugestao):
    corpo = _corpo(dentro, reverse("quadro"))
    for etapa in legenda_das_etapas():
        assert etapa["explicacao"] in corpo, etapa["chave"]
    assert VOTAR_NUNCA_FECHA in corpo


@pytest.mark.parametrize("situacao", [s.value for s in Sugestao.Status])
def test_a_pagina_diz_o_que_a_situacao_desta_ideia_significa(
    dentro, sugestao, situacao
):
    """Inclusive `nao_planejado` e `mesclado`, que não têm bolinha na linha.

    São as duas situações em que a pessoa mais precisa de uma frase, e as duas
    que a legenda sozinha não cobriria: elas não são etapa do caminho, chegam
    pelo link direto e aparecem só como selo.

    `update()` e não `save()`: `Sugestao.save()` recusa
    `planejado → em_desenvolvimento` sem ChangeSpec aprovado (EVO-40), e esta
    prova é sobre o TEXTO da página, não sobre o corredor da moderação.
    """
    Sugestao.objects.filter(pk=sugestao.pk).update(status=situacao)
    corpo = _corpo(dentro, reverse("sugestao", args=[sugestao.id]))
    assert EXPLICACAO_DAS_ETAPAS[situacao] in corpo


def test_o_texto_das_etapas_nao_esta_copiado_em_nenhum_template():
    """Uma fonte só. Copiar a frase no HTML passa nos outros guardas e apodrece.

    O guarda lê o DISCO porque é a única forma de medir isto: no HTML
    renderizado, o texto vindo do Python e o texto copiado à mão são
    indistinguíveis — que é exatamente o que torna a cópia perigosa.
    """
    for arquivo in sorted(TEMPLATES.glob("*.html")):
        fonte = arquivo.read_text(encoding="utf-8")
        for chave, texto in EXPLICACAO_DAS_ETAPAS.items():
            assert texto not in fonte, (
                f"{arquivo.name} copiou o texto de {chave}: ele mora em "
                "EXPLICACAO_DAS_ETAPAS (apps/core/participacao.py) e o template "
                "o recebe pelo contexto"
            )
        assert VOTAR_NUNCA_FECHA not in fonte, arquivo.name


# As três riscas longas da lei do `CLAUDE.md`, mais as formas de HTML que viram
# risca na tela. Escritas aqui e não importadas de `ci/travessao.py`: uma célula
# não importa do runner do repositório, e a lista é curta e estável.
RISCAS = ("—", "–", "―", "&mdash;", "&ndash;", "&#8212;", "&#8211;")


def test_o_texto_do_aluno_nao_tem_travessao():
    """A lei de 30/08/2026, no único lugar desta célula onde o portão não olha.

    `ci/travessao.py` varre `templates/`, `traducoes/`, `documentos/` e
    `management/commands/`. Ele diz na própria docstring que texto publicado
    morando em `.py` é um buraco conhecido, e que a superfície cresce no dia em
    que a cópia do site passar a morar lá.

    Nesta célula ela mora: os RÓTULOS de `Sugestao.Status` (o "Em análise" que o
    aluno lê no selo) sempre estiveram em `models.py`, e desde 31/08/2026 as
    explicações estão em `participacao.py`. Enquanto o portão do repositório não
    alcança esta classe de arquivo, quem segura a lei aqui é este guarda.
    """
    publicados = {
        **{
            f"explicação de {chave}": texto
            for chave, texto in EXPLICACAO_DAS_ETAPAS.items()
        },
        **{f"rótulo de {s.value}": s.label for s in Sugestao.Status},
        "a frase do voto": VOTAR_NUNCA_FECHA,
    }
    for onde, texto in publicados.items():
        achadas = [risca for risca in RISCAS if risca in texto]
        assert not achadas, (
            f"{onde} tem travessão ({achadas}): a lei do CLAUDE.md manda trocar "
            "por vírgula, parênteses, dois-pontos ou aspas, REESCREVENDO a frase"
        )


def test_a_legenda_lista_as_quatro_etapas_do_caminho_e_so_elas():
    """As duas saídas têm texto, e de propósito NÃO entram na legenda.

    A legenda acompanha uma linha de quatro bolinhas; listar seis passos ali
    faria a explicação discordar do desenho que ela explica.
    """
    assert [etapa["chave"] for etapa in legenda_das_etapas()] == list(ETAPAS)
