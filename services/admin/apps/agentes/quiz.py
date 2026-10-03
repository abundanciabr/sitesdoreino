"""O robô no quiz: conferir os links no site e ler os números.

Dois trabalhos que rodam no servidor, como o panorama:

* **conferência dos links** (`conferencia_quiz`), sem modelo e sem gasto. O
  quiz devolve a conta exata de cada link: as somas de pontos possíveis, a
  faixa e a oferta de cada soma e o endereço final da saída com a origem da
  campanha, montado pela mesma função da saída real. O robô então abre cada
  página no site como um visitante, marcada como teste (`src=teste`), e confere
  se ela abre com a versão, o título e o vídeo certos. Nenhum formulário é
  enviado: enviar cria contato, e-mail e registro no CRM de verdade.
* **leitura dos números** (`leitura_quiz`): junta a leitura de gargalos, as
  propostas e as versões, escreve a parte de números sem modelo (é conta) e
  pede ao modelo forte a leitura e as ações num esquema JSON fixo. Proposta de
  nova versão só sai de gargalo com amostra suficiente, nunca muda versão
  existente e nunca publica nada.

A página de links e números (`/conteudos/quiz/<slug>/campanhas`) mostra o
robô, os botões e a última entrega (`painel_na_pagina`). As ações da conversa
(`ferramentas.py`) usam as mesmas funções daqui.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import urlencode, urlsplit

import httpx
from django.conf import settings
from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from apps.core import equipe_operacoes as operacoes
from apps.core.conteudos import (
    FORMATOS_LEGIVEIS,
    _nome_de_campanha_sugerido,
    pedir_por_host,
    proxima_chave,
)
from apps.core.documentos import para_html
from apps.core.models import MembroDaEquipe, Tarefa

from . import modelo, trabalhos
from .executor import batimento, guardar_estado, terminar
from .models import Conexao, Entrega, Execucao, Mensagem
from .panorama import _comentar_uma_vez

log = logging.getLogger(__name__)

S = Execucao.Situacao
TIPOS_DO_QUIZ = (Execucao.Tipo.CONFERENCIA_QUIZ, Execucao.Tipo.LEITURA_QUIZ)

# A escolha de links, com os mesmos nomes do link do anúncio.
SELECAO = (
    "v", "fmt", "seg", "src", "med", "cpg", "ctv",
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
)
LISTAS = ("v", "fmt", "seg", "ctv")
DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

ESPERA_DO_QUIZ = 20.0
LIMITE_DE_PAGINAS = 150
AGENTE = "MeshcraftRobo/1 (conferencia de links; aberturas marcadas como teste)"
MAX_SAIDA_DA_LEITURA = 8000
DADOS_VALEM = timedelta(hours=1)
EM_ANDAMENTO = ("proposta", "aceita", "publicada")


# ---------------------------------------------------------------- o quiz


class QuizRecusou(Exception):
    """O quiz respondeu que não dá (versão que não existe, data inválida…)."""


class QuizIndisponivel(modelo.Temporario):
    frase = "O quiz não respondeu agora. O robô tenta de novo em instantes."


def pedir_ao_quiz(host: str, metodo: str, slug: str = "", gesto: str = "", corpo=None, params=None) -> dict:
    status, dados = pedir_por_host(
        host, "quiz", metodo, slug, gesto, corpo, params, timeout=ESPERA_DO_QUIZ
    )
    if 200 <= status < 300 and isinstance(dados, dict):
        return dados
    detalhe = str(dados.get("detail") or "") if isinstance(dados, dict) else ""
    if status in (400, 404, 409, 422):
        raise QuizRecusou(detalhe[:500] or "O quiz recusou o pedido.")
    if status in (401, 403):
        raise QuizRecusou("O quiz recusou o acesso do painel.")
    raise QuizIndisponivel()


def caminho(nome: str, *args) -> str:
    """O endereço de uma tela do painel com o prefixo público (`/admin`),
    também fora de uma requisição: o executor roda numa thread sem ele."""
    endereco = reverse(nome, args=args)
    prefixo = (settings.FORCE_SCRIPT_NAME or "").rstrip("/")
    if prefixo and not endereco.startswith(prefixo + "/"):
        endereco = prefixo + endereco
    return endereco


def endereco_da_pagina(host: str, slug: str, params: dict | None = None, ancora: str = "") -> str:
    consulta = urlencode({"gerar": "1", **params}) if params else ""
    return (
        f"https://{host}{caminho('quiz_campanhas', slug)}"
        + (f"?{consulta}" if consulta else "")
        + ancora
    )


def limpar_selecao(cru: dict) -> dict:
    """A escolha (da página ou do pedido na conversa) no formato do quiz:
    listas viram texto separado por vírgula, sem repetição e sem vazios."""
    params = {}
    for nome in SELECAO:
        valor = cru.get(nome)
        if valor is None:
            continue
        itens = valor if isinstance(valor, (list, tuple)) else [valor]
        partes: list[str] = []
        for item in itens:
            texto = str(item or "")
            partes += re.split(r"[,\n]", texto) if nome in LISTAS else [texto]
        partes = list(dict.fromkeys(p.strip()[:200] for p in partes if p and p.strip()))
        if partes:
            params[nome] = ",".join(partes)[:2000] if nome in LISTAS else partes[0]
    return params


def selecao_da_tela(consulta: str) -> dict:
    """A escolha que está na página de links (a consulta do endereço dela).
    Só vale depois de a pessoa criar os links (`gerar=1`); a campanha sem
    nome ganha o mesmo nome sugerido que a página mostrou."""
    from django.http import QueryDict

    dados = QueryDict((consulta or "")[:4000])
    if dados.get("gerar") != "1":
        return {}
    params = limpar_selecao({nome: dados.getlist(nome) for nome in SELECAO})
    if "cpg" not in params:
        params["cpg"] = _nome_de_campanha_sugerido(
            [s for s in params.get("seg", "").split(",") if s]
        )
    return params


def selecao_dos_argumentos(args: dict, sugerir_campanha: bool = False) -> dict:
    publicos = [p for p in args.get("publicos") or [] if isinstance(p, str)]
    params = limpar_selecao(
        {
            "v": args.get("versoes") or [],
            "fmt": args.get("formatos") or [],
            "seg": publicos,
            "src": args.get("origem") or "",
            "med": args.get("meio") or "",
            "cpg": args.get("campanha") or "",
            "ctv": args.get("anuncios") or [],
            "utm_term": args.get("utm_term") or "",
        }
    )
    if sugerir_campanha and "cpg" not in params:
        params["cpg"] = _nome_de_campanha_sugerido(publicos)
    return params


def formato_legivel(fmt) -> str:
    return FORMATOS_LEGIVEIS.get(fmt, fmt or "—")


def descrever_selecao(params: dict) -> str:
    if not params:
        return "todos os links ativos do quiz"
    partes = []
    if params.get("v"):
        partes.append("versões " + params["v"].replace(",", ", "))
    if params.get("fmt"):
        partes.append(
            "formatos " + ", ".join(formato_legivel(f) for f in params["fmt"].split(","))
        )
    if params.get("seg"):
        partes.append("públicos " + params["seg"].replace(",", ", "))
    if params.get("src"):
        partes.append("origem " + params["src"])
    if params.get("med"):
        partes.append("tipo " + params["med"])
    if params.get("cpg"):
        partes.append("campanha " + params["cpg"])
    if params.get("ctv"):
        partes.append("anúncios " + params["ctv"].replace(",", ", "))
    return " · ".join(partes) or "todos os links ativos do quiz"


def rotulo(item: dict) -> str:
    partes = [
        item.get("version_key") or "?",
        formato_legivel(item.get("fmt")),
        item.get("seg") or "geral",
    ]
    if item.get("ctv"):
        partes.append(f"anúncio {item['ctv']}")
    return " · ".join(partes)


def _celula(texto) -> str:
    return " ".join(str(texto if texto is not None else "—").split()).replace("|", "/")


def _agora() -> str:
    return f"{timezone.localtime():%d/%m/%Y às %H:%M}"


def _data_br(iso, vazio: str) -> str:
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return vazio


def _membro(execucao: Execucao) -> MembroDaEquipe | None:
    return MembroDaEquipe.objects.filter(
        pk=execucao.pedido_por_membro_id or execucao.robo.membro_id
    ).first()


def _entregar(execucao: Execucao, titulo: str, conteudo: str, tipo: str, pendencias=None) -> Entrega:
    """A entrega do trabalho; numa retomada a mesma entrega ganha versão nova."""
    estado = execucao.estado
    pendencias = list(pendencias or [])
    entrega = Entrega.objects.filter(pk=estado.get("entrega_id")).first()
    if entrega is None:
        entrega = Entrega.objects.create(
            robo=execucao.robo,
            execucao=execucao,
            tarefa_id=execucao.tarefa_id,
            tipo=tipo,
            titulo=titulo[:200],
            conteudo=conteudo,
            parcial=bool(pendencias),
            pendencias=pendencias,
        )
        estado["entrega_id"] = entrega.id
        guardar_estado(execucao)
    elif entrega.conteudo != conteudo or entrega.parcial != bool(pendencias):
        entrega.conteudo = conteudo
        entrega.parcial = bool(pendencias)
        entrega.pendencias = pendencias
        entrega.versao += 1
        entrega.save()
    return entrega


# ---------------------------------------------------------------- conferência


MARCAS_LEGIVEIS = (
    ("data-versao=", "a marca da versão certa"),
    ("<h1>", "o título esperado"),
    ('class="video-pendente"', "o aviso de vídeo em produção"),
    ("<iframe", "o vídeo"),
    ("<source", "o vídeo"),
    ('id="experiencia-calculadora"', "a calculadora"),
    ('name="quiz_attempt"', "o formulário da conversa"),
)


def marca_legivel(marca: str) -> str:
    for inicio, texto in MARCAS_LEGIVEIS:
        if marca.startswith(inicio):
            return texto
    return "um trecho esperado"


def abrir_pagina(cliente: httpx.Client, experiencia: dict, host: str, slug: str) -> dict:
    """Abre a página de teste como um visitante e confere os trechos que ela
    precisa trazer. Só GET: nenhum formulário sai daqui."""
    url = experiencia.get("teste_url") or ""
    try:
        partes = urlsplit(url)
        fora = (
            partes.scheme != "https"
            or partes.netloc != host
            or partes.username
            or partes.password
            or not partes.path.startswith(f"/quiz/{slug}/")
        )
    except ValueError:
        fora = True
    if fora:
        return {"status": 0, "ms": 0, "faltam": [], "erro": "endereço fora do site do quiz"}
    inicio = time.monotonic()
    try:
        resposta = cliente.get(url)
    except httpx.HTTPError as erro:
        return {
            "status": 0,
            "ms": int((time.monotonic() - inicio) * 1000),
            "faltam": [],
            "erro": type(erro).__name__,
        }
    ms = int((time.monotonic() - inicio) * 1000)
    if resposta.status_code != 200:
        return {"status": resposta.status_code, "ms": ms, "faltam": [], "erro": ""}
    texto = resposta.text
    return {
        "status": 200,
        "ms": ms,
        "faltam": [m for m in experiencia.get("marcas") or [] if m not in texto],
        "erro": "",
    }


def _status_legivel(status: int) -> str:
    if status == 404:
        return "página não encontrada"
    if 300 <= status < 400:
        return "a página mandou para outro endereço"
    if status >= 500:
        return "erro no site"
    return "resposta inesperada"


def _problema_da_pagina(pagina: dict) -> str:
    if pagina.get("erro"):
        return f"a página não abriu ({pagina['erro']})"
    if pagina.get("status") != 200:
        return f"{_status_legivel(pagina.get('status') or 0)} ({pagina.get('status')})"
    if pagina.get("faltam"):
        faltam = list(dict.fromkeys(marca_legivel(m) for m in pagina["faltam"]))
        return "a página abriu, mas sem " + ", ".join(faltam)
    return ""


def problemas_da_conferencia(dados: dict, paginas: dict) -> list[str]:
    itens = []
    for versao in dados.get("versoes") or []:
        itens += [f"Versão {versao.get('key')}: {p}" for p in versao.get("problemas") or []]
    for experiencia in dados.get("experiencias") or []:
        itens += [f"{rotulo(experiencia)}: {p}" for p in experiencia.get("problemas") or []]
        pagina = paginas.get(experiencia.get("chave"))
        if pagina and _problema_da_pagina(pagina):
            itens.append(f"{rotulo(experiencia)}: {_problema_da_pagina(pagina)}.")
    # O mesmo problema de saída se repete em cada link: conta uma vez só.
    por_link = Counter(p for link in dados.get("links") or [] for p in link.get("problemas") or [])
    itens += [f"{p} ({n} links)" if n > 1 else p for p, n in por_link.items()]
    return itens


def avisos_da_conferencia(dados: dict) -> list[str]:
    itens = []
    for versao in dados.get("versoes") or []:
        itens += [f"Versão {versao.get('key')}: {a}" for a in versao.get("avisos") or []]
    onde = defaultdict(list)
    for experiencia in dados.get("experiencias") or []:
        for aviso in experiencia.get("avisos") or []:
            onde[aviso].append(rotulo(experiencia))
    for aviso, lista in onde.items():
        if len(lista) <= 3:
            itens.append(f"{aviso} ({'; '.join(lista)})")
        else:
            itens.append(f"{aviso} ({len(lista)} combinações, por exemplo {'; '.join(lista[:3])})")
    return itens


def _exemplo_legivel(exemplo: dict) -> str:
    respostas = "; ".join(
        f"{r.get('pergunta')}ª «{r.get('opcao')}»" for r in exemplo.get("respostas") or []
    )
    return f"soma {exemplo.get('pontuacao')} ({respostas})" if respostas else f"soma {exemplo.get('pontuacao')}"


def relatorio_da_conferencia(estado: dict, robo_nome: str, pedido: str) -> tuple[str, str, list[str]]:
    """O relatório em Markdown, o veredito curto e a lista de problemas."""
    dados = estado["conferencia"]
    paginas = estado.get("paginas") or {}
    experiencias = dados.get("experiencias") or []
    links = dados.get("links") or []
    problemas = problemas_da_conferencia(dados, paginas)
    avisos = avisos_da_conferencia(dados)
    if problemas:
        veredito = f"NÃO SUBA OS ANÚNCIOS AINDA: {len(problemas)} problema(s) para corrigir"
    elif avisos:
        veredito = "PODE SUBIR OS ANÚNCIOS, com avisos para saber"
    else:
        veredito = "PODE SUBIR OS ANÚNCIOS: tudo conferido"

    abertas = [p for p in paginas.values()]
    boas = [p for p in abertas if p.get("status") == 200 and not p.get("faltam") and not p.get("erro")]
    tempos = [p["ms"] for p in abertas if p.get("status") == 200]
    media = (sum(tempos) / len(tempos) / 1000) if tempos else None
    com_saida_real = [l for l in links if any(not s.get("demonstracao") for s in l.get("saidas") or [])]
    inteiras = [
        l for l in com_saida_real
        if all(s.get("url_final") and not s.get("faltam") for s in l["saidas"] if not s.get("demonstracao"))
    ]
    so_demonstracao = [l for l in links if l.get("saidas") and l not in com_saida_real]

    linhas = [
        f"# Conferência dos links — {dados.get('quiz_titulo') or dados.get('quiz_slug')}",
        "",
        f"**Veredito: {veredito}.**",
        "",
        f"Conferido pelo {robo_nome} em {_agora()}, no site {dados.get('host')}. "
        f"Escolha conferida: {descrever_selecao(estado.get('params') or {})}."
        + (f" Pedido: {_curto(pedido, 500)}" if pedido else ""),
        "",
        "## Resumo",
        "",
        f"- Links conferidos: **{len(links)}** ({len(dados.get('versoes') or [])} versão(ões), "
        f"{len(experiencias)} combinação(ões) de formato e público)",
        f"- Páginas abertas no site: **{len(boas)} de {len(experiencias)}** abriram certas"
        + (f" (tempo médio {media:.2f} s)".replace(".", ",") if media is not None else ""),
    ]
    if estado.get("fora_do_limite"):
        linhas.append(
            f"- {estado['fora_do_limite']} página(s) ficaram sem abrir: o limite é "
            f"{LIMITE_DE_PAGINAS} por conferência. Peça uma conferência só das versões que vão anunciar."
        )
    if com_saida_real:
        linhas.append(
            f"- Saída para o checkout: **{len(inteiras)} de {len(com_saida_real)}** links levam a "
            "origem da campanha inteira até o checkout"
        )
    if so_demonstracao:
        linhas.append(
            f"- {len(so_demonstracao)} link(s) só levam a ofertas de demonstração (sem cobrança)"
        )
    linhas += [f"- Problemas: **{len(problemas)}** · Avisos: **{len(avisos)}**", ""]

    if problemas:
        linhas += ["## O que corrigir antes de anunciar", ""]
        linhas += [f"- {p}" for p in problemas[:60]]
        if len(problemas) > 60:
            linhas.append(f"- e mais {len(problemas) - 60} problema(s).")
        linhas.append("")

    linhas += [
        "## Que oferta cada pontuação mostra",
        "",
        "| Versão | Faixa | Pontos | Acontece? | Oferta | Saída |",
        "|---|---|---|---|---|---|",
    ]
    exemplos = []
    for versao in dados.get("versoes") or []:
        for faixa in versao.get("faixas") or []:
            saida = "demonstração, sem cobrança" if faixa.get("demonstracao") else "checkout real"
            linhas.append(
                f"| {_celula(versao.get('key'))} | {_celula(faixa.get('key'))} | "
                f"{faixa.get('min')} a {faixa.get('max')} | {'sim' if faixa.get('alcancavel') else 'nunca'} | "
                f"{_celula(faixa.get('oferta') or faixa.get('oferta_id') or '—')} | {saida} |"
            )
            if faixa.get("exemplos"):
                exemplos.append(
                    f"- **{versao.get('key')} · {faixa.get('key')}**: "
                    + _exemplo_legivel(faixa["exemplos"][0])
                )
    if exemplos:
        linhas += ["", "Exemplo de respostas que caem em cada faixa (a menor soma de cada uma):", ""]
        linhas += exemplos
    linhas.append("")

    exemplo_de_saida = next(iter(com_saida_real), None)
    if exemplo_de_saida:
        linhas += [
            "## Para onde a pessoa vai ao clicar na oferta",
            "",
            f"Exemplo do link **{rotulo(exemplo_de_saida)}**, montado pela mesma função da saída real:",
            "",
        ]
        for saida in exemplo_de_saida["saidas"]:
            if saida.get("demonstracao"):
                linhas.append(f"- Faixa **{saida.get('faixa')}**: página de demonstração, sem cobrança")
            else:
                linhas.append(f"- Faixa **{saida.get('faixa')}**: `{saida.get('url_final')}`")
        linhas.append("")

    linhas += [
        "## Páginas abertas no site",
        "",
        "| Versão · formato · público | Abriu? | Tempo | O que o robô viu |",
        "|---|---|---|---|",
    ]
    ordenadas = sorted(
        experiencias,
        key=lambda e: (not _problema_da_pagina(paginas.get(e.get("chave")) or {}), e.get("chave") or ""),
    )
    for experiencia in ordenadas[:80]:
        pagina = paginas.get(experiencia.get("chave"))
        if pagina is None:
            linhas.append(f"| {_celula(rotulo(experiencia))} | não aberta | — | ficou fora do limite |")
            continue
        problema = _problema_da_pagina(pagina)
        visto = problema or (
            f"versão certa; título «{_celula(experiencia.get('headline'))}»"
            if experiencia.get("headline")
            else "versão certa"
        )
        tempo = f"{pagina['ms'] / 1000:.2f} s".replace(".", ",") if pagina.get("ms") else "—"
        linhas.append(
            f"| {_celula(rotulo(experiencia))} | {'sim' if not problema else 'com problema'} | "
            f"{tempo} | {_celula(visto)} |"
        )
    if len(ordenadas) > 80:
        linhas.append(f"| e mais {len(ordenadas) - 80} combinação(ões) | | | |")
    linhas.append("")

    if avisos:
        linhas += ["## Avisos (não impedem anunciar, mas é bom saber)", ""]
        linhas += [f"- {a}" for a in avisos[:30]]
        linhas.append("")

    linhas += ["## Os links conferidos", ""]
    linhas += [f"- **{_celula(rotulo(l))}**: `{l.get('url')}`" for l in links[:30]]
    if len(links) > 30:
        linhas.append(f"- e mais {len(links) - 30} link(s), na página de links e números.")
    linhas += [
        "",
        "## O que o robô não fez",
        "",
        "- Não enviou nenhum formulário: enviar criaria contato, e-mail e registro no CRM de verdade.",
        "- Não abriu o checkout nem comprou nada: o endereço final foi montado pela mesma função "
        "que o site usa no clique da oferta.",
        "- Abriu as páginas marcadas como teste (`src=teste`): essas aberturas ficam fora das porcentagens.",
        "- Não usou IA: esta conferência não gasta nada.",
    ]
    return "\n".join(linhas) + "\n", veredito, problemas


def _tarefa_de_correcao(execucao: Execucao, membro: MembroDaEquipe, slug: str, problemas: list[str], entrega: Entrega):
    """Problema achado vira trabalho no painel: uma tarefa para a pessoa
    corrigir, ou um comentário na que já está aberta."""
    if execucao.estado.get("tarefa_de_correcao"):
        return execucao.estado["tarefa_de_correcao"]
    quem = f"{execucao.robo.nome} (a pedido de {membro.nome})"
    titulo = f"Corrigir os links do quiz {slug} antes de anunciar"
    aberta = (
        Tarefa.objects.filter(titulo=titulo)
        .exclude(situacao=Tarefa.Situacao.CONCLUIDA)
        .order_by("-id")
        .first()
    )
    if aberta is not None:
        operacoes.comentar(
            aberta,
            (
                f"Nova conferência (entrega nº {entrega.id}) achou {len(problemas)} "
                f"problema(s). O primeiro: {problemas[0]}"
            )[:500],
            quem,
            None,
        )
        tarefa = aberta
    else:
        lista = "\n".join(f"- {p}" for p in problemas[:30])
        tarefa, erros = operacoes.criar_tarefa(
            {
                "titulo": titulo,
                "descricao": (
                    f"A conferência do robô achou {len(problemas)} problema(s) nos links do "
                    f"quiz {slug}. Corrija e peça uma nova conferência na página de links e "
                    f"números.\n\n{lista}\n\nRelatório completo: entrega nº {entrega.id}."
                )[:5000],
                "responsavel": str(membro.id),
                "situacao": Tarefa.Situacao.A_FAZER,
            },
            quem,
            executor=Tarefa.Executor.PESSOA,
        )
        if erros:  # pragma: no cover - os dados acima são sempre válidos
            log.warning("Tarefa de correção não criada: %s", erros)
            return None
    entrega.tarefa_id = tarefa.id
    entrega.save(update_fields=["tarefa_id", "atualizada_em"])
    execucao.estado["tarefa_de_correcao"] = tarefa.id
    guardar_estado(execucao)
    return tarefa.id


def executar_conferencia(execucao: Execucao) -> None:
    membro = _membro(execucao)
    if membro is None or not membro.ativo:
        terminar(execucao, S.CANCELADA, "A pessoa não está mais ativa na equipe.")
        return
    estado = execucao.estado
    host, slug = estado.get("host") or "", estado.get("quiz") or ""

    if "conferencia" not in estado:
        batimento(
            execucao,
            "Pedindo ao quiz a conta de cada link: pontos, faixas, ofertas e saídas",
            progresso=5,
        )
        try:
            estado["conferencia"] = pedir_ao_quiz(
                host, "GET", slug, "conferencia", params=estado.get("params") or {}
            )
        except QuizRecusou as recusa:
            terminar(execucao, S.FALHOU, f"O quiz recusou a conferência: {recusa}")
            return
        guardar_estado(execucao)

    dados = estado["conferencia"]
    experiencias = [e for e in dados.get("experiencias") or [] if e.get("teste_url")]
    paginas = estado.setdefault("paginas", {})
    faltam = [e for e in experiencias if e.get("chave") not in paginas]
    cabe = max(0, LIMITE_DE_PAGINAS - len(paginas))
    estado["fora_do_limite"] = max(0, len(faltam) - cabe)
    faltam = faltam[:cabe]
    if faltam:
        batimento(
            execucao,
            f"Abrindo {len(faltam)} página(s) do quiz no site como um visitante (marcadas como teste)",
            progresso=12,
        )
        with httpx.Client(
            headers={"User-Agent": AGENTE}, follow_redirects=False, timeout=15.0
        ) as cliente:
            for n, experiencia in enumerate(faltam, 1):
                paginas[experiencia["chave"]] = abrir_pagina(
                    cliente, experiencia, dados.get("host") or host, slug
                )
                cliente.cookies.clear()
                # Só o progresso: a etapa escrita a cada página encheria o registro.
                batimento(execucao, progresso=12 + int(76 * len(paginas) / max(len(experiencias), 1)))
                if n % 10 == 0:
                    guardar_estado(execucao)
        guardar_estado(execucao)

    batimento(execucao, "Escrevendo o relatório", progresso=92)
    conteudo, veredito, problemas = relatorio_da_conferencia(estado, execucao.robo.nome, execucao.pedido)
    entrega = _entregar(
        execucao,
        f"Conferência dos links do quiz {slug} — {timezone.localtime():%d/%m %H:%M}",
        conteudo,
        "conferencia_quiz",
    )
    if problemas:
        _tarefa_de_correcao(execucao, membro, slug, problemas, entrega)
    terminar(execucao, S.CONCLUIDA, resultado=f"{veredito}. Entrega nº {entrega.id}.")


# ---------------------------------------------------------------- números


def _taxa(medida) -> dict | None:
    if not isinstance(medida, dict):
        return None
    return {
        "valor": medida.get("valor"),
        "de": medida.get("numerador"),
        "em": medida.get("denominador"),
        "inconclusiva": bool(medida.get("inconclusiva")),
    }


def _gargalo(g: dict) -> dict:
    return {
        "id": g.get("id"),
        "tipo": g.get("tipo"),
        "onde": (g.get("escopo") or {}).get("nome"),
        "versao": g.get("version_key"),
        "prioridade": g.get("prioridade"),
        "evidencia": (g.get("evidencia") or {}).get("texto"),
        "inconclusivo": bool(g.get("inconclusivo")),
    }


def _curto(texto, limite: int = 200) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _proposta_curta(p: dict) -> dict:
    return {
        "id": p.get("id"),
        "versao_base": p.get("versao_base"),
        "key_sugerida": p.get("key_sugerida"),
        "estado": p.get("estado"),
        "prioridade": p.get("prioridade"),
        "gargalo": p.get("gargalo"),
        "hipotese": _curto(p.get("hipotese")),
        "mudanca": _curto(p.get("mudanca")),
        "resultado": _curto(p.get("resultado_texto")) or None,
    }


def _chaves_do_rascunho(rascunho: dict) -> list[str]:
    conteudo = rascunho.get("content") if isinstance(rascunho.get("content"), dict) else {}
    return [
        v["key"]
        for v in conteudo.get("versions") or []
        if isinstance(v, dict) and isinstance(v.get("key"), str)
    ]


def resumo_dos_numeros(evolucao: dict, propostas: dict, rascunho: dict) -> dict:
    """O que importa da leitura de gargalos, num tamanho que cabe no pedido
    ao modelo e na entrega."""
    versoes = []
    for funil in evolucao.get("funil") or []:
        if not isinstance(funil, dict) or not (funil.get("visitas_elegiveis") or funil.get("ativa")):
            continue
        versoes.append(
            {
                "versao": funil.get("version_key"),
                "ativa": bool(funil.get("ativa")),
                "visitas": funil.get("visitas_elegiveis") or 0,
                "chegaram_ao_resultado": funil.get("conclusoes") or 0,
                "foram_para_a_oferta": funil.get("saidas") or 0,
                "saidas_reais": funil.get("saidas_reais") or 0,
                "saidas_de_demonstracao": funil.get("saidas_demonstracao") or 0,
                "taxa_de_resultado": _taxa(funil.get("taxa_conclusao")),
                "taxa_de_saida": _taxa(funil.get("taxa_saida_total")),
                "etapas": [
                    {
                        "etapa": e.get("rotulo"),
                        "viram": e.get("viram"),
                        "seguiram": e.get("avancaram"),
                        "perderam": e.get("perda"),
                    }
                    for e in funil.get("etapas") or []
                    if isinstance(e, dict) and e.get("medida")
                ][:15],
            }
        )
    campanhas = []
    for escopo in evolucao.get("por_campanha") or []:
        if not isinstance(escopo, dict):
            continue
        campanhas.append(
            {
                "campanha": escopo.get("nome"),
                "sessoes": escopo.get("sessoes") or 0,
                "versoes": [
                    {
                        "versao": v.get("version_key"),
                        "visitas": v.get("visitas_elegiveis"),
                        "chegaram_ao_resultado": v.get("conclusoes"),
                        "saidas_reais": v.get("saidas_reais"),
                        "saidas_de_demonstracao": v.get("saidas_demonstracao"),
                    }
                    for v in escopo.get("versoes") or []
                    if isinstance(v, dict)
                ],
                "gargalos": [_gargalo(g) for g in (escopo.get("gargalos") or [])[:2] if isinstance(g, dict)],
            }
        )
    campanhas.sort(key=lambda c: -c["sessoes"])
    dimensoes = {
        d.get("tipo"): [
            {"valor": e.get("nome"), "sessoes": e.get("sessoes")}
            for e in d.get("escopos") or []
            if isinstance(e, dict)
        ][:12]
        for d in evolucao.get("por_dimensao") or []
        if isinstance(d, dict)
    }
    dias = [
        {
            "dia": e.get("nome"),
            "sessoes": e.get("sessoes") or 0,
            "chegaram_ao_resultado": sum(
                (v.get("conclusoes") or 0) for v in e.get("versoes") or [] if isinstance(v, dict)
            ),
        }
        for e in evolucao.get("por_dia") or []
        if isinstance(e, dict)
    ][-21:]
    return {
        "periodo": evolucao.get("periodo") or {},
        "amostra_minima": evolucao.get("amostra_minima") or 30,
        "visitas_elegiveis": evolucao.get("visitas_elegiveis") or 0,
        "teste": evolucao.get("teste") or {},
        "versoes": versoes,
        "gargalos": [_gargalo(g) for g in (evolucao.get("gargalos") or [])[:15] if isinstance(g, dict)],
        "campanhas": campanhas[:15],
        "dimensoes": dimensoes,
        "dias": dias,
        "dados_faltantes": [
            d.get("texto") for d in evolucao.get("dados_faltantes") or [] if isinstance(d, dict) and d.get("texto")
        ],
        "propostas": [_proposta_curta(p) for p in (propostas.get("propostas") or [])[:20] if isinstance(p, dict)],
        "versoes_publicadas": [k for k in rascunho.get("publicadas") or [] if isinstance(k, str)],
        "versoes_no_rascunho": _chaves_do_rascunho(rascunho),
        "comercial": (evolucao.get("comercial") or {}).get("estado") or "sem dados de compra",
        "avisos": [a for a in evolucao.get("avisos") or [] if isinstance(a, str)],
    }


def coletar_numeros(host: str, slug: str, inicio: str = "", fim: str = "") -> dict:
    periodo = {k: v for k, v in (("inicio", inicio), ("fim", fim)) if v}
    evolucao = pedir_ao_quiz(host, "GET", slug, "evolucao", params=periodo)
    propostas = pedir_ao_quiz(host, "GET", slug, "propostas")
    rascunho = pedir_ao_quiz(host, "GET", slug, "rascunho")
    return resumo_dos_numeros(evolucao, propostas, rascunho)


def _pct(medida) -> str:
    if not medida or medida.get("valor") is None:
        return "—"
    return f"{round(medida['valor'] * 100)}%"


def documento_dos_numeros(dados: dict, robo_nome: str, slug: str, host: str) -> str:
    periodo = dados.get("periodo") or {}
    amostra = dados.get("amostra_minima") or 30
    teste = dados.get("teste") or {}
    linhas = [
        f"# Leitura dos números — quiz {slug}",
        "",
        f"Período: {_data_br(periodo.get('inicio'), 'o começo')} a {_data_br(periodo.get('fim'), 'hoje')} "
        f"(horário de São Paulo). Montada pelo {robo_nome} em {_agora()}.",
        "",
        f"Contam só visitas de verdade: **{dados.get('visitas_elegiveis', 0)}** visita(s). "
        f"As {teste.get('visitas', 0)} visita(s) de teste da equipe ficaram de fora.",
        f"Com menos de {amostra} visitas, um número serve para observar, não para decidir.",
        "",
        "## Por versão",
        "",
        "| Versão | Visitas | Chegaram ao resultado | Foram para a oferta (dos que chegaram) | Dá para decidir? |",
        "|---|---|---|---|---|",
    ]
    for v in dados.get("versoes") or []:
        incerta = (v.get("taxa_de_resultado") or {}).get("inconclusiva", True)
        linhas.append(
            f"| {_celula(v.get('versao'))}{'' if v.get('ativa') else ' (desligada)'} | {v.get('visitas')} | "
            f"{v.get('chegaram_ao_resultado')} ({_pct(v.get('taxa_de_resultado'))}) | "
            f"{v.get('foram_para_a_oferta')} ({_pct(v.get('taxa_de_saida'))}) | "
            f"{'não: amostra pequena' if incerta else 'sim'} |"
        )
    if not dados.get("versoes"):
        linhas.append("| — | 0 | — | — | — |")
    linhas += ["", "## Onde o quiz perde gente", ""]
    gargalos = dados.get("gargalos") or []
    if gargalos:
        for g in gargalos[:10]:
            marca = "amostra pequena" if g.get("inconclusivo") else f"prioridade {g.get('prioridade')}"
            linhas.append(f"- **{g.get('versao')}** · {g.get('evidencia')} — {marca}")
    else:
        linhas.append("Ainda não há perda medida: faltam visitas.")
    campanhas = dados.get("campanhas") or []
    if campanhas:
        linhas += [
            "",
            "## Por campanha",
            "",
            "| Campanha | Visitas | Chegaram ao resultado | Saídas reais | Saídas de demonstração |",
            "|---|---|---|---|---|",
        ]
        for c in campanhas[:12]:
            versoes = c.get("versoes") or []
            linhas.append(
                f"| {_celula(c.get('campanha'))} | {c.get('sessoes')} | "
                f"{sum((v.get('chegaram_ao_resultado') or 0) for v in versoes)} | "
                f"{sum((v.get('saidas_reais') or 0) for v in versoes)} | "
                f"{sum((v.get('saidas_de_demonstracao') or 0) for v in versoes)} |"
            )
    dias = [d for d in dados.get("dias") or [] if d.get("sessoes")]
    if dias:
        linhas += ["", "## Por dia", "", "| Dia | Visitas | Chegaram ao resultado |", "|---|---|---|"]
        linhas += [
            f"| {_data_br(d.get('dia'), _celula(d.get('dia')))} | {d.get('sessoes')} | {d.get('chegaram_ao_resultado')} |"
            for d in dias[-14:]
        ]
    linhas += ["", "## O que ainda falta medir", ""]
    linhas += [f"- {t}" for t in dados.get("dados_faltantes") or []] or ["Nada faltando."]
    propostas = dados.get("propostas") or []
    if propostas:
        linhas += ["", "## Propostas de nova versão que já existiam", ""]
        for p in propostas[:10]:
            linhas.append(
                f"- Nº {p.get('id')}: a partir da **{p.get('versao_base')}**, criar a "
                f"**{p.get('key_sugerida')}** ({p.get('estado')}). {p.get('hipotese')}"
            )
    linhas += [
        "",
        f"Detalhe etapa por etapa: [Onde o quiz perde gente](https://{host}{caminho('quiz_evolucao', slug)}).",
    ]
    return "\n".join(linhas) + "\n"


INSTRUCOES_DA_LEITURA = (
    "Você é o robô de uma pessoa da equipe da Meshcraft, uma escola de modelagem "
    "3D. Recebe em JSON os números de um quiz que leva cada pessoa a uma de duas "
    "ofertas. O quiz tem versões (A, B1, B2…) que coexistem, formatos (texto, "
    "vídeo, calculadora, conversa com IA) e públicos; cada anúncio usa um link "
    "fixo de versão, formato e público. Escreva em português do Brasil, para quem "
    "não é técnico.\n\n"
    "Regras:\n"
    "- Use só os números recebidos. Não invente números, datas, versões nem campanhas.\n"
    "- Abaixo de amostra_minima visitas o número é inconclusivo: diga isso e trate "
    "como observação, não como decisão.\n"
    "- As campanhas são direcionadas, não sorteadas: comparar versões ou campanhas "
    "mostra o que aconteceu, não prova causa.\n"
    "- Clique para a oferta não é compra; não há dados de compra.\n"
    "- Visitas de teste já estão fora das contas.\n"
    "- Nunca proponha mudar uma versão existente: mudança vira versão nova.\n"
    "- Não sugira aumentar verba nem mexer em orçamento de anúncio.\n\n"
    "Devolva:\n"
    "- leitura: Markdown simples (parágrafos curtos e listas com '- '), sem "
    "título, até 300 palavras: o que os números mostram, onde o quiz perde gente "
    "e o que falta medir.\n"
    "- acoes: até 5 ações concretas para a equipe, em ordem de prioridade, cada "
    "uma com o porquê e a evidência (o número que a sustenta). tipo é um de: "
    "medir, corrigir, testar_versao, campanha, conteudo.\n"
    "- propostas: proposta de nova versão só para gargalos da lista com "
    "inconclusivo=false; use o id do gargalo em gargalo_id e a versão dele em "
    "versao_base. Se todos forem inconclusivos, devolva a lista vazia."
)

FORMATO_DA_LEITURA = {
    "type": "json_schema",
    "name": "leitura_do_quiz",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["leitura", "acoes", "propostas"],
        "properties": {
            "leitura": {"type": "string"},
            "acoes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["titulo", "porque", "evidencia", "tipo"],
                    "properties": {
                        "titulo": {"type": "string"},
                        "porque": {"type": "string"},
                        "evidencia": {"type": "string"},
                        "tipo": {
                            "type": "string",
                            "enum": ["medir", "corrigir", "testar_versao", "campanha", "conteudo"],
                        },
                    },
                },
            },
            "propostas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["gargalo_id", "versao_base", "hipotese", "mudanca", "prioridade"],
                    "properties": {
                        "gargalo_id": {"type": "string"},
                        "versao_base": {"type": "string"},
                        "hipotese": {"type": "string"},
                        "mudanca": {"type": "string"},
                        "prioridade": {"type": "string", "enum": ["alta", "media", "baixa"]},
                    },
                },
            },
        },
    },
}


def ler_com_o_modelo(execucao: Execucao, dados: dict, slug: str) -> dict:
    conexao = modelo.conexao()
    execucao.modelo = conexao.modelo_forte
    Execucao.objects.filter(pk=execucao.pk).update(modelo=execucao.modelo)
    pedido = {
        "quiz": slug,
        "hoje": operacoes.hoje().isoformat(),
        "pedido_da_pessoa": execucao.pedido or None,
        **dados,
    }
    resposta = modelo.responder(
        modelo=execucao.modelo,
        instrucoes=INSTRUCOES_DA_LEITURA,
        itens=[{"role": "user", "content": json.dumps(pedido, ensure_ascii=False)}],
        max_saida=MAX_SAIDA_DA_LEITURA,
        execucao=execucao,
        robo=execucao.robo,
        formato=FORMATO_DA_LEITURA,
    )
    try:
        leitura = json.loads(resposta.texto)
    except ValueError:
        leitura = None
    if not isinstance(leitura, dict) or not isinstance(leitura.get("leitura"), str):
        raise modelo.ProblemaDoModelo(
            "A resposta do modelo veio cortada. Peça a leitura de novo."
            if not resposta.completa
            else "A resposta do modelo não veio no formato combinado."
        )
    return {
        "leitura": leitura["leitura"].strip(),
        "acoes": [a for a in leitura.get("acoes") or [] if isinstance(a, dict)][:5],
        "propostas": [p for p in leitura.get("propostas") or [] if isinstance(p, dict)],
    }


def propostas_aceitaveis(leitura: dict, dados: dict) -> list[dict]:
    """O que o modelo propôs, filtrado pelo código: só gargalo conclusivo da
    lista, da versão dele, que exista publicada e sem proposta em andamento."""
    conclusivos = {g["id"]: g for g in dados.get("gargalos") or [] if not g.get("inconclusivo")}
    ocupados = {p.get("gargalo") for p in dados.get("propostas") or [] if p.get("estado") in EM_ANDAMENTO}
    publicadas = set(dados.get("versoes_publicadas") or [])
    escolhidas = []
    for proposta in leitura.get("propostas") or []:
        gargalo = conclusivos.get(proposta.get("gargalo_id"))
        if (
            gargalo is None
            or proposta.get("versao_base") != gargalo.get("versao")
            or gargalo.get("versao") not in publicadas
            or gargalo["id"] in ocupados
            or any(e["gargalo_id"] == gargalo["id"] for e in escolhidas)
            or not str(proposta.get("hipotese") or "").strip()
            or not str(proposta.get("mudanca") or "").strip()
        ):
            continue
        escolhidas.append(proposta)
        if len(escolhidas) == 2:
            break
    return escolhidas


def registrar_propostas(execucao: Execucao, host: str, slug: str) -> None:
    estado = execucao.estado
    escolhidas = propostas_aceitaveis(estado["leitura"], estado["dados"])
    registradas = estado.setdefault("propostas_registradas", {})
    if not escolhidas:
        return
    batimento(
        execucao,
        "Registrando propostas de nova versão (nenhuma versão existente muda)",
        progresso=78,
    )
    # Lista de agora, não a da coleta: numa retomada a proposta já pode existir.
    atuais = pedir_ao_quiz(host, "GET", slug, "propostas").get("propostas") or []
    em_andamento = {p.get("gargalo"): p for p in atuais if p.get("estado") in EM_ANDAMENTO}
    ocupadas = (
        set(estado["dados"].get("versoes_publicadas") or [])
        | set(estado["dados"].get("versoes_no_rascunho") or [])
        | {p.get("key_sugerida") for p in atuais if p.get("estado") in EM_ANDAMENTO}
    )
    for proposta in escolhidas:
        gargalo = proposta["gargalo_id"]
        if gargalo in registradas:
            continue
        if gargalo in em_andamento:
            existente = em_andamento[gargalo]
            registradas[gargalo] = {
                "id": existente.get("id"),
                "key": existente.get("key_sugerida"),
                "base": existente.get("versao_base"),
                "hipotese": _curto(existente.get("hipotese")),
                "ja_existia": True,
            }
        else:
            key = proxima_chave(proposta["versao_base"], ocupadas)
            try:
                criada = pedir_ao_quiz(
                    host,
                    "POST",
                    slug,
                    "propostas",
                    corpo={
                        "versao_base": proposta["versao_base"],
                        "gargalo": gargalo[:200],
                        "hipotese": proposta["hipotese"][:4000],
                        "mudanca": proposta["mudanca"][:4000],
                        "prioridade": proposta.get("prioridade") or "media",
                        "key_sugerida": key,
                    },
                )
                registradas[gargalo] = {
                    "id": criada.get("id"),
                    "key": criada.get("key_sugerida") or key,
                    "base": proposta["versao_base"],
                    "hipotese": _curto(proposta["hipotese"]),
                }
                ocupadas.add(key)
            except QuizRecusou as recusa:
                registradas[gargalo] = {"erro": str(recusa), "base": proposta["versao_base"]}
        guardar_estado(execucao)


def conteudo_da_leitura(estado: dict, host: str, slug: str) -> str:
    partes = [estado["documento"].rstrip(), "", "## Leitura do robô", ""]
    leitura = estado.get("leitura")
    if leitura:
        partes.append(leitura["leitura"])
        partes += ["", "## O que fazer agora", ""]
        if leitura.get("acoes"):
            for n, acao in enumerate(leitura["acoes"], 1):
                partes.append(
                    f"{n}. **{_celula(acao.get('titulo'))}** — {_celula(acao.get('porque'))} "
                    f"*Evidência: {_celula(acao.get('evidencia'))}*"
                )
        else:
            partes.append("Nenhuma ação sugerida com estes números.")
        partes += ["", "## Propostas de nova versão desta leitura", ""]
        registradas = estado.get("propostas_registradas") or {}
        if registradas:
            evolucao = f"https://{host}{caminho('quiz_evolucao', slug)}"
            for gargalo, r in registradas.items():
                if r.get("erro"):
                    partes.append(f"- Gargalo {gargalo}: o quiz não aceitou a proposta ({r['erro']}).")
                elif r.get("ja_existia"):
                    partes.append(
                        f"- Gargalo {gargalo}: já havia a proposta nº {r.get('id')} "
                        f"(criar a {r.get('key')} a partir da {r.get('base')}); nada novo registrado."
                    )
                else:
                    partes.append(
                        f"- Proposta nº {r.get('id')}: criar a **{r.get('key')}** a partir da "
                        f"**{r.get('base')}**. {r.get('hipotese')} Aceite ou descarte em "
                        f"[Onde o quiz perde gente]({evolucao})."
                    )
            partes.append("")
            partes.append("Nada mudou no quiz: a proposta só registra a ideia; quem decide é a equipe.")
        else:
            partes.append(
                "Nenhuma registrada: só sai proposta de gargalo com amostra suficiente "
                f"(pelo menos {estado['dados'].get('amostra_minima', 30)} visitas), e nenhuma "
                "versão existente muda."
            )
    else:
        partes.append("Ainda não feita: veja as pendências abaixo.")
    pendencias = estado.get("pendencias") or []
    if pendencias:
        partes += ["", "## Pendências", ""]
        partes += [f"- {p}" for p in pendencias]
    return "\n".join(partes) + "\n"


def executar_leitura(execucao: Execucao) -> None:
    robo = execucao.robo
    membro = _membro(execucao)
    if membro is None or not membro.ativo:
        terminar(execucao, S.CANCELADA, "A pessoa não está mais ativa na equipe.")
        return
    estado = execucao.estado
    host, slug = estado.get("host") or "", estado.get("quiz") or ""

    coletado_em = estado.get("coletado_em")
    if (
        coletado_em
        and not estado.get("leitura")
        and timezone.now() - datetime.fromisoformat(coletado_em) > DADOS_VALEM
    ):
        # Retomada muito depois (o teto voltou no mês seguinte): os números
        # guardados envelheceram.
        estado.pop("dados", None)
        estado.pop("documento", None)

    if "dados" not in estado:
        batimento(
            execucao,
            "Lendo os números do quiz: visitas, respostas, cliques e onde perde gente",
            progresso=10,
        )
        try:
            estado["dados"] = coletar_numeros(
                host, slug, estado.get("inicio") or "", estado.get("fim") or ""
            )
        except QuizRecusou as recusa:
            terminar(execucao, S.FALHOU, f"O quiz recusou a leitura: {recusa}")
            return
        estado["coletado_em"] = timezone.now().isoformat()
        guardar_estado(execucao)

    if "documento" not in estado:
        batimento(execucao, "Montando a parte de números", progresso=30)
        estado["documento"] = documento_dos_numeros(estado["dados"], robo.nome, slug, host)
        guardar_estado(execucao)

    pendencias = []
    espera = None
    if not estado.get("leitura"):
        batimento(execucao, "Escrevendo a leitura e as ações com o modelo forte", progresso=50)
        try:
            estado["leitura"] = ler_com_o_modelo(execucao, estado["dados"], slug)
        except modelo.Temporario:
            raise
        except modelo.ProblemaDoModelo as problema:
            espera = problema
            pendencias.append("Leitura do robô: " + problema.frase)
        guardar_estado(execucao)

    if estado.get("leitura") and not estado.get("propostas_feitas"):
        registrar_propostas(execucao, host, slug)
        estado["propostas_feitas"] = True
        guardar_estado(execucao)

    estado["pendencias"] = pendencias
    batimento(execucao, "Salvando a entrega", progresso=90)
    entrega = _entregar(
        execucao,
        f"Leitura dos números do quiz {slug} — {timezone.localtime():%d/%m}",
        conteudo_da_leitura(estado, host, slug),
        "leitura_quiz",
        pendencias,
    )
    if espera is not None:
        _comentar_uma_vez(
            execucao,
            membro,
            entrega,
            f"Entrega parcial salva: «{entrega.titulo}» (nº {entrega.id}). Falta a "
            f"leitura do robô: {espera.frase}",
        )
        terminar(execucao, espera.situacao, espera.frase, resultado=f"Entrega parcial nº {entrega.id}.")
        return
    _comentar_uma_vez(
        execucao,
        membro,
        entrega,
        f"Entrega pronta: «{entrega.titulo}» (nº {entrega.id}). Abra na página de "
        "links e números do quiz ou na página do robô.",
    )
    if execucao.tarefa_id:
        tarefa = Tarefa.objects.filter(pk=execucao.tarefa_id).first()
        if tarefa is not None and tarefa.situacao != Tarefa.Situacao.CONCLUIDA:
            operacoes.mudar_situacao(
                tarefa,
                Tarefa.Situacao.CONCLUIDA,
                "",
                f"{robo.nome} (a pedido de {membro.nome})",
            )
    novas = [r for r in (estado.get("propostas_registradas") or {}).values() if r.get("id") and not r.get("ja_existia")]
    terminar(
        execucao,
        S.CONCLUIDA,
        resultado=f"Entrega nº {entrega.id}"
        + (f"; {len(novas)} proposta(s) de nova versão registrada(s)." if novas else "."),
    )


# ---------------------------------------------------------------- conversa


def lista_de_quizzes(host: str) -> dict:
    dados = pedir_ao_quiz(host, "GET")
    return {
        "quizzes": [
            {
                "slug": q.get("slug"),
                "titulo": q.get("title"),
                "publicado": q.get("published"),
                "por_versao_no_link": q.get("directed"),
            }
            for q in dados.get("items") or []
            if isinstance(q, dict)
        ]
    }


def retrato_do_quiz(host: str, slug: str, levantar: bool = False) -> dict:
    """A estrutura do quiz para o robô responder sem consultar: versões,
    formatos, públicos, faixas e a oferta de cada faixa."""
    try:
        dados = pedir_ao_quiz(host, "GET", slug, "conferencia")
    except (QuizRecusou, QuizIndisponivel) as falha:
        if levantar:
            raise
        return {"erro": getattr(falha, "frase", "") or str(falha)}
    combinacoes = defaultdict(lambda: {"formatos": set(), "publicos": set()})
    for experiencia in dados.get("experiencias") or []:
        combinacao = combinacoes[experiencia.get("version_key")]
        combinacao["formatos"].add(f"{formato_legivel(experiencia.get('fmt'))} ({experiencia.get('fmt')})")
        combinacao["publicos"].add(experiencia.get("seg") or "geral")
    versoes = []
    for versao in dados.get("versoes") or []:
        combinacao = combinacoes.get(versao.get("key")) or {"formatos": set(), "publicos": set()}
        pontuacao = versao.get("pontuacao") or {}
        versoes.append(
            {
                "versao": versao.get("key"),
                "perguntas": versao.get("perguntas"),
                "pontos_possiveis": f"{pontuacao.get('min')} a {pontuacao.get('max')}",
                "formatos": sorted(combinacao["formatos"]),
                "publicos": sorted(combinacao["publicos"]),
                "faixas": [
                    {
                        "faixa": f.get("key"),
                        "pontos": f"{f.get('min')} a {f.get('max')}",
                        "acontece": f.get("alcancavel"),
                        "oferta": f.get("oferta") or f.get("oferta_id"),
                        "saida": "demonstração sem cobrança" if f.get("demonstracao") else f.get("destino"),
                    }
                    for f in versao.get("faixas") or []
                ],
                "problemas": versao.get("problemas") or [],
                "avisos": (versao.get("avisos") or [])[:6],
            }
        )
    resumo = dados.get("resumo") or {}
    return {
        "quiz": slug,
        "titulo": dados.get("quiz_titulo"),
        "site": dados.get("host"),
        "conversa_com_ia_ligada": dados.get("ia_ligada"),
        "versoes_ativas": versoes,
        "links_possiveis_sem_criativo": resumo.get("links"),
        "problemas_na_estrutura": resumo.get("problemas"),
        "pagina_de_links": endereco_da_pagina(host, slug),
    }


def kit_de_links(robo, execucao, host: str, slug: str, params: dict) -> dict:
    """Os links do anúncio, montados pelo quiz (nunca à mão), salvos como
    entrega e abertos na página já preenchida."""
    dados = pedir_ao_quiz(host, "GET", slug, "links", params=params)
    links = [l for l in dados.get("links") or [] if isinstance(l, dict) and isinstance(l.get("url"), str)]
    if not links:
        raise QuizRecusou("Nenhum link saiu com essa escolha.")
    pagina = endereco_da_pagina(host, slug, params, "#links")
    linhas = [
        f"# Kit de links — quiz {slug}",
        "",
        f"Montado pelo {robo.nome} em {_agora()}. Escolha: {descrever_selecao(params)}.",
        "",
        f"[Abrir a página com estes {len(links)} links prontos para copiar e testar]({pagina})",
        "",
        "Antes de subir os anúncios, peça na mesma página a conferência dos links no site.",
        "",
        "## Links",
        "",
    ]
    linhas += [f"- **{_celula(rotulo(l))}**: `{l['url']}`" for l in links]
    entrega = Entrega.objects.create(
        robo=robo,
        execucao=execucao,
        tipo="kit_de_links",
        titulo=f"Kit de links do quiz {slug} — {len(links)} link(s)"[:200],
        conteudo="\n".join(linhas) + "\n",
    )
    return {
        "total": len(links),
        "campanha": params.get("cpg"),
        "pagina_com_os_links": pagina,
        "entrega_id": entrega.id,
        "primeiros": [{"link": rotulo(l), "url": l["url"]} for l in links[:10]],
        "aviso": (
            "Mande a pessoa abrir a página: lá cada link tem Copiar e Testar. "
            "Ofereça a conferência dos links antes de anunciar."
        ),
    }


def numeros_do_quiz(host: str, slug: str, inicio: str = "", fim: str = "") -> dict:
    dados = coletar_numeros(host, slug, inicio, fim)
    dados["campanhas"] = dados["campanhas"][:8]
    dados.pop("dias", None)
    dados["pagina_onde_perde_gente"] = f"https://{host}{caminho('quiz_evolucao', slug)}"
    return dados


def propostas_do_quiz(host: str, slug: str) -> dict:
    dados = pedir_ao_quiz(host, "GET", slug, "propostas")
    return {
        "propostas": [_proposta_curta(p) for p in dados.get("propostas") or [] if isinstance(p, dict)],
        "aviso": "Propostas não alteram versões existentes.",
    }


def registrar_proposta(host: str, slug: str, *, versao_base: str, gargalo: str, hipotese: str, mudanca: str, prioridade: str) -> dict:
    rascunho = pedir_ao_quiz(host, "GET", slug, "rascunho")
    publicadas = {k for k in rascunho.get("publicadas") or [] if isinstance(k, str)}
    if versao_base not in publicadas:
        raise QuizRecusou(f"A versão {versao_base} não existe neste quiz.")
    atuais = pedir_ao_quiz(host, "GET", slug, "propostas").get("propostas") or []
    ocupadas = (
        publicadas
        | set(_chaves_do_rascunho(rascunho))
        | {p.get("key_sugerida") for p in atuais if p.get("estado") in EM_ANDAMENTO}
    )
    key = proxima_chave(versao_base, ocupadas)
    criada = pedir_ao_quiz(
        host,
        "POST",
        slug,
        "propostas",
        corpo={
            "versao_base": versao_base,
            "gargalo": gargalo[:200],
            "hipotese": hipotese[:4000],
            "mudanca": mudanca[:4000],
            "prioridade": prioridade,
            "key_sugerida": key,
        },
    )
    return {
        "registrada": True,
        "proposta": _proposta_curta(criada),
        "aviso": (
            f"Nada mudou no quiz: a proposta só registra a ideia. Se a equipe aceitar, "
            f"a versão {key} é criada no estúdio a partir da {versao_base}."
        ),
    }


DECISOES = {
    "aceitar": "aceita",
    "descartar": "descartada",
    "marcar_publicada": "publicada",
    "registrar_resultado": "medida",
}


def decidir_proposta(host: str, slug: str, proposta_id: int, decisao: str, resultado: str = "") -> dict:
    if decisao not in DECISOES:
        raise QuizRecusou("Decisão desconhecida.")
    corpo = {"estado": DECISOES[decisao]}
    if decisao == "registrar_resultado":
        if not resultado.strip():
            raise QuizRecusou("Diga o resultado observado antes de marcar a proposta como medida.")
        corpo["resultado_texto"] = resultado.strip()[:4000]
    dados = pedir_ao_quiz(host, "PATCH", slug, f"propostas/{int(proposta_id)}", corpo=corpo)
    saida = {"feito": True, "proposta": _proposta_curta(dados)}
    if isinstance(dados.get("criar_no_estudio"), dict):
        saida["proximo_passo"] = dados["criar_no_estudio"].get("mensagem")
    return saida


# ---------------------------------------------------------------- a página


RESULTADOS = {
    "conferencia": (
        "Conferência pedida. O robô abre as páginas no servidor; o relatório "
        "aparece aqui em instantes."
    ),
    "conferencia_rodando": "Já há uma conferência deste quiz em andamento. Acompanhe abaixo.",
    "leitura": (
        "Leitura pedida. Ela roda no servidor e a tarefa já está no painel da equipe."
    ),
    "leitura_rodando": "Já há uma leitura deste quiz em andamento. Acompanhe abaixo.",
    "pedido": "Pedido enviado. O robô responde aqui mesmo; pode fechar a página.",
    "vazia": "O pedido estava vazio. Nada foi enviado.",
    "longa": "O pedido passou de 4000 letras. Encurte e envie de novo.",
    "datas": "Use as datas do calendário. Nada foi pedido.",
    "sem_robo": (
        "Seu acesso não está ligado a uma pessoa da equipe; por isso ainda não "
        "há robô para você aqui."
    ),
}


def _do_quiz(robo, slug: str):
    return robo.execucoes.filter(
        Q(tipo__in=TIPOS_DO_QUIZ, estado__quiz=slug)
        | Q(tipo=Execucao.Tipo.CONVERSA, estado__contexto__quiz=slug)
    )


def marca_do_quiz(robo, slug: str) -> str:
    """Muda quando um trabalho deste quiz começa ou termina, quando chega
    resposta ou entrega: é o que a página pergunta para saber se recarrega.
    Cada página aberta ou etapa nova não conta, para a página não piscar."""
    execucoes = _do_quiz(robo, slug)
    abertas = list(
        execucoes.filter(situacao__in=Execucao.ABERTAS)
        .order_by("id")
        .values_list("id", "situacao")
    )
    terminadas = execucoes.exclude(situacao__in=Execucao.ABERTAS).aggregate(m=Max("atualizada_em"))["m"]
    mensagens = Mensagem.objects.filter(execucao__in=execucoes).aggregate(m=Max("id"))["m"]
    entregas = Entrega.objects.filter(execucao__in=execucoes).aggregate(m=Max("atualizada_em"))["m"]
    return f"{abertas}|{terminadas}|{mensagens}|{entregas}"


def painel_na_pagina(request, slug: str) -> dict:
    from apps.core.equipe import _membro_da_sessao

    membro = _membro_da_sessao(request)
    if membro is None:
        return {"robo": None}
    robo = trabalhos.robo_de(membro)
    execucoes = _do_quiz(robo, slug)
    lista = list(execucoes.exclude(tipo=Execucao.Tipo.CONVERSA).order_by("-criada_em")[:6])
    for execucao in lista:
        # O veredito da conferência em verde ou vermelho, para ler de longe.
        execucao.tom = (
            "ruim" if execucao.resultado.startswith("NÃO SUBA")
            else "bom" if execucao.resultado.startswith("PODE SUBIR")
            else ""
        )
    conversas = list(execucoes.filter(tipo=Execucao.Tipo.CONVERSA).order_by("-criada_em")[:5])
    mensagens = list(Mensagem.objects.filter(execucao__in=conversas).order_by("id"))[-14:]
    for mensagem in mensagens:
        if mensagem.papel == Mensagem.Papel.ROBO:
            mensagem.html = para_html(mensagem.texto)
    entregas = list(Entrega.objects.filter(execucao__in=execucoes).order_by("-atualizada_em")[:6])
    rodando = [
        e for e in lista + conversas
        if e.situacao in (Execucao.Situacao.NA_FILA, Execucao.Situacao.EXECUTANDO)
    ]
    respondendo = next((e for e in conversas if e.situacao in Execucao.ABERTAS), None)
    conexao = modelo.conexao()
    autorizacao = modelo.autorizacao_ativa()
    return {
        "robo": robo,
        "membro": membro,
        "ia_pronta": (
            modelo.tem_chave()
            and conexao.situacao == Conexao.Situacao.CONFERIDA
            and autorizacao is not None
        ),
        "conexao": conexao,
        "gasto": modelo.gasto_do_mes(autorizacao.pk) if autorizacao else None,
        "teto": autorizacao.teto_mensal_usd if autorizacao else None,
        "trabalhos": lista,
        "mensagens": mensagens,
        "respondendo": respondendo,
        "entrega": entregas[0] if entregas else None,
        "entrega_html": para_html(entregas[0].conteudo) if entregas else "",
        "outras_entregas": entregas[1:],
        "acompanhar": bool(rodando),
        "intervalo": 1500 if any(e.tipo == Execucao.Tipo.CONVERSA for e in rodando) else 3000,
        "marca": marca_do_quiz(robo, slug),
        "chave": uuid.uuid4().hex,
    }


def endereco_de_volta(slug: str, consulta: str):
    """A página de onde o pedido saiu, com a mesma escolha, o recado e a
    âncora do robô. Só parâmetros: o caminho é sempre o da página."""
    from django.http import QueryDict

    dados = QueryDict((consulta or "")[:4000], mutable=True)
    dados.pop("robo", None)
    base = reverse("quiz_campanhas", args=[slug])

    def montar(resultado: str) -> str:
        if resultado:
            dados["robo"] = resultado
        texto = dados.urlencode()
        return base + (f"?{texto}" if texto else "") + "#robo"

    return montar
