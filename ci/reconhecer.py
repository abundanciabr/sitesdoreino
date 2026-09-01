#!/usr/bin/env python3
"""O RECONHECIMENTO — o que a plataforma JÁ tem sobre um tema, antes de planejar.

POR QUE ISTO EXISTE
-------------------
Em 01/09/2026 um aluno pediu na Caixa de Sugestões "guias de portfólio com
check-list". Antes de escrever uma linha de plano, a sessão gastou quarenta
comandos de leitura para responder três perguntas que se repetem em TODA
sugestão que vira obra:

    1. isto já existe em alguma célula, com outro nome?
    2. já foi decidido antes, e por quem?
    3. a casa sabe fazer a coisa que isto exige (guardar foto, gerar PDF,
       mandar e-mail), ou essa capacidade não existe em lugar nenhum?

A terceira é a cara: a resposta ("nenhuma tela desta plataforma recebe
arquivo") mudou o plano inteiro, e ninguém a tinha escrito em lugar nenhum
porque ela não é um fato sobre um arquivo, é um fato sobre a AUSÊNCIA de todos
eles. Ausência não se documenta à mão: um documento que dissesse "não temos
upload" ficaria mentindo no dia em que alguém escrevesse o primeiro, e ninguém
voltaria para corrigi-lo. É a Classe 8 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`
(mapa velho), e a cura é a mesma de sempre: **não guardar a resposta, guardar a
pergunta e medi-la na hora.**

O QUE ELE DEVOLVE
-----------------
Um dossiê em Markdown, pronto para colar na seção "O que eu medi" do
`docs/caixa-de-sugestoes/MODELO-ESTUDO-DE-VIABILIDADE.md`:

    onde o tema já aparece no código, agrupado por pasta dona
    as decisões e planos que já falaram dele
    os endereços do site que já existem e casam
    as tarefas da fila e as armadilhas que casam
    as capacidades da casa: o que ela sabe fazer, e onde está o molde

ELE LÊ DO `origin/main`, NUNCA DO DISCO
---------------------------------------
Toda medição sai de `git grep <ref>`, com `--ref origin/main` por padrão. O
clone principal deste projeto é espelho e vive semanas atrás sem avisar; em
28/08/2026 essa distância custou uma tela errada e um pedido inútil ao
mantenedor (`armadilhas/148`). Uma ferramenta de reconhecimento que lesse o
disco herdaria exatamente esse erro, e o herdaria calada.

QUANDO NÃO CONSEGUE MEDIR, ELE DIZ
-----------------------------------
`git` ausente, ref inexistente, repositório mudo: tudo isso vira ERRO em voz
alta e saída 2, nunca um dossiê vazio. Um relatório que dissesse "nada
encontrado" porque a ref não existe é o falso-verde do padrão 1 da
`RETROSPECTIVA-FASE-D` na forma mais convincente que ele tem: uma página limpa.

Uso:

    python ci/reconhecer.py portfolio portifolio estudio
    python ci/reconhecer.py --ref HEAD checklist
    python ci/reconhecer.py                # só o retrato das capacidades
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao, configurar_saida, raiz_do_repo  # noqa: E402

# ---------------------------------------------------------------------------
# ONDE PROCURAR — os cantos do repositório que respondem perguntas diferentes.
# Não é um mapa de células (esse mora em `celulas.yml` e tem varredor próprio);
# é a lista dos lugares onde uma resposta ÚTIL pode estar, com o nome que ela
# tem para quem lê o dossiê.
# ---------------------------------------------------------------------------
FRENTES = (
    ("O código das células", ("services",)),
    ("Os contratos entre células", ("contracts",)),
    ("A infraestrutura e o CI", ("infra", "ci", ".github")),
    ("As decisões e os planos", ("docs",)),
    ("As leis da raiz e as constituições", ("constituicoes",)),
)

#: Pastas cujo resultado é ruído se listado arquivo por arquivo: elas guardam
#: histórico (o livro tem milhares de registros) e casariam com quase tudo.
#: Elas entram no dossiê CONTADAS, com o caminho para quem quiser abrir.
FRENTES_CONTADAS = (
    ("O livro de ocorrências", ("painel/registros",)),
    ("As armadilhas do catálogo", ("armadilhas",)),
    ("A fila de trabalho", ("fila/tarefas",)),
)

#: O que NÃO conta ao medir uma capacidade. Teste, tradução, semeador e
#: documento são TEXTO sobre o mecanismo, não o mecanismo — e foi assim que a
#: primeira versão deste script respondeu "SIM, a casa serve aula em vídeo"
#: por causa de um aluno de mentira que escreveu "YouTube" num semeador de
#: demonstração, e "SIM, a casa guarda arquivo" porque `minio` casa dentro da
#: palavra "doMINIOs". As duas respostas erradas eram do tipo mais caro: as
#: que dizem que existe o que não existe, e apagam do plano o trabalho real.
FORA_DA_CAPACIDADE = (
    # `glob` é obrigatório para o `**` cruzar barras: sem ele, o `*` do git
    # para na primeira `/` e a exclusão não exclui nada (medido em 01/09/2026,
    # com um teste de gamificação teimando em provar que a casa serve vídeo).
    ":(exclude,glob)services/**/tests/**",
    ":(exclude,glob)services/**/traducoes/**",
    ":(exclude,glob)services/**/management/commands/**",
    ":(exclude,glob)services/**/*.md",
)


@dataclass(frozen=True)
class Capacidade:
    """Uma coisa que a plataforma sabe ou não sabe fazer.

    `assinatura` é a PERGUNTA, não a resposta: ela é medida a cada execução,
    então uma capacidade que nasça amanhã aparece sozinha aqui, sem ninguém
    lembrar de atualizar lista nenhuma. É o oposto de um inventário.
    """

    nome: str
    assinatura: str
    onde: tuple[str, ...]
    #: O que dizer quando a resposta é NÃO. Nunca é "impossível": é o que a
    #: ausência CUSTA para quem estava planejando contar com ela.
    se_falta: str


CAPACIDADES = (
    Capacidade(
        nome="Guardar um arquivo que alguém enviou (foto, PDF, zip)",
        assinatura=r"FileField|ImageField|MEDIA_ROOT|DEFAULT_FILE_STORAGE|boto3|minio|enctype|request\.FILES",
        onde=("services",),
        se_falta=(
            "Nenhuma tela recebe arquivo. Qualquer plano com foto, anexo ou "
            "envio de imagem precisa ANTES de uma decisão do mantenedor sobre "
            "onde os arquivos moram (disco da máquina, serviço pago), e de um "
            "PR de infraestrutura próprio."
        ),
    ),
    Capacidade(
        nome="Gerar um PDF",
        assinatura=r"weasyprint|reportlab|pdfkit|fpdf|xhtml2pdf",
        onde=("services",),
        se_falta=(
            "Nada aqui monta PDF. A saída barata é uma página com desenho de "
            "impressão (o navegador salva em PDF sozinho); o arquivo montado "
            "no servidor é dependência nova na imagem e merece PR próprio."
        ),
    ),
    Capacidade(
        nome="Enviar e-mail de verdade para fora",
        assinatura=r"send_mail|EmailMultiAlternatives|EMAIL_HOST|resend|sendgrid|postmark|smtplib",
        onde=("services",),
        se_falta=(
            "O envio para fora não existe ou é fingido. Aviso ao aluno hoje "
            "chega pelo sininho da Caixa, não por e-mail."
        ),
    ),
    Capacidade(
        nome="Avisar no celular (aplicativo instalado)",
        assinatura=r"pywebpush|webpush|vapid|VAPID",
        onde=("services",),
        se_falta="Não há caminho até a tela de bloqueio do celular do aluno.",
    ),
    Capacidade(
        nome="Cobrar dinheiro",
        assinatura=r"mercadopago|MP_ACCESS_TOKEN|preference|webhook_pagamento",
        onde=("services",),
        se_falta="Nada cobra. (Se isto aparecer como ausente, meça de novo: é sinal de instrumento torto.)",
    ),
    Capacidade(
        nome="Trabalhar em segundo plano (tarefa agendada, reenvio)",
        assinatura=r"huey|periodic_task|crontab|Redis Streams|consume_eventos",
        onde=("services",),
        se_falta="Tudo acontece dentro da requisição; nada roda depois nem repete sozinho.",
    ),
    Capacidade(
        nome="Procurar dentro do texto que os alunos escreveram",
        assinatura=r"SearchVector|SearchQuery|tsvector|ts_rank|websearch_to_tsquery",
        onde=("services",),
        se_falta="Não há busca; achar conteúdo depende de link direto.",
    ),
    Capacidade(
        nome="Servir aula em vídeo",
        assinatura=r"vimeo|youtube|m3u8|videoaula|jwplayer",
        onde=("services",),
        se_falta=(
            "O curso NÃO mora no site. O site não sabe sozinho quem assistiu "
            "o quê, então 'quando o aluno terminar as aulas' precisa de um "
            "gatilho declarado por alguém, não medido pela plataforma."
        ),
    ),
    Capacidade(
        nome="Falar mais de um idioma na tela",
        assinatura=r"gettext|LocaleMiddleware|traducoes/",
        onde=("services",),
        se_falta="As telas nascem em um idioma só.",
    ),
    Capacidade(
        nome="Reconhecer quem entrou (sessão de verdade)",
        assinatura=r"meshcraft_sessao|getSessionFull|SessionFull",
        onde=("services",),
        se_falta="Nenhuma célula sabe quem é a pessoa. (Ausência improvável: meça de novo.)",
    ),
)


# ---------------------------------------------------------------------------
# A conversa com o git — a única fonte de dado deste script.
# ---------------------------------------------------------------------------
def _git(
    args: list[str], *, raiz: Path, descricao: str, tolerar: tuple[int, ...] = ()
) -> tuple[int, str]:
    """Roda um `git` e devolve `(exit, stdout)`.

    `git grep` responde 1 quando não achou nada, e isso é uma RESPOSTA, não uma
    falha: por isso este script não usa `_nucleo.executar`, que trata todo exit
    diferente de zero como anomalia. Qualquer exit acima de 1 (ref inexistente,
    repositório corrompido) vira `ErroDeInstrumentacao` e o dossiê não nasce.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(raiz),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as erro:  # git ausente do PATH
        raise ErroDeInstrumentacao(
            f"{descricao}: o git não foi encontrado",
            "Sem git não há medição nenhuma. Nada foi conferido.",
        ) from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroDeInstrumentacao(
            f"{descricao}: o git demorou demais (120s)",
            "A medição foi abandonada. Nada foi conferido.",
        ) from erro

    if proc.returncode > 1 and proc.returncode not in tolerar:
        raise ErroDeInstrumentacao(
            f"{descricao}: o git recusou o comando (exit {proc.returncode})",
            f"comando: git {' '.join(args)}\n{proc.stderr.strip()}",
        )
    return proc.returncode, proc.stdout


def conferir_ref(ref: str, raiz: Path) -> str:
    """Prova que a ref existe ANTES de qualquer busca, e devolve o commit.

    Sem esta conferência, uma ref errada devolveria zero resultado em todas as
    frentes e o dossiê diria "não existe nada sobre isto" com a cara mais
    convincente possível.
    """
    # O 128 é tolerado AQUI e só aqui: ref inexistente é a causa mais provável,
    # e ela merece a frase que ensina o conserto em vez de "o git recusou o
    # comando (exit 128)". Nas buscas, 128 continua sendo erro de instrumento.
    codigo, saida = _git(
        ["rev-parse", "--short", f"{ref}^{{commit}}"],
        raiz=raiz,
        descricao="conferir a ref",
        tolerar=(128,),
    )
    commit = saida.strip()
    if codigo != 0 or not commit:
        raise ErroDeInstrumentacao(
            f"a ref '{ref}' não existe neste repositório",
            "Rode `git fetch origin` e tente de novo. Nada foi medido.",
        )
    return commit


def procurar(
    termos: list[str],
    caminhos: tuple[str, ...],
    *,
    ref: str,
    raiz: Path,
    palavra_inteira: bool = False,
) -> list[str]:
    """Os arquivos da ref que contêm QUALQUER um dos termos, sem caixa.

    `palavra_inteira` é o que separa medir de adivinhar. Procurando um TEMA, o
    pedaço serve: quem digita `portfoli` quer achar "portfólio" e "portifolio".
    Medindo uma CAPACIDADE, o pedaço mente: `minio` casa dentro de "domínios",
    e a resposta vira "a casa guarda arquivo" num projeto onde nenhuma tela
    recebe arquivo nenhum.
    """
    if not termos:
        return []
    # `--extended-regexp` porque as assinaturas de capacidade são alternativas
    # (`a|b|c`): na expressão BÁSICA que o git usa por padrão, o `|` é literal e
    # a busca acha zero — uma capacidade existente apareceria como ausente, que
    # é exatamente a mentira que este script existe para não contar.
    args = ["grep", "--ignore-case", "--extended-regexp", "--files-with-matches"]
    if palavra_inteira:
        args.append("--word-regexp")
    for termo in termos:
        args += ["-e", termo]
    args += [ref, "--", *caminhos]
    _, saida = _git(args, raiz=raiz, descricao=f"procurar em {', '.join(caminhos)}")
    # `git grep <ref>` prefixa cada linha com "<ref>:" — o dossiê mostra o
    # caminho, que é o que se abre depois.
    return sorted(linha.split(":", 1)[1] for linha in saida.splitlines() if ":" in linha)


def ler(caminho: str, *, ref: str, raiz: Path) -> str:
    codigo, saida = _git(["show", f"{ref}:{caminho}"], raiz=raiz, descricao=f"ler {caminho}")
    return saida if codigo == 0 else ""


# ---------------------------------------------------------------------------
# As leituras que viram seções do dossiê.
# ---------------------------------------------------------------------------
def titulo_do_documento(caminho: str, *, ref: str, raiz: Path) -> str:
    """A primeira linha de título de um `.md`, para o dossiê não virar lista de caminhos."""
    for linha in ler(caminho, ref=ref, raiz=raiz).splitlines()[:40]:
        limpa = linha.strip()
        if limpa.startswith("#"):
            return limpa.lstrip("#").strip()
    return ""


def enderecos_que_casam(termos: list[str], *, ref: str, raiz: Path) -> list[str]:
    """As rotas do site que já existem e casam com o tema.

    Fonte: `painel/mapa-do-site.json`, que é conferido em todo PR contra o
    roteamento real (`ci/mapa_do_site.py`). Ler dele em vez de varrer `urls.py`
    é a lei anti-duplicação: quem sabe os endereços deste projeto é ele.
    """
    cru = ler("painel/mapa-do-site.json", ref=ref, raiz=raiz)
    if not cru.strip():
        raise ErroDeInstrumentacao(
            "o mapa do site não veio",
            "painel/mapa-do-site.json não existe nesta ref. Os endereços não foram medidos.",
        )
    try:
        dados = json.loads(cru)
    except json.JSONDecodeError as erro:
        raise ErroDeInstrumentacao(
            "o mapa do site não é JSON válido nesta ref",
            f"{erro}. Os endereços não foram medidos.",
        ) from erro

    achados = []
    for endereco in dados.get("enderecos", []):
        alvo = f"{endereco.get('celula', '')} {endereco.get('rota', '')} {endereco.get('titulo', '')}"
        if any(re.search(termo, alvo, re.IGNORECASE) for termo in termos):
            rota = endereco.get("rota") or "(raiz)"
            achados.append(f"`{endereco.get('celula')}` · `{rota}` · {endereco.get('titulo', '')}")
    return achados


def medir_capacidades(*, ref: str, raiz: Path) -> list[tuple[Capacidade, list[str]]]:
    """Mede cada capacidade no código de PRODUÇÃO, por palavra inteira."""
    return [
        (
            cap,
            procurar(
                [cap.assinatura],
                cap.onde + FORA_DA_CAPACIDADE,
                ref=ref,
                raiz=raiz,
                palavra_inteira=True,
            ),
        )
        for cap in CAPACIDADES
    ]


# ---------------------------------------------------------------------------
# O dossiê.
# ---------------------------------------------------------------------------
def _bloco(titulo: str, linhas: list[str], vazio: str) -> list[str]:
    saida = [f"### {titulo}", ""]
    saida += [f"- {linha}" for linha in linhas] if linhas else [f"_{vazio}_"]
    saida.append("")
    return saida


def montar(termos: list[str], *, ref: str, raiz: Path, teto: int = 12) -> str:
    commit = conferir_ref(ref, raiz)
    linhas = [
        "# Dossiê de reconhecimento",
        "",
        f"**Tema procurado:** {', '.join(f'`{t}`' for t in termos) if termos else '_(nenhum: só o retrato das capacidades)_'}  ",
        f"**Lido de:** `{ref}` no commit `{commit}` (nunca do disco desta pasta)",
        "",
    ]

    if termos:
        linhas += ["## Onde o tema já aparece", ""]
        for nome, caminhos in FRENTES:
            achados = procurar(termos, caminhos, ref=ref, raiz=raiz)
            enfeitados = []
            for caminho in achados[:teto]:
                titulo = titulo_do_documento(caminho, ref=ref, raiz=raiz) if caminho.endswith(".md") else ""
                enfeitados.append(f"`{caminho}`" + (f" — {titulo}" if titulo else ""))
            if len(achados) > teto:
                enfeitados.append(f"_e mais {len(achados) - teto}, use `git grep` para ver o resto_")
            linhas += _bloco(nome, enfeitados, "nada. Se o tema é novo mesmo, esta é a resposta certa.")

        for nome, caminhos in FRENTES_CONTADAS:
            achados = procurar(termos, caminhos, ref=ref, raiz=raiz)
            recado = (
                [f"{len(achados)} arquivo(s) casam em `{caminhos[0]}` — os 5 mais recentes:"]
                + [f"`{c}`" for c in sorted(achados)[-5:]]
                if achados
                else []
            )
            linhas += _bloco(nome, recado, "nenhum.")

        linhas += ["## Endereços que já existem no site", ""]
        rotas = enderecos_que_casam(termos, ref=ref, raiz=raiz)
        linhas += [f"- {r}" for r in rotas] if rotas else ["_nenhuma rota casa: o endereço é novo._"]
        linhas.append("")

    linhas += [
        "## O que a casa sabe fazer",
        "",
        "Cada linha é medida agora, não lembrada. Onde diz SIM, o caminho citado",
        "é o molde que se copia; onde diz NÃO, a ausência é custo do seu plano.",
        "",
    ]
    for cap, achados in medir_capacidades(ref=ref, raiz=raiz):
        if achados:
            amostra = ", ".join(f"`{c}`" for c in achados[:3])
            extra = f" (e mais {len(achados) - 3})" if len(achados) > 3 else ""
            linhas.append(f"- **SIM** · {cap.nome} — {amostra}{extra}")
        else:
            linhas.append(f"- **NÃO** · {cap.nome} — {cap.se_falta}")
    linhas += [
        "",
        "---",
        "",
        "Próximo passo: `docs/caixa-de-sugestoes/DA-IDEIA-A-OBRA.md`, estação 2.",
    ]
    return "\n".join(linhas)


def principal(argv: list[str] | None = None) -> int:
    configurar_saida()
    analisador = argparse.ArgumentParser(
        prog="reconhecer",
        description="O que a plataforma já tem sobre um tema, medido do origin/main.",
    )
    analisador.add_argument("termos", nargs="*", help="palavras do tema (ex.: portfolio estudio)")
    analisador.add_argument("--ref", default="origin/main", help="a ref lida (padrão: origin/main)")
    analisador.add_argument("--teto", type=int, default=12, help="máximo de arquivos listados por frente")
    args = analisador.parse_args(argv)

    try:
        print(montar(args.termos, ref=args.ref, raiz=raiz_do_repo(), teto=args.teto))
    except ErroDeInstrumentacao as erro:
        print("NÃO MEDI, o reconhecimento não aconteceu.", file=sys.stderr)
        print(f"  {erro.resumo}", file=sys.stderr)
        if erro.detalhe:
            for linha in erro.detalhe.splitlines():
                print(f"  {linha}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
