"""INVARIANTE 1 DA ECONOMIA — nada nesta célula se compra com dinheiro real.

Lei: `docs/decisoes/DECISAO-gamificacao.md` §3.1 e §8; `PLANO` §10.5. A frase
inteira, com as palavras dela: *"Nenhum item, moeda, proteção ou vantagem se
compra. Cristais são earn-only por construção do banco (`CheckConstraint`), não
por convenção."*

**Este guarda não se afrouxa por agente, e não se afrouxou.** Ele perdeu uma
frente em 06/09/2026, e perdeu pelo único caminho que a lei prevê: o critério de
morte nº 6 (*"qualquer invariante do CI precisar de exceção"*) foi exercido, a
sessão parou, e o mantenedor decidiu o alcance em pergunta estruturada. O que
está escrito abaixo é o guarda que ele mandou existir.

POR QUE ELE NASCE AQUI, NO PR DAS TABELAS
------------------------------------------
Porque é aqui que a promessa vira mecanismo. A escola vende formação a
adultos que pagam por ela, e a diferença entre "nós não vendemos vantagem" dito num
documento e a mesma frase conferida pelo PostgreSQL é a diferença entre uma
intenção e uma garantia. Documento não sobrevive a seis meses e quatro sessões
diferentes (`RETROSPECTIVA-FASE-D` §2); restrição de banco sobrevive.

O QUE ELE MEDE, EM TRÊS FRENTES
--------------------------------
1. **Instrumento de pagamento** — nenhum campo, de tipo nenhum, nomeia cartão,
   boleto, Pix, gateway ou fatura. Não há razão legítima para esta célula
   COBRAR de alguém: quem cobra é o `checkout`.
2. **Import** — nenhum módulo desta célula conhece um SDK de cobrança.
3. **O banco** — o PostgreSQL recusa o INSERT, venha ele de onde vier. É esta
   frente que continua valendo numa madrugada de incidente, com alguém logado
   no `psql`.

A FRENTE QUE CAIU EM 06/09/2026, E POR QUE ELA NÃO VOLTA SOZINHA
------------------------------------------------------------------
Havia uma quarta frente: nenhum campo que CARREGASSE valor podia nomear real,
dólar, centavo ou preço. Ela mirava UMA direção do dinheiro — alguém pagando
para levar vantagem no jogo — e barrava a outra por tabela: o dinheiro que o
aluno GANHOU no mundo real, que é a espinha desta escola (o `marco` de carreira
com `envolve_dinheiro`, a escada dos primeiros dólares). Com ela de pé, a escada
sabia QUEM chegou ao degrau e nunca QUANTO, e a escola não conseguia somar o que
os alunos dela faturaram.

O mantenedor reabriu o §3.1 e decidiu o alcance com estas palavras: **toda
quantia, em qualquer tabela desta célula**. A promessa do invariante continua
inteira, e é a do título dele: nada aqui se COMPRA. Quem a garante agora são as
três frentes acima e as restrições do banco — Cristal não nasce de compra,
débito só existe com o recibo do cosmético junto, e o vocabulário de origens é
fechado no PostgreSQL.

**O que isso deixa possível, dito em voz alta:** uma coluna de preço em reais ao
lado do `custo_em_cristais` não fica mais vermelha sozinha. O que impede a loja
de aceitar dinheiro passou a ser o banco e a decisão de quem escreve o código, e
não mais o nome do campo. Foi a troca que ele escolheu, sabendo dela.

Se um dia a frente tiver de voltar, ela volta pelo mesmo caminho — decisão do
mantenedor —, e não como "conserto" de uma sessão que achou o guarda
incompleto. Está escrito aqui porque guarda que encolhe sem explicação é guarda
que a próxima sessão restaura por engano.
"""

import ast
from pathlib import Path

import pytest
from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.gamificacao.models import (
    ItemCosmetico,
    MovimentoDeCristais,
    Pessoa,
    Sequencia,
)

CELULA = Path(__file__).resolve().parent.parent
APP = CELULA / "apps" / "gamificacao"

# INSTRUMENTO DE PAGAMENTO — proibido em campo de QUALQUER tipo. Não existe
# razão legítima para a gamificação nomear um meio de cobrança.
INSTRUMENTO_DE_PAGAMENTO = (
    "pagamento",
    "pagamentos",
    "pagar",
    "cobranca",
    "cartao",
    "boleto",
    "pix",
    "checkout",
    "mercadopago",
    "stripe",
    "paypal",
    "gateway",
    "fatura",
    "fiscal",
    "mensalidade",
    "assinatura",
)

# Os SDKs e clientes que só existem para mover dinheiro. Um import destes dentro
# desta célula é o primeiro passo de tudo o que a lei §8 veta.
BIBLIOTECAS_DE_COBRANCA = (
    "mercadopago",
    "stripe",
    "paypal",
    "pagarme",
    "asaas",
    "iugu",
    "braintree",
    "adyen",
)


def _modelos():
    return list(apps.get_app_config("gamificacao").get_models())


def _campos_concretos(modelo):
    return [f for f in modelo._meta.get_fields() if getattr(f, "concrete", False)]


def _palavras(nome: str) -> set:
    """As palavras de um nome de campo. Régua de TOKEN, nunca de pedaço.

    `cristais` não contém `reais` por acidente, e `pixel` não contém `pix`: a
    quebra por `_` é o que impede um guarda desta seriedade de reprovar campo
    inocente e, com isso, ensinar a próxima sessão a afrouxá-lo.
    """
    return set(nome.lower().split("_"))


def test_nenhum_campo_desta_celula_nomeia_um_instrumento_de_pagamento():
    """Cartão, boleto, Pix, gateway, fatura. Em campo de tipo nenhum, jamais.

    Vale inclusive para booleano: um `aceita_cartao = BooleanField()` é a linha
    exata que abriria a porta, e ela não guarda quantia alguma.
    """
    achados = []
    for modelo in _modelos():
        for campo in _campos_concretos(modelo):
            for palavra in _palavras(campo.name) & set(INSTRUMENTO_DE_PAGAMENTO):
                achados.append(f"{modelo.__name__}.{campo.name} (por {palavra!r})")

    assert sorted(achados) == [], (
        "INVARIANTE 1 QUEBRADO: campo desta célula nomeia meio de pagamento.\n  "
        + "\n  ".join(sorted(achados))
        + "\n\nSe a escola precisa cobrar por algo, isso é a célula `checkout`, "
        "nunca esta. A constituição da `gamificacao` proíbe `checkout` e "
        "`pagamentos` INCLUSIVE para leitura."
    )


def test_o_detector_de_pagamento_morde_o_que_deve_e_so_o_que_deve():
    """A prova de que a frente 1 continua mordendo depois da queda da frente 2.

    Um portão que nunca fica vermelho é indistinguível de um portão desligado, e
    o teste acima só olha os campos que existem HOJE: enquanto nenhum deles
    nomear um meio de cobrança, ele passa sem jamais provar que morderia. Esta
    asserção morde nomes de MENTIRA, que é como se prova o detector sem plantar
    um campo de pagamento num modelo de verdade.

    A terceira linha é a que impede o excesso: a régua é de TOKEN, e `pixel` não
    é `pix`.
    """
    assert _palavras("aceita_cartao") & set(INSTRUMENTO_DE_PAGAMENTO) == {"cartao"}
    assert _palavras("pix_do_aluno") & set(INSTRUMENTO_DE_PAGAMENTO) == {"pix"}
    assert _palavras("pixel_do_avatar") & set(INSTRUMENTO_DE_PAGAMENTO) == set()


def test_nenhuma_escolha_declarada_nomeia_um_meio_de_pagamento():
    """O vocabulário que o banco guarda também não conhece dinheiro.

    Mede os VALORES das `TextChoices` (o que fica gravado na coluna), não os
    rótulos: rótulo é português para humano, e ele pode legitimamente dizer
    "marco que envolve dinheiro". Valor é vocabulário de máquina, e é ele que um
    `INSERT` usaria.
    """
    proibido = set(INSTRUMENTO_DE_PAGAMENTO)
    achados = []
    for modelo in _modelos():
        for campo in _campos_concretos(modelo):
            for valor, _rotulo in getattr(campo, "choices", None) or []:
                for palavra in _palavras(str(valor)) & proibido:
                    achados.append(
                        f"{modelo.__name__}.{campo.name} = {valor!r} "
                        f"(por {palavra!r})"
                    )

    assert sorted(achados) == [], (
        "INVARIANTE 1 QUEBRADO: escolha de banco nomeia meio de pagamento.\n  "
        + "\n  ".join(sorted(achados))
    )


def test_nenhum_modulo_desta_celula_importa_meio_de_pagamento():
    """A célula não conhece nenhum SDK de cobrança, e não é por falta de vontade.

    Mede IMPORT, via `ast` — não texto cru. Um varredor de texto acusaria a
    própria prosa deste arquivo, que precisa escrever as palavras proibidas para
    poder proibi-las.
    """
    achados = []
    for caminho in APP.rglob("*.py"):
        if "migrations" in caminho.parts:
            continue
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom):
                nomes = [no.module or ""]
            else:
                continue
            for nome in nomes:
                if nome.split(".")[0].lower() in BIBLIOTECAS_DE_COBRANCA:
                    achados.append(f"{caminho.name}: import {nome}")

    assert achados == [], (
        "INVARIANTE 1 QUEBRADO: esta célula importou um meio de cobrança.\n  "
        + "\n  ".join(achados)
    )


# ---------------------------------------------------------------------------
# A frente que continua valendo às três da manhã: o PostgreSQL
# ---------------------------------------------------------------------------


@pytest.fixture
def aluno(db):
    return Pessoa.objects.create(
        id_da_plataforma="pes-1", email="aluno@exemplo.com", nome_exibido="Aluno"
    )


def _movimento(aluno, **campos):
    padrao = {
        "pessoa": aluno,
        "site_id": "escola-a",
        "occurred_at": timezone.now(),
        "dia_local": timezone.localdate(),
    }
    padrao.update(campos)
    return MovimentoDeCristais.objects.create(**padrao)


def test_cristal_entra_por_esforco_e_sai_comprando_cosmetico(aluno):
    """O caminho FELIZ, e ele existe para as recusas abaixo significarem algo.

    Sem esta contraprova, um banco que recusasse tudo passaria nos outros
    testes e a suíte diria "invariante mantido" sobre uma tabela inútil.
    """
    ganho = _movimento(
        aluno,
        delta=25,
        origem=MovimentoDeCristais.Origem.CONQUISTA,
        referencia="conquista:fundador",
    )
    gasto = _movimento(
        aluno,
        delta=-20,
        origem=MovimentoDeCristais.Origem.COMPRA_NA_LOJA,
        referencia="compra:moldura-madeira",
    )

    assert ganho.pk and gasto.pk
    assert MovimentoDeCristais.objects.filter(pessoa=aluno).count() == 2


def test_o_banco_recusa_cristal_que_nasce_de_uma_compra(aluno):
    """Um Cristal que ENTRA por compra é a definição de comprável. O banco recusa.

    Esta é a linha exata que alguém escreveria no dia em que a escola decidisse
    vender pacote de Cristais: `delta=+500, origem=compra`. Ela não chega a
    existir.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _movimento(
                aluno,
                delta=500,
                origem=MovimentoDeCristais.Origem.COMPRA_NA_LOJA,
                referencia="compra:pacote-de-500",
            )

    assert "cristal_positivo_nunca_vem_de_compra" in str(erro.value)


def test_o_banco_recusa_uma_origem_de_cristal_inventada(aluno):
    """O vocabulário é fechado no BANCO, não só nas `TextChoices` do Python.

    Escolha de Python é conferida pelo Django, e o Django só entra quando o
    caminho passa por ele. Este INSERT é SQL cru, do jeito que sai de um `psql`
    aberto numa madrugada de incidente ou de um script de migração de dados
    escrito às pressas. É a única frente que não depende de ninguém lembrar.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO gamificacao_movimentodecristais "
                    "(pessoa_id, site_id, delta, origem, referencia, "
                    " occurred_at, dia_local, criado_em) "
                    "VALUES (%s, %s, %s, %s, %s, NOW(), CURRENT_DATE, NOW())",
                    [aluno.pk, "escola-a", 1000, "compra_com_dinheiro", "cartao:4111"],
                )

    assert "origem_de_cristal_no_vocabulario_fechado" in str(erro.value)


def test_o_banco_recusa_um_debito_que_nao_e_compra_na_loja(aluno):
    """Cristal só SAI comprando cosmético. Não há outra porta de saída.

    É isto que torna a moeda intransferível na prática: uma "gorjeta" para
    outro aluno precisaria de um débito que não é compra, e ele não existe.
    Gorjeta de Cristais entre alunos está vetada por escrito (lei §8), e o veto
    nunca foi sobre idade: a intenção sobrevive no botão Parabéns.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _movimento(
                aluno,
                delta=-10,
                origem=MovimentoDeCristais.Origem.CONQUISTA,
                referencia="gorjeta:para-o-colega",
            )

    assert "cristal_negativo_so_com_referencia_de_compra" in str(erro.value)


def test_o_banco_recusa_debito_sem_a_referencia_da_compra(aluno):
    """Compra sem recibo é saldo sumindo sem explicação. O banco exige o recibo."""
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _movimento(
                aluno,
                delta=-10,
                origem=MovimentoDeCristais.Origem.COMPRA_NA_LOJA,
                referencia="sem-recibo",
            )

    assert "cristal_negativo_so_com_referencia_de_compra" in str(erro.value)


def test_o_escudo_nunca_esta_a_venda_nem_por_cristais():
    """Decisão fechada 7 da Sessão A, e a garantia é a AUSÊNCIA de um tipo de item.

    Vender proteção de sequência é a mecânica que transforma a criança em
    cliente ansioso: ela paga para não perder o que já construiu. O escudo é 1
    por mês, automático e grátis, e mora na `Sequencia` — não há tipo de
    cosmético que o represente, e o banco recusa um quinto tipo.
    """
    tipos = {valor for valor, _ in ItemCosmetico.Tipo.choices}

    assert not any(
        "escudo" in t or "protecao" in t or "imunidade" in t for t in tipos
    ), f"INVARIANTE 1 QUEBRADO: a loja passou a vender proteção. Tipos: {tipos}"

    campos_da_sequencia = {c.name for c in Sequencia._meta.get_fields()}
    assert "escudos" in campos_da_sequencia, (
        "o escudo saiu da `Sequencia`. Ele é 1 por mês, automático e grátis; se "
        "mudou de casa, confira que não virou item de loja no caminho."
    )
