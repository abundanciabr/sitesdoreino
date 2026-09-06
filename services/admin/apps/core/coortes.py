"""`/admin/placar/coortes/` — o que aconteceu com cada grupo que entrou junto.

Degrau 10 do `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` (§6.4). A barra do mês
responde "quantas pessoas viraram alunas neste mês" e zera no dia 1. Esta tela
guarda as barras que já fecharam, uma linha por mês, e é o que transforma um
número que reinicia numa história que se lê de cima a baixo.

## De onde sai cada número, e por que não sai da `alunos`

Da memória, sempre: `countMilestones` do contrato congelado da `metricas`
(`contracts/metricas.openapi.yaml`), uma chamada só, sem tabela nova e sem
porta nova. O placar conta AO VIVO na `alunos`, e é o certo lá: ele responde
"quantas há agora". Coorte é pergunta sobre o passado, e o passado desta casa
mora no livro de fatos (plano §2, a linha de 25/08/2026).

Os dois podem discordar, e a tela diz isso em vez de esconder: a memória só
sabe o que os eventos trouxeram desde que ela passou a escutar, e uma ficha
consertada à mão na `alunos` não reescreve o fato que já foi publicado.

## A LIGAÇÃO QUE ESTA TELA NÃO FAZ, e é a decisão mais cara dela

O plano pede "o que aconteceu com quem entrou em setembro", e a resposta
honesta hoje é: **dá para dizer quantas pessoas entraram, e não o que elas
fizeram depois.** O motivo não é preguiça, é vocabulário de identidade.

`virou-aluno-comprando` e `virou-aluno-liberado` têm sujeito `matricula`; o
`matricula_id` é local da célula `alunos` e "não serve para creditar ninguém
fora de lá" (`matricula.situacao-alterada.v1`). `escreveu-no-forum` e
`ajudou-alguem` têm sujeito `pessoa`, que é a identidade da plataforma. Não
existe, em porta congelada nenhuma, a tradução de um para o outro — e
`countMilestones` devolve contagens, nunca ids, então nem uma varredura por
fora resolveria.

Somar os dois vocabulários é o que o contrato proíbe em voz alta (regra 7) e o
que a `armadilhas/303` chama de medir a coisa errada com precisão. Uma tabela
que dissesse "a coorte de setembro escreveu 4 vezes no fórum" estaria
comparando matrículas com pessoas, e ninguém veria o erro, porque o número
pareceria certo.

Então a tela mostra as duas metades **lado a lado e nomeadas**: quem entrou
(matrículas) e o que a plataforma ganhou no mês (pessoas), com a frase que
impede o leitor de cruzá-las com o olho.

## O que entra desenhado, e por quê

Três dimensões que o plano pede e que hoje não têm fonte. Elas aparecem
escritas, com o motivo, no mesmo molde do `sem_fonte_porque` dos cartões:
número inventado é pior que número ausente, e zero mudo é a pior das três
saídas, porque parece medição.

- **Por turma.** A turma é dado da `alunos` (campo `turma` da matrícula), e
  **não viaja no evento**: `matricula.situacao-alterada.v1` carrega `site_id`,
  `matricula_id`, `situacao_anterior`, `situacao_nova`, `origem` e
  `virou_aluno_em`, e nada mais. Buscá-la ao vivo na `alunos` daria uma tabela
  cujos totais não fechariam com os desta página, porque as duas fontes contam
  coisas diferentes.
- **Por canal.** Depende de "como você conheceu a escola?" no pedido de
  entrada, que pertence ao checkout, congelado por decisão do mantenedor de
  22/08/2026.
- **A foto ao longo do tempo (D7, D30, D90, D180, D365).** Guardar foto exige
  tabela e operação novas na memória, e operação nova em contrato congelado é
  Rito de Contrato com o mantenedor presente.

## As três regras do cálculo

1. **O mês vem do `dia` que a memória já devolveu, sem reconverter fuso.** Ela
   grava o dia de São Paulo na recepção (`armadilhas/099`), e o contrato promete
   isso na descrição de `countMilestones`. Reaplicar fuso aqui seria deslocar o
   dia uma segunda vez e jogar quem entrou às 22h do dia 30 no mês errado.
2. **A tabela começa no primeiro mês com conquista, nunca antes.** Mês vazio
   ANTES do primeiro fato não vira zero: ali não se sabe se ninguém entrou ou
   se a memória ainda não escutava. Depois do primeiro fato o zero é honesto,
   porque a memória já estava de pé, e o buraco no meio é informação.
3. **Conquista com dia ilegível não some.** Ela sai da tabela e entra numa
   contagem própria, que a tela mostra. Descartar em silêncio encolheria o
   total sem ninguém perceber, que é o modo de falha que a `armadilhas/303`
   descreve.
"""

from __future__ import annotations

import datetime as dt

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .clients import MedicaoClient

#: Quantos meses a tabela olha para trás, contando o mês corrente. Doze porque
#: é o maior horizonte que o plano nomeia (a foto D365), e porque a porta da
#: memória tem teto de 366 dias por intervalo: uma janela de doze meses
#: inteiros cabe nele no pior caso do calendário, e treze não caberiam.
MESES_DA_JANELA = 12

#: As conquistas de sujeito `matricula`: a vida da ficha do aluno. É o
#: vocabulário que a meta do ciclo conta, e a ordem é a da jornada.
COLUNAS_DE_MATRICULA = (
    ("pediu-entrada", "Pediram entrada"),
    ("virou-aluno-comprando", "Entraram comprando"),
    ("virou-aluno-liberado", "Entraram por liberação"),
)

#: As conquistas de sujeito `pessoa`: a vida de quem usa a plataforma. NUNCA
#: se somam com as de cima, e a tela diz por quê (ver o docstring do módulo).
COLUNAS_DE_PESSOA = (
    ("entrou-no-site", "Chegaram no site"),
    ("escreveu-no-forum", "Escreveram no fórum"),
    ("ajudou-alguem", "Ajudaram alguém"),
)

#: As duas que somadas dão "entrou na escola". Sair de `COLUNAS_DE_MATRICULA`
#: seria somar `pediu-entrada` junto, e pedir entrada não é ter entrado.
COLUNAS_DE_ENTRADA = ("virou-aluno-comprando", "virou-aluno-liberado")

#: O nome do mês em português. Uma tupla, e não o filtro de data do Django: o
#: idioma da tela não pode depender de o `LANGUAGE_CODE` da célula continuar
#: onde está, e a lista de doze palavras não envelhece.
MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def janela(hoje: dt.date) -> tuple[dt.date, dt.date]:
    """De quando até quando perguntar: doze meses inteiros terminando hoje.

    O começo é sempre o DIA 1, e não "hoje menos 365 dias", porque a unidade
    desta tela é o mês: uma janela que começasse no meio de um mês mostraria a
    primeira linha pela metade sem dizer que está pela metade.
    """
    contados = hoje.year * 12 + (hoje.month - 1) - (MESES_DA_JANELA - 1)
    return dt.date(contados // 12, contados % 12 + 1, 1), hoje


def _mes_do_dia(texto: object) -> str | None:
    """ "2026-09-14" → "2026-09". `None` quando o dia não é um dia.

    Sem reconversão de fuso, de propósito: o `dia` que a memória devolve JÁ é o
    dia de São Paulo (regra 1 do docstring). O que este código confere é só que
    o texto é mesmo uma data, para que lixo não vire um mês inventado.
    """
    try:
        dia = dt.date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None
    return f"{dia.year:04d}-{dia.month:02d}"


def nome_do_mes(chave: str) -> str:
    """ "2026-09" → "setembro de 2026"."""
    ano, mes = chave.split("-")
    return f"{MESES[int(mes) - 1]} de {ano}"


def _contar_por_mes(conquistas: list) -> tuple[dict, int, list]:
    """`(sujeito_tipo, tipo)` → `{mês: quantos}`, mais o que não deu para pôr
    em mês e os tipos que esta tela ainda não sabe nomear.

    Os desconhecidos voltam em lista em vez de serem ignorados: a memória pode
    ganhar uma conquista nova sem esta tela saber, e uma coluna que não existe
    é motivo para uma nota no rodapé, nunca para um fato sumir.
    """
    conhecidos = {tipo for tipo, _ in COLUNAS_DE_MATRICULA + COLUNAS_DE_PESSOA}
    por_chave: dict[tuple[str, str], dict[str, int]] = {}
    sem_dia = 0
    desconhecidos: dict[str, int] = {}
    for linha in conquistas:
        if not isinstance(linha, dict):
            continue
        sujeito = str(linha.get("sujeito_tipo") or "")
        tipo = str(linha.get("tipo") or "")
        dias = linha.get("por_dia")
        if not isinstance(dias, list):
            continue
        for ponto in dias:
            if not isinstance(ponto, dict):
                continue
            quantos = ponto.get("quantidade")
            if not isinstance(quantos, int):
                continue
            mes = _mes_do_dia(ponto.get("dia"))
            if mes is None:
                sem_dia += quantos
                continue
            if tipo not in conhecidos:
                desconhecidos[tipo] = desconhecidos.get(tipo, 0) + quantos
                continue
            contas = por_chave.setdefault((sujeito, tipo), {})
            contas[mes] = contas.get(mes, 0) + quantos
    novos = [
        {"tipo": tipo, "total": total} for tipo, total in sorted(desconhecidos.items())
    ]
    return por_chave, sem_dia, novos


def _meses_da_tabela(por_chave: dict, hoje: dt.date) -> list[str]:
    """Do primeiro mês com conquista até o mês de hoje, sem buraco.

    Antes do primeiro fato a lista PARA, e a regra 2 do docstring é a razão:
    mês anterior ao primeiro fato não é zero, é desconhecido.
    """
    vistos = {mes for contas in por_chave.values() for mes in contas}
    if not vistos:
        return []
    primeiro = min(vistos)
    ano, mes = int(primeiro[:4]), int(primeiro[5:7])
    fim = hoje.year * 12 + (hoje.month - 1)
    meses = []
    atual = ano * 12 + (mes - 1)
    while atual <= fim:
        meses.append(f"{atual // 12:04d}-{atual % 12 + 1:02d}")
        atual += 1
    return meses


def montar(desfecho: str, conquistas: list | None, hoje: dt.date) -> dict:
    """A tela inteira, calculada. `veredito` antes de qualquer número.

    Quatro desfechos, e nenhum deles é um zero disfarçado:

    - `sem-configuracao` — o par admin→metricas não foi ligado na VPS.
    - `nao-respondeu` — perguntei e a memória não respondeu.
    - `vazia` — perguntei, respondeu, e não há conquista nenhuma no período.
    - `medindo` — há tabela.

    A diferença entre os três primeiros é a razão de a célula de medição
    existir: "não perguntei" e "perguntei e não há nada" são fatos diferentes
    sobre o mundo, e a tela que os achata mente com cara de precisão.
    """
    if desfecho != MedicaoClient.OK or conquistas is None:
        return {"veredito": desfecho, "meses": []}

    por_chave, sem_dia, novos = _contar_por_mes(conquistas)
    chaves = _meses_da_tabela(por_chave, hoje)
    if not chaves:
        return {"veredito": "vazia", "meses": [], "sem_dia": sem_dia, "novos": novos}

    aberto = f"{hoje.year:04d}-{hoje.month:02d}"
    linhas = []
    for chave in reversed(chaves):  # o mês mais novo em cima
        matricula = {
            tipo: por_chave.get(("matricula", tipo), {}).get(chave, 0)
            for tipo, _ in COLUNAS_DE_MATRICULA
        }
        pessoa = {
            tipo: por_chave.get(("pessoa", tipo), {}).get(chave, 0)
            for tipo, _ in COLUNAS_DE_PESSOA
        }
        linhas.append(
            {
                "chave": chave,
                "nome": nome_do_mes(chave),
                "aberto": chave == aberto,
                "matricula": [matricula[tipo] for tipo, _ in COLUNAS_DE_MATRICULA],
                "pessoa": [pessoa[tipo] for tipo, _ in COLUNAS_DE_PESSOA],
                "entraram": sum(matricula[tipo] for tipo in COLUNAS_DE_ENTRADA),
            }
        )
    return {
        "veredito": "medindo",
        "meses": linhas,
        "colunas_de_matricula": [nome for _, nome in COLUNAS_DE_MATRICULA],
        "colunas_de_pessoa": [nome for _, nome in COLUNAS_DE_PESSOA],
        "entraram_no_total": sum(linha["entraram"] for linha in linhas),
        "sem_dia": sem_dia,
        "novos": novos,
    }


@require_GET
def coortes(request):
    """A tela. Fail-OPEN, como as outras do placar: ela abre e DIZ o que faltou.

    A janela é calculada aqui e viaja para o template porque ela é parte da
    afirmação: um número sem a janela em que foi contado não é um número
    (`armadilhas/303`). O mesmo vale para o recorte: esta contagem é da
    plataforma inteira, e não de uma escola, porque a tabela de marcos não
    guarda o site — está escrito no contrato, e a tela repete para quem lê.
    """
    hoje = timezone.localdate()
    de, ate = janela(hoje)
    desfecho, conquistas = MedicaoClient().conquistas(de, ate)
    return render(
        request,
        "admin/coortes.html",
        {
            "admin": request.admin,
            "de": de,
            "ate": ate,
            "coortes": montar(desfecho, conquistas, hoje),
        },
    )
