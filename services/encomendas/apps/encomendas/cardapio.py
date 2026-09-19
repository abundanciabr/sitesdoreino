"""O cardápio do cliente e o briefing blindado: por onde um pedido nasce.

Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §5.1 (os três cartões) e §5.2
(o briefing blindado). Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md`
§3.4, que manda a escola ser a primeira cliente e o dinheiro ficar por último.

O `apps/core/views.py` do degrau 2.7 escreveu, com todas as letras, o que
faltava para este arquivo existir: *"abrir encomenda da escola precisa do
briefing com a lista FECHADA de entregáveis, e essa lista é produto da Fase 3"*.
É esta lista, e é esta fase.

O CARTÃO DECIDE TUDO O QUE O CLIENTE NÃO ESCOLHE
------------------------------------------------
O cliente escolhe o CARTÃO, e nunca o nível do modelador (§5.1, e é o critério
de morte 1 da lei §9). O nível sai de `Encomenda.NIVEL_DO_CARTAO`, o prazo de
produção sai do parâmetro `prazo_producao.<cartao>` e a lista de entregáveis
possíveis sai da letra miúda do cartão. Nenhum dos três é campo de formulário.

NENHUM PREÇO APARECE AQUI, E A AUSÊNCIA É A LEI
------------------------------------------------
Até 04/09/2026 o cardápio tinha preço de tabela. A negociação trocou isso: o
valor só existe depois do Acordo (`PLANO-AREA-DE-NEGOCIACAO.md` §5), e o piso
por nível nasce sem número de propósito. Um preço escrito aqui seria um número
inventado que a tela defenderia como se fosse decisão do dono.

O QUE "BLINDADO" QUER DIZER, EM CÓDIGO
---------------------------------------
[INV-ENC-S1] proíbe texto livre entre cliente e aluno fora dos campos
estruturados, e [INV-ENC-S3] proíbe dado de contato atravessando essa fronteira.
`models.Encomenda.briefing` já anotava que *"o guarda deles nasce na Fase 3"*.
Ele nasce aqui, e são duas metades:

1. **Não existe campo de contato.** Nome da peça, onde vai ser usada, estilo,
   entregáveis e observações. Mais nada entra no dicionário gravado, porque quem
   monta o dicionário é `preparar`, e não o formulário.
2. **O campo livre é peneirado.** As observações são o único texto que o cliente
   escreve, e é por ele que um e-mail, um telefone ou um `@` de rede social
   passariam para o outro lado. `sem_contato` recusa os quatro, dizendo o que
   aconteceu e o que fazer. Sem essa peneira, "sem campo de contato" seria uma
   promessa de formulário, e formulários não seguram nada.

O QUE NÃO NASCE AQUI, E O MOTIVO
---------------------------------
**As imagens de referência do §5.2.** Elas são arquivo, e armazenamento de
arquivo é o degrau 5.1 da escada. Aceitar endereço de imagem em texto seria
abrir, com outro nome, o campo livre que a peneira acabou de fechar.

**O limite de triângulos de cada cartão.** É número, é do mantenedor, e não
está no vocabulário de parâmetros. A letra miúda diz o que cada cartão aceita
sem inventar a conta que ninguém decidiu.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from apps.encomendas import mural
from apps.encomendas.models import Encomenda, MudancaDeStatus, Parametro

# As recusas, com nome. A tela traduz cada uma em uma frase que diz o que
# aconteceu e o que fazer; aqui elas são código, para o teste poder afirmar
# qual recusa aconteceu em vez de comparar texto de tela.
CARTAO_DESCONHECIDO = "cartao_desconhecido"
SEM_NOME_DA_PECA = "sem_nome_da_peca"
NOME_DA_PECA_LONGO_DEMAIS = "nome_da_peca_longo_demais"
ONDE_FORA_DA_LISTA = "onde_fora_da_lista"
ESTILO_FORA_DA_LISTA = "estilo_fora_da_lista"
SEM_ENTREGAVEL = "sem_entregavel"
ENTREGAVEL_FORA_DO_CARTAO = "entregavel_fora_do_cartao"
OBSERVACOES_LONGAS_DEMAIS = "observacoes_longas_demais"
CONTATO_NO_BRIEFING = "contato_no_briefing"

MOTIVO_DA_ABERTURA = "o cliente descreveu o projeto pelo cardapio"

# O TETO DO TEXTO LIVRE DESTA CÉLULA, e ele é DADO, não número em código.
#
# O `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §5.2 pede "observações até 500
# caracteres", e 500 é exatamente o que o mantenedor já gravou em
# `limite_da_justificativa` para o único campo livre que existia antes deste.
# Escrever 500 aqui seria congelar em PR um número que ele edita numa tela, e o
# guarda `tests/test_parametros_sao_dado.py` reprova isso na cara (critério de
# morte 5 da lei §9): ele reprovou este, quando nasceu assim.
#
# **Uma chave para os dois lados, e não duas.** A régua é a mesma pergunta,
# "quanto texto corrido esta célula aceita de uma pessoa", e ela vale para o
# aluno que justifica uma proposta e para o cliente que descreve a peça. Duas
# chaves com o mesmo significado divergiriam no dia em que ele mudasse uma.
CHAVE_DO_TETO_DO_TEXTO = "limite_da_justificativa"


def teto_do_texto(agora, *, site_id: str) -> int:
    return Parametro.inteiro_vigente(CHAVE_DO_TETO_DO_TEXTO, agora, site_id=site_id)


@dataclass(frozen=True)
class CartaoDoCardapio:
    """Um cartão do cardápio, do jeito que o cliente o lê.

    `prazo_producao` não é campo: ele é parâmetro do mantenedor, lido em
    `listar` no instante da consulta. Guardá-lo aqui seria uma segunda fonte da
    verdade, e a que não muda quando ele mudar o valor pela tela.
    """

    valor: str
    titulo: str
    o_que_e: str
    letra_miuda: tuple[str, ...]
    entregaveis: tuple[str, ...]


# Os entregáveis possíveis, e o nome que o cliente lê. A lista é fechada porque
# é dela que toda proposta marca um subconjunto ([INV-ENC-N1], via
# `negociacao.entregaveis_do_briefing`): um entregável inventado no formulário
# viraria um item que ninguém sabe conferir na entrega.
ENTREGAVEIS = {
    "modelo_fbx": "Modelo em .fbx",
    "texturas": "Texturas",
    "arquivo_fonte": "Arquivo fonte (.blend)",
    "previa": "Imagem de prévia",
    "rig": "Rig pronto para animar",
    "animacao": "Animação",
}

# Onde a peça vai ser usada. Fechada de propósito: é o que diz ao modelador
# para qual plataforma construir, e uma caixa de texto aqui seria a mesma
# conversa livre que o [INV-ENC-S1] fecha.
ONDE_VAI_SER_USADA = {
    "ugc": "Item UGC do Roblox",
    "jogo_proprio": "Um jogo meu",
    "outro": "Outro uso",
}

ESTILOS = {
    "realista": "Realista",
    "estilizado": "Estilizado",
    "cartoon": "Cartoon",
    "low_poly": "Low poly",
}

CARTOES = {
    Encomenda.Cartao.ITEM_SIMPLES: CartaoDoCardapio(
        valor=Encomenda.Cartao.ITEM_SIMPLES,
        titulo="Item simples",
        o_que_e=(
            "Um prop, uma arma ou um acessório rígido: o que fica parado no "
            "corpo do personagem ou na mão dele."
        ),
        letra_miuda=(
            "Uma peça por pedido.",
            "Sem rig e sem animação.",
            "Textura simples, sem material PBR.",
            "As correções inclusas são as que o acordo combinar.",
        ),
        entregaveis=("modelo_fbx", "texturas", "arquivo_fonte", "previa"),
    ),
    Encomenda.Cartao.VESTIVEL_OU_VEICULO: CartaoDoCardapio(
        valor=Encomenda.Cartao.VESTIVEL_OU_VEICULO,
        titulo="Vestível ou veículo",
        o_que_e=(
            "Cabelo, roupa em camadas ou veículo: o que acompanha o corpo ou "
            "tem partes que se encaixam."
        ),
        letra_miuda=(
            "Uma peça por pedido.",
            "Sem animação.",
            "Textura PBR quando o pedido precisar.",
            "As correções inclusas são as que o acordo combinar.",
        ),
        entregaveis=("modelo_fbx", "texturas", "arquivo_fonte", "previa"),
    ),
    Encomenda.Cartao.PERSONAGEM: CartaoDoCardapio(
        valor=Encomenda.Cartao.PERSONAGEM,
        titulo="Personagem",
        o_que_e=(
            "Corpo ou cabeça completos, com a opção de rig e de animação. É o "
            "cartão mais alto do cardápio."
        ),
        letra_miuda=(
            "Uma peça por pedido.",
            "Rig e animação entram quando você os marcar nos entregáveis.",
            "Textura PBR.",
            "As correções inclusas são as que o acordo combinar.",
        ),
        entregaveis=(
            "modelo_fbx",
            "texturas",
            "arquivo_fonte",
            "previa",
            "rig",
            "animacao",
        ),
    ),
}

# O cartão do cardápio e a chave do parâmetro têm nomes diferentes desde a lei
# §6, e a tradução mora aqui, em um lugar só. Escrevê-la dentro da função que
# lê o prazo faria a próxima leitora procurar por que `personagem` funciona e
# `vestivel_ou_veiculo` não.
PARAMETRO_DO_PRAZO = {
    Encomenda.Cartao.ITEM_SIMPLES: "prazo_producao.simples",
    Encomenda.Cartao.VESTIVEL_OU_VEICULO: "prazo_producao.vestivel_veiculo",
    Encomenda.Cartao.PERSONAGEM: "prazo_producao.personagem",
}

# A peneira do campo livre. Quatro formas, porque são as quatro por onde um
# contato passa: o e-mail, o endereço de página, o arroba de rede social e a
# sequência longa de dígitos que é telefone em qualquer formatação.
_FORMAS_DE_CONTATO = (
    re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+"),
    re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE),
    re.compile(r"(?<![^\s(])@[A-Za-z0-9_.]{3,}"),
    re.compile(r"(?:\d[\s().-]*){8,}"),
)


def sem_contato(texto: str) -> bool:
    """Verdadeiro quando o texto não carrega nenhuma das quatro formas.

    **Peneirar não é adivinhar intenção.** Quem quiser burlar isto com palavras
    consegue, e este arquivo não finge o contrário: quem lê tudo o que os dois
    lados trocam é o plantão ([INV-ENC-S1], `negociacao.para_o_plantao`). O que
    a peneira impede é o caso comum e silencioso, o cliente que escreve o
    telefone dele sem saber que não devia.
    """
    return not any(forma.search(texto) for forma in _FORMAS_DE_CONTATO)


def prazo_de_producao_em_dias(cartao: str, agora, *, site_id: str) -> int:
    """Os dias de produção daquele cartão, do parâmetro do mantenedor."""
    return Parametro.inteiro_vigente(PARAMETRO_DO_PRAZO[cartao], agora, site_id=site_id)


def listar(agora, *, site_id: str) -> tuple[tuple[CartaoDoCardapio, int], ...]:
    """Os três cartões com o prazo de produção vigente de cada um.

    A ordem é a do cardápio em papel (§5.1), do mais simples ao mais alto, e ela
    é a ordem do dicionário: ordenar por prazo ou por nome trocaria a escada que
    o cliente precisa enxergar por um critério que não significa nada para ele.
    """
    return tuple(
        (cartao, prazo_de_producao_em_dias(valor, agora, site_id=site_id))
        for valor, cartao in CARTOES.items()
    )


def preparar(cartao: str, respostas: dict, agora, *, site_id: str) -> tuple[str, dict]:
    """Confere o formulário e devolve (recusa, briefing) com o briefing pronto.

    A ORDEM DAS RECUSAS É A ORDEM DAS PERGUNTAS: primeiro se o cartão existe,
    depois se a peça tem nome, depois se as escolhas fechadas estão dentro das
    listas, e só então os campos livres. Uma recusa por vez, para a tela poder
    apontar o campo.

    `agora` e `site_id` entram por causa do teto do texto, que é parâmetro e é
    lido no instante do gesto, como todo gesto desta célula faz: um teto mudado
    às 15h não reescreve um briefing enviado às 14h (lei §3.8).

    O briefing devolvido é MONTADO aqui, chave por chave, e não copiado do que
    chegou. É essa montagem que faz "sem campo de contato" valer: um campo a
    mais no formulário não vira um campo a mais no banco.
    """
    if cartao not in CARTOES:
        return CARTAO_DESCONHECIDO, {}
    teto = teto_do_texto(agora, site_id=site_id)

    nome = (respostas.get("nome_da_peca") or "").strip()
    if not nome:
        return SEM_NOME_DA_PECA, {}
    if len(nome) > teto:
        return NOME_DA_PECA_LONGO_DEMAIS, {}

    onde = (respostas.get("onde_vai_ser_usada") or "").strip()
    if onde not in ONDE_VAI_SER_USADA:
        return ONDE_FORA_DA_LISTA, {}

    estilo = (respostas.get("estilo") or "").strip()
    if estilo not in ESTILOS:
        return ESTILO_FORA_DA_LISTA, {}

    escolhidos = tuple(respostas.get("entregaveis") or ())
    if not escolhidos:
        return SEM_ENTREGAVEL, {}
    possiveis = CARTOES[cartao].entregaveis
    if any(item not in possiveis for item in escolhidos):
        return ENTREGAVEL_FORA_DO_CARTAO, {}

    observacoes = (respostas.get("observacoes") or "").strip()
    if len(observacoes) > teto:
        return OBSERVACOES_LONGAS_DEMAIS, {}
    if not sem_contato(f"{nome} {observacoes}"):
        return CONTATO_NO_BRIEFING, {}

    return "", {
        "nome_da_peca": nome,
        "onde_vai_ser_usada": onde,
        "estilo": estilo,
        # A ordem do cartão, e não a que o formulário mandou: duas encomendas
        # com os mesmos entregáveis ficam iguais no banco, e a proposta que os
        # compara não depende da ordem em que alguém clicou nas caixas.
        "entregaveis": [item for item in possiveis if item in escolhidos],
        "observacoes": observacoes,
    }


def abrir(
    *,
    site_id: str,
    cliente_id: str,
    cartao: str,
    briefing: dict,
    autoriza_portfolio: bool,
) -> Encomenda:
    """Põe o pedido na pista que o nível dele manda, com rastro de nascimento.

    Quem escolhe a pista é `mural.nascer`, a única porta de nascimento da
    célula, e por isso este gesto não repete a regra de rota. O que ele
    acrescenta é a LINHA DE HISTÓRICO do nascimento: sem ela, o primeiro fato da
    vida de um pedido seria invisível, e a mediação que lesse o histórico
    começaria a leitura no meio.

    **A origem é `escola`**, e é a lei §3.4 em código: até a Fase 3 a escola é a
    cliente, e o banco só aceita a confirmação de pagamento pelo plantão nessa
    origem (`confirmacao_pelo_plantao_so_para_a_escola`). Aceitar outra origem
    aqui abriria um pedido que ninguém consegue levar à produção.
    """
    projeto = mural.nascer(
        site_id=site_id,
        origem=Encomenda.Origem.ESCOLA,
        cliente_id=cliente_id,
        cartao=cartao,
        briefing=briefing,
        autorizacao_portfolio=autoriza_portfolio,
    )
    MudancaDeStatus.objects.create(
        encomenda=projeto,
        site_id=site_id,
        de="",
        para=projeto.status,
        ator_id=cliente_id,
        motivo=MOTIVO_DA_ABERTURA,
    )
    return projeto
