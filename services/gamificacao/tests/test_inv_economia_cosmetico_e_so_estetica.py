"""INVARIANTE 2 DA ECONOMIA — cosmético muda a APARÊNCIA, e não muda mais nada.

Lei: `docs/decisoes/DECISAO-gamificacao.md` §3.2. A frase inteira: *"Cosmético é
só estética. Nunca vantagem em XP, ranking ou visibilidade."*

**Este teste nunca se flexibiliza** (§10.5 do plano). Se um dia ele precisar de
exceção, isso é o critério de morte nº 6 acontecendo.

POR QUE ESTE INVARIANTE, E POR QUE ELE É O MAIS FÁCIL DE PERDER
----------------------------------------------------------------
Os outros dois se quebram por uma decisão grande, que alguém tomaria de olhos
abertos. Este se quebra por uma boa ideia numa tarde qualquer: *"e se a moldura
dourada desse 5% a mais de XP?"*, *"e se quem comprou o tema aparecesse antes na
galeria?"*. Cada uma parece um detalhe simpático, e juntas transformam a loja no
lugar onde se compra posição — que é exatamente o que a lei proíbe, e o que a
economia earn-only existe para tornar impossível.

O que o teste mede é a FORMA do modelo, não a intenção de quem o escreveu: um
cosmético que não tem onde guardar um multiplicador não consegue multiplicar
nada, mesmo que o motor de XP de amanhã queira.
"""

import pytest
from django.db import IntegrityError, connection, transaction

from apps.gamificacao.models import (
    Aquisicao,
    Concessao,
    ConquistaDefinicao,
    GrupoDaSemana,
    ItemCosmetico,
    LancamentoDeXP,
    LigaDefinicao,
    MissaoDefinicao,
    NivelDefinicao,
    ParticipacaoNaLiga,
    ProgressoDeMissao,
    RegraDePontuacao,
)

# Os quatro tipos, todos visuais. `decoracao_estudio` é o sumidouro principal de
# Cristais (a decoração do Meu Estúdio), e é sumidouro justamente por não fazer
# nada além de enfeitar.
TIPOS_VISUAIS = {"titulo", "moldura", "tema", "decoracao_estudio"}

# O vocabulário da VANTAGEM. Um campo de cosmético que carregue qualquer destas
# palavras já é, pelo nome, a coisa proibida.
VANTAGEM = (
    "xp",
    "ponto",
    "multiplicador",
    "bonus",
    "boost",
    "impulso",
    "vantagem",
    "peso",
    "prioridade",
    "destaque",
    "ranking",
    "posicao",
    "visibilidade",
    "alcance",
    "escudo",
    "protecao",
    "imunidade",
    "desconto",
    "acelera",
    "turbo",
    "poder",
)

# A FORMA FECHADA do item de loja. Acrescentar um campo aqui é decisão, nunca
# detalhe: quem acrescentar precisa atualizar esta lista no mesmo PR e escrever,
# no corpo do PR, por que o campo novo não é vantagem.
FORMA_DO_COSMETICO = {
    "id",
    "slug",
    "site_id",
    "nome",
    "descricao",
    "tipo",
    "custo_em_cristais",
    "sazonal",
    "ativa",
    "versao",
}

# As tabelas que decidem XP, nível, ranking e visibilidade de conquista. Nenhuma
# delas pode conhecer um cosmético: no instante em que uma conhecer, "o que você
# veste" passa a poder entrar na conta do "quanto você vale".
QUEM_NAO_PODE_CONHECER_COSMETICO = (
    RegraDePontuacao,
    LancamentoDeXP,
    NivelDefinicao,
    MissaoDefinicao,
    ProgressoDeMissao,
    ConquistaDefinicao,
    Concessao,
    LigaDefinicao,
    GrupoDaSemana,
    ParticipacaoNaLiga,
)


def _campos_concretos(modelo):
    return [f for f in modelo._meta.get_fields() if getattr(f, "concrete", False)]


def test_o_cosmetico_nao_tem_onde_guardar_uma_vantagem():
    """A asserção central deste invariante: nome de campo contra o vocabulário.

    Se `ItemCosmetico` ganhar `multiplicador_de_xp`, `peso_no_ranking` ou
    `destaque_na_galeria`, a CI fica vermelha AQUI, antes de existir uma linha
    de motor que leia esse campo.
    """
    achados = []
    for modelo in (ItemCosmetico, Aquisicao):
        for campo in _campos_concretos(modelo):
            nome = campo.name.lower()
            for palavra in VANTAGEM:
                if palavra in nome:
                    achados.append(f"{modelo.__name__}.{campo.name} (por {palavra!r})")

    assert achados == [], (
        "INVARIANTE 2 QUEBRADO: um cosmético ganhou campo de vantagem.\n  "
        + "\n  ".join(achados)
        + "\n\nA lei §3.2 é literal: cosmético nunca dá vantagem em XP, ranking "
        "ou visibilidade. Se a ideia é recompensar mais, o lugar é uma "
        "`RegraDePontuacao` (que é DADO, anunciado e não retroativo), nunca um "
        "item que se adquire."
    )


def test_a_forma_do_item_de_loja_e_fechada():
    """Campo novo em cosmético é decisão revisada, não detalhe que passa batido.

    A asserção é de conjunto exato, e isso é deliberado: um campo cujo nome
    escape do vocabulário de vantagem (`fator`, `k`, `plus`) ainda assim para
    aqui, e quem o acrescentar precisa dizer em voz alta o que ele faz.
    """
    forma = {campo.name for campo in _campos_concretos(ItemCosmetico)}

    assert forma == FORMA_DO_COSMETICO, (
        "a forma do `ItemCosmetico` mudou.\n"
        f"  sobrou:  {sorted(forma - FORMA_DO_COSMETICO)}\n"
        f"  faltou:  {sorted(FORMA_DO_COSMETICO - forma)}\n\n"
        "Se o campo novo é legítimo, atualize `FORMA_DO_COSMETICO` no MESMO PR "
        "e escreva no corpo dele por que o campo não é vantagem em XP, ranking "
        "ou visibilidade."
    )


def test_os_tipos_de_cosmetico_sao_exatamente_os_quatro_visuais():
    """Título, moldura, tema e decoração. Nada que aja sobre a mecânica."""
    tipos = {valor for valor, _ in ItemCosmetico.Tipo.choices}

    assert tipos == TIPOS_VISUAIS, (
        f"INVARIANTE 2 QUEBRADO: os tipos de cosmético mudaram.\n"
        f"  agora: {sorted(tipos)}\n"
        f"  lei:   {sorted(TIPOS_VISUAIS)}"
    )


@pytest.mark.django_db
def test_o_banco_recusa_um_quinto_tipo_de_cosmetico():
    """A frente que vale às três da manhã: SQL cru também é recusado.

    Escolha de `TextChoices` é conferida pelo Django, e o Django só entra
    quando o caminho passa por ele. A restrição `tipo_de_cosmetico_e_so_estetica`
    está no PostgreSQL.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO gamificacao_itemcosmetico "
                    "(slug, site_id, nome, descricao, tipo, custo_em_cristais, "
                    " sazonal, ativa, versao) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        "impulso-dourado",
                        "escola-a",
                        "Impulso dourado",
                        "",
                        "impulso_de_xp",
                        999,
                        False,
                        False,
                        1,
                    ],
                )

    assert "tipo_de_cosmetico_e_so_estetica" in str(erro.value)


def test_nenhuma_tabela_que_calcula_xp_nivel_ou_ranking_conhece_um_cosmetico():
    """A segunda porta pela qual a vantagem entraria: não pelo item, pela conta.

    Um `ItemCosmetico` sem campo de vantagem ainda daria vantagem se a
    `RegraDePontuacao` ganhasse `item_que_multiplica`, ou se
    `ParticipacaoNaLiga` ganhasse `moldura_que_pontua`. A relação inversa
    (`Aquisicao` apontar para `ItemCosmetico`) é legítima e é a única que
    existe: ela diz o que a pessoa TEM, e nada mais.
    """
    proibidos = {ItemCosmetico, Aquisicao}
    achados = []
    for modelo in QUEM_NAO_PODE_CONHECER_COSMETICO:
        for campo in _campos_concretos(modelo):
            alvo = getattr(campo, "related_model", None)
            if alvo in proibidos:
                achados.append(f"{modelo.__name__}.{campo.name} -> {alvo.__name__}")

    assert achados == [], (
        "INVARIANTE 2 QUEBRADO: uma tabela de XP, nível ou ranking passou a "
        "conhecer um cosmético.\n  " + "\n  ".join(achados) + "\n\n"
        "É por esta porta que 'a moldura dourada dá 5% a mais' entra sem "
        "ninguém decidir nada."
    )
