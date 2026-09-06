"""O roteiro da Prancheta, com as palavras da ESCOLA, e a semente que o planta.

ci:texto-publicado

A MARCA ACIMA NÃO É ENFEITE. Ela liga o portão do travessão neste arquivo
inteiro (`ci/travessao.py`, terceira regra de alcance no `CLAUDE.md`), e aqui
ela é obrigatória por dois motivos que se somam: este é texto que o ALUNO lê, e
ele não está numa `templates/` nem num rótulo de `TextChoices`, que são as duas
regras que pegam sozinhas. Sem a marca, o texto da escola ficaria fora da régua
do mantenedor.

DE ONDE VEM CADA PALAVRA
------------------------
Do guia da escola, que o aluno lê em `meshcraft.top/docs/guia-do-portfolio` e
que o mantenedor edita em `/admin/documentos/` sem abrir PR. Ele foi escrito
pela PROFESSORA do curso e repassado pelo mantenedor em 05/09/2026
(`PLANO-PORTFOLIO-DO-ALUNO.md` §8). **Nada aqui é invenção de robô:** as cinco
etapas são as cinco seções daquele guia, e os quatro itens de conferência são,
palavra por palavra, os quatro pontos objetivos que a professora escreveu no
fecho dele.

POR QUE O TEXTO MORA NESTA CÉLULA, E NÃO É PEDIDO À `admin`
-----------------------------------------------------------
O corredor assinado é explícito: os contratos permitidos desta casa são o da
`identidade`, o da `alunos` e os eventos `pages.portfolio.*`, e **nenhum outro
contrato novo** (`CS-PAGES-0001.md`, seção "Contratos permitidos"). Pedir o
guia à `admin` por HTTP seria um contrato novo, e ler o banco dela seria a Lei 3
quebrada. Então o roteiro é DADO desta casa, no banco desta casa, e o guia longo
continua sendo a leitura corrida na biblioteca de documentos. As duas peças
falam a mesma língua porque saem da mesma professora, e a tela liga uma na
outra.

POR QUE EM ARQUIVO, E NÃO CRAVADO NA MIGRAÇÃO QUE O PLANTA
-----------------------------------------------------------
Texto dentro de `migrations/` fica FORA do portão do travessão, por decisão
escrita da casa (`ci/travessao.py`: o rótulo lá é fotografia do modelo naquele
dia). Uma semente escrita direto na migração passaria a régua do mantenedor por
baixo, em silêncio. Aqui o texto mora num módulo medido, e a migração chama
`semear()`.

COMO SE CORRIGE UMA PALAVRA DEPOIS
-----------------------------------
Editar este arquivo NÃO muda o site sozinho: `semear()` roda dentro de uma
migração, e migração roda uma vez. A correção de texto é este arquivo mais uma
migração de uma linha que chama `semear()` de novo, e é por isso que ela
atualiza o texto de quem já existe em vez de só criar o que falta. É a mesma
lição do `armadilhas/347` e do `documentos/LEIA-ME.md`, de onde ela vem: em
30/08/2026 um travessão sobreviveu no fórum porque o semeador foi corrigido e o
banco não.

A tela que deixa o mantenedor editar isto sozinho, como ele já edita o guia
longo, não existe hoje e não se inventa aqui: seria produto que ninguém pediu
neste degrau.
"""

from __future__ import annotations

# As cinco etapas do roteiro, na ordem em que o aluno as lê.
#
# O `numero` é lei desta obra (`CS-PAGES-0001`, critério AC-06, e a restrição
# de 1 a 5 que o banco já impõe desde o degrau 02); o `titulo` e o `resumo` são
# da escola.
#
# A `chave` de cada item é o nome ESTÁVEL dele, e é ela que viaja para a
# marcação do aluno (`ItemDeConferencia.chave`). Ela nunca muda: corrigir o
# texto é corrigir `texto`, e trocar a chave apagaria a marcação de todo mundo
# sem nada acusar.
#
# A ETAPA 5 NÃO TEM ITEM, e a ausência é decisão, não esquecimento. No guia da
# escola ela é o fecho que repete as quatro regras, e o aluno já marca cada uma
# delas na etapa em que ela é explicada. Repetir as caixas aqui deixaria o mesmo
# fato marcável em dois lugares, livre para discordar de si mesmo, que é a
# doença que o próprio modelo desta app recusou no degrau 02.
ROTEIRO = (
    {
        "numero": 1,
        "titulo": "Escolha pelo menos 3 tipos de modelo",
        "resumo": (
            "No curso você aprende a criar vários tipos de modelo: armas, "
            "carros, cabelos, acessórios, animais e outros. É interessante que "
            "você TENTE criar todos eles. Mas sempre existem alguns de que "
            "gostamos mais do que de outros, e alguns em que temos mais "
            "facilidade.\n\n"
            "Para o portfólio, escolha pelo menos 3 desses tipos, de "
            "preferência os que você faz com mais gosto e mais facilidade. Por "
            'exemplo: "eu tenho mais facilidade em criar acessórios, animais e '
            'armas".'
        ),
        "itens": (
            (
                "tres-tipos-escolhidos",
                "Pelo menos 3 tipos de modelo, entre os que o curso ensina.",
            ),
        ),
    },
    {
        "numero": 2,
        "titulo": "Faça pelo menos 3 peças de cada tipo escolhido",
        "resumo": (
            "Escolhidos os tipos, crie pelo menos 3 peças de cada um. No "
            "exemplo acima, seriam 3 animais, 3 acessórios e 3 armas.\n\n"
            "São 9 peças no mínimo, e é com elas que se começa um bom "
            "portfólio."
        ),
        "itens": (
            (
                "tres-pecas-de-cada-tipo",
                "Pelo menos 3 peças de cada tipo escolhido, o que dá 9 peças "
                "no mínimo.",
            ),
        ),
    },
    {
        "numero": 3,
        "titulo": "A maioria em high poly",
        "resumo": (
            "Os modelos devem ser low poly ou high poly (mais simples ou mais "
            "detalhados)?\n\n"
            "O ideal é que sejam high poly, para impressionar o cliente e "
            "mostrar o máximo do seu potencial. Você também pode criar algumas "
            "variações mais simples, mas o ideal é que a maioria seja mesmo "
            "high poly."
        ),
        "itens": (
            (
                "maioria-high-poly",
                "A maioria das peças em high poly, com algumas variações mais "
                "simples permitidas.",
            ),
        ),
    },
    {
        "numero": 4,
        "titulo": "Nada que se pareça com o modelo da aula",
        "resumo": (
            "Posso usar no portfólio o mesmo modelo que eu aprendi na aula?\n\n"
            "É bom que você crie 3 variações que não se pareçam com a aula. "
            "Assim você evita repetir muitos modelos parecidos dentro do "
            "próprio portfólio."
        ),
        "itens": (
            (
                "nada-parecido-com-a-aula",
                "Nada que se pareça com o modelo feito na aula.",
            ),
        ),
    },
    {
        "numero": 5,
        "titulo": "Em resumo",
        "resumo": (
            "Pelo menos 3 tipos de modelo, entre os que o curso ensina.\n\n"
            "Pelo menos 3 peças de cada tipo escolhido, o que dá 9 peças no "
            "mínimo.\n\n"
            "A maioria das peças em high poly, com algumas variações mais "
            "simples permitidas.\n\n"
            "Nada que se pareça com o modelo feito na aula."
        ),
        "itens": (),
    },
)

# O aviso que a própria professora pediu que o aluno lesse, e que já está no
# alto do guia longo. Ele viaja com o roteiro porque a Prancheta é onde o aluno
# vai passar o tempo dele: um rascunho que só se anuncia na outra página é um
# rascunho que ninguém sabe que é rascunho.
AVISO_DE_RASCUNHO = (
    "Estes critérios foram escritos pela professora do curso e ainda podem "
    "mudar. Quando mudarem, a mudança aparece aqui."
)


def semear(apps) -> None:
    """Planta (ou corrige) as cinco etapas e os itens delas. Roda em migração.

    Recebe o `apps` da migração, e não importa os modelos do módulo: dentro de
    uma migração quem vale é o modelo histórico daquele ponto da história.

    **Atualiza o que já existe**, de propósito. Um `get_or_create` só criaria o
    que falta, e o dia em que a professora corrigisse uma palavra o aluno
    continuaria lendo a antiga, com a migração verde e ninguém sabendo
    (`armadilhas/347`). A chave de cada linha é o que NÃO muda: o número da
    etapa e a chave do item.
    """
    Etapa = apps.get_model("portfolio", "EtapaDoRoteiro")
    Item = apps.get_model("portfolio", "ItemDoRoteiro")

    for etapa_escrita in ROTEIRO:
        etapa, _ = Etapa.objects.update_or_create(
            numero=etapa_escrita["numero"],
            defaults={
                "titulo": etapa_escrita["titulo"],
                "resumo": etapa_escrita["resumo"],
            },
        )
        for ordem, (chave, texto) in enumerate(etapa_escrita["itens"], start=1):
            Item.objects.update_or_create(
                chave=chave,
                defaults={"etapa": etapa, "ordem": ordem, "texto": texto},
            )
