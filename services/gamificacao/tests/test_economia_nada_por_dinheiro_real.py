"""INVARIANTE 1 DA ECONOMIA — nada nesta célula se compra com dinheiro real.

Lei: `docs/decisoes/DECISAO-gamificacao.md` §3.1 e §8; `PLANO` §10.5. A frase
inteira, com as palavras dela: *"Nenhum item, moeda, proteção ou vantagem se
compra. Cristais são earn-only por construção do banco (`CheckConstraint`), não
por convenção."*

**Este teste nunca se flexibiliza.** Se um dia ele precisar de exceção, isso não
é um teste chato: é o critério de morte nº 2 e nº 6 da lei acontecendo, e a
resposta certa é parar e reabrir a decisão com o mantenedor.

POR QUE ELE NASCE AQUI, NO PR DAS TABELAS
------------------------------------------
Porque é aqui que a promessa vira mecanismo. A escola vende para famílias, o
público é criança, e a diferença entre "nós não vendemos vantagem" dito num
documento e a mesma frase conferida pelo PostgreSQL é a diferença entre uma
intenção e uma garantia. Documento não sobrevive a seis meses e quatro sessões
diferentes (`RETROSPECTIVA-FASE-D` §2); restrição de banco sobrevive.

O QUE ELE MEDE, EM QUATRO FRENTES
----------------------------------
1. **Instrumento de pagamento** — nenhum campo, de tipo nenhum, nomeia cartão,
   boleto, Pix, gateway ou fatura. Não há razão legítima para esta célula
   conhecer um.
2. **Quantia em dinheiro** — nenhum campo que CARREGUE valor (número, texto,
   decimal) nomeia real, dólar, centavo ou preço.
3. **Import** — nenhum módulo desta célula conhece um SDK de cobrança.
4. **O banco** — o PostgreSQL recusa o INSERT, venha ele de onde vier. É esta
   frente que continua valendo numa madrugada de incidente, com alguém logado
   no `psql`.

POR QUE A FRENTE 2 OLHA O TIPO DO CAMPO, E POR QUE ISSO NÃO É UMA BRECHA
-------------------------------------------------------------------------
Existe um campo legítimo nesta célula com a palavra "dinheiro" no nome:
`ConquistaDefinicao.envolve_dinheiro`. Ele não guarda dinheiro — é um booleano
que diz *"este marco fala do aluno RECEBENDO dinheiro na vida real"*, e serve
para o banco poder EXIGIR faixa 13+ e validação por adulto
(`marco_de_dinheiro_e_13mais_e_so_adulto_valida`). Ou seja: é uma trava de
proteção de menor, o oposto de uma violação.

A régua honesta, então, não é a palavra — é o CARREGADOR. Um booleano não
guarda quantia; uma coluna numérica ou de texto guarda. Por isso a frente 2 mede
só os campos que poderiam segurar um valor, e a frente 1 (instrumento de
pagamento) continua valendo para TODO campo, booleano incluído: um
`aceita_cartao = BooleanField()` seria recusado na hora.

A alternativa seria uma lista de exceções ao lado do guarda — e lista de exceção
é por onde guarda morre, uma linha de cada vez.
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

# QUANTIA EM DINHEIRO — proibida em campo que CARREGUE valor. Note que
# `cristais`, `custo` e `compra` não estão aqui, e não é descuido: comprar uma
# moldura com Cristais ganhos é exatamente o que a loja existe para fazer. O
# proibido é o real, o dólar, o centavo e o preço.
QUANTIA_EM_DINHEIRO = (
    "preco",
    "precos",
    "price",
    "prices",
    "real",
    "reais",
    "brl",
    "centavo",
    "centavos",
    "cents",
    "dinheiro",
    "dolar",
    "dolares",
    "usd",
    "valor",
    "valores",
    "moeda",
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


def _carrega_valor(campo) -> bool:
    """O campo pode SEGURAR uma quantia? Booleano não segura; número e texto sim."""
    return campo.get_internal_type() != "BooleanField"


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


def test_nenhum_campo_que_carrega_valor_nomeia_dinheiro_real():
    """Não existe onde guardar um preço em reais. Nem por engano, nem por pressa.

    A tentação concreta tem endereço: `ItemCosmetico`. No dia em que a escola
    quiser faturar mais, o caminho de menor esforço é uma coluna
    `preco_em_reais` ao lado do `custo_em_cristais`, e a partir dali a loja
    aceita as duas moedas sem que ninguém precise decidir nada. Esta asserção é
    o que transforma esse caminho de menor esforço numa CI vermelha.
    """
    achados = []
    for modelo in _modelos():
        for campo in _campos_concretos(modelo):
            if not _carrega_valor(campo):
                continue
            for palavra in _palavras(campo.name) & set(QUANTIA_EM_DINHEIRO):
                achados.append(
                    f"{modelo.__name__}.{campo.name} "
                    f"[{campo.get_internal_type()}] (por {palavra!r})"
                )

    assert sorted(achados) == [], (
        "INVARIANTE 1 QUEBRADO: campo desta célula carrega dinheiro real.\n  "
        + "\n  ".join(sorted(achados))
        + "\n\nA lei §3.1 diz que nenhum item, moeda, proteção ou vantagem se "
        "compra. Ver `DECISAO-gamificacao.md` §8 e o critério de morte nº 2."
    )


def test_nenhuma_escolha_declarada_nomeia_um_meio_de_pagamento():
    """O vocabulário que o banco guarda também não conhece dinheiro.

    Mede os VALORES das `TextChoices` (o que fica gravado na coluna), não os
    rótulos: rótulo é português para humano, e ele pode legitimamente dizer
    "marco que envolve dinheiro". Valor é vocabulário de máquina, e é ele que um
    `INSERT` usaria.
    """
    proibido = set(INSTRUMENTO_DE_PAGAMENTO) | set(QUANTIA_EM_DINHEIRO)
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
        "INVARIANTE 1 QUEBRADO: escolha de banco nomeia dinheiro real.\n  "
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
    Gorjeta entre menores está vetada por escrito (lei §8).
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
