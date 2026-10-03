"""O mapa de conhecimento do robô (GraphRAG, 03/10/2026).

Em vez de procurar trechos parecidos com a pergunta, o robô anda por um
mapa de COISAS (pessoas, tarefas, objetivos, cursos, ofertas, sistemas...)
e das LIGAÇÕES entre elas, e cada ligação traz o trecho que a sustenta. É
o que deixa responder "o que depende disso?", "quem cuida daquilo?" ou "por
que isto existe?" cruzando o painel com os documentos, e dizer de onde tirou.

Duas partes, no mesmo banco do site (sem serviço novo):

* **o painel**, lido NA HORA a cada consulta: pessoas, tarefas, objetivos,
  o que cada objetivo move no placar, compromissos e comentários. Não gasta
  nada e nunca fica velho;
* **os documentos** (`core.Documento`), lidos uma vez pelo modelo rápido
  (`Execucao.Tipo.CONHECIMENTO`), que devolve as coisas e as ligações em JSON
  de esquema fixo. Só documento novo ou mudado é lido de novo (`impressao`).

Quem não administra o site só enxerga o que vem de documento público.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.core.models import Comentario, Compromisso, Documento, MembroDaEquipe, Objetivo, Tarefa

from . import modelo
from .executor import batimento, guardar_estado, terminar
from .models import (
    EntidadeDoConhecimento,
    Execucao,
    FonteDoConhecimento,
    LigacaoDoConhecimento,
)

TIPOS = [
    "pessoa", "equipe", "empresa", "curso", "aula", "oferta", "produto",
    "quiz", "campanha", "pagina", "sistema", "servico", "ferramenta",
    "processo", "regra", "decisao", "objetivo", "metrica", "problema",
    "conceito", "outro",
]

TAMANHO_DO_PEDACO = 9000
MAX_PEDACOS_POR_DOCUMENTO = 8
MAX_SAIDA = 6000

ESQUEMA = {
    "type": "json_schema",
    "name": "mapa_de_conhecimento",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["entidades", "ligacoes"],
        "properties": {
            "entidades": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["nome", "tipo", "resumo"],
                    "properties": {
                        "nome": {"type": "string"},
                        "tipo": {"type": "string", "enum": TIPOS},
                        "resumo": {"type": "string"},
                    },
                },
            },
            "ligacoes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["origem", "relacao", "destino", "evidencia"],
                    "properties": {
                        "origem": {"type": "string"},
                        "relacao": {"type": "string"},
                        "destino": {"type": "string"},
                        "evidencia": {"type": "string"},
                    },
                },
            },
        },
    },
}


def normal(texto: str) -> str:
    """Sem acento, minúsculo e com espaços simples: 'Lívia ' casa 'livia'."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split())


_ARTIGOS = {"o", "a", "os", "as", "um", "uma", "uns", "umas", "the"}
_ARTIGOS_DEFINIDOS = {"o", "a", "os", "as"}


def nome_chave(texto: str) -> str:
    """O que decide se dois nomes são a mesma coisa: além de `normal`, sem
    pontuação nem símbolo, sem artigo na frente ou no meio e sem plural
    ('O Crivo' = 'crivo', 'Alunos' = 'aluno', 'cartas_de_celebração' =
    'carta de celebração', 'Capítulo 3: A comunidade' = 'Capítulo 3 — comunidade',
    '/admin/' = 'admin'). Artigo no fim conta: 'Plano A' não é 'Plano'."""
    palavras = re.sub(r"[^\w\s]|_", " ", normal(texto)).split()
    while len(palavras) > 1 and palavras[0] in _ARTIGOS:
        palavras = palavras[1:]
    palavras = [p for i, p in enumerate(palavras)
                if not (0 < i < len(palavras) - 1 and p in _ARTIGOS_DEFINIDOS)]
    return " ".join(
        p[:-1] if len(p) > 3 and p.endswith("s") and not p.endswith(("ss", "is", "us")) else p
        for p in palavras
    )


def _impressao(documento: Documento) -> str:
    return hashlib.sha256(
        (documento.titulo + "\n" + documento.corpo).encode("utf-8")
    ).hexdigest()


def _endereco(documento: Documento) -> str:
    try:
        return reverse("documento_admin", args=[documento.nome])
    except NoReverseMatch:  # pragma: no cover - rota fora desta célula
        return ""


def _documentos():
    return Documento.objects.filter(arquivado=False).exclude(corpo="").order_by("ordem", "nome")


def documentos_a_ler() -> list[Documento]:
    """Os documentos novos ou mudados desde a última leitura."""
    lidas = dict(FonteDoConhecimento.objects.values_list("chave", "impressao"))
    return [d for d in _documentos() if lidas.get(f"documento:{d.nome}") != _impressao(d)]


def pedacos(texto: str) -> list[str]:
    """Corta o texto em pedaços pelo parágrafo, para cada pedido caber folgado."""
    partes, atual = [], ""
    for paragrafo in texto.split("\n\n"):
        if atual and len(atual) + len(paragrafo) > TAMANHO_DO_PEDACO:
            partes.append(atual)
            atual = ""
        atual = (atual + "\n\n" + paragrafo).strip() if atual else paragrafo[:TAMANHO_DO_PEDACO * 2]
    if atual:
        partes.append(atual)
    return partes[:MAX_PEDACOS_POR_DOCUMENTO]


def _instrucoes_de_leitura() -> str:
    pessoas = ", ".join(MembroDaEquipe.objects.filter(ativo=True).values_list("nome", flat=True))
    objetivos = "; ".join(Objetivo.objects.filter(ativo=True).values_list("titulo", flat=True))
    return (
        "Você monta o mapa de conhecimento da Meshcraft, uma escola de modelagem 3D. "
        "Leia o trecho de documento e devolva as coisas importantes que ele cita "
        "(entidades) e as ligações que ele AFIRMA entre elas.\n"
        "- Entidade: nome curto e estável, como apareceria em outro documento; "
        "resumo de uma frase com o que o texto diz dela.\n"
        "- Ligação: origem e destino são nomes de entidades da sua lista; relação "
        "é um verbo curto em português e em minúsculas (depende de, cuida de, "
        "vende, usa, mede, decidiu, substitui, faz parte de, leva a, bloqueia...). "
        "Evidência: o trecho do texto que sustenta a ligação, até 300 letras.\n"
        "- Só o que está escrito. Não invente, não complete com conhecimento geral.\n"
        "- Nunca copie senha, chave, token, número de cartão ou dado pessoal sensível.\n"
        "- No máximo 40 entidades e 60 ligações; prefira as que ajudam a responder "
        "'quem cuida', 'o que depende de', 'por que', 'como funciona'.\n"
        f"Pessoas da equipe (use estes nomes quando o texto falar delas): {pessoas or 'nenhuma'}.\n"
        f"Objetivos ativos da equipe (use estes títulos): {objetivos or 'nenhum'}."
    )


def ler_pedaco(documento: Documento, numero: int, pedaco: str, *, execucao=None, robo=None) -> dict:
    """Pede ao modelo rápido as entidades e ligações de um pedaço."""
    resposta = modelo.responder(
        modelo=modelo.conexao().modelo_rapido,
        instrucoes=_instrucoes_de_leitura(),
        itens=[{
            "role": "user",
            "content": f"Documento: {documento.titulo} (parte {numero})\n\n{pedaco}",
        }],
        max_saida=MAX_SAIDA,
        esforco="low",
        execucao=execucao,
        robo=robo,
        formato=ESQUEMA,
    )
    try:
        dados = json.loads(resposta.texto or "{}")
    except ValueError:
        return {"entidades": [], "ligacoes": []}
    return {"entidades": dados.get("entidades") or [], "ligacoes": dados.get("ligacoes") or []}


def guardar_leitura(documento: Documento, dados: dict) -> FonteDoConhecimento:
    """Troca o que o mapa sabia deste documento pelo que acabou de ser lido."""
    with transaction.atomic():
        fonte, _ = FonteDoConhecimento.objects.update_or_create(
            chave=f"documento:{documento.nome}",
            defaults={
                "titulo": documento.titulo[:200],
                "endereco": _endereco(documento)[:300],
                "publica": bool(documento.publico),
                "impressao": _impressao(documento),
            },
        )
        fonte.entidades.all().delete()
        fonte.ligacoes.all().delete()
        vistos = set()
        novas = []
        for e in dados.get("entidades") or []:
            nome = (e.get("nome") or "").strip()[:200]
            if not nome or nome_chave(nome) in vistos:
                continue
            vistos.add(nome_chave(nome))
            tipo = e.get("tipo") if e.get("tipo") in TIPOS else "outro"
            novas.append(EntidadeDoConhecimento(
                fonte=fonte, nome=nome, tipo=tipo, resumo=(e.get("resumo") or "")[:500]
            ))
        EntidadeDoConhecimento.objects.bulk_create(novas)
        LigacaoDoConhecimento.objects.bulk_create([
            LigacaoDoConhecimento(
                fonte=fonte,
                origem=(l.get("origem") or "").strip()[:200],
                relacao=(l.get("relacao") or "").strip().lower()[:80],
                destino=(l.get("destino") or "").strip()[:200],
                evidencia=(l.get("evidencia") or "").strip()[:400],
            )
            for l in dados.get("ligacoes") or []
            if (l.get("origem") or "").strip() and (l.get("destino") or "").strip()
        ])
    return fonte


def esquecer_os_que_sairam() -> int:
    """Documento arquivado ou apagado sai do mapa."""
    vivos = {f"documento:{d.nome}" for d in _documentos()}
    velhas = FonteDoConhecimento.objects.filter(chave__startswith="documento:").exclude(chave__in=vivos)
    n = velhas.count()
    velhas.delete()
    return n


DAR_A_VEZ = timedelta(seconds=2)


def executar(execucao: Execucao) -> None:
    """O trabalho do servidor: lê UM pedaço de documento por vez e volta para
    a fila, para a conversa de alguém da equipe passar na frente entre um
    pedaço e outro. O que já foi lido do documento fica em `estado`; o
    documento é gravado no mapa quando o último pedaço chega."""
    estado = execucao.estado or {}
    a_ler = documentos_a_ler()
    estado.setdefault("total", len(a_ler))
    feitos = estado.setdefault("feitos", 0)
    if a_ler:
        documento = a_ler[0]
        atual = estado.get("atual") or {}
        if atual.get("impressao") != _impressao(documento):
            atual = {"impressao": _impressao(documento), "parte": 0, "entidades": [], "ligacoes": []}
        partes = pedacos(documento.corpo)
        numero = atual["parte"] + 1
        batimento(
            execucao,
            f"Lendo: {documento.titulo} ({numero} de {len(partes)})"[:200],
            progresso=min(95, int(100 * feitos / max(estado["total"], 1))),
        )
        if numero <= len(partes):
            dados = ler_pedaco(documento, numero, partes[numero - 1], execucao=execucao, robo=execucao.robo)
            atual["entidades"] += dados["entidades"]
            atual["ligacoes"] += dados["ligacoes"]
            atual["parte"] = numero
        if atual["parte"] >= len(partes):
            guardar_leitura(documento, atual)
            atual = {}
            estado["feitos"] = feitos + 1
        estado["atual"] = atual
        execucao.estado = estado
        guardar_estado(execucao)
        if atual or len(a_ler) > 1:
            _dar_a_vez(execucao)
            return
    saiu = esquecer_os_que_sairam()
    terminar(
        execucao,
        Execucao.Situacao.CONCLUIDA,
        resultado=(
            f"{estado.get('feitos', 0)} documento(s) lido(s) para o mapa"
            + (f"; {saiu} saiu(saíram) do mapa" if saiu else "")
            + f". O mapa tem {EntidadeDoConhecimento.objects.count()} coisas e "
            f"{LigacaoDoConhecimento.objects.count()} ligações vindas dos documentos."
        ),
    )


def _dar_a_vez(execucao: Execucao) -> None:
    """De volta à fila sem contar como tentativa que parou no meio."""
    from .executor import PerdeuAPosse, _minha

    agora = timezone.now()
    if not _minha(execucao).update(
        situacao=Execucao.Situacao.NA_FILA,
        trabalhador="",
        ocupada_ate=None,
        tentativas=0,
        nao_antes_de=agora + DAR_A_VEZ,
        atualizada_em=agora,
    ):
        raise PerdeuAPosse()


# ------------------------------------------------------------------ o mapa


class Mapa:
    """O grafo montado para UMA consulta: nós por chave, ligações com fonte."""

    def __init__(self):
        self.nos: dict[str, dict] = {}
        self.ligacoes: list[dict] = []
        self.vizinhos: dict[str, list[int]] = defaultdict(list)
        self.por_nome: dict[str, str] = {}
        self._ja_ligadas: dict[tuple, dict] = {}

    def no(self, chave: str, tipo: str, nome: str, resumo: str = "", fonte: str = "") -> str:
        existente = self.nos.get(chave)
        if existente is None:
            self.nos[chave] = {"tipo": tipo, "nome": nome, "resumo": resumo, "fontes": []}
            self.por_nome.setdefault(nome_chave(nome), chave)
        elif resumo and not existente["resumo"]:
            existente["resumo"] = resumo
        if fonte and fonte not in self.nos[chave]["fontes"]:
            self.nos[chave]["fontes"].append(fonte)
        return chave

    def ligar(self, de: str, relacao: str, para: str, evidencia: str = "", fonte: str = "painel") -> None:
        """A mesma ligação dita por vários documentos fica uma só, com as fontes juntas."""
        if de == para:
            return
        repetida = self._ja_ligadas.get((de, normal(relacao), para))
        if repetida is not None:
            if fonte not in repetida["fontes"]:
                repetida["fontes"].append(fonte)
            repetida["evidencia"] = repetida["evidencia"] or evidencia
            return
        indice = len(self.ligacoes)
        ligacao = {"de": de, "relacao": relacao, "para": para, "evidencia": evidencia, "fontes": [fonte]}
        self.ligacoes.append(ligacao)
        self._ja_ligadas[(de, normal(relacao), para)] = ligacao
        self.vizinhos[de].append(indice)
        self.vizinhos[para].append(indice)

    def chave_do_nome(self, nome: str, tipo: str = "outro") -> str:
        """O mesmo nome em documentos diferentes é a mesma coisa; e o nome de
        uma pessoa ou objetivo do painel aponta para o nó do painel."""
        n = nome_chave(nome)
        achado = self.por_nome.get(n)
        if achado is not None:
            return achado
        return self.no(f"coisa:{n}", tipo, nome.strip())


def montar(*, com_privados: bool) -> Mapa:
    mapa = Mapa()
    _painel(mapa)
    _dos_documentos(mapa, com_privados=com_privados)
    return mapa


def _painel(mapa: Mapa) -> None:
    for m in MembroDaEquipe.objects.filter(ativo=True):
        mapa.no(f"pessoa:{m.id}", "pessoa", m.nome, m.area, "painel")
        primeiro = nome_chave(m.nome).split(" ")[0]
        mapa.por_nome.setdefault(primeiro, f"pessoa:{m.id}")
    movidos = dict(Objetivo.Move.choices)
    for o in Objetivo.objects.all():
        chave = mapa.no(
            f"objetivo:{o.id}", "objetivo", o.titulo,
            (o.descricao or "")[:300] + ("" if o.ativo else " (inativo)"), "painel",
        )
        if o.move:
            medida = mapa.no(f"placar:{o.move}", "metrica", movidos.get(o.move, o.move), "", "placar")
            mapa.ligar(chave, "move", medida)
    semana = None
    try:
        from apps.core import equipe_operacoes as operacoes

        semana = operacoes.segunda(operacoes.hoje())
    except Exception:  # noqa: BLE001 - sem semana, só não marca compromisso
        pass
    compromissos = set(
        Compromisso.objects.filter(semana=semana).values_list("tarefa_id", flat=True)
    ) if semana else set()
    for t in Tarefa.objects.select_related("responsavel", "objetivo").order_by("-id")[:400]:
        resumo = f"situação {t.get_situacao_display().lower()}"
        if t.prazo:
            resumo += f", prazo {t.prazo:%d/%m/%Y}"
        if t.id in compromissos:
            resumo += ", compromisso desta semana"
        if t.impedimento:
            resumo += f", impedimento: {t.impedimento[:120]}"
        chave = mapa.no(f"tarefa:{t.id}", "tarefa", f"Tarefa nº {t.id}: {t.titulo}", resumo, "painel")
        mapa.por_nome.setdefault(nome_chave(t.titulo), chave)
        if t.responsavel_id:
            mapa.ligar(f"pessoa:{t.responsavel_id}", "responde por", chave)
        if t.objetivo_id:
            mapa.ligar(chave, "serve ao objetivo", f"objetivo:{t.objetivo_id}")
    for c in Comentario.objects.filter(tarefa_id__in=[
        int(k.split(":")[1]) for k in mapa.nos if k.startswith("tarefa:")
    ]).order_by("-criado_em")[:300]:
        autor = f"pessoa:{c.autor_membro_id}" if c.autor_membro_id and f"pessoa:{c.autor_membro_id}" in mapa.nos else None
        if autor:
            mapa.ligar(autor, "comentou em", f"tarefa:{c.tarefa_id}", c.texto[:300])


def _dos_documentos(mapa: Mapa, *, com_privados: bool) -> None:
    fontes = FonteDoConhecimento.objects.all()
    if not com_privados:
        fontes = fontes.filter(publica=True)
    fontes = {f.id: f for f in fontes}
    rotulo = {i: f"{f.titulo} ({f.endereco})" if f.endereco else f.titulo for i, f in fontes.items()}
    for e in EntidadeDoConhecimento.objects.filter(fonte_id__in=fontes):
        chave = mapa.chave_do_nome(e.nome, e.tipo)
        mapa.no(chave, e.tipo, e.nome, e.resumo, rotulo[e.fonte_id])
    for l in LigacaoDoConhecimento.objects.filter(fonte_id__in=fontes):
        mapa.ligar(
            mapa.chave_do_nome(l.origem), l.relacao, mapa.chave_do_nome(l.destino),
            l.evidencia, rotulo[l.fonte_id],
        )


def consultar(termos: list[str], *, com_privados: bool, profundidade: int = 2,
              max_ligacoes: int = 60) -> dict:
    """Acha os nós que casam os termos e anda até `profundidade` passos."""
    mapa = montar(com_privados=com_privados)
    termos = [normal(t) for t in termos if normal(t)]
    sementes = []
    for termo in termos:
        termo = nome_chave(termo) or termo
        exatos = [c for n, c in mapa.por_nome.items() if n == termo]
        parecidos = [c for c, no in mapa.nos.items() if c not in exatos and termo in nome_chave(no["nome"])]
        if exatos:
            # Com o nome exato achado, junta só quem tem o termo como palavra inteira:
            # 'Comunidade' traz 'Comunidade Meshcraft', mas 'IA' não traz 'Academia'.
            parecidos = [c for c in parecidos if f" {termo} " in f" {nome_chave(mapa.nos[c]['nome'])} "]
        # Os mais ligados primeiro: são os que mais têm a contar.
        parecidos.sort(key=lambda c: -len(mapa.vizinhos.get(c, [])))
        sementes.extend((exatos + parecidos)[:8])
    if not sementes:
        # Nenhum nome casou: procura o termo nos trechos e resumos.
        for i, l in enumerate(mapa.ligacoes):
            if any(t in normal(l["evidencia"]) for t in termos):
                sementes.extend([l["de"], l["para"]])
        for c, no in mapa.nos.items():
            if any(t in normal(no["resumo"]) for t in termos):
                sementes.append(c)
        sementes = sementes[:12]
    vistos = list(dict.fromkeys(sementes))
    # Quantos documentos confirmam cada par de coisas, com a relação escrita de qualquer jeito.
    confirmam: dict[frozenset, set] = {}
    for l in mapa.ligacoes:
        confirmam.setdefault(frozenset((l["de"], l["para"])), set()).update(l["fontes"])

    def peso(chave: str, indice: int) -> tuple[int, int]:
        l = mapa.ligacoes[indice]
        outro = l["para"] if l["de"] == chave else l["de"]
        return (-len(confirmam[frozenset((l["de"], l["para"]))]), -len(mapa.nos.get(outro, {}).get("fontes", [])))

    escolhidas: list[int] = []
    fronteira = list(vistos)
    for _ in range(max(1, min(profundidade, 3))):
        proxima = []
        for chave in fronteira:
            # Primeiro as ligações que mais documentos confirmam; depois as coisas citadas em mais documentos.
            for indice in sorted(mapa.vizinhos.get(chave, []), key=lambda i: peso(chave, i)):
                if indice in escolhidas or len(escolhidas) >= max_ligacoes:
                    continue
                escolhidas.append(indice)
                l = mapa.ligacoes[indice]
                outro = l["para"] if l["de"] == chave else l["de"]
                if outro not in vistos:
                    vistos.append(outro)
                    proxima.append(outro)
        fronteira = proxima
        if not fronteira or len(escolhidas) >= max_ligacoes:
            break
    nos = {c: mapa.nos[c] for c in vistos if c in mapa.nos}
    return {
        "achou": bool(sementes),
        "encontrados": [mapa.nos[c]["nome"] for c in dict.fromkeys(sementes) if c in mapa.nos][:12],
        "coisas": [
            {"nome": n["nome"], "tipo": n["tipo"], "resumo": n["resumo"], "fontes": n["fontes"][:3]}
            for n in list(nos.values())[:80]
        ],
        "ligacoes": [
            {
                "de": mapa.nos[l["de"]]["nome"],
                "relacao": l["relacao"],
                "para": mapa.nos[l["para"]]["nome"],
                "evidencia": l["evidencia"],
                "fontes": l["fontes"][:3],
            }
            for l in (mapa.ligacoes[i] for i in escolhidas)
        ],
    }


def numeros() -> dict:
    return {
        "documentos": FonteDoConhecimento.objects.count(),
        "documentos_no_site": _documentos().count(),
        "a_ler": len(documentos_a_ler()),
        "coisas": EntidadeDoConhecimento.objects.count(),
        "ligacoes": LigacaoDoConhecimento.objects.count(),
        "ultima": FonteDoConhecimento.objects.order_by("-lida_em").values_list("lida_em", flat=True).first(),
        "leitura_aberta": Execucao.objects.filter(
            tipo=Execucao.Tipo.CONHECIMENTO, situacao__in=Execucao.ABERTAS
        ).first(),
    }


def pedir_leitura(robo, quem: str) -> Execucao:
    """Põe na fila a leitura dos documentos; pedir de novo enquanto uma está
    aberta devolve a mesma."""
    aberta = Execucao.objects.filter(
        tipo=Execucao.Tipo.CONHECIMENTO, situacao__in=Execucao.ABERTAS
    ).first()
    if aberta is not None:
        return aberta
    from .trabalhos import _acordar_o_executor, registrar

    with transaction.atomic():
        execucao = Execucao.objects.create(
            robo=robo,
            tipo=Execucao.Tipo.CONHECIMENTO,
            origem="mapa",
            pedido_por_membro_id=robo.membro_id,
            pedido_por=quem[:200],
            pedido="Ler os documentos do site para o mapa de conhecimento.",
        )
        registrar(execucao, "Pedida a leitura dos documentos.")
        _acordar_o_executor()
    return execucao
