"""`/admin/placar/talentos/` — a rede de talentos, e o laço que ela fecha.

Degrau 17 do `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`: *"contagens digitadas
(alunos selecionados, estúdios parceiros, encaixes) como medição; o laço de
talentos sai do cinza"*.

O laço de talentos é o quarto laço do Scale OS (documento 2, §45): mais alunas
levam a mais talentos, que levam a mais estúdios, que levam a mais
oportunidades, que levam a mais resultados, que aumentam o valor da escola, que
traz mais alunas. Ele era a única parte do sistema que não existia em tela
nenhuma. Esta tela o desenha inteiro e põe, ao lado de cada etapa, o número que
a casa tem hoje. Sair do cinza é isto: as etapas medidas mostram o número, e as
que não têm número dizem em português que ainda não têm, e qual é o gesto.

## As três leis desta tela

**1. A contagem digitada é um REGISTRO do livro, nunca uma tabela.** Ninguém
consegue medir sozinho quantas alunas a escola escolheu, quantos estúdios
aceitaram, quantos encaixes aconteceram: isso mora fora do sistema, numa
conversa. Então a escola conta e digita, e o que guarda é o livro, pelo mesmo
campo `foto` que a foto da semana já usa (`mudancas.py`, degrau 6): uma
`medicao` com a linha `nome=valor; nome=valor`. Nenhum banco novo (plano §9),
nenhum estado escrito à mão, e a data em que a contagem foi feita sai da data
do registro, não de um campo que alguém preenche.

**2. Esta tela não escreve nada.** Como a reunião de segunda, o que ela produz
é o PEDIDO PARA O ROBÔ: um bloco de texto que o mantenedor cola numa sessão, e
que vira registro por PR. Recarregar a página apaga o que foi digitado, e isso
é dito na tela: o que vale é o que chegar ao livro.

**3. A foto que este pedido monta é COMPLETA.** A linha `foto` leva junto os
números que o placar já mede sozinho hoje. O bloco "o que mudou" da capa
compara a foto mais recente do livro com o que a tela mostra agora; uma foto só
com as três contagens da rede seria a mais recente sem ter os outros números, e
todo o resto do placar apareceria como "sem par" na segunda-feira seguinte.
Levar o placar junto custa uma linha e evita esse estrago.

## O que esta tela recusa

Nenhum marketplace, nenhuma tabela de estúdio, nenhuma ficha de talento (plano
§9: "nenhum marketplace automatizado: talentos começam à mão"). E nenhum número
inventado: estúdio parceiro nenhum é zero contado ou "nunca contado", que são
coisas diferentes e aparecem diferentes na tela.
"""

from __future__ import annotations

import datetime as dt

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .direcao import ler_registros
from .mudancas import FRESCOR_PADRAO, foto_em_texto, ler_foto
from .placar import diretorio_dos_cartoes, ler_cartao, montar_o_placar, site_de

#: As três contagens que a escola digita, na ordem em que o laço gira. A chave
#: é o nome do campo do formulário; o valor é o nome do cartão, que é também a
#: chave dentro da linha `foto` do livro.
DIGITADAS = (
    ("talentos", "alunos-selecionados-para-a-rede"),
    ("estudios", "estudios-parceiros"),
    ("encaixes", "encaixes-com-estudio"),
)

#: Os seis passos do laço (Scale OS 2 §45). O sétimo é o retorno ao primeiro, e
#: por isso não tem cartão próprio: quem o desenha é a tela.
#:
#: `origem` diz de onde o número daquele passo vem, e é o que decide o estado:
#: `ao-vivo` (a célula `alunos` responde agora), `digitada` (a escola conta e o
#: livro guarda) e `cartao` (o cartão já existe e ainda não tem fonte nenhuma;
#: quem explica o porquê é o próprio cartão, não esta tela).
LACO = (
    {
        "chave": "alunas",
        "titulo": "Mais alunas",
        "porque": "O laço começa na escola cheia: sem alunas não há talento para escolher.",
        "cartao": "alunos-na-plataforma",
        "origem": "ao-vivo",
    },
    {
        "chave": "talentos",
        "titulo": "Mais talentos",
        "porque": "Das alunas, a escola escolhe as que já podem ser apresentadas a um estúdio.",
        "cartao": "alunos-selecionados-para-a-rede",
        "origem": "digitada",
    },
    {
        "chave": "estudios",
        "titulo": "Mais estúdios",
        "porque": "Talento bom atrai estúdio: cada aluna apresentada é a prova que abre a próxima porta.",
        "cartao": "estudios-parceiros",
        "origem": "digitada",
    },
    {
        "chave": "encaixes",
        "titulo": "Mais oportunidades",
        "porque": "Estúdio parceiro só vira oportunidade quando uma aluna de fato começa um trabalho.",
        "cartao": "encaixes-com-estudio",
        "origem": "digitada",
    },
    {
        "chave": "resultados",
        "titulo": "Mais resultados",
        "porque": "O trabalho feito vira resultado profissional da aluna, que é a primeira estrela-guia da escola.",
        "cartao": "alunos-com-resultado-profissional",
        "origem": "cartao",
    },
    {
        "chave": "valor",
        "titulo": "Mais valor da Meshcraft",
        "porque": "Aluna com resultado é a melhor propaganda que existe, e é ela que traz a próxima turma: o laço fecha aqui e recomeça em cima.",
        "cartao": "margem-mensal",
        "origem": "cartao",
    },
)


def _data(texto: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None


def ultima_medicao(registros: list[dict] | None, nome: str) -> dict | None:
    """A contagem mais recente daquele cartão no livro; `None` se não há nenhuma.

    Olha TODA `medicao` com `foto`, e não só a foto mais recente: uma contagem
    da rede feita em agosto continua sendo a última que existe, mesmo que a
    foto da semana passada não a tenha levado junto. É por isso que este módulo
    não reusa `mudancas.ultima_foto`, que procura a foto inteira mais recente
    para comparar duas datas iguais para todos os números.
    """
    melhor: dict | None = None
    for r in registros or []:
        if r.get("tipo") != "medicao":
            continue
        valores = ler_foto(r.get("foto"))
        dia = _data(r.get("quando"))
        if valores is None or dia is None or nome not in valores:
            continue
        if melhor is None or dia >= melhor["quando"]:
            melhor = {
                "quando": dia,
                "valor": valores[nome],
                "arquivo": r.get("arquivo"),
            }
    return melhor


def montar(
    registros: list[dict] | None,
    total_de_alunos: int | None,
    hoje: dt.date,
    pasta=None,
) -> dict:
    """Os seis passos do laço, cada um com o número que a casa tem hoje.

    `total_de_alunos` vem do placar (a célula `alunos` ao vivo) e pode ser
    `None`: a porta não respondeu. `registros` `None` é o livro que não chegou
    até esta imagem, que é outra coisa de "nenhuma contagem feita", e as duas
    aparecem diferentes na tela (`armadilhas/271`).
    """
    pasta = pasta if pasta is not None else diretorio_dos_cartoes()
    passos = []
    for passo in LACO:
        cartao, problemas = ler_cartao(passo["cartao"], pasta)
        item = {
            **passo,
            "cartao_lido": cartao,
            "problemas": problemas,
            "valor": None,
            "contado_em": None,
            "dias": None,
            "velha": False,
        }
        if cartao is None:
            item["estado"] = "sem-cartao"
        elif passo["origem"] == "ao-vivo":
            item["estado"] = "medido" if total_de_alunos is not None else "nao-medi"
            item["valor"] = total_de_alunos
        elif passo["origem"] == "cartao":
            item["estado"] = "sem-fonte" if not cartao.get("fonte") else "no-placar"
        elif registros is None:
            item["estado"] = "nao-consigo-olhar"
        else:
            medicao = ultima_medicao(registros, passo["cartao"])
            if medicao is None:
                item["estado"] = "nunca-contado"
            else:
                dias = (hoje - medicao["quando"]).days
                frescor = cartao.get("frescor_maximo") or FRESCOR_PADRAO
                item["estado"] = "medido"
                item["valor"] = medicao["valor"]
                item["contado_em"] = medicao["quando"]
                item["dias"] = dias
                item["velha"] = dias > frescor
        passos.append(item)
    return {
        "passos": passos,
        "livro_ausente": registros is None,
        "nunca_contadas": sum(1 for p in passos if p["estado"] == "nunca-contado"),
    }


def ler_as_contagens(campos) -> tuple[dict[str, int], list[str]]:
    """O que o mantenedor digitou: `cartão → contagem`, e o que foi recusado.

    Campo vazio é campo não digitado (a escola conta uma etapa hoje e outra na
    semana que vem), e não zero: gravar zero por um campo em branco apagaria
    uma contagem verdadeira do livro na foto seguinte.
    """
    contagens: dict[str, int] = {}
    recusas: list[str] = []
    for campo, cartao in DIGITADAS:
        bruto = str(campos.get(campo, "")).strip()
        if not bruto:
            continue
        try:
            valor = int(bruto)
        except ValueError:
            recusas.append(
                f"Não entendi a contagem de {cartao}: você digitou "
                f"'{bruto}', e ali cabe um número inteiro de 0 para cima."
            )
            continue
        if valor < 0:
            recusas.append(
                f"A contagem de {cartao} não pode ser negativa: você digitou {valor}."
            )
            continue
        contagens[cartao] = valor
    return contagens, recusas


def montar_o_pedido(
    contagens: dict[str, int], hoje: dt.date, foto_do_placar: str | None = None
) -> str | None:
    """O bloco para colar numa sessão de robô; `None` se não há o que pedir.

    `foto_do_placar` é a linha `cartao=valor; ...` que o placar mede agora. Ela
    entra junto (lei 3 do topo deste arquivo): a foto que vai ao livro precisa
    ser completa, senão ela vira a mais recente sem ter os outros números.
    """
    if not contagens:
        return None
    foto = ler_foto(foto_do_placar) or {}
    foto.update(contagens)
    linhas = [
        f"Contagem da rede de talentos, {hoje.strftime('%d/%m/%Y')}.",
        "Registre no livro de ocorrências (painel/registros/), UM registro,",
        "pelo rito de sempre (PR com o registro a bordo; molde em painel/LEIA-ME.md):",
        "",
        "- MEDIÇÃO (tipo `medicao`, autoridade: mantenedor, gravidade: info,",
        "  evidencia: o link do PR, verificado_em: "
        f"{hoje.isoformat()}), com o campo `foto` exatamente assim:",
        f'  foto: "{foto_em_texto(foto)}"',
        "  Título: 'Contagem da rede de talentos'.",
        "  Detalhe: quem contou, e o que entrou na conta.",
        "",
        "As contagens digitadas hoje:",
    ]
    for _campo, cartao in DIGITADAS:
        if cartao in contagens:
            linhas.append(f"- {cartao}: {contagens[cartao]}")
    linhas += [
        "",
        "A linha `foto` acima leva junto os números que o placar mede sozinho",
        "(é ela que o bloco 'o que mudou' compara na segunda-feira seguinte).",
    ]
    return "\n".join(linhas)


@require_http_methods(["GET", "POST"])
def talentos(request):
    """O laço desenhado. GET mostra; POST devolve o pedido para o robô."""
    hoje = timezone.localdate()
    contexto = montar_o_placar(hoje, site_de(request))
    total = (contexto.get("contagem") or {}).get("total_de_alunos")
    contagens: dict[str, int] = {}
    recusas: list[str] = []
    if request.method == "POST":
        contagens, recusas = ler_as_contagens(request.POST)
    foto_do_placar = (contexto.get("mudancas") or {}).get("foto_de_hoje")
    return render(
        request,
        "admin/talentos.html",
        {
            "admin": request.admin,
            "laco": montar(ler_registros(), total, hoje),
            "campos": request.POST if request.method == "POST" else {},
            "recusas": recusas,
            "pedido": montar_o_pedido(contagens, hoje, foto_do_placar),
            "montou": request.method == "POST",
        },
    )
