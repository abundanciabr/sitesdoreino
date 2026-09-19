"""`/admin/encomendas/parametros/`, os números que a Fila do Primeiro Dólar obedece.

Quantas horas o aluno tem para responder, quantos dias dura a produção de um
personagem, quantas rodadas de proposta cada lado tem, qual é o piso de preço de
cada nível. Todos eles moram na célula `encomendas`, e esta tela é por onde o
mantenedor os muda sem esperar ninguém.

## Por que esta tela é obrigatória, e não conveniência

A lei da célula (`DECISAO-fila-do-primeiro-dolar.md` §3.8) diz que parâmetro é
DADO com histórico, nunca número em código, e o §9 dela chama de **critério de
morte 5** o dia em que um destes números voltar a viver no motor. Enquanto
trocar um prazo dependesse de um robô editar o semeador e esperar uma
publicação, a régua era código com aparência de dado. Esta tela é o que torna
aquela lei verdade.

## Mudar é ACRESCENTAR uma linha, e a tela diz isso na cara

Nada aqui sobrescreve nada. Cada mudança grava uma linha nova, com o valor, o
motivo escrito e o nome de quem mudou, e ela vale de agora em diante: uma
proposta feita às 14h continua obedecendo ao número que valia às 14h, mesmo que
ele mude às 15h. Quem garante isso não é este arquivo, é o banco da `encomendas`
(gatilho que recusa `UPDATE` e `DELETE`) e a leitura por `vigente_em(agora)` que
o próprio motor usa.

## Onde o dado mora, e por que não aqui

Na `encomendas`, que é a dona da fila. Esta tela **não guarda nada**: lê pela
porta de máquina, aplica UM gesto, e mostra o que voltou. Guardar uma cópia aqui
seria o mesmo fato em dois lugares (a lei anti-duplicação do `CLAUDE.md`), e no
dia em que as duas discordassem esta tela mostraria um prazo e o aluno cumpriria
outro.

**Nem as FRASES são daqui**, e essa é a diferença em relação a
`/admin/economia/`. Lá o contrato manda slug e as frases nascem na tela, porque
o site serve três idiomas. Aqui a descrição de cada chave viaja pela porta, já
em português, pela mesma exceção declarada que as conquistas usam: estes números
só aparecem no bastidor do mantenedor, e um catálogo de trinta e cinco frases
copiado para cá envelheceria calado no primeiro parâmetro novo da célula. O que
esta tela acrescenta é a UNIDADE de cada tipo, que é apresentação, e não dado.

## Quem autoriza é ESTA célula

A `encomendas` não assina sessão ([INV-P12]) e o Bearer da porta dela prova só
QUEM CHAMA. O crachá que vale é o desta área, que a porta do `/admin/` já exige.
É o mesmo desenho de `/admin/economia/` e de `/admin/menu/`.

## Dois graus de crachá, e a tela precisa do alto (`armadilhas/318`)

Ler a régua e MUDAR a régua da fila inteira não podem ser o mesmo poder. A porta
da `encomendas` separa `TOKENS_ACEITOS_ADMIN` (ler) de `TOKENS_ESCRITA_ADMIN`
(gravar) e recusa com 403 quem tem o baixo e pediu o alto. Se o segundo não
estiver no servidor, a tela ABRE e mostra tudo, e o botão de gravar responde em
português dizendo qual roteiro rodar. Erro cru nesse caminho seria um leigo
diante de um 403.

## Por que é formulário simples, sem script

Cada gesto é um POST que recarrega a página, como em `/admin/economia/` e
`/admin/menu/`, pelas mesmas três razões: o que se vê é o que está gravado; a
política de segurança desta área exige um hash na CSP para cada script embutido
(`armadilhas/199`); e o mantenedor é leigo, e um formulário com o nome do gesto
escrito no botão não tem como ser mal entendido.
"""

from __future__ import annotations

from datetime import datetime

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import EncomendasClient
from .views import _auditar

# A UNIDADE de cada tipo de chave, em português de gente. É a única coisa desta
# tela que fala sobre os parâmetros, e ela fala do TIPO (são seis), nunca da
# chave (são trinta e cinco): um catálogo por chave seria a cópia que a docstring
# acima proíbe, e envelheceria no primeiro parâmetro novo da célula.
#
# Tipo desconhecido mostra o valor cru, sem unidade, feio e honesto, do mesmo
# jeito que a economia mostra o slug de uma regra sem tradução. Esconder uma
# linha da tela dele seria pior.
UNIDADE_DO_TIPO = {
    "horas": "horas",
    "dias": "dias",
    "inteiro": "",
    "hora_do_dia": "(hora do dia, no formato 08:00)",
    "enum": "(uma escolha escrita por extenso)",
    "centavos": "centavos (500 são cinco reais)",
}

# O que dizer de uma chave que ainda não tem linha nenhuma. Vale para as três do
# piso de preço, que nascem assim de propósito (`PLANO-AREA-DE-NEGOCIACAO.md` §7
# e §9: o número sai do piloto de papel, e chutar um agora seria inventá-lo para
# depois defendê-lo), e vale para qualquer outra que um dia nasça vazia.
#
# SEM ESTA FRASE, um campo em branco no meio de trinta e quatro números parece
# defeito da tela, e o mantenedor procuraria o problema no lugar errado em vez
# de entender que a decisão ainda é dele.
SEM_NUMERO_AINDA = (
    "Ainda sem número, e isso não é defeito. Enquanto estiver vazio, nada no "
    "site usa este valor: nenhum aviso aparece para o aluno e nenhuma proposta "
    "é impedida. Escreva o número quando você o tiver."
)


def _data(bruta) -> str:
    """A data como o mantenedor a lê, e não como o JSON a escreve.

    A porta devolve o instante no formato do contrato (`2026-01-01T00:00:00Z`),
    que é o certo para uma máquina e ilegível para uma pessoa. Isto NÃO é
    guardar uma cópia: nada aqui é gravado, e o valor continua vindo da célula a
    cada visita. É a mesma diferença que a `UNIDADE_DO_TIPO` acima carrega,
    apresentação, e não dado.

    Formato que não der para ler volta como veio, inteiro. Uma tela que
    escondesse o instante por não saber formatá-lo tiraria do mantenedor
    justamente o dado que responde "desde quando este número vale?".
    """
    texto = str(bruta or "")
    if not texto:
        return ""
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return texto


def _linha(parametro: dict) -> dict:
    """Um parâmetro como a tela o desenha: o valor de agora e a viagem até aqui."""
    vigente = parametro.get("vigente") or {}
    historico = parametro.get("historico") or []
    return {
        "chave": str(parametro.get("chave", "")),
        "descricao": str(parametro.get("descricao") or parametro.get("chave", "")),
        "unidade": UNIDADE_DO_TIPO.get(str(parametro.get("tipo", "")), ""),
        "valor": str(vigente.get("valor") or ""),
        "desde": _data(vigente.get("desde")),
        "motivo": str(vigente.get("motivo") or ""),
        "quem": str(vigente.get("quem") or ""),
        "tem_valor": bool(vigente.get("valor")),
        # As linhas ANTERIORES, da mais nova para a mais velha. A que está
        # valendo sai da lista porque ela já é o cartão inteiro logo acima, e
        # repeti-la faria parecer que houve duas mudanças iguais.
        "anteriores": [
            {
                "valor": str(linha.get("valor") or ""),
                "desde": _data(linha.get("desde")),
                "motivo": str(linha.get("motivo") or ""),
                "quem": str(linha.get("quem") or ""),
            }
            for linha in historico
            if linha.get("desde") != vigente.get("desde")
        ],
    }


def _contexto(request, parametros, erro="", recado=""):
    """O que a tela desenha, e a ordem não é alfabética por acaso.

    As chaves SEM número vêm primeiro. É a única separação desta tela, ela é
    CALCULADA do que a célula respondeu (nunca de uma lista escrita aqui, que
    envelheceria), e ela existe porque é exatamente o que ele precisa decidir: um
    campo vazio no meio de trinta e quatro números preenchidos não seria
    encontrado nunca.
    """
    linhas = [_linha(p) for p in parametros]
    return {
        "admin": request.admin,
        "sem_numero": [linha for linha in linhas if not linha["tem_valor"]],
        "com_numero": [linha for linha in linhas if linha["tem_valor"]],
        "aviso_sem_numero": SEM_NUMERO_AINDA,
        "total": len(linhas),
        "erro": erro,
        "recado": recado,
    }


def _sem_encomendas(request, status=200):
    """A tela abre mesmo sem o par de tokens, e diz o que falta.

    Fail-OPEN na leitura, como em `/admin/economia/`: uma tela de operação que
    não abre é inútil justamente quando você precisa dela. E o que falta é um
    passo DELE dentro do servidor, então a tela nomeia o passo.
    """
    return render(
        request,
        "admin/parametros_da_fila.html",
        {"admin": request.admin, "sem_encomendas": True},
        status=status,
    )


@require_GET
def parametros_da_fila(request):
    """A tela: um cartão por número, com o histórico de cada um."""
    parametros = EncomendasClient().parametros()
    if parametros is None:
        return _sem_encomendas(request)
    return render(
        request,
        "admin/parametros_da_fila.html",
        _contexto(request, parametros, recado=request.GET.get("recado", "")),
    )


@require_POST
def parametros_da_fila_mudar(request):
    """Acrescenta UMA linha nova ao histórico de um número, e volta para a tela.

    Padrão POST-redirect-GET, como nas outras telas de escrita desta área, e
    aqui ele é mais que higiene: repetir este gesto NÃO é inofensivo, porque
    cada envio grava uma linha de histórico nova. Sem o redirecionamento, um F5
    depois de gravar poria duas linhas idênticas na tabela, e a tabela é
    append-only: não haveria como desfazer a segunda.

    O AUTOR NÃO É DIGITADO, e a ausência do campo é decisão: quem grava é quem
    está logado nesta área, e um campo aberto convidaria a escrever o nome de
    outra pessoa numa tabela que ninguém pode corrigir depois.
    """
    chave = (request.POST.get("chave") or "").strip()
    valor = (request.POST.get("valor") or "").strip()
    motivo = (request.POST.get("motivo") or "").strip()
    if not chave:
        return _voltar_com_erro(request, "não veio o nome do número")
    if not valor:
        return _voltar_com_erro(
            request, "escreva o valor novo: um campo vazio não muda nada"
        )
    if not motivo:
        return _voltar_com_erro(
            request,
            "escreva por que você está mudando. É o que a próxima pessoa (ou "
            "você mesmo daqui a seis meses) vai ler para entender este número.",
        )

    quem = request.admin.get("id") or request.admin.get("email") or ""
    situacao, frase = EncomendasClient().mudar(chave, valor, motivo, quem)
    if situacao == EncomendasClient.OK:
        _auditar(request, Registro.MUDAR_PARAMETRO, chave, Registro.OK, motivo)
        return HttpResponseRedirect(f"{reverse('parametros_da_fila')}?recado=gravado")

    desfecho = (
        Registro.RECUSADO_PELA_CELULA
        if situacao == EncomendasClient.RECUSADO
        else Registro.NAO_RESPONDEU
    )
    _auditar(request, Registro.MUDAR_PARAMETRO, chave, desfecho, frase)
    return _voltar_com_erro(
        request,
        frase,
        status=422 if situacao == EncomendasClient.RECUSADO else 503,
    )


def _voltar_com_erro(request, frase: str, status: int = 400):
    """A tela de volta, com o que ESTÁ GRAVADO e o erro por cima.

    Nunca com o valor que não pegou: mostrar o número recusado faria a página
    discordar do motor, e é sobre este número que ele vai confiar depois.
    """
    parametros = EncomendasClient().parametros()
    if parametros is None:
        return _sem_encomendas(request, status=503)
    return render(
        request,
        "admin/parametros_da_fila.html",
        _contexto(request, parametros, erro=frase),
        status=status,
    )
