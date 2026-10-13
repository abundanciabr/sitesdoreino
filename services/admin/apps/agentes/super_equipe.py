"""Especialistas técnicos do site, sobre a fila e o orçamento existentes."""

from __future__ import annotations

import json
import hashlib
import math
import re
import statistics
import uuid

import httpx
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum, Q
from django.utils import timezone

from apps.core.clients import CatalogoClient
from apps.core.governanca import orientacao_dos_robos
from apps.core.paginas import SLUG_DA_PAGINA
from apps.core.painel_negocio import montar_painel_negocio
from apps.core.resultado_do_experimento import calcular
from apps.core.models import Tarefa

from . import modelo, trabalhos
from .models import (ChamadaDeFerramenta, Consumo, Entrega, Execucao,
                     MelhoriaSuperEquipe, RoboPessoal, RotinaSuperEquipe)
from .super_equipe_perfis import PERFIS, VERSAO_PERFIL, contexto_do_perfil, instrucoes, rotulo
from . import super_equipe_avaliacao as avaliacao

ESPECIALIDADES = {
    "arquitetura": "Arquitetura e ligação entre as partes do site",
    "desempenho": "Desempenho das páginas e do painel",
    "confiabilidade": "Confiabilidade, disponibilidade e execução",
    "seguranca": "Segurança, acesso e dados pessoais",
    "robos_ia": "Robôs de IA, respostas e custos",
}
REFERENCIA = "https://meshcraft.top/admin/documentos/sistema-e-equipe-especialista-do-projeto"
MAX_PEDIDO = 4000


def _host_proprio(host: str) -> str:
    host = (host or "").split(":")[0].strip().lower().rstrip(".")
    if host != "meshcraft.top" and not host.endswith(".meshcraft.top"):
        raise ValueError("O domínio informado não é deste site.")
    return host


def _sem_dados_pessoais(texto: str) -> str:
    texto = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[e-mail omitido]", texto)
    texto = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}\b", "[CPF omitido]", texto)
    texto = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[número omitido]", texto)
    return texto


def pedir_trabalho(membro, *, site_id: str, host: str, pedido: str,
                  especialidades: list[str], chave: str,
                  tarefa_id: int | None = None) -> tuple[Execucao, bool]:
    """Põe uma análise da organização na fila, com o robô pessoal só como suporte."""
    host = _host_proprio(host)
    pedido = (pedido or "").strip()
    if not pedido or len(pedido) > MAX_PEDIDO:
        raise ValueError("Escreva um pedido de até 4.000 caracteres.")
    recebidas = set(dict.fromkeys(especialidades))
    validas = set(ESPECIALIDADES) | set(PERFIS)
    if not recebidas or any(e not in validas for e in recebidas):
        raise ValueError("Escolha ao menos uma especialidade válida.")
    # Ordem estável: a avaliação independente do trabalho fica por último;
    # códigos antigos continuam legíveis sem reescrever autoria histórica.
    escolhidas = [codigo for codigo in PERFIS if codigo in recebidas]
    escolhidas.extend(codigo for codigo in ESPECIALIDADES if codigo in recebidas)
    if not site_id:
        raise ValueError("Não foi possível identificar o site.")
    if tarefa_id and not Tarefa.objects.filter(pk=tarefa_id).exists():
        raise ValueError("Essa tarefa não existe no painel da equipe.")
    marca = "super-equipe-" + ((chave or str(uuid.uuid4())).strip()[:100])
    existente = Execucao.objects.filter(chave_de_repeticao=marca).first()
    if existente:
        return existente, False
    robo = trabalhos.robo_de(membro) if membro else RoboPessoal.objects.filter(
        situacao=RoboPessoal.Situacao.ATIVO).order_by("id").first()
    if not robo:
        raise ValueError("Nenhum robô da equipe está disponível para a fila.")
    try:
        with transaction.atomic():
            execucao = Execucao.objects.create(
                robo=robo, tipo=Execucao.Tipo.SUPER_EQUIPE, origem="super_equipe",
                pedido_por_membro_id=membro.pk if membro else None,
                pedido_por=membro.nome if membro else "Administração",
                tarefa_id=tarefa_id, pedido=pedido,
                chave_de_repeticao=marca, etapa_atual="Na fila do servidor",
                estado={"site_id": str(site_id), "host": host,
                        "especialidades": escolhidas, "resultados": {},
                        "fluxo_avaliacao": avaliacao.VERSAO if any(c in PERFIS for c in escolhidas) else "",
                        "versoes_perfil": {codigo: VERSAO_PERFIL for codigo in escolhidas if codigo in PERFIS}},
            )
            trabalhos.registrar(execucao, "Pedido da equipe técnica recebido no site.")
            from .super_equipe_checklist import acompanhar
            transaction.on_commit(lambda: acompanhar(execucao))
            transaction.on_commit(__import__("apps.agentes.executor", fromlist=["acordar"]).acordar)
            return execucao, True
    except IntegrityError:
        return Execucao.objects.get(chave_de_repeticao=marca), False


def _painel(site_id: str) -> dict:
    negocio = montar_painel_negocio(site_id)["negocio"]
    # A fonte traz tarefas e responsáveis; para os especialistas bastam totais.
    objetivos = negocio.pop("objetivos", [])
    negocio["trabalho"] = {
        "objetivos": sum(o["id"] is not None for o in objetivos),
        "tarefas_abertas": sum(o["abertas"] for o in objetivos),
        "bloqueadas": sum(o["bloqueadas"] for o in objetivos),
        "atrasadas": sum(o["atrasadas"] for o in objetivos),
    }
    return negocio


def _fluxo_entregas(site_id: str, host: str = "meshcraft.top") -> dict:
    """Tempos do próprio fluxo técnico, com amostra e ausências explícitas."""
    base = Execucao.objects.filter(tipo=Execucao.Tipo.SUPER_EQUIPE,
                                   estado__site_id=str(site_id))
    estados = list(base.values("situacao").annotate(total=Count("id")).order_by("situacao"))
    amostra = list(base.order_by("-id").values_list(
        "criada_em", "iniciada_em", "terminada_em", "situacao")[:200])
    espera, execucao = [], []
    for criada, iniciada, terminada, situacao in amostra:
        if iniciada and criada:
            espera.append(max(0, (iniciada - criada).total_seconds()))
        if iniciada and terminada and situacao in (Execucao.Situacao.CONCLUIDA,
                                                    Execucao.Situacao.AGUARDANDO_INFORMACAO,
                                                    Execucao.Situacao.FALHOU):
            execucao.append(max(0, (terminada - iniciada).total_seconds()))

    def resumo(valores):
        valores = sorted(valores)
        return {"amostra": len(valores),
                "mediana_segundos": round(statistics.median(valores), 3) if valores else None,
                "p95_segundos": round(valores[math.ceil(.95 * len(valores)) - 1], 3)
                if len(valores) >= 20 else None}

    from .super_equipe_entregas import consultar
    from django.utils.dateparse import parse_datetime
    fotografias = consultar(RotinaSuperEquipe.objects.filter(host=host, site_id=str(site_id)).first())
    codigo = []
    for item in fotografias['itens']:
        fluxo = item.get('fluxo') or {}
        recebida, iniciada, concluida = [parse_datetime(fluxo.get(k) or '') for k in (
            'recebida_em', 'iniciada_em', 'concluida_em')]
        def intervalo(a, b):
            return round((b-a).total_seconds(), 3) if a and b and b >= a else None
        codigo.append({'id': item['id'], 'candidata': item['candidata'],
            'coletada_em': item.get('coletada_em'), 'atualidade': item['atualidade'],
            'confirmacao_atual': item['confirmacao_atual'],
            'espera_recebimento_inicio_segundos': intervalo(recebida, iniciada),
            'duracao_inicio_conclusao_segundos': intervalo(iniciada, concluida),
            'duracao_recebimento_conclusao_segundos': intervalo(recebida, concluida),
            **fluxo})
    return {"estado": "medido", "universo": "trabalhos da Super Equipe deste site",
            "total": base.count(), "estados": estados, "janela": "200 trabalhos mais recentes",
            "espera_pedido_inicio": resumo(espera), "duracao_inicio_fim": resumo(execucao),
            "entregas_codigo": {"amostra": len(codigo), "itens": codigo,
                "limite": "Última consulta importada por ID, inclusive entregas não concluídas. Cobertura limitada às importadas; datas ausentes não são zero. Tempo entre recebimento/início não é espera pura: pode incluir integração e tentativas. Tempos de etapas podem se sobrepor, não somar. Conclusão técnica não mede jornada comercial."},
            "limite": "Trabalhos administrativos e entregas importadas são populações separadas; processamento ativo não inferido de duração. Datas ausentes não entram como zero."}


def _entregas(host: str) -> dict:
    from .super_equipe_entregas import consultar
    rotina = RotinaSuperEquipe.objects.filter(host=host).first()
    melhorias = MelhoriaSuperEquipe.objects.filter(rotina__host=host)
    estados = list(melhorias.values("situacao").annotate(total=Count("id")).order_by("situacao"))
    recentes = []
    for item in melhorias.order_by("-observada_em", "-id")[:20]:
        recentes.append({"id": item.pk, "situacao": item.situacao,
                         "entrega": item.entrega or None, "trabalho_id": item.trabalho_id,
                         "observada_em": item.observada_em.isoformat() if item.observada_em else None,
                         "resolvida_em": item.resolvida_em.isoformat() if item.resolvida_em else None})
    rotina_automatica = ("indisponivel" if rotina is None else "ativa" if rotina.ativa else "pausada")
    return {"estado": "medido", "rotina_automatica": rotina_automatica,
            "canal_operacional": consultar(rotina),
            "melhorias_por_estado": estados, "ultimas_20": recentes,
            "limite": "Estado administrativo do site; uma entrega registrada não comprova efeito posterior."}


def _integridade(site_id: str) -> dict:
    trabalhos = Execucao.objects.filter(tipo=Execucao.Tipo.SUPER_EQUIPE,
                                        estado__site_id=str(site_id))
    ids = list(trabalhos.values_list("id", flat=True)[:500])
    chamadas = ChamadaDeFerramenta.objects.filter(execucao_id__in=ids)
    consumos = Consumo.objects.filter(execucao_id__in=ids)
    return {"estado": "medido", "trabalhos_amostrados": len(ids),
            "trabalhos_com_chave_de_repeticao": trabalhos.exclude(chave_de_repeticao__isnull=True).exclude(chave_de_repeticao="").count(),
            "chamadas_registradas": chamadas.count(),
            "chamadas_por_estado": list(chamadas.values("situacao").annotate(total=Count("id")).order_by("situacao")),
            "consumos_com_resposta_desconhecida": consumos.filter(desconhecido=True).count(),
            "entregas_salvas": Entrega.objects.filter(execucao_id__in=ids).count(),
            "limite": "Contagens dos trabalhos técnicos; não medem unicidade de efeitos comerciais. Chamadas de ferramenta não incluem a coleta determinística das fontes pelo servidor. Lista vazia com chamadas_registradas=0 é zero registrado nessa amostra, não fonte indisponível."}


def _contratos_tecnicos(site_id: str) -> dict:
    """Contrato instalado e estados da fila própria, sem conteúdo dos pedidos."""
    base = Execucao.objects.filter(tipo=Execucao.Tipo.SUPER_EQUIPE,
                                   estado__site_id=str(site_id)).order_by("-id")[:20]
    itens = []
    for e in base:
        itens.append({"id": e.pk, "url": f"https://meshcraft.top/admin/super-equipe/{e.pk}/",
            "situacao": e.situacao, "tentativas": e.tentativas,
            "tem_chave": bool(e.chave_de_repeticao),
            "posse_vencida": bool(e.ocupada_ate and e.ocupada_ate < timezone.now()
                                  and e.situacao == Execucao.Situacao.EXECUTANDO),
            "versoes_perfil": {c: v for c, v in (e.estado.get("versoes_perfil") or {}).items()
                                if c in PERFIS and isinstance(v, str)},
            "respostas_salvas": len(e.estado.get("resultados") or {}),
            "entregas": e.entregas.count()})
    return {"estado": "medido", "origem": "Modelos instalados e fila técnica deste site",
        "contratos": {
            "execucao": {"estados": list(Execucao.Situacao.values),
                "chave_unica": Execucao._meta.get_field("chave_de_repeticao").unique,
                "posse": "ocupada_ate; tentativa e trabalhador conferidos ao persistir"},
            "ferramenta": {"unicidade": [list(c.fields) for c in ChamadaDeFerramenta._meta.constraints]},
            "consumo": {"incerto": "desconhecido; reserva conservada sem reenvio automático"}},
        "amostra": len(itens), "janela": "20 trabalhos técnicos mais recentes", "itens": itens,
        "limite": "Contrato e estado locais. Não consulta pagamentos, eventos externos, código arbitrário ou confirmações do provedor."}


def _experimentos(site_id: str) -> dict:
    cliente = CatalogoClient()
    situacao, lista = cliente.experimentos_da_pagina(site_id, SLUG_DA_PAGINA)
    if situacao != cliente.OK or not isinstance(lista, list):
        return {"estado": "indisponivel", "motivo": str(situacao)}
    saida = []
    for corpo in lista[:12]:
        if not isinstance(corpo, dict):
            continue
        item = {"id": str(corpo.get("id", ""))[:100],
                "estado_catalogo": str(corpo.get("estado", ""))[:40]}
        try:
            conta = calcular(site_id, corpo, timezone.localdate())
            item.update(estado=conta.get("estado"), veredito=conta.get("veredito"),
                        motivo=conta.get("motivo"), dias_corridos=conta.get("dias_corridos"),
                        linhas=conta.get("linhas"), conta=conta.get("conta"))
        except (KeyError, TypeError, ValueError) as erro:
            item.update(estado="indisponivel", motivo=type(erro).__name__)
        saida.append(item)
    return {"estado": "medido", "itens": saida, "total_lido": len(saida)}


def _probes(host: str) -> dict:
    saida = []
    for caminho in ("/", "/robots.txt"):
        url = f"https://{_host_proprio(host)}{caminho}"
        try:
            inicio = timezone.now()
            resposta = httpx.get(url, follow_redirects=False, timeout=12)
            saida.append({"url": url, "estado": "medido", "http": resposta.status_code,
                          "duracao_ms": round((timezone.now() - inicio).total_seconds() * 1000),
                          "bytes": len(resposta.content)})
        except httpx.HTTPError as erro:
            saida.append({"url": url, "estado": "indisponivel", "motivo": type(erro).__name__})
    return {"itens": saida, "limite": "Duas consultas GET pontuais; não provam disponibilidade contínua."}


def coletar_fontes(site_id: str, host: str) -> dict:
    """Fotografia atual compartilhada; cada falha mantém seu estado explícito."""
    fontes = {"consultado_em": timezone.now().isoformat(), "site_id": site_id,
              "referencia_historica": REFERENCIA,
              "referencia_historica_resumo": (
                  "Núcleo técnico: fontes de verdade, fluxos completos e conferência dos limites; "
                  "o documento é referência anterior, não uma medição atual."),
              "trabalhos_anteriores": []}
    anteriores = (Execucao.objects.filter(tipo=Execucao.Tipo.SUPER_EQUIPE,
                    estado__site_id=str(site_id),
                    situacao__in=[Execucao.Situacao.CONCLUIDA,
                                  Execucao.Situacao.AGUARDANDO_INFORMACAO])
                  .prefetch_related("entregas")[:3])
    for anterior in anteriores:
        entrega = anterior.entregas.first()
        fontes["trabalhos_anteriores"].append({
            "id": anterior.pk, "situacao": anterior.situacao,
            "especialidades": anterior.estado.get("especialidades", []),
            "fontes_em": anterior.estado.get("fontes", {}).get("consultado_em"),
            "entrega_id": entrega.pk if entrega else None,
            "entrega_parcial": entrega.parcial if entrega else None,
        })
    from .super_equipe_operacao import coletar, servidor
    from .super_equipe_percurso import coletar as coletar_percurso
    for nome, consulta in (("execucao_operacional", coletar),
                           ("servidor", servidor),
                           ("negocio", lambda: _painel(site_id)),
                           ("percurso_comercial", lambda: coletar_percurso(site_id, host)),
                           ("experimentos", lambda: _experimentos(site_id)),
                           ("robos_ia", lambda: _robos_ia(site_id)),
                           ("fluxo_entregas", lambda: _fluxo_entregas(site_id, host)),
                           ("entregas", lambda: _entregas(host)),
                           ("integridade", lambda: _integridade(site_id)),
                           ("fontes", lambda: _contratos_tecnicos(site_id)),
                           ("paginas_publicas", lambda: _probes(host))):
        try:
            fontes[nome] = consulta()
        except Exception as erro:  # cada porta pode falhar separadamente
            fontes[nome] = {"estado": "indisponivel", "motivo": type(erro).__name__}
    return json.loads(json.dumps(fontes, ensure_ascii=False, default=str))


def _robos_ia(site_id: str) -> dict:
    conexao = modelo.conexao()
    autorizacao = modelo.autorizacao_ativa()
    tecnicos = Execucao.objects.filter(tipo=Execucao.Tipo.SUPER_EQUIPE,
                                       estado__site_id=str(site_id))
    consumos = Consumo.objects.filter(execucao__in=tecnicos)
    totais = consumos.aggregate(custo=Sum("custo_estimado_usd"),
                               uso=Sum("custo_estimado_usd", filter=Q(desconhecido=False)),
                               reserva=Sum("custo_estimado_usd", filter=Q(desconhecido=True)),
                               entrada=Sum("tokens_entrada"), saida=Sum("tokens_saida"))
    return {"estado": "medido", "fonte": "Fila, entregas, consumo e autorização de IA do site",
            "modelo_tecnico": conexao.modelo_forte,
            "trabalhos_tecnicos": tecnicos.count(),
            "concluidos": tecnicos.filter(situacao=Execucao.Situacao.CONCLUIDA).count(),
            "respostas_registradas": consumos.count(),
            "custo_tecnico_registrado_usd": totais["custo"] or 0,
            "uso_com_resposta_registrada_usd": totais["uso"] or 0,
            "reserva_incerta_usd": totais["reserva"] or 0,
            "chamadas_incertas": consumos.filter(desconhecido=True).count(),
            "ultimas_20_chamadas": list(consumos.order_by("-criado_em", "-id").values(
                "execucao_id", "modelo", "desconhecido", "custo_estimado_usd",
                "tokens_entrada", "tokens_saida", "criado_em")[:20]),
            "tokens_entrada": totais["entrada"] or 0, "tokens_saida": totais["saida"] or 0,
            "gasto_mensal_equipe_usd": modelo.gasto_do_mes(autorizacao.pk) if autorizacao else None,
            "teto_mensal_equipe_usd": autorizacao.teto_mensal_usd if autorizacao else None,
            "limite": "Consumo registrado, não auditoria de qualidade ou conformidade das respostas."}


def _pendencias(fontes: dict) -> list[str]:
    pendentes = []
    negocio = fontes.get("negocio", {})
    if negocio.get("estado") == "indisponivel":
        pendentes.append("Painel do negócio não respondeu.")
    for nome in ("financeiro", "alunos", "cursos"):
        if (negocio.get(nome) or {}).get("estado") in ("indisponivel", "sem_dados"):
            pendentes.append(f"{nome.capitalize()}: fonte indisponível ou sem dados.")
    if any(f.get("estado") in ("indisponivel", "sem_dados")
           for f in negocio.get("funis", [])):
        pendentes.append("Pelo menos uma janela do funil está sem dados verificáveis.")
    if fontes.get("experimentos", {}).get("estado") != "medido":
        pendentes.append("Resultados dos experimentos indisponíveis.")
    if fontes.get("robos_ia", {}).get("estado") != "medido":
        pendentes.append("Robôs de IA: fonte indisponível ou não consultada.")
    for pagina in fontes.get("paginas_publicas", {}).get("itens", []):
        status = pagina.get("http")
        if (pagina.get("estado") != "medido" or not isinstance(status, int)
                or not 200 <= status < 300):
            # As sondas não seguem redirecionamento: 3xx também não comprova
            # que a página solicitada abriu. A URL vem da sonda, não da IA.
            url = pagina.get("url", "Página pública")
            detalhe = f"HTTP {status}" if isinstance(status, int) else "sem resposta verificável"
            pendentes.append(f"{url}: {detalhe}.")
    if not fontes.get("paginas_publicas", {}).get("itens"):
        pendentes.append("As páginas públicas não foram verificadas.")
    operacao = fontes.get("execucao_operacional", {})
    if operacao.get("estado") == "indisponivel":
        pendentes.append("Fila operacional indisponível.")
    for campo, texto in (("posses_vencidas", "Execuções com posse vencida"),
                         ("fila_atrasada", "Trabalhos na fila há mais de 20 minutos"),
                         ("falhas_24h", "Execuções com falha nas últimas 24 horas")):
        if operacao.get(campo, 0):
            pendentes.append(texto + ".")
    servidor = fontes.get("servidor")
    if servidor is not None:
        if servidor.get("estado") != "medido":
            pendentes.append("Medição da VPS indisponível ou desatualizada.")
        else:
            for nome in ("aplicacao", "funil"):
                if servidor.get(nome) != "ativo":
                    pendentes.append(f"Serviço {nome}: atividade não confirmada na VPS.")
            if servidor.get("http_5xx_15m"):
                pendentes.append("VPS: erros HTTP 5xx observados nos últimos 15 minutos.")
            integrador = servidor.get("integrador") or {}
            if integrador.get("repeticoes_identicas"):
                pendentes.append("Integrador: novas combinações de conflitos com entradas idênticas foram observadas.")
            livre, pico = servidor.get("disco_livre_mb"), servidor.get("pico_entre_coletas_mb")
            if livre is not None and pico is not None and livre < pico:
                pendentes.append("Disco: a folga atual é menor que um pico de crescimento já medido entre coletas.")
    return pendentes


def _entrega(execucao: Execucao, *, parcial: bool, pendencias: list[str]) -> Entrega:
    estado = execucao.estado
    blocos = [f"# Equipe de especialistas — trabalho {execucao.pk}", "",
              f"Pedido: {execucao.pedido}", "",
              f"Fontes consultadas em {estado.get('fontes', {}).get('consultado_em', 'não consultadas')}.",
              f"Referência histórica: {REFERENCIA}", "",
              "Operações realizadas: leitura de dados agregados do painel, leitura do catálogo e resultado dos experimentos e duas consultas GET públicas. Nenhum código foi alterado por este trabalho."]
    for codigo in estado["especialidades"]:
        resultado = estado.get("resultados", {}).get(codigo)
        if resultado:
            versao = estado.get("versoes_perfil", {}).get(codigo)
            complemento = f" · perfil v{versao}" if versao else ""
            blocos += ["", f"## {rotulo(codigo, ESPECIALIDADES)}{complemento}", resultado["texto"]]
    if pendencias:
        blocos += ["", "## Limites e pendências", *[f"- {p}" for p in pendencias]]
    sintese = estado.get("sintese_final")
    if sintese:
        blocos += ["", "## Nicole Forsgren · síntese final posterior aos pareceres", sintese["texto"],
                   "", "Síntese do modelo; não é aprovação obrigatória nem comprovação independente de efeito externo."]
    conteudo = "\n".join(blocos)
    entrega = execucao.entregas.filter(tipo="super_equipe").first()
    if entrega:
        entrega.conteudo, entrega.parcial, entrega.pendencias = conteudo, parcial, pendencias
        entrega.versao += 1
        entrega.save()
    else:
        entrega = Entrega.objects.create(
            robo=execucao.robo, execucao=execucao, tarefa_id=execucao.tarefa_id,
            tipo="super_equipe", titulo=f"Equipe de especialistas — trabalho {execucao.pk}",
            conteudo=conteudo, parcial=parcial, pendencias=pendencias)
    return entrega


def executar(execucao: Execucao) -> None:
    from .executor import batimento, guardar_estado, terminar

    estado = execucao.estado
    if "fontes" not in estado or estado.get("fontes_tentativa", 1) != execucao.tentativas:
        batimento(execucao, "Consultando fontes atuais do site", 8)
        if "fontes" in estado:
            estado.setdefault("fontes_anteriores", []).append(estado["fontes"])
        estado["fontes"] = coletar_fontes(estado["site_id"], estado["host"])
        estado["fontes_tentativa"] = execucao.tentativas
        guardar_estado(execucao)
        _entrega(execucao, parcial=True, pendencias=["Análise dos especialistas em andamento."])
    digest_fontes = hashlib.sha256(json.dumps(
        estado["fontes"], sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    conexao = modelo.conexao()
    if execucao.modelo != conexao.modelo_forte:
        Execucao.objects.filter(pk=execucao.pk, trabalhador=execucao.trabalhador).update(
            modelo=conexao.modelo_forte)
        execucao.modelo = conexao.modelo_forte
    etapas = list(estado["especialidades"])
    rastreavel = estado.get("fluxo_avaliacao") == avaliacao.VERSAO
    if rastreavel and "nicole_forsgren" in etapas and len(etapas) > 1:
        etapas.append(avaliacao.SINTESE)
    total = len(etapas)
    for indice, codigo in enumerate(etapas):
        sintese = codigo == avaliacao.SINTESE
        if (estado.get("sintese_final") if sintese else codigo in estado["resultados"]):
            continue
        papel = "nicole_forsgren" if sintese else codigo
        nome = "Nicole · síntese final" if sintese else rotulo(codigo, ESPECIALIDADES)
        batimento(execucao, f"{nome} em análise", 15 + 75 * indice // total)
        # Chamada paga que retornou sem ponto de retomada não é repetida
        # silenciosamente; a reserva/consumo existente permanece visível.
        salvas = len(estado["resultados"]) + bool(estado.get("sintese_final"))
        if Consumo.objects.filter(execucao=execucao).count() > salvas:
            pendencias = ["Uma resposta paga ficou sem resultado salvo após interrupção. Requer conferência antes de retomar."]
            _entrega(execucao, parcial=True, pendencias=pendencias)
            terminar(execucao, Execucao.Situacao.FALHOU, pendencias[0])
            return
        anterior = {c: _sem_dados_pessoais(r["texto"][:1800])
                    for c, r in estado["resultados"].items()
                    if r.get("fontes_digest") == digest_fontes
                    or (not estado.get("fontes_anteriores") and not r.get("fontes_digest"))}
        contexto = contexto_do_perfil(
            papel, _sem_dados_pessoais(execucao.pedido), estado["fontes"], anterior)
        instrucao = instrucoes(papel, ESPECIALIDADES) + "\n\n" + orientacao_dos_robos()
        if rastreavel and (sintese or codigo == "shreya_shankar"):
            contexto["confronto"] = avaliacao.material(estado, digest_fontes, _sem_dados_pessoais)
            instrucao += avaliacao.orientacao(codigo)
        inicio = timezone.now()
        if rastreavel:
            entrada = {"perfil": papel, "etapa": codigo, "fluxo_avaliacao": avaliacao.VERSAO,
                       "modelo": conexao.modelo_forte, "instrucoes_digest": avaliacao.digest(instrucao),
                       "fontes_digest": digest_fontes, "iniciada_em": inicio.isoformat(),
                       "contexto_digest": avaliacao.digest(contexto), "contexto": contexto,
                       "instrucoes": instrucao,
                       "limite": "Leitura determinística de fontes minimizadas; capacidades declaradas não são chamadas de ferramenta. Efeito externo não observado por esta etapa."}
            entradas = estado.setdefault("entradas_avaliacao", {})
            if codigo in entradas:
                estado.setdefault("entradas_avaliacao_anteriores", []).append(entradas[codigo])
            entradas[codigo] = entrada
            guardar_estado(execucao)
        resposta = modelo.responder(
            modelo=conexao.modelo_forte,
            instrucoes=instrucao,
            itens=[{"role": "user", "content": json.dumps(contexto, ensure_ascii=False, default=str)}],
            max_saida=3000, esforco="medium", execucao=execucao,
            robo=execucao.robo, origem="super_equipe")
        if not resposta.completa or not resposta.texto.strip():
            pendencias = [f"{nome}: resposta paga incompleta ou vazia; consumo registrado."]
            _entrega(execucao, parcial=True, pendencias=pendencias)
            terminar(execucao, Execucao.Situacao.FALHOU, pendencias[0])
            return
        resultado = {"texto": _sem_dados_pessoais(resposta.texto.strip()),
                                         "resposta_id": resposta.id,
                                         "consumo_id": resposta.consumo.pk,
                                         "fontes_digest": digest_fontes,
                                         "fontes_consultadas_em": estado["fontes"].get("consultado_em"),
                                         "concluido_em": timezone.now().isoformat()}
        if rastreavel:
            resultado["rastreio"] = {k: v for k, v in entrada.items() if k not in ("contexto", "instrucoes")}
            resultado["rastreio"].update({"consumo_id": resposta.consumo.pk,
                "custo_estimado_usd": str(resposta.consumo.custo_estimado_usd),
                "desconhecido": resposta.consumo.desconhecido,
                "tokens_entrada": resposta.consumo.tokens_entrada,
                "tokens_saida": resposta.consumo.tokens_saida,
                "duracao_segundos": (timezone.now() - inicio).total_seconds()})
        if sintese:
            estado["sintese_final"] = resultado
        else:
            estado["resultados"][codigo] = resultado
        guardar_estado(execucao)
        _entrega(execucao, parcial=True, pendencias=["Outros especialistas ainda trabalham."])
    pendencias = _pendencias(estado["fontes"])
    if estado.get("fontes_anteriores") and any(
            r.get("fontes_digest") != digest_fontes for r in (
                list(estado["resultados"].values()) + ([estado["sintese_final"]] if estado.get("sintese_final") else []))):
        pendencias.append("Respostas anteriores preservadas usam outra fotografia das fontes; não foram regeneradas nem reutilizadas na nova análise.")
    entrega = _entrega(execucao, parcial=bool(pendencias), pendencias=pendencias)
    if pendencias:
        terminar(execucao, Execucao.Situacao.AGUARDANDO_INFORMACAO,
                 "Análise salva com fontes indisponíveis; veja os limites na entrega.",
                 f"Entrega {entrega.pk} parcial")
    else:
        terminar(execucao, Execucao.Situacao.CONCLUIDA,
                 "Especialistas concluíram a análise com as fontes disponíveis.",
                 f"Entrega {entrega.pk} concluída")
