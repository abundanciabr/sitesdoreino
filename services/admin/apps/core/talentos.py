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

**3. A foto que este pedido monta é COMPLETA, ou não existe.** A linha `foto`
leva junto os números que o placar já mede sozinho hoje. O bloco "o que mudou"
da capa compara a foto mais recente do livro com o que a tela mostra agora; uma
foto só com as três contagens da rede seria a mais recente sem ter os outros
números, e todo o resto do placar apareceria como "sem par" na segunda-feira
seguinte. Por isso o pedido só se monta quando o placar mediu de verdade: se
ele não mediu (o cartão da meta faltou, o livro não chegou), a tela recusa
montar o bloco e diz o que fazer, exatamente como a reunião de segunda se
recusa a pedir a foto quando não há foto. Meio bloco copiado é pior do que
bloco nenhum: o estrago só aparece na segunda seguinte, e aí ninguém liga uma
coisa à outra.

**O efeito de lado desta lei, dito em voz alta.** A foto que este pedido grava
é completa, então ela vira a foto mais recente do livro. A comparação de
segunda-feira passa a ser contra o dia em que a rede foi contada, e não contra
a segunda anterior: contar a rede numa quarta encurta a janela da comparação
seguinte para cinco dias. Isso é o preço da lei 3, e é o preço menor. A
alternativa (marcar esta foto para a comparação semanal ignorá-la) tornaria
inútil carregar o placar junto, e devolveria o "sem par" que a lei 3 existe
para evitar. A tela diz isso ao mantenedor antes de ele copiar o bloco.

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

from .mudancas import FRESCOR_PADRAO, foto_em_texto, ler_foto
from .placar import diretorio_dos_cartoes, ler_cartao, montar_o_placar, site_de

#: As três contagens que a escola digita, na ordem em que o laço gira. Cada
#: tupla é `(campo do formulário, nome do cartão, rótulo que o mantenedor lê)`.
#: O nome do cartão é também a chave dentro da linha `foto` do livro, e ele
#: NUNCA aparece em tela: quem o vê são as máquinas. O rótulo existe para que a
#: recusa fale a mesma língua da etiqueta que ele acabou de ler no formulário,
#: e por isso é o próprio formulário que o imprime (`talentos.html` percorre
#: esta tupla; `tests/test_talentos.py` prova que os três chegam à tela).
#:
#: O rótulo dos encaixes conta TRABALHOS, e não pessoas, porque é isso que o
#: cartão `encaixes-com-estudio` define ("a mesma aluna em dois trabalhos conta
#: duas vezes"). O laço mede oportunidades abertas nesta etapa; quem conta
#: pessoas é a etapa seguinte, a dos resultados (`armadilhas/303`).
DIGITADAS = (
    (
        "talentos",
        "alunos-selecionados-para-a-rede",
        "Alunas já selecionadas para a rede",
    ),
    ("estudios", "estudios-parceiros", "Estúdios que já aceitaram receber alunas"),
    (
        "encaixes",
        "encaixes-com-estudio",
        "Trabalhos que alunas já começaram em estúdios",
    ),
)

#: Os seis passos do laço (Scale OS 2 §45). O sétimo é o retorno ao primeiro, e
#: por isso não tem cartão próprio: quem o desenha é a tela.
#:
#: `origem` diz de onde o número daquele passo vem, e é o que decide o estado:
#: `ao-vivo` (a célula `alunos` responde agora), `digitada` (a escola conta e o
#: livro guarda) e `cartao` (quem mede é o placar, e o número chega aqui pela
#: mesma linha `foto` que o placar acabou de montar). Os dois passos `cartao`
#: de hoje não têm fonte nenhuma, e aí quem explica o porquê é o próprio
#: cartão, nunca esta tela.
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
    medidos: dict[str, int | float] | None = None,
    pasta=None,
) -> dict:
    """Os seis passos do laço, cada um com o número que a casa tem hoje.

    `total_de_alunos` vem do placar (a célula `alunos` ao vivo) e pode ser
    `None`: a porta não respondeu. `registros` `None` é o livro que não chegou
    até esta imagem, que é outra coisa de "nenhuma contagem feita", e as duas
    aparecem diferentes na tela (`armadilhas/271`).

    `medidos` é `nome do cartão → valor` do que o placar mediu agora, lido da
    mesma linha `foto` que ele monta. É por ele que os passos de origem
    `cartao` mostram o número em vez de mandar o leitor procurar no placar: o
    degrau 17 prometeu o número AO LADO de cada etapa, e mandar procurar em
    outra tela não é cumprir a promessa. `None` é o placar que não mediu.
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
            # Três fatos diferentes, e nenhum deles é zero (`armadilhas/271`):
            # o placar trouxe o número; o cartão tem fonte e o placar não
            # trouxe nada agora; e o cartão não tem fonte nenhuma, caso em que
            # `sem_fonte_porque` é obrigatório no cartão e é ele quem fala.
            valor = (medidos or {}).get(passo["cartao"])
            if valor is not None:
                item["estado"] = "medido"
                item["valor"] = valor
            elif cartao.get("fonte"):
                item["estado"] = "sem-numero-agora"
            else:
                item["estado"] = "sem-fonte"
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
    for campo, cartao, rotulo in DIGITADAS:
        bruto = str(campos.get(campo, "")).strip()
        if not bruto:
            continue
        try:
            valor = int(bruto)
        except ValueError:
            recusas.append(
                f"Não entendi o campo '{rotulo}': você digitou "
                f"'{bruto}', e ali cabe um número inteiro de 0 para cima."
            )
            continue
        if valor < 0:
            recusas.append(
                f"O campo '{rotulo}' não pode ser negativo: você digitou {valor}."
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

    Placar que não mediu devolve `None`, e não meia foto. `ler_foto` diz `None`
    tanto para a linha ausente (o cartão da meta faltou, ou o livro não chegou
    e `o_que_mudou` devolveu só o veredito) quanto para a linha torta, e os
    dois casos dão no mesmo: não há foto completa para gravar. É o mesmo gesto
    da reunião de segunda, que só pede a foto quando existe foto
    (`reuniao.py`). Quem avisa o mantenedor é a tela.
    """
    foto = ler_foto(foto_do_placar)
    if not contagens or foto is None:
        return None
    # A contagem digitada vence o mesmo nome vindo do placar: quem contou à mão
    # a rede sabe mais do que o placar sabe sobre ela.
    foto.update(contagens)
    linhas = [
        f"Contagem da rede de talentos, {hoje.strftime('%d/%m/%Y')}.",
        "Registre no livro de ocorrências (painel/registros/), UM registro,",
        "pelo rito de sempre (PR com o registro a bordo; molde em painel/LEIA-ME.md):",
        "",
        "- MEDIÇÃO (tipo `medicao`, autoridade: mantenedor, gravidade: info,",
        # `quando` é o dia em que a contagem foi FEITA, e é essa data que
        # `ultima_medicao` lê de volta para dizer "contado por você em tal
        # dia". Sem pedir a data aqui, o registro sai carimbado com o dia em
        # que o PR entrou, e a tela passa a jurar que alguém contou num dia em
        # que ninguém contou nada.
        f"  quando: {hoje.isoformat()}, evidencia: o link do PR,",
        f"  verificado_em: {hoje.isoformat()}), com o campo `foto` assim:",
        f'  foto: "{foto_em_texto(foto)}"',
        "  Título: 'Contagem da rede de talentos'.",
        "  Detalhe: quem contou, e o que entrou na conta.",
        f"  O `quando` é {hoje.isoformat()} mesmo, e não o dia em que este",
        "  registro entrar: é essa data que a tela lê de volta para dizer",
        "  quando a contagem foi feita.",
        "",
        "As contagens digitadas hoje:",
    ]
    for _campo, cartao, rotulo in DIGITADAS:
        if cartao in contagens:
            linhas.append(f"- {cartao} ({rotulo}): {contagens[cartao]}")
    linhas += [
        "",
        "A linha `foto` acima leva junto os números que o placar mede sozinho,",
        "e é ela que o bloco 'o que mudou' compara na segunda-feira seguinte.",
        "Por isso esta foto passa a ser a mais recente do livro: a comparação",
        "da próxima segunda será contra hoje, e não contra a segunda passada.",
    ]
    return "\n".join(linhas)


@require_http_methods(["GET", "POST"])
def talentos(request):
    """O laço desenhado. GET mostra; POST devolve o pedido para o robô.

    O livro é lido UMA vez por requisição, e a leitura é a que `montar_o_placar`
    já pagou (`contexto["registros"]`). Chamar `ler_registros()` de novo aqui
    varreria a pasta inteira de `painel/registros/` uma segunda vez, com um
    `read_text` por arquivo, para chegar exatamente à mesma lista. É a mesma
    regra que o placar escreve para as portas de rede ("UMA leitura de cada
    porta por requisição"), e pelo mesmo motivo: duas leituras podem discordar
    entre si por um registro que entrou no meio.
    """
    hoje = timezone.localdate()
    contexto = montar_o_placar(hoje, site_de(request))
    total = (contexto.get("contagem") or {}).get("total_de_alunos")
    foto_do_placar = (contexto.get("mudancas") or {}).get("foto_de_hoje")
    medidos = ler_foto(foto_do_placar)
    enviados = request.POST if request.method == "POST" else {}
    contagens: dict[str, int] = {}
    recusas: list[str] = []
    if request.method == "POST":
        contagens, recusas = ler_as_contagens(enviados)
    # Recusa e bloco pronto são coisas que nunca aparecem juntas: quem digita
    # "4" e "dois" recebe a ordem de corrigir E um bloco com metade da
    # contagem, cola, e grava metade. Por isso o pedido nem se monta.
    pedido = None if recusas else montar_o_pedido(contagens, hoje, foto_do_placar)
    return render(
        request,
        "admin/talentos.html",
        {
            "admin": request.admin,
            "laco": montar(contexto["registros"], total, hoje, medidos),
            "digitadas": [
                {"campo": campo, "rotulo": rotulo, "valor": enviados.get(campo, "")}
                for campo, _cartao, rotulo in DIGITADAS
            ],
            "recusas": recusas,
            "pedido": pedido,
            "montou": request.method == "POST",
            "contou": bool(contagens),
            "placar_nao_mediu": medidos is None,
        },
    )
