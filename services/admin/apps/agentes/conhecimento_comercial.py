"""O conhecimento comercial dos agentes, por site e por produto (03/10/2026).

O que o atendimento precisa saber de um curso para conversar com um lead do
quiz: o que é, os módulos, quantas aulas, como se acessa, para quem não
serve, o que a página de venda promete e os depoimentos que podem ser usados.
Tudo com a fonte (tipo + id) e a data, para o agente dizer de onde tirou.

## De onde vem

* **Catálogo, lido pelas portas das outras células** (nunca pelo banco
  delas): os cursos publicados do site e as aulas publicadas (`cursos`), os
  nomes dos produtos e a oferta da página de venda com as seções publicadas
  (`catalogo`).
* **Documentos do site marcados** em `/admin/robos/conhecimento/comercial`
  (`MaterialComercial`): material comercial e depoimentos. Depoimento só entra
  com autorização de uso marcada.

## O que NÃO é lembrado

Preço e condições (parcelas, cupom, Pix, boleto, vencimento). Os espaços de
preço da página ficam de fora, e a frase de documento que fala de preço sai do
trecho. Quando a pergunta é de preço, a consulta busca o preço NA HORA no
catálogo e devolve com `ao_vivo: true`; as condições vêm do checkout, também
na hora.

## Sem vazar entre sites

Cada trecho guarda o `site_id`, e a consulta só lê os trechos do site pedido.
A marca de um documento vale para UM site.

## O mapa

Cada fonte é uma `FonteDoConhecimento` com chave `comercial:<site>:<tipo>:<id>`
e a mesma `impressao` do mapa: fonte que não mudou não é regravada. Os cursos e
a oferta entram também como coisas e ligações do mapa (curso faz parte do
produto, curso tem módulo, oferta vende produto), sem gastar modelo nenhum.
Curso, módulo e oferta levam o site no nome ('Oferta anual (a.test)'): o
mesmo apelido em outro site é outra coisa. O produto é do catálogo inteiro.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from datetime import timezone as fuso
from urllib.parse import quote

from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.clients import CatalogoClient, CursosClient
from apps.core.models import Documento

from .models import (
    EntidadeDoConhecimento,
    FonteDoConhecimento,
    LigacaoDoConhecimento,
    MaterialComercial,
    TrechoComercial,
)

log = logging.getLogger(__name__)

PREFIXO = "comercial:"
HOST_PADRAO = "meshcraft.top"
INTERVALO = timedelta(minutes=30)
TAMANHO_DO_TRECHO = 700
MAX_TRECHOS_POR_FONTE = 40
MAX_TRECHOS_NA_RESPOSTA = 6

TIPOS = ("curso", "oferta", "documento", "depoimento")

# Os espaços da página de venda que são preço, condição ou botão: não entram.
SLOTS_FORA = {"preco_texto", "parcelamento", "cta_texto", "cta_destino", "imagem"}

NOMES_DAS_SECOES = {
    "cubo": "Apresentação",
    "viloes": "Problemas que o curso resolve",
    "metodo": "Método",
    "instrumentos": "Instrumentos",
    "percurso": "Percurso: o que se estuda",
    "tempo": "Tempo e duração",
    "para_quem_nao_serve": "Para quem não serve (requisitos)",
    "se_eu_parar": "Se eu parar",
    "oferta": "O que recebe",
    "carta": "Carta",
    "perguntas": "Perguntas frequentes",
    "abertura": "Apresentação",
    "entrega": "O que recebe",
    "convite": "Convite",
    "prova": "Prova",
}

PROGRESSAO = {
    "livre": "a próxima aula abre quando o aluno conclui a anterior",
    "por_laudo": "a próxima aula abre com o laudo (a avaliação) da professora sobre a anterior",
}

# Frase que fala de preço ou de condição de compra: sai do trecho lembrado.
_PRECO = re.compile(
    r"R\$|US\$|€|\$\s*\d|\d+\s*[x×]\s*(de\s+)?(R\$\s*)?\d|\bparcel|\bdesconto|\bcupo[mn]s?\b|"
    r"\b[àa] vista\b|\bboleto|\bpix\b|\bpre[çc]o|\bpromo[çc]|"
    # preço sem cifrão: "497 reais", "12 vezes de 49,70", "49,90", "Valor: 497"
    r"\d\s*(reais|real|d[óo]lares?|euros?|conto)\b|\b(reais|d[óo]lares|euros)\b|"
    r"\d+\s*vezes\s+(de|sem)\b|\b\d{1,3}(\.\d{3})*,\d{2}\b|"
    r"\binvestimento|\bmensalidade|\banuidade|\bvalor(es)?\b|\bcust(a|am|o|ar)\b|"
    r"\bpagamento|\bpagar\b|\bcart[ãa]o de cr[ée]dito|\bgr[áa]tis\b|\bgratuit|"
    # condição de compra (garantia, reembolso, vagas, parcelas, juros): vem ao
    # vivo do catálogo e do checkout, nunca do conhecimento lembrado
    r"\bgarantia|\breembols|\bdevolu[çc]|\bvagas?\b|\d+\s*[x×]\b|\bsem juros\b|"
    # preço escrito só com número: "por 497", "só 97", "de 997 por 497", "entrada de 97".
    # Número de duas casas ou mais depois dessas palavras, a menos que seja medida do curso.
    r"\b(por|s[óo]|apenas|somente|entrada|de|a partir de|hoje)\s+(apenas\s+|somente\s+)?\d{2,}([.,]\d+)*\b"
    r"(?!\s*(%|h\b|hs\b|min\w*|horas?|aulas?|m[óo]dulos?|dias?|semanas?|mes(es)?|anos?|alunos?|"
    r"exerc[íi]cios?|projetos?|v[íi]deos?|li[çc][õo]es|encontros?|p[áa]ginas?|lives?|modelos?|"
    r"texturas?|arquivos?|materiais|itens?|etapas?|desafios?|temas?|t[óo]picos?|pessoas?|vagas?|"
    r"partes?|cap[íi]tulos?|mentorias?|corre[çc][õo]es|pacotes?|brushes|pinc[ée]is))",
    re.IGNORECASE,
)
_MARCA_DE_PRECO = "(preço e condições: consultar ao vivo)"

# Pergunta de preço ou condição (já sem acento): a resposta busca o preço na hora.
_PERGUNTA_DE_PRECO = re.compile(
    r"\b(preco\w*|valor\w*|custa\w*|custo\w*|quanto (e|custa|sai|fica|pago|cobra\w*)|"
    r"cobra\w*|parcel\w*|desconto\w*|cupo[mn]\w*|pix|boleto|cartao|pagamento\w*|pagar|"
    r"vista|promocao|promocoes|condic\w*|investimento\w*|investir|mensalidade\w*|"
    r"anuidade\w*|mensal|reais|caro|barato|gratis|gratuito|"
    r"garantia\w*|reembols\w*|devolu\w*|vaga\w*|juros|\d+\s*x)\b"
)

_VAZIAS = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "pelo", "pela", "para", "pra", "com", "sem",
    "que", "qual", "quais", "quanto", "quantos", "quanta", "quantas", "como", "onde",
    "quando", "e", "ou", "eu", "voce", "voces", "vc", "meu", "minha", "seu", "sua",
    "isso", "isto", "este", "esta", "esse", "essa", "ele", "ela", "tem", "ter", "ser",
    "sao", "esta", "estou", "sobre", "mais", "menos", "muito", "pode", "posso", "queria",
    "quero", "gostaria", "saber", "sim", "nao", "tambem", "ja", "ate", "the", "and",
}


def _normal(texto: str) -> str:
    from .conhecimento import normal

    return normal(texto)


def _nome_chave(texto: str) -> str:
    from .conhecimento import nome_chave

    return nome_chave(texto)


# ------------------------------------------------------------- a leitura


@dataclass
class Fonte:
    """Uma fonte comercial lida agora, ainda fora do banco."""

    tipo: str
    ref: str
    titulo: str
    endereco: str = ""
    publica: bool = True
    produto_ref: str = ""
    produto_nome: str = ""
    oferta_ref: str = ""
    vigente_desde: datetime | None = None
    partes: list[tuple[str, str]] = field(default_factory=list)
    entidades: list[dict] = field(default_factory=list)
    ligacoes: list[dict] = field(default_factory=list)

    def impressao(self) -> str:
        corpo = {
            "titulo": self.titulo,
            "endereco": self.endereco,
            "publica": self.publica,
            "produto": [self.produto_ref, self.produto_nome, self.oferta_ref],
            "vigente_desde": self.vigente_desde.isoformat() if self.vigente_desde else "",
            "partes": self.partes,
            "entidades": self.entidades,
            "ligacoes": self.ligacoes,
        }
        return hashlib.sha256(
            json.dumps(corpo, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()


@dataclass
class Leitura:
    site_id: str
    host: str
    fontes: list[Fonte] = field(default_factory=list)
    lidos: set[str] = field(default_factory=set)
    faltou: list[str] = field(default_factory=list)
    # Fontes que continuam valendo mesmo sem terem sido lidas agora (o catálogo
    # de produtos não respondeu): não saem do índice. O resto do tipo sai normal.
    mantidas: set[str] = field(default_factory=set)


def chave(site_id: str, tipo: str, ref: str) -> str:
    """A chave da fonte no mapa. Longa demais, o fim vira um resumo: o começo
    (site e tipo) continua legível, e é por ele que se acha o que é do site."""
    inteira = f"{PREFIXO}{site_id}:{tipo}:{ref}"
    if len(inteira) <= 120:
        return inteira
    return inteira[:96] + ":" + hashlib.sha1(inteira.encode("utf-8")).hexdigest()[:23]


def no_do_site(nome: str, leitura: Leitura) -> str:
    """O nome da coisa no mapa da equipe, com o site: 'Oferta anual (a.test)'."""
    return f"{nome} ({leitura.host or leitura.site_id})"


def _tipo_da_chave(texto: str) -> str:
    partes = texto[len(PREFIXO):].split(":")
    return partes[1] if len(partes) > 1 else ""


def sem_preco(texto: str) -> str:
    """Tira as frases de preço e condição; no lugar, uma marca só por linha."""
    linhas = []
    for linha in (texto or "").splitlines():
        frases = re.split(r"(?<=[.!?;])\s+", linha)
        boas = [f for f in frases if not _PRECO.search(f)]
        if len(boas) != len(frases):
            boas.append(_MARCA_DE_PRECO)
        linhas.append(" ".join(f for f in boas if f.strip()))
    return "\n".join(linhas).strip()


def nome_sem_preco(nome: str, reserva: str) -> str:
    """Um nome (de curso, de complemento) sem a parte de preço. Se o nome todo
    era preço, vale a reserva (o apelido ou o id)."""
    limpo = sem_preco(nome).replace(_MARCA_DE_PRECO, "").strip(" -:;,")
    return limpo or reserva


def _so_marca(texto: str) -> bool:
    return not texto.replace(_MARCA_DE_PRECO, "").strip()


def pedacos(texto: str, origem: str = "") -> list[str]:
    """Corta pelo parágrafo, sem passar muito de TAMANHO_DO_TRECHO. Passando de
    MAX_TRECHOS_POR_FONTE, o resto é cortado e o corte fica no log."""
    partes, atual = [], ""
    for paragrafo in re.split(r"\n\s*\n", texto or ""):
        paragrafo = paragrafo.strip()
        if not paragrafo:
            continue
        while len(paragrafo) > TAMANHO_DO_TRECHO * 2:
            corte = paragrafo.rfind(" ", 0, TAMANHO_DO_TRECHO)
            corte = corte if corte > 0 else TAMANHO_DO_TRECHO
            if atual:
                partes.append(atual)
                atual = ""
            partes.append(paragrafo[:corte].strip())
            paragrafo = paragrafo[corte:].strip()
        if atual and len(atual) + len(paragrafo) > TAMANHO_DO_TRECHO:
            partes.append(atual)
            atual = ""
        atual = f"{atual}\n\n{paragrafo}" if atual else paragrafo
    if atual:
        partes.append(atual)
    if len(partes) > MAX_TRECHOS_POR_FONTE:
        log.warning(
            "Conhecimento comercial: %s tem %d trechos e só os %d primeiros entram no índice",
            origem or "uma fonte", len(partes), MAX_TRECHOS_POR_FONTE,
        )
    return partes[:MAX_TRECHOS_POR_FONTE]


def _data(valor) -> datetime | None:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor
    lida = parse_datetime(str(valor))
    if lida is not None and timezone.is_naive(lida):
        lida = timezone.make_aware(lida, fuso.utc)
    return lida


def _produtos(leitura: Leitura) -> dict[str, str] | None:
    """Os nomes dos produtos. None quando o catálogo não respondeu: aí o que
    depende do nome (cursos e documentos marcados com produto) fica como está."""
    lista = CatalogoClient().listar_produtos()
    if lista is None:
        leitura.faltou.append("nomes dos produtos (catálogo)")
        return None
    return {str(p.get("id")): str(p.get("name") or "") for p in lista if isinstance(p, dict)}


def _ler_cursos(leitura: Leitura, produtos: dict[str, str] | None) -> None:
    if produtos is None:
        # Sem o nome do produto o curso mudaria à toa e perderia a ligação no mapa.
        leitura.faltou.append("cursos (sem os nomes dos produtos)")
        return
    cliente = CursosClient()
    desfecho, cursos = cliente.cursos(leitura.site_id)
    if desfecho != cliente.OK:
        leitura.faltou.append(f"cursos ({desfecho})")
        return
    fontes = []
    for curso in cursos or []:
        if not isinstance(curso, dict) or curso.get("estado") != "publicado":
            continue
        slug = str(curso.get("slug") or "")
        desfecho, aulas = cliente.aulas(leitura.site_id, slug)
        if desfecho != cliente.OK:
            # Sem as aulas, a fonte sairia pela metade e mudaria a impressão à toa.
            leitura.faltou.append(f"aulas do curso {slug} ({desfecho})")
            return
        fontes.append(_fonte_do_curso(leitura, curso, aulas or [], produtos))
    leitura.fontes.extend(f for f in fontes if f.partes)
    leitura.lidos.add("curso")


def _fonte_do_curso(leitura: Leitura, curso: dict, aulas: list, produtos: dict) -> Fonte:
    slug = str(curso.get("slug") or "")
    nome = nome_sem_preco(str(curso.get("nome") or slug), slug)
    produto_id = str(curso.get("produto_id") or "")
    produto_nome = produtos.get(produto_id, "")
    publicadas = [a for a in aulas if isinstance(a, dict) and a.get("estado") == "publicada"]
    blocos: dict[tuple, dict] = {}
    for aula in publicadas:
        bloco = aula.get("bloco") or {}
        chave_do_bloco = (bloco.get("parte") or 0, bloco.get("ordem") or 0, bloco.get("letra") or "?")
        b = blocos.setdefault(chave_do_bloco, {"nome": bloco.get("nome") or "", "aulas": []})
        b["aulas"].append(str(aula.get("titulo_exibido") or aula.get("numero") or ""))
    partes_do_livro = sorted({c[0] for c in blocos if c[0]})
    endereco = f"https://{leitura.host}/cursos/{quote(slug)}/" if leitura.host else ""

    geral = f"{nome} é um curso on-line do site {leitura.host or leitura.site_id}"
    if produto_nome:
        geral += f", vendido como o produto {produto_nome}"
    geral += f". Tem {len(publicadas)} aula{'s' if len(publicadas) != 1 else ''} publicada{'s' if len(publicadas) != 1 else ''}"
    if blocos:
        geral += f" em {len(blocos)} módulo{'s' if len(blocos) != 1 else ''}"
    if len(partes_do_livro) > 1:
        geral += f", divididos em {len(partes_do_livro)} partes"
    geral += "."
    acesso = (
        "Forma de acesso: o aluno estuda na sala de aula do site"
        + (f" ({endereco})" if endereco else "")
        + ", e a sala abre pela matrícula no produto do curso, depois da compra confirmada."
    )
    if curso.get("progressao") in PROGRESSAO:
        acesso += f" Ritmo: {PROGRESSAO[curso['progressao']]}."
    partes = [("Visão geral", f"{geral}\n\n{acesso}")]

    linhas = []
    for (parte, _ordem, letra), b in sorted(blocos.items()):
        rotulo = f"Parte {parte}, módulo {letra}" if parte else f"Módulo {letra}"
        if b["nome"]:
            rotulo += f": {b['nome']}"
        titulos = "; ".join(t for t in b["aulas"] if t)
        linhas.append(f"{rotulo} ({len(b['aulas'])} aula{'s' if len(b['aulas']) != 1 else ''})" + (f". Aulas: {titulos}." if titulos else "."))
    for pedaco in pedacos("\n\n".join(linhas), f"o curso {slug}"):
        partes.append(("Módulos e aulas", pedaco))

    datas = [d for d in (_data(a.get("publicada_em")) for a in publicadas) if d]
    # No mapa da equipe o curso e o módulo levam o site no nome: o curso de
    # mesmo nome em outro site é outra coisa e não pode virar o mesmo nó.
    no_do_curso = no_do_site(nome, leitura)
    entidades = [{"nome": no_do_curso, "tipo": "curso", "resumo": geral[:500]}]
    ligacoes = []
    if produto_nome:
        entidades.append({"nome": produto_nome, "tipo": "produto", "resumo": f"Produto do catálogo (id {produto_id})."})
        ligacoes.append({"origem": no_do_curso, "relacao": "faz parte do produto", "destino": produto_nome, "evidencia": geral[:400]})
    for (parte, _ordem, letra), b in sorted(blocos.items()):
        if b["nome"]:
            ligacoes.append({
                "origem": no_do_curso, "relacao": "tem módulo",
                "destino": f"{b['nome']} ({nome}, {leitura.host or leitura.site_id})",
                "evidencia": f"Módulo {letra} do curso {nome}, com {len(b['aulas'])} aula(s) publicada(s).",
            })
    return Fonte(
        tipo="curso",
        ref=slug,
        titulo=f"Curso {nome}",
        endereco=endereco,
        produto_ref=produto_id,
        produto_nome=produto_nome,
        vigente_desde=max(datas) if datas else None,
        partes=partes,
        entidades=entidades,
        ligacoes=ligacoes,
    )


def oferta_ao_vivo(site_id: str, slug: str) -> tuple[str, dict | str]:
    """`getOffer` do catálogo, agora. Desfechos: ok, nao_existe, nao_respondeu."""
    return CatalogoClient()._falar(
        "GET",
        f"/sites/{quote(str(site_id), safe='')}/ofertas/{quote(str(slug), safe='')}",
        especiais=((404, "nao_existe"),),
    )


def _ler_oferta(leitura: Leitura, site: dict, produtos: dict[str, str] | None) -> None:
    catalogo = CatalogoClient()
    desfecho, pagina = catalogo.pagina_publicada(leitura.site_id, "oferta")
    if desfecho == catalogo.SEM_PAGINA:
        pagina = {}
    elif desfecho != catalogo.OK:
        leitura.faltou.append("página de venda (catálogo)")
        return
    slug = str((pagina or {}).get("offer_slug") or site.get("default_offer_slug") or "")
    if not slug:
        leitura.lidos.add("oferta")
        return
    desfecho, oferta = oferta_ao_vivo(leitura.site_id, slug)
    if desfecho == "nao_existe":
        leitura.lidos.add("oferta")  # a oferta saiu do site: sai do índice
        return
    if desfecho != catalogo.OK:
        leitura.faltou.append(f"oferta {slug} (catálogo)")
        return
    produto = oferta.get("product") or {}
    produto_id = str(produto.get("id") or "")
    produto_nome = str(produto.get("name") or (produtos or {}).get(produto_id, ""))
    if not produto_nome and produtos is None:
        leitura.faltou.append(f"oferta {slug} (sem o nome do produto)")
        return
    partes = []
    headline = ""
    for secao in (pagina or {}).get("secoes") or []:
        if not isinstance(secao, dict):
            continue
        slots = secao.get("slots") or {}
        headline = headline or nome_sem_preco(str(slots.get("headline") or ""), "")
        textos = [
            sem_preco(str(v)) for s, v in slots.items()
            if s not in SLOTS_FORA and isinstance(v, str) and v.strip()
        ]
        texto = "\n\n".join(t for t in textos if t and not _so_marca(t))
        if texto:
            titulo = NOMES_DAS_SECOES.get(str(secao.get("nome")), str(secao.get("nome") or "Página"))
            for pedaco in pedacos(texto, f"a oferta {slug} ({titulo})"):
                partes.append((titulo, pedaco))
    resumo = f"A oferta '{slug}' do site {leitura.host or leitura.site_id} vende o produto {produto_nome or produto_id}."
    partes.insert(0, ("Oferta", resumo))
    bumps = [b for b in oferta.get("bumps") or [] if isinstance(b, dict) and b.get("name")]
    if bumps:
        partes.append(("Complementos oferecidos junto", "\n".join(
            nome_sem_preco(str(b["name"]), "Complemento")
            + (f": {chamada}" if (chamada := sem_preco(str(b.get("headline") or ""))) else "")
            for b in bumps
        )))
    no_da_oferta = no_do_site(f"Oferta {slug}", leitura)  # o apelido só é único dentro do site
    entidades = [{"nome": no_da_oferta, "tipo": "oferta", "resumo": (headline or resumo)[:500]}]
    ligacoes = []
    if produto_nome:
        entidades.append({"nome": produto_nome, "tipo": "produto", "resumo": f"Produto do catálogo (id {produto_id})."})
        ligacoes.append({"origem": no_da_oferta, "relacao": "vende", "destino": produto_nome, "evidencia": resumo[:400]})
    leitura.fontes.append(Fonte(
        tipo="oferta",
        ref=slug,
        titulo=f"Oferta {slug}" + (f": {headline}" if headline else ""),
        endereco=f"https://{leitura.host}/" if leitura.host else "",
        produto_ref=produto_id,
        produto_nome=produto_nome,
        oferta_ref=slug,
        vigente_desde=_data((pagina or {}).get("published_at")),
        partes=partes,
        entidades=entidades,
        ligacoes=ligacoes,
    ))
    leitura.lidos.add("oferta")


def _produto_da_marca(texto: str, produtos: dict[str, str]) -> tuple[str, str]:
    texto = (texto or "").strip()
    if not texto:
        return "", ""
    if texto in produtos:
        return texto, produtos[texto]
    for pid, nome in produtos.items():
        if _nome_chave(nome) == _nome_chave(texto):
            return pid, nome
    return "", texto


def _ler_materiais(leitura: Leitura, produtos: dict[str, str] | None) -> None:
    from .conhecimento import _endereco

    marcas = MaterialComercial.objects.filter(site_id=leitura.site_id)
    documentos = {
        d.nome: d for d in Documento.objects.filter(
            nome__in=[m.documento_nome for m in marcas], arquivado=False
        ).exclude(corpo="")
    }
    for marca in marcas:
        documento = documentos.get(marca.documento_nome)
        if documento is None:
            continue
        if marca.tipo == MaterialComercial.Tipo.DEPOIMENTO and not marca.utilizavel:
            continue
        tipo = "depoimento" if marca.tipo == MaterialComercial.Tipo.DEPOIMENTO else "documento"
        if produtos is None and (marca.produto or "").strip():
            # Sem os nomes dos produtos, a marca perderia o produto: esta fonte
            # fica como está. As outras (e as revogadas) seguem o curso normal.
            leitura.mantidas.add(chave(leitura.site_id, tipo, documento.nome))
            leitura.faltou.append(f"documento {documento.nome} (sem os nomes dos produtos)")
            continue
        produto_ref, produto_nome = _produto_da_marca(marca.produto, produtos or {})
        rotulo = f"Depoimento: {documento.titulo}" if tipo == "depoimento" else documento.titulo
        partes = [
            (rotulo, p) for p in pedacos(sem_preco(documento.corpo), f"o documento {documento.nome}")
            if not _so_marca(p)
        ]
        if not partes:
            continue
        leitura.fontes.append(Fonte(
            tipo=tipo,
            ref=documento.nome,
            titulo=rotulo[:200],
            endereco=_endereco(documento),
            publica=bool(documento.publico),
            produto_ref=produto_ref,
            produto_nome=produto_nome,
            oferta_ref=(marca.oferta or "").strip(),
            vigente_desde=documento.atualizado_em,
            partes=partes,
        ))
    leitura.lidos.update({"documento", "depoimento"})


def ler(site: dict) -> Leitura:
    """Lê o que o site tem de comercial agora. O que não respondeu fica em
    `faltou` e o tipo dele fora de `lidos`: o índice daquele tipo não é tocado."""
    leitura = Leitura(site_id=str(site.get("id") or ""), host=str(site.get("host") or "").lower())
    produtos = _produtos(leitura)
    _ler_cursos(leitura, produtos)
    _ler_oferta(leitura, site, produtos)
    _ler_materiais(leitura, produtos)
    return leitura


# --------------------------------------------------------------- o índice


def _gravar(leitura: Leitura, fonte: Fonte, chave_da_fonte: str, impressao: str, agora) -> None:
    with transaction.atomic():
        registro, _ = FonteDoConhecimento.objects.update_or_create(
            chave=chave_da_fonte,
            defaults={
                "titulo": fonte.titulo[:200],
                "endereco": fonte.endereco[:300],
                "publica": fonte.publica,
                "impressao": impressao,
            },
        )
        registro.entidades.all().delete()
        registro.ligacoes.all().delete()
        registro.trechos_comerciais.all().delete()
        EntidadeDoConhecimento.objects.bulk_create([
            EntidadeDoConhecimento(
                fonte=registro, nome=e["nome"][:200], tipo=e["tipo"][:40], resumo=(e.get("resumo") or "")[:500]
            )
            for e in fonte.entidades
        ])
        LigacaoDoConhecimento.objects.bulk_create([
            LigacaoDoConhecimento(
                fonte=registro,
                origem=l["origem"][:200],
                relacao=l["relacao"][:80],
                destino=l["destino"][:200],
                evidencia=(l.get("evidencia") or "")[:400],
            )
            for l in fonte.ligacoes
        ])
        TrechoComercial.objects.bulk_create([
            TrechoComercial(
                fonte=registro,
                site_id=leitura.site_id,
                site_host=leitura.host[:200],
                tipo=fonte.tipo,
                ref=fonte.ref[:255],
                produto_ref=fonte.produto_ref[:64],
                produto_nome=fonte.produto_nome[:255],
                oferta_ref=fonte.oferta_ref[:255],
                titulo=titulo[:200],
                texto=texto,
                texto_normal=_normal(f"{titulo} {texto}"),
                ordem=ordem,
                publico=fonte.publica,
                endereco=fonte.endereco[:300],
                vigente_desde=fonte.vigente_desde or agora,
                conferido_em=agora,
            )
            for ordem, (titulo, texto) in enumerate(fonte.partes)
        ])


ESPERA_DA_TRAVA = 120  # segundos esperando a outra atualização do mesmo site


def numero_da_trava(site_id: str) -> int:
    return int.from_bytes(hashlib.sha1(f"{PREFIXO}{site_id}".encode("utf-8")).digest()[:8], "big", signed=True)


@contextmanager
def _um_de_cada_vez(site_id: str):
    """Uma atualização por site de cada vez, entre processos e entre a tela e a
    volta automática (trava do Postgres). Quem chega depois lê DEPOIS de quem
    estava gravando: uma leitura velha não regrava o que outra acabou de tirar.
    Devolve False se a outra não terminou a tempo."""
    if connection.vendor != "postgresql":
        yield True
        return
    numero = numero_da_trava(site_id)
    prazo = time.monotonic() + ESPERA_DA_TRAVA
    with connection.cursor() as cursor:
        pegou = False
        while True:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [numero])
            pegou = bool(cursor.fetchone()[0])
            if pegou or time.monotonic() >= prazo:
                break
            time.sleep(0.2)
        try:
            yield pegou
        finally:
            if pegou:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [numero])


def atualizar(site: dict) -> dict:
    """Põe o índice comercial do site em dia com o que ele tem agora. Só a
    fonte nova ou mudada é regravada; a que sumiu sai, mas só se o tipo dela
    foi lido inteiro agora. A leitura e a gravação são uma volta só, uma de
    cada vez por site."""
    site_id = str(site.get("id") or "")
    with _um_de_cada_vez(site_id) as pegou:
        if not pegou:
            return {
                "site": {"id": site_id, "host": str(site.get("host") or "").lower()},
                "novas": 0, "mudadas": 0, "iguais": 0, "sairam": 0,
                "faltou": ["outra atualização deste site ainda está rodando"],
            }
        return _atualizar(site)


def _atualizar(site: dict) -> dict:
    leitura = ler(site)
    agora = timezone.now()
    prefixo = f"{PREFIXO}{leitura.site_id}:"
    existentes = {f.chave: f for f in FonteDoConhecimento.objects.filter(chave__startswith=prefixo)}
    vistas: set[str] = set()
    novas = mudadas = iguais = 0
    for fonte in leitura.fontes:
        chave_da_fonte = chave(leitura.site_id, fonte.tipo, fonte.ref)
        if chave_da_fonte in vistas:
            continue
        vistas.add(chave_da_fonte)
        impressao = fonte.impressao()
        atual = existentes.get(chave_da_fonte)
        if atual is not None and atual.impressao == impressao:
            iguais += 1
            TrechoComercial.objects.filter(fonte=atual).update(conferido_em=agora, site_host=leitura.host[:200])
            continue
        _gravar(leitura, fonte, chave_da_fonte, impressao, agora)
        if atual is None:
            novas += 1
        else:
            mudadas += 1
    sairam = [
        c for c in existentes
        if c not in vistas and c not in leitura.mantidas and _tipo_da_chave(c) in leitura.lidos
    ]
    FonteDoConhecimento.objects.filter(chave__in=sairam).delete()
    return {
        "site": {"id": leitura.site_id, "host": leitura.host},
        "novas": novas,
        "mudadas": mudadas,
        "iguais": iguais,
        "sairam": len(sairam),
        "faltou": leitura.faltou,
    }


def atualizar_host(host: str) -> dict:
    host = (host or "").strip().lower()
    site = CatalogoClient().site_por_host(host)
    if site is None:
        return {
            "site": {"id": "", "host": host},
            "capacidade_indisponivel": True,
            "faltou": [f"o catálogo não devolveu o site {host}"],
        }
    return atualizar(site)


def hosts_conhecidos() -> list[str]:
    configurados = os.environ.get("CONHECIMENTO_COMERCIAL_HOSTS") or HOST_PADRAO
    hosts = [h.strip().lower() for h in configurados.split(",")]
    # `.order_by()` antes do `.distinct()`: a ordem padrão do modelo entraria no
    # DISTINCT e devolveria o mesmo domínio muitas vezes.
    hosts += list(TrechoComercial.objects.order_by().values_list("site_host", flat=True).distinct())
    hosts += list(MaterialComercial.objects.order_by().values_list("site_host", flat=True).distinct())
    return list(dict.fromkeys(h for h in hosts if h))


# A volta de sucesso espera meia hora; a que falhou (exceção, ou o catálogo não
# respondeu em nenhum domínio) tenta de novo logo, sem esperar a meia hora.
INTERVALO_APOS_FALHA = timedelta(minutes=2)

_ultima_volta: dict[str, datetime] = {}
_trava = threading.Lock()


def _deu_certo(resultados: list[dict]) -> bool:
    return any(not r.get("capacidade_indisponivel") for r in resultados)


def manter_em_dia(*, forcar: bool = False) -> list[dict] | None:
    """A volta automática (do laço dos robôs, a cada meia hora por processo):
    o catálogo mudou, o índice muda junto. Sem o par com o catálogo, não faz
    nada; e nunca derruba quem chamou. A meia hora só conta depois de uma volta
    que funcionou: se falhou, a próxima tentativa vem em poucos minutos."""
    if CatalogoClient()._configuracao() is None:
        return None
    agora = timezone.now()
    with _trava:
        if _ultima_volta.get("rodando"):
            return None  # outra volta deste processo está em andamento
        if not forcar:
            certa = _ultima_volta.get("certa")
            falhou = _ultima_volta.get("falhou")
            if certa is not None and agora - certa < INTERVALO:
                return None
            if falhou is not None and agora - falhou < INTERVALO_APOS_FALHA:
                return None
        _ultima_volta["rodando"] = agora
    try:
        resultados = [atualizar_host(h) for h in hosts_conhecidos()]
    except Exception:  # noqa: BLE001 - o índice não pode derrubar o laço
        log.exception("Conhecimento comercial: a atualização automática falhou")
        with _trava:
            _ultima_volta["falhou"] = timezone.now()
        return None
    finally:
        with _trava:
            _ultima_volta.pop("rodando", None)
    with _trava:
        if resultados and not _deu_certo(resultados):
            log.warning("Conhecimento comercial: o catálogo não respondeu; tenta de novo em poucos minutos")
            _ultima_volta["falhou"] = timezone.now()
        else:
            _ultima_volta["certa"] = timezone.now()
            _ultima_volta.pop("falhou", None)
    return resultados


# -------------------------------------------------------------- a consulta


def _termos(pergunta: str) -> list[str]:
    palavras = re.sub(r"[^\w\s]|_", " ", _normal(pergunta)).split()
    termos = []
    for p in palavras:
        if len(p) < 3 or p in _VAZIAS:
            continue
        if len(p) > 3 and p.endswith("s") and not p.endswith(("ss", "is", "us")):
            p = p[:-1]
        if len(p) >= 6:
            p = p[: max(4, len(p) - 3)]
        termos.append(p)
    return list(dict.fromkeys(termos))[:12]


def _site_do_indice(site: str) -> tuple[str, str] | None:
    """O site pedido, pelo id ou pelo domínio. Nunca um site parecido."""
    pedido = (site or "").strip()
    if not pedido:
        return None
    linha = (
        TrechoComercial.objects.filter(site_id=pedido).values_list("site_id", "site_host").first()
        or TrechoComercial.objects.filter(site_host=pedido.lower()).values_list("site_id", "site_host").first()
    )
    if linha:
        return linha[0], linha[1]
    if "." in pedido:
        achado = CatalogoClient().site_por_host(pedido.lower())
        if achado and achado.get("id"):
            return str(achado["id"]), str(achado.get("host") or pedido.lower())
    return None


def _sem_prefixo_de_oferta(produto: str) -> str:
    """O coordenador manda 'oferta:<apelido>' (a forma do CRM) ou o apelido do
    quiz; o índice guarda só o apelido."""
    return re.sub(r"^\s*oferta\s*:\s*", "", (produto or "").strip(), flags=re.IGNORECASE).strip()


def _do_produto(trechos: list[TrechoComercial], produto: str) -> tuple[list[TrechoComercial], bool]:
    """Os trechos daquele produto ou oferta, mais os gerais do site. Trecho de
    OUTRO produto fica de fora. O segundo valor diz se o produto foi achado."""
    pedido = _sem_prefixo_de_oferta(produto)
    if not pedido:
        return trechos, False
    chave_pedida = _nome_chave(pedido)

    def casa(t: TrechoComercial) -> bool:
        return pedido in (t.produto_ref, t.oferta_ref) or (t.tipo == "curso" and t.ref == pedido) or (
            bool(chave_pedida) and bool(t.produto_nome) and (
                _nome_chave(t.produto_nome) == chave_pedida
                or f" {chave_pedida} " in f" {_nome_chave(t.produto_nome)} "
            )
        ) or (t.tipo == "curso" and bool(chave_pedida) and _nome_chave(t.titulo.removeprefix("Curso ")) == chave_pedida)

    casados = [t for t in trechos if casa(t)]
    refs = {t.produto_ref for t in casados if t.produto_ref}
    nomes = {_nome_chave(t.produto_nome) for t in casados if t.produto_nome}
    ofertas = {t.oferta_ref for t in casados if t.oferta_ref}

    def do_mesmo(t: TrechoComercial) -> bool:
        return (t.produto_ref and t.produto_ref in refs) or (
            t.produto_nome and _nome_chave(t.produto_nome) in nomes
        ) or (t.oferta_ref and t.oferta_ref in ofertas)

    def geral(t: TrechoComercial) -> bool:
        return not (t.produto_ref or t.produto_nome or t.oferta_ref)

    return [t for t in trechos if casa(t) or do_mesmo(t) or geral(t)], bool(casados)


def _pontos(trecho: TrechoComercial, termos: list[str]) -> tuple[int, int]:
    titulo = _normal(trecho.titulo)
    casados = pontos = 0
    for termo in termos:
        achados = len(re.findall(rf"\b{re.escape(termo)}", trecho.texto_normal))
        if achados:
            casados += 1
            pontos += min(achados, 3) + (2 if re.search(rf"\b{re.escape(termo)}", titulo) else 0)
    return casados, pontos


def _dia(valor) -> str | None:
    return timezone.localtime(valor).date().isoformat() if valor else None


def _saida(t: TrechoComercial) -> dict:
    return {
        "titulo": t.titulo,
        "texto": t.texto[: TAMANHO_DO_TRECHO * 2],
        # O endereço de uma fonte que não é pública não sai daqui.
        "fonte": {"tipo": t.tipo, "id": t.ref, "titulo": t.fonte.titulo,
                  "endereco": (t.endereco or None) if t.publico else None},
        "produto": {"ref": t.produto_ref or None, "nome": t.produto_nome or None}
        if (t.produto_ref or t.produto_nome) else None,
        "oferta": t.oferta_ref or None,
        "vigencia": {"desde": _dia(t.vigente_desde), "conferido_em": _dia(t.conferido_em)},
        "publico": t.publico,
        "ao_vivo": False,
    }


def _reais(centavos) -> str:
    inteiro, resto = divmod(int(centavos), 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def _ofertas_da_pergunta(escolhidos: list[TrechoComercial], trechos: list[TrechoComercial]
                         ) -> tuple[list[str], list[str]]:
    """As ofertas cujo preço responde à pergunta: as dos trechos escolhidos e
    as que vendem o MESMO produto deles. Só quando nenhum trecho escolhido é de
    produto (pergunta geral do site) vêm as ofertas do site. O segundo valor
    são os produtos dos trechos que não têm oferta indexada neste site."""
    ofertas = [t.oferta_ref for t in escolhidos if t.oferta_ref]
    da_oferta = [t for t in trechos if t.tipo == "oferta" and t.oferta_ref]
    produtos: dict[str, tuple[str, str]] = {}  # nome do produto -> (ref, chave do nome)
    for t in escolhidos:
        if t.produto_ref or t.produto_nome:
            produtos.setdefault(t.produto_nome or t.produto_ref, (t.produto_ref, _nome_chave(t.produto_nome)))
    if not produtos:
        ofertas += [t.oferta_ref for t in da_oferta]
        return list(dict.fromkeys(ofertas)), []

    def do_produto(t: TrechoComercial, ref: str, nome: str) -> bool:
        return bool(ref and t.produto_ref == ref) or bool(nome and _nome_chave(t.produto_nome) == nome)

    sem_oferta = []
    for nome_do_produto, (ref, nome) in produtos.items():
        casadas = [t.oferta_ref for t in da_oferta + escolhidos if t.oferta_ref and do_produto(t, ref, nome)]
        ofertas += casadas
        if not casadas:
            sem_oferta.append(nome_do_produto)
    return list(dict.fromkeys(ofertas)), sem_oferta


def _fatos_ao_vivo(site_id: str, ofertas: list[str], sem_oferta: list[str] = ()) -> list[dict]:
    agora = timezone.now().isoformat()
    fatos = []
    for nome in sem_oferta:
        fatos.append({
            "texto": f"O produto {nome} não tem oferta indexada neste site; não diga um preço para ele "
            "(o preço de outra oferta é de outro produto).",
            "fonte": {"tipo": "produto", "id": nome},
            "vigencia": {"consultado_em": agora},
            "ao_vivo": True,
        })
    for slug in ofertas[:3]:
        desfecho, oferta = oferta_ao_vivo(site_id, slug)
        if desfecho == "ok":
            produto = oferta.get("product") or {}
            nome_do_produto = str(produto.get("name") or produto.get("id") or "")
            fatos.append({
                "texto": f"Preço da oferta '{slug}'"
                + (f", que vende o produto {nome_do_produto}," if nome_do_produto else "")
                + f" agora no catálogo: {_reais(oferta.get('price_cents') or 0)}"
                f" (versão {oferta.get('version')}).",
                "fonte": {"tipo": "oferta", "id": slug},
                "produto": {"ref": str(produto.get("id") or "") or None, "nome": nome_do_produto or None},
                "vigencia": {"consultado_em": agora},
                "ao_vivo": True,
            })
        elif desfecho == "nao_existe":
            fatos.append({
                "texto": f"A oferta '{slug}' não está à venda neste site agora.",
                "fonte": {"tipo": "oferta", "id": slug},
                "vigencia": {"consultado_em": agora},
                "ao_vivo": True,
            })
        else:
            fatos.append({
                "capacidade_indisponivel": True,
                "capacidade": "preco_ao_vivo",
                "fonte": {"tipo": "oferta", "id": slug},
                "motivo": "O catálogo não respondeu agora; não diga um preço lembrado.",
                "ao_vivo": True,
            })
    fatos.append({
        "texto": (
            "Parcelas, cupons, formas de pagamento e vencimento vêm do checkout NA HORA, "
            "pela consulta de condições de compra da oferta; nunca use valores lembrados."
        ),
        "fonte": {"tipo": "checkout", "id": "condicoes_de_compra"},
        "ao_vivo": True,
    })
    return fatos


def consultar(site: str, pergunta: str, produto: str = "", *, com_privados: bool = True,
              limite: int = MAX_TRECHOS_NA_RESPOSTA) -> dict:
    """Os trechos do conhecimento comercial de UM site que respondem à
    pergunta, com fonte e vigência. A pergunta é só texto de busca: nada nela
    vira ordem para a ferramenta."""
    achado = _site_do_indice(site)
    if achado is None:
        return {
            "site": {"pedido": (site or "")[:200]},
            "achou": False,
            "trechos": [],
            "fatos_ao_vivo": [],
            "aviso": "Este site ainda não tem conhecimento comercial indexado. Não invente: diga que vai confirmar.",
        }
    site_id, host = achado
    trechos = list(TrechoComercial.objects.filter(site_id=site_id).select_related("fonte"))
    if not com_privados:
        trechos = [t for t in trechos if t.publico]
    aviso = ""
    produto = _sem_prefixo_de_oferta(produto)[:255]
    sem_correspondencia = False
    if produto:
        do_produto, casou = _do_produto(trechos, produto)
        if casou:
            trechos = do_produto
        else:
            # Apelido que não casa com nada (por exemplo o do quiz): não esconde
            # o site; devolve tudo dele e avisa que o produto não foi achado.
            sem_correspondencia = True
            aviso = (
                f"Nada indexado para '{produto}' neste site; os trechos vêm do site inteiro e "
                "podem ser de outro produto: confira a fonte de cada um."
            )
    termos = _termos(pergunta)
    pontuados = []
    for t in trechos:
        casados, pontos = _pontos(t, termos)
        if casados:
            pontuados.append((casados, pontos, -t.ordem, t))
    pontuados.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    escolhidos = [p[3] for p in pontuados[:limite]]
    if not escolhidos and produto and not aviso:
        # Nada casou as palavras, mas o produto é conhecido: a visão geral dele.
        escolhidos = sorted(
            (t for t in trechos if t.produto_ref or t.produto_nome or t.oferta_ref),
            key=lambda t: (t.tipo != "curso", t.ordem),
        )[:min(limite, 3)]
    resposta = {
        "site": {"id": site_id, "host": host},
        "achou": bool(escolhidos),
        "trechos": [_saida(t) for t in escolhidos],
        "fatos_ao_vivo": [],
        "preco_e_condicoes": "ao_vivo",
    }
    if sem_correspondencia:
        resposta["produto_sem_correspondencia"] = True
    if _PERGUNTA_DE_PRECO.search(_normal(pergunta)):
        ofertas, sem_oferta = _ofertas_da_pergunta(escolhidos, trechos)
        resposta["fatos_ao_vivo"] = _fatos_ao_vivo(site_id, ofertas, sem_oferta)
    if not escolhidos:
        aviso = (aviso + " " if aviso else "") + "Nenhum trecho responde a isso. Não invente: diga que vai confirmar."
    if aviso:
        resposta["aviso"] = aviso
    return resposta


def numeros(site_id: str) -> dict:
    trechos = TrechoComercial.objects.filter(site_id=site_id)
    por_tipo = {tipo: 0 for tipo in TIPOS}
    # `.order_by()` antes do `.distinct()`: a ordem padrão do modelo entra no
    # DISTINCT e infla a conta (uma linha por trecho, não por fonte).
    for tipo, fonte_id in trechos.order_by().values_list("tipo", "fonte_id").distinct():
        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
    ultima = trechos.order_by("-conferido_em").values_list("conferido_em", flat=True).first()
    return {"fontes": por_tipo, "trechos": trechos.count(), "conferido_em": ultima}


# --------------------------------------------------------------- a ferramenta

NOME_DA_FERRAMENTA = "consultar_conhecimento_comercial"

DEFINICAO = {
    "type": "function",
    "name": NOME_DA_FERRAMENTA,
    "description": (
        "Conhecimento comercial de UM site: cursos, módulos, aulas, forma de acesso, "
        "requisitos, duração e o que a página de venda diz, materiais comerciais e "
        "depoimentos autorizados. Devolve trechos com fonte (tipo e id) e vigência. "
        "Preço e condições NUNCA vêm da memória: quando a pergunta é de preço, vem o "
        "preço consultado agora (ao_vivo: true). Não use trecho de outro site."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "site": {"type": "string", "description": "O id do site ou o domínio (ex.: meshcraft.top)."},
            "produto": {
                "type": ["string", "null"],
                "description": "Produto, curso ou oferta (id, apelido ou nome). Nulo: o site todo.",
            },
            "pergunta": {"type": "string", "description": "A dúvida, em poucas palavras."},
        },
        "required": ["site", "produto", "pergunta"],
        "additionalProperties": False,
    },
    "strict": True,
}


def executar_ferramenta(argumentos: dict, *, com_privados: bool = True) -> dict:
    """A ferramenta para qualquer agente: confere os argumentos e consulta."""
    site = str(argumentos.get("site") or "").strip()[:200]
    pergunta = str(argumentos.get("pergunta") or "").strip()[:500]
    if not site or not pergunta:
        return {"erro": "Diga o site e a pergunta."}
    return consultar(site, pergunta, str(argumentos.get("produto") or ""), com_privados=com_privados)


def consultar_conhecimento_comercial(*, site_id, termos, produto=None, com_privados=False) -> dict:
    """A porta da equipe comercial de agentes (`apps.comercial.ferramentas`),
    que a procura por este nome. O coordenador fala com o lead: nunca recebe
    material interno, então `com_privados` é sempre falso, seja qual for o
    valor pedido (o parâmetro existe só para a assinatura combinada)."""
    pergunta = " ".join(str(t).strip() for t in (termos or []) if str(t).strip())[:500]
    return consultar(str(site_id or ""), pergunta, str(produto or ""), com_privados=False)
