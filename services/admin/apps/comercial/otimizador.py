"""O otimizador das estratégias comerciais: mede, testa e, se piorar, volta.

Roda de hora em hora no trabalho `analisar_resultados` (`coordenador.manutencao`
cria o da hora). A ideia, em quatro passos:

1. **Medir.** Junta os resultados por versão da estratégia e, dentro dela, por
   quiz, campanha e oferta. Só vendas que o PROVEDOR confirmou
   (`pagamento.aprovado`), só oportunidades reais (teste fica de fora) e só
   venda depois da mensagem.
2. **Propor.** Com amostra suficiente numa versão (`MIN_AMOSTRA`) e sem outro
   teste rodando naquele papel, o modelo forte lê os números e pode propor uma
   versão nova das INSTRUÇÕES. Com pouca amostra o relatório é inconclusivo e
   o modelo nem é chamado: uma venda num grupo pequeno não prova nada.
3. **Testar.** A versão nova não substitui a do ar: vira candidata e atende uma
   fatia das oportunidades (`OTIMIZADOR_PERCENTUAL_TESTE`, padrão 20%; 0 deixa
   a proposta só como proposta, para a pessoa pôr no ar). A divisão é
   determinística: a mesma oportunidade fica sempre na mesma versão. Cada
   decisão guarda a versão usada (`DecisaoComercial.versao_estrategia`).
4. **Decidir.** Comparando as duas no mesmo período (teste de duas proporções com corte que vale para conferência a toda hora, `z_critico`):
   candidata pior com amostra nas duas => o teste acaba e todo o tráfego volta
   para a versão anterior, com o motivo registrado; melhor com amostra => vira
   a versão do ar (a anterior fica guardada para voltar); sem diferença, o teste
   acaba depois de `DURACAO_MAXIMA`.

O que a estratégia NÃO muda: só o texto das instruções é versionado. O
catálogo, as condições de compra, as permissões de cada canal e o fato de que
pagamento só é aprovado pelo provedor vivem em outras células e no código das
ferramentas (`ferramentas.py`, `papeis.COMUM`), que nenhuma versão alcança: as
regras fixas vão SEMPRE antes das instruções da versão
(`papeis.instrucoes_completas`).

As funções do começo do módulo (`balde`, `escolher_versao`, `comparar`) não
tocam o banco: recebem qualquer objeto com `papel`, `versao` e `instrucoes`
(o protocolo `Versao`).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from . import papeis
from .experimentos import ExperimentoEstrategia
from .models import DecisaoComercial, EstrategiaComercial, EventoComercial, TrabalhoComercial

MIN_AMOSTRA = 30
# O teste roda a cada hora e decide no primeiro veredito claro. Olhar muitas
# vezes com o corte fixo de 1,96 erra em cerca de um teste em quatro quando as
# duas versões são iguais; por isso o corte sobe com a amostra de um jeito que
# vale para olhadas sem fim (`z_critico`). ALFA é o erro aceito no teste todo.
ALFA = 0.05
AMOSTRA_DE_REFERENCIA = 15  # informação (n_a*n_b/(n_a+n_b)) de duas amostras mínimas de 30
PERCENTUAL_PADRAO = 20
PERCENTUAL_MAXIMO = 50
DURACAO_MAXIMA = timedelta(days=21)
MAX_VALORES_NO_PEDIDO = 8  # por quiz, campanha ou oferta que vai ao modelo

E = TrabalhoComercial.Estado
T = TrabalhoComercial.Tipo
P = EstrategiaComercial.Papel
X = ExperimentoEstrategia.Estado

# Os papéis que têm resultado medido (venda depois da mensagem). O analista só
# lê e o de resultados não fala com lead: não há o que comparar neles.
PAPEIS_OTIMIZAVEIS = (P.ABORDAGEM, P.ATENDIMENTO)
TIPOS_DO_PAPEL = {
    P.ABORDAGEM: (T.ABORDAR,),
    P.ATENDIMENTO: (T.ATENDER_MENSAGEM, T.ACOMPANHAR_PAGAMENTO),
}
DIMENSOES = (("por_quiz", "quiz"), ("por_campanha", "campanha"), ("por_oferta", "oferta"))


class Versao(Protocol):
    papel: str
    versao: int
    instrucoes: str


# ------------------------------------------------- partes puras (sem banco)


def balde(experimento_id: int | str, chave: str) -> int:
    """Um número de 0 a 99 que só depende do experimento e da chave."""
    resumo = hashlib.sha256(f"{experimento_id}:{chave}".encode()).digest()
    return int.from_bytes(resumo[:8], "big") % 100


def escolher_versao(base: Versao, candidata: Versao, experimento_id, percentual: int, chave: str) -> Versao:
    """A candidata atende `percentual`% das chaves; a mesma chave dá sempre a
    mesma resposta."""
    return candidata if balde(experimento_id, chave) < percentual else base


def z_de_duas_proporcoes(sucessos_a: int, n_a: int, sucessos_b: int, n_b: int) -> float | None:
    """z de (a - b). None quando não há como comparar."""
    if not n_a or not n_b:
        return None
    total = (sucessos_a + sucessos_b) / (n_a + n_b)
    erro = math.sqrt(total * (1 - total) * (1 / n_a + 1 / n_b))
    if erro == 0:
        return None
    return (sucessos_a / n_a - sucessos_b / n_b) / erro


def z_critico(n_a: int, n_b: int) -> float:
    """O corte do z para afirmar `pior` ou `melhor` com tamanhos n_a e n_b.

    Vem do teste de misturas (mSPRT) para duas proporções: com
    I = n_a*n_b/(n_a+n_b) e r = I/AMOSTRA_DE_REFERENCIA, afirma-se quando
    z² >= (1+r)/r * (2*ln(1/ALFA) + ln(1+r)). Diferente do 1,96 fixo, o erro de
    todo o teste (e não de uma olhada) fica perto de ALFA mesmo conferindo
    toda hora. Pouca amostra pede z alto; com mais amostra o corte desce um
    pouco e depois sobe devagar."""
    if n_a <= 0 or n_b <= 0:
        return math.inf
    informacao = n_a * n_b / (n_a + n_b)
    r = informacao / AMOSTRA_DE_REFERENCIA
    return math.sqrt((1 + r) / r * (2 * math.log(1 / ALFA) + math.log(1 + r)))


def comparar(base: dict, candidata: dict, *, minimo: int = MIN_AMOSTRA) -> dict:
    """Candidata contra base, em vendas por abordagem. O veredito é
    `inconclusivo` (pouca amostra), `pior`, `melhor` ou `igual`."""
    n_b, n_c = int(base.get("abordagens") or 0), int(candidata.get("abordagens") or 0)
    v_b, v_c = int(base.get("vendas") or 0), int(candidata.get("vendas") or 0)
    z = z_de_duas_proporcoes(v_c, n_c, v_b, n_b)
    if n_b < minimo or n_c < minimo or z is None:
        veredito = "inconclusivo"
    elif z < -z_critico(n_b, n_c):
        veredito = "pior"
    elif z > z_critico(n_b, n_c):
        veredito = "melhor"
    else:
        veredito = "igual"
    return {"veredito": veredito, "z": None if z is None else round(z, 3),
            "base": {"abordagens": n_b, "vendas": v_b}, "candidata": {"abordagens": n_c, "vendas": v_c}}


def percentual_de_teste() -> int:
    """`OTIMIZADOR_PERCENTUAL_TESTE` no ambiente; 0 desliga os testes
    automáticos (a proposta fica esperando a pessoa)."""
    bruto = (os.environ.get("OTIMIZADOR_PERCENTUAL_TESTE") or "").strip()
    try:
        valor = int(bruto) if bruto else PERCENTUAL_PADRAO
    except ValueError:
        valor = PERCENTUAL_PADRAO
    return max(0, min(PERCENTUAL_MAXIMO, valor))


# ------------------------------------------------- qual versão atende

def _teste_em_andamento(papel: str) -> ExperimentoEstrategia | None:
    return (
        ExperimentoEstrategia.objects.filter(papel=papel, estado=X.EM_TESTE)
        .select_related("base", "candidata").first()
    )


def chave_da_oportunidade(trabalho: TrabalhoComercial) -> str:
    quem = trabalho.oportunidade_id or trabalho.contato_id or trabalho.chave_da_conversa or f"trabalho:{trabalho.pk}"
    return f"{trabalho.site_id}:{quem}"


def _versao_ja_usada(experimento: ExperimentoEstrategia, trabalho: TrabalhoComercial) -> EstrategiaComercial | None:
    """Se a oportunidade já foi atendida por uma das duas versões durante o
    teste, ela continua nessa — mesmo que o identificador dela tenha
    aparecido só agora (a ficha chega depois do evento)."""
    quem = Q()
    for campo in ("oportunidade_id", "contato_id", "chave_da_conversa"):
        valor = getattr(trabalho, campo)
        if valor:
            quem |= Q(**{f"trabalho__{campo}": valor})
    if not quem:
        return None
    anterior = (
        DecisaoComercial.objects.filter(quem, papel=experimento.papel, trabalho__site_id=trabalho.site_id,
                                        estrategia_id__in=[experimento.base_id, experimento.candidata_id],
                                        criada_em__gte=experimento.iniciado_em)
        .exclude(trabalho_id=trabalho.pk)
        .select_related("estrategia").order_by("criada_em", "id").first()
    )
    return anterior.estrategia if anterior else None


def escolher_para(trabalho: TrabalhoComercial) -> EstrategiaComercial:
    """A versão que atende este trabalho. Sem teste rodando no papel, é a do
    ar. Trabalho de teste (lead de teste) nunca entra na divisão: ficaria
    fora dos totais."""
    ativa = papeis.estrategia_ativa(trabalho.papel)
    if trabalho.teste or trabalho.papel not in PAPEIS_OTIMIZAVEIS:
        return ativa
    experimento = _teste_em_andamento(trabalho.papel)
    if experimento is None or experimento.base_id != ativa.pk:
        return ativa
    ja = _versao_ja_usada(experimento, trabalho)
    if ja is not None:
        return ja
    return escolher_versao(experimento.base, experimento.candidata, experimento.pk, experimento.percentual,
                           chave_da_oportunidade(trabalho))


# ------------------------------------------------- medir


def _texto(valor, limite: int = 120) -> str:
    if isinstance(valor, dict):
        valor = valor.get("slug") or valor.get("nome") or valor.get("name") or valor.get("id") or ""
    return str(valor or "").strip()[:limite]


def _dimensoes(trabalho: TrabalhoComercial) -> dict:
    entrada = trabalho.entrada or {}
    utm = entrada.get("utm") if isinstance(entrada.get("utm"), dict) else {}
    return {
        "quiz": _texto(entrada.get("quiz")) or "(sem quiz)",
        "campanha": _texto(entrada.get("campanha")) or _texto(utm.get("utm_campaign")) or "(sem campanha)",
        "oferta": _texto(entrada.get("oferta_ref")) or "(sem oferta)",
    }


def _linha_vazia(versao: int) -> dict:
    return {"versao": versao, "abordagens": 0, "respostas": 0, "vendas": 0, "custo_usd": Decimal("0")}


def _fechar(linha: dict) -> dict:
    return {**linha, "custo_usd": str(linha["custo_usd"])}


def numeros(papel: str = P.ABORDAGEM, desde: datetime | None = None) -> dict:
    """Abordagens (ou atendimentos), respostas, vendas e custo por versão da
    estratégia do papel, e o mesmo por quiz, campanha e oferta. `desde`
    limita às mensagens enviadas a partir daquele momento."""
    tipos = TIPOS_DO_PAPEL.get(papel, (T.ABORDAR,))
    envios = (
        DecisaoComercial.objects.filter(
            ferramenta="enviar_mensagem",
            resultado=DecisaoComercial.Resultado.FEITO,
            trabalho__tipo__in=tipos,
            trabalho__teste=False,
        )
        .filter(saida__ja_feito__isnull=True)  # a repetição ("ja_feito") não conta como mensagem nova
        .select_related("trabalho")
        .order_by("criada_em", "id")
    )
    if desde is not None:
        envios = envios.filter(criada_em__gte=desde)
    vendas_por_oportunidade: dict[str, list] = {}
    vendas_por_pedido: dict[str, list] = {}
    for oportunidade, pedido, quando in EventoComercial.objects.filter(nome="pagamento.aprovado").values_list(
            "oportunidade_ref", "pedido_id", "recebido_em"):
        if oportunidade:
            vendas_por_oportunidade.setdefault(oportunidade, []).append(quando)
        if pedido:
            vendas_por_pedido.setdefault(pedido, []).append(quando)
    respondeu_em: dict[tuple[str, str], datetime] = {}
    if papel == P.ABORDAGEM:
        for contato, conversa, quando in TrabalhoComercial.objects.filter(
                tipo=T.ATENDER_MENSAGEM, teste=False).values_list("contato_id", "conversa_id", "criado_em"):
            chave = ("contato", contato) if contato else ("conversa", conversa or "-")
            if chave not in respondeu_em or quando > respondeu_em[chave]:
                respondeu_em[chave] = quando

    por_versao: dict[int, dict] = {}
    por_dimensao: dict[str, dict[str, dict[int, dict]]] = {nome: {} for nome, _ in DIMENSOES}
    vistas: set[tuple[int, str]] = set()
    for envio in envios:
        trabalho = envio.trabalho
        chave = trabalho.oportunidade_id or trabalho.chave_da_conversa
        versao = envio.versao_estrategia or 0
        if (versao, chave) in vistas:
            continue
        vistas.add((versao, chave))
        vendeu = any(q >= envio.criada_em for q in vendas_por_oportunidade.get(trabalho.oportunidade_id, ())) or any(
            q >= envio.criada_em for q in vendas_por_pedido.get(trabalho.pedido_id, ()))
        chave_resposta = ("contato", trabalho.contato_id) if trabalho.contato_id else (
            "conversa", trabalho.conversa_id or "-")
        respondeu = papel == P.ABORDAGEM and respondeu_em.get(chave_resposta, envio.criada_em) > envio.criada_em
        alvos = [por_versao.setdefault(versao, _linha_vazia(versao))]
        for nome, dimensao in DIMENSOES:
            valor = _dimensoes(trabalho)[dimensao]
            alvos.append(por_dimensao[nome].setdefault(valor, {}).setdefault(versao, _linha_vazia(versao)))
        for linha in alvos:
            linha["abordagens"] += 1
            linha["respostas"] += int(respondeu)
            linha["vendas"] += int(vendeu)
            linha["custo_usd"] += trabalho.custo_usd or 0
    custo_total = TrabalhoComercial.objects.filter(teste=False).aggregate(s=Sum("custo_usd"))["s"] or 0
    resultado = {
        "papel": papel,
        "versoes": [_fechar(linha) for _, linha in sorted(por_versao.items())],
        "custo_total_usd": str(custo_total),
        "min_amostra": MIN_AMOSTRA,
    }
    for nome, _ in DIMENSOES:
        resultado[nome] = {
            valor: [_fechar(linha) for _, linha in sorted(linhas.items())]
            for valor, linhas in sorted(por_dimensao[nome].items())
        }
    return resultado


def _linha_da_versao(dados: dict, versao: int) -> dict:
    return next((linha for linha in dados["versoes"] if linha["versao"] == versao),
                {"versao": versao, "abordagens": 0, "respostas": 0, "vendas": 0, "custo_usd": "0"})


def _maior_amostra(dados: dict) -> int:
    return max((linha["abordagens"] for linha in dados["versoes"]), default=0)


# ------------------------------------------------- testar e decidir


def iniciar_teste(papel: str, instrucoes: str, *, motivo: str, evidencias: dict | None = None,
                  criada_por: str = "agente:resultados",
                  percentual: int | None = None) -> tuple[EstrategiaComercial, ExperimentoEstrategia | None]:
    """Guarda a versão nova e, se o percentual de teste for maior que zero,
    coloca-a para atender uma fatia. A versão do ar não muda."""
    base = papeis.estrategia_ativa(papel)
    proposta = papeis.propor_versao(
        papel, instrucoes, criada_por=criada_por, origem="otimizador", motivo=motivo, evidencias=evidencias)
    fatia = percentual_de_teste() if percentual is None else max(0, min(PERCENTUAL_MAXIMO, percentual))
    if fatia <= 0 or papel not in PAPEIS_OTIMIZAVEIS:
        return proposta, None
    try:
        with transaction.atomic():
            experimento = ExperimentoEstrategia.objects.create(
                papel=papel, base=base, candidata=proposta, percentual=fatia, motivo=motivo[:4000])
    except IntegrityError:
        return proposta, None  # já há um teste neste papel: a proposta espera
    proposta.historico = [*proposta.historico, papeis._marca(
        "em teste", criada_por, f"atende {fatia}% das oportunidades, contra a v{base.versao}")]
    proposta.save(update_fields=["historico"])
    return proposta, experimento


def _fechar_teste(experimento: ExperimentoEstrategia, estado: str, texto: str, quem: str = "otimizador") -> None:
    candidata = EstrategiaComercial.objects.get(pk=experimento.candidata_id)
    if not candidata.ativa:
        candidata.situacao = EstrategiaComercial.Situacao.ARQUIVADA
        candidata.desativada_em = timezone.now()
        candidata.historico = [*candidata.historico, papeis._marca("saiu do teste", quem, texto)]
        candidata.save(update_fields=["situacao", "desativada_em", "historico"])
    experimento.estado = estado
    experimento.conclusao = texto[:4000]
    experimento.encerrado_em = timezone.now()
    experimento.save(update_fields=["estado", "conclusao", "encerrado_em", "comparativo"])


def encerrar(experimento: ExperimentoEstrategia, quem: str, motivo: str = "") -> bool:
    """A pessoa encerra o teste: a candidata sai e a versão do ar segue sozinha."""
    if experimento.estado != X.EM_TESTE:
        return False
    _fechar_teste(experimento, X.ENCERRADA, f"Encerrado por {quem[:100]}. {motivo}".strip(), quem)
    return True


def _frase(comparacao: dict, base: EstrategiaComercial, candidata: EstrategiaComercial) -> str:
    b, c = comparacao["base"], comparacao["candidata"]
    return (f"A v{candidata.versao} vendeu {c['vendas']} em {c['abordagens']} oportunidade(s) e a "
            f"v{base.versao} vendeu {b['vendas']} em {b['abordagens']} no mesmo período (z={comparacao['z']})")


def avaliar(experimento: ExperimentoEstrategia, agora: datetime | None = None) -> dict:
    """Confere um teste em andamento e, se der para concluir, conclui."""
    agora = agora or timezone.now()
    base, candidata = experimento.base, experimento.candidata
    saida = {"papel": experimento.papel, "base": base.versao, "candidata": candidata.versao}
    if papeis.estrategia_ativa(experimento.papel).pk != base.pk:
        _fechar_teste(experimento, X.ENCERRADA,
                      f"A versão no ar mudou durante o teste (a v{base.versao} já não é a do ar); a comparação "
                      "deixou de valer.")
        return {**saida, "desfecho": "encerrado", "motivo": experimento.conclusao}
    dados = numeros(experimento.papel, desde=experimento.iniciado_em)
    comparacao = comparar(_linha_da_versao(dados, base.versao), _linha_da_versao(dados, candidata.versao))
    experimento.comparativo = {
        **comparacao, "avaliado_em": agora.isoformat(),
        **{nome: dados[nome] for nome, _ in DIMENSOES},
    }
    veredito = comparacao["veredito"]
    saida["comparacao"] = {k: comparacao[k] for k in ("veredito", "z", "base", "candidata")}
    if veredito == "pior":
        texto = (_frase(comparacao, base, candidata) + f"; piorou com amostra suficiente. Todo o tráfego voltou "
                 f"para a v{base.versao}.")
        _fechar_teste(experimento, X.REVERTIDA, texto)
        return {**saida, "desfecho": "voltou", "motivo": texto}
    if veredito == "melhor":
        texto = _frase(comparacao, base, candidata) + f"; melhorou com amostra suficiente. A v{candidata.versao} passou a ser a do ar."
        experimento.estado = X.PROMOVIDA
        experimento.conclusao = texto[:4000]
        experimento.encerrado_em = agora
        experimento.save(update_fields=["estado", "conclusao", "encerrado_em", "comparativo"])
        papeis.ativar(candidata, "otimizador", texto)
        return {**saida, "desfecho": "promovida", "motivo": texto}
    if agora - experimento.iniciado_em >= DURACAO_MAXIMA:
        texto = (f"Sem diferença que se possa afirmar em {DURACAO_MAXIMA.days} dias ("
                 + (_frase(comparacao, base, candidata) if comparacao["z"] is not None else "sem amostra para comparar")
                 + f"). Fica a v{base.versao}.")
        _fechar_teste(experimento, X.ENCERRADA, texto)
        return {**saida, "desfecho": "encerrado", "motivo": texto}
    experimento.save(update_fields=["comparativo"])
    return {**saida, "desfecho": "continua"}


def volta_se_piorou(papel: str) -> dict | None:
    """A versão do ar (posta por pessoa ou promovida por um teste) contra a
    anterior: se vendeu claramente menos com amostra nas duas, a anterior
    volta. Quando veio de um teste, compara só o período do teste."""
    ativa = papeis.estrategia_ativa(papel)
    anterior = ativa.anterior
    if anterior is None or anterior.pk == ativa.pk:
        return None
    if anterior.versao > ativa.versao:
        # A do ar é uma versão MAIS VELHA que a "anterior": alguém voltou
        # (a pessoa, ou o próprio otimizador). A escolha dessa volta fica.
        return None
    promovido = ExperimentoEstrategia.objects.filter(papel=papel, candidata=ativa, estado=X.PROMOVIDA).first()
    dados = numeros(papel, desde=promovido.iniciado_em if promovido else None)
    comparacao = comparar(_linha_da_versao(dados, anterior.versao), _linha_da_versao(dados, ativa.versao))
    if comparacao["veredito"] != "pior":
        return None
    motivo = (_frase(comparacao, anterior, ativa) + f"; vendeu menos com amostra suficiente. A v{anterior.versao} voltou.")
    papeis.voltar_a_anterior(papel, "otimizador", motivo)
    return {"papel": papel, "voltou_de": ativa.versao, "voltou_para": anterior.versao,
            "z": comparacao["z"], "motivo": motivo}


# ------------------------------------------------- o trabalho de hora em hora


def _resumido(dados: dict) -> dict:
    """O pedido ao modelo não leva a lista inteira de quizzes, campanhas e
    ofertas: só as que têm mais abordagens."""
    saida = {k: v for k, v in dados.items() if k not in {nome for nome, _ in DIMENSOES}}
    for nome, _ in DIMENSOES:
        grupos = sorted(dados[nome].items(), key=lambda kv: -sum(linha["abordagens"] for linha in kv[1]))
        saida[nome] = dict(grupos[:MAX_VALORES_NO_PEDIDO])
    return saida


def _sem_custo(por_papel) -> dict:
    """O custo total muda a cada trabalho (a própria análise custa): não conta
    como novidade."""
    return {papel: {k: v for k, v in (dados or {}).items() if k != "custo_total_usd"}
            for papel, dados in (por_papel or {}).items()}


def analisar(trabalho: TrabalhoComercial) -> None:
    from .coordenador import conversar, terminar

    por_papel = {papel: numeros(papel) for papel in PAPEIS_OTIMIZAVEIS}
    trabalho.resultado = {**(trabalho.resultado or {}), "numeros": por_papel[P.ABORDAGEM],
                          "papeis": por_papel}
    desfechos = [avaliar(e) for e in ExperimentoEstrategia.objects.filter(estado=X.EM_TESTE)
                 .select_related("base", "candidata")]
    voltas = [v for v in (volta_se_piorou(papel) for papel in PAPEIS_OTIMIZAVEIS) if v]
    if desfechos:
        trabalho.resultado["experimentos"] = desfechos
    if voltas:
        trabalho.resultado["voltou"] = voltas[0]
        trabalho.resultado["voltas"] = voltas
    mudancas = [d for d in desfechos if d["desfecho"] != "continua"]
    if mudancas or voltas:
        # Algo mudou nesta hora (voltou, foi promovida ou o teste acabou): o modelo espera os números
        # da situação nova em vez de reagir já a uma amostra que ainda é da situação antiga.
        desfechos_voltou = [d for d in mudancas if d["desfecho"] == "voltou"] + voltas
        trabalho.resultado["conclusao"] = (
            "voltou" if desfechos_voltou else "promovida" if any(d["desfecho"] == "promovida" for d in mudancas)
            else "encerrado")
        terminar(trabalho, E.CONCLUIDO, resumo=" ".join(
            [d["motivo"] for d in mudancas] + [v["motivo"] for v in voltas])[:4000])
        return
    em_teste = set(ExperimentoEstrategia.objects.filter(estado=X.EM_TESTE).values_list("papel", flat=True))
    livres = [papel for papel in PAPEIS_OTIMIZAVEIS if papel not in em_teste
              and _linha_da_versao(por_papel[papel], papeis.estrategia_ativa(papel).versao)["abordagens"] >= MIN_AMOSTRA]
    maior = max(_maior_amostra(dados) for dados in por_papel.values())
    if not livres:
        if em_teste:
            trabalho.resultado["conclusao"] = "em_teste"
            terminar(trabalho, E.CONCLUIDO, resumo="Teste de estratégia em andamento; o modelo não foi chamado.")
        elif maior < MIN_AMOSTRA:
            trabalho.resultado["conclusao"] = "inconclusivo"
            terminar(trabalho, E.CONCLUIDO, resumo=(
                f"Inconclusivo: a maior amostra tem {maior} abordagem(ns); são precisas {MIN_AMOSTRA}. "
                "O modelo não foi chamado."))
        else:
            trabalho.resultado["conclusao"] = "manter"
            terminar(trabalho, E.CONCLUIDO, resumo=(
                "Nenhuma versão do ar tem amostra própria suficiente; o modelo não foi chamado."))
        return
    ultima = (
        TrabalhoComercial.objects.filter(tipo=T.ANALISAR_RESULTADOS, estado=E.CONCLUIDO)
        .exclude(pk=trabalho.pk).order_by("-terminado_em").first()
    )
    if ultima is not None and _sem_custo((ultima.resultado or {}).get("papeis")) \
            == _sem_custo(json.loads(json.dumps(por_papel))):
        trabalho.resultado["conclusao"] = "sem_novidade"
        terminar(trabalho, E.CONCLUIDO, resumo="Sem novidade desde a última análise; o modelo não foi chamado.")
        return
    ativas = {papel: papeis.estrategia_ativa(papel) for papel in (P.ANALISTA, *PAPEIS_OTIMIZAVEIS)}
    pedido = (
        "Números consolidados por versão da estratégia (só vendas confirmadas pelo provedor, só depois da "
        "mensagem; registros de teste fora). Cada papel traz o total por versão e a divisão por quiz, "
        "campanha e oferta:\n"
        + json.dumps({papel: _resumido(por_papel[papel]) for papel in livres}, ensure_ascii=False)
        + f"\nVersões ativas: {json.dumps({p: a.versao for p, a in ativas.items()})}.\n"
        + "Você pode propor UMA nova versão das instruções de um destes papéis: " + ", ".join(livres) + ".\n"
        + "\n".join(f"Instruções atuais de {papel}:\n{ativas[papel].instrucoes}" for papel in livres)
    )
    final = conversar(trabalho, pedido, forte=True)
    trabalho.resultado["decisao"] = final
    trabalho.resultado["conclusao"] = final.get("conclusao") or "manter"
    proposta = experimento = None
    papel = final.get("papel")
    texto = (final.get("instrucoes_propostas") or "").strip()
    if final.get("conclusao") == "proposta" and texto:
        if papel not in livres:
            trabalho.resultado["conclusao"] = "manter"
            trabalho.resultado["proposta_recusada"] = (
                f"O papel {papel or '—'} não pode receber proposta agora (sem resultado próprio medido, ou já "
                "em teste).")
        elif texto == ativas[papel].instrucoes.strip():
            trabalho.resultado["conclusao"] = "manter"
        else:
            proposta, experimento = iniciar_teste(
                papel, texto, motivo=str(final.get("motivo") or "")[:4000],
                evidencias={"numeros": _resumido(por_papel[papel]), "evidencias": final.get("evidencias") or []})
            trabalho.resultado["proposta"] = {"papel": proposta.papel, "versao": proposta.versao, "id": proposta.pk,
                                              "em_teste": bool(experimento),
                                              "percentual": experimento.percentual if experimento else 0}
    if proposta:
        resumo = (f"Proposta a v{proposta.versao} de {proposta.get_papel_display()}"
                  + (f", em teste com {experimento.percentual}% das oportunidades." if experimento
                     else "; espera a pessoa pôr no ar."))
    else:
        resumo = f"Conclusão: {trabalho.resultado['conclusao']}."
    terminar(trabalho, E.CONCLUIDO, resumo=resumo)


# ------------------------------------------------- para a tela


def relatorio() -> dict:
    """O que a página dos agentes mostra: por papel, a versão do ar, os
    números por versão e o teste em andamento (ou o último que terminou)."""
    saida = {}
    for papel in PAPEIS_OTIMIZAVEIS:
        ativa = papeis.estrategia_ativa(papel)
        dados = numeros(papel)
        teste = _teste_em_andamento(papel)
        ultimo = None if teste else ExperimentoEstrategia.objects.filter(papel=papel).select_related(
            "base", "candidata").first()
        saida[papel] = {"no_ar": ativa.versao, "numeros": dados, "teste": teste, "ultimo_teste": ultimo,
                        "amostra_minima": MIN_AMOSTRA}
    return saida
