"""Consulta e configuração da satisfação, separada das oportunidades de venda."""

import json
import copy
from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.db import DatabaseError
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from .clients import CatalogoClient
from .nps_client import NPSClient


FATOS_OPCOES = {
    "reclamacao": ("Reclamação", "Em aberto", "Resolvida", "Só opinião ou barreira pessoal", "Nenhuma"),
    "continuidade": ("Continuidade", "Fica", "Em dúvida", "Sai", "Concluiu"),
    "boca_a_boca": ("Boca a boca", "A favor", "Contra", "Dos dois jeitos", "Nenhum"),
    "ponto_curso": ("Ponto do curso", "nenhuma", "recente", "antiga", "todas"),
}
PONTO_CURSO_LEGENDAS = {
    "nenhuma": "Não assistiu a nenhuma aula", "recente": "Viu aula no último mês",
    "antiga": "Viu aula, mas faz mais de um mês", "todas": "Concluiu todas as aulas",
}


def _leitura_tela(chave, valor):
    rotulos = {"satisfacao": "Satisfação", "reclamacao": "Reclamação", "continuidade": "Continuidade",
               "boca_a_boca": "Boca a boca", "ponto_curso": "Aulas vistas"}
    traduzir = lambda dado: PONTO_CURSO_LEGENDAS.get(dado, dado) if chave == "ponto_curso" else dado
    origem = valor.get("fonte")
    if isinstance(origem, dict):
        fonte = " · ".join(parte for parte in (origem.get("fonte"), origem.get("referencia")) if parte)
    else:
        fonte = origem or ""
    return {"nome": rotulos.get(chave, chave), "valor": traduzir(valor.get("valor") or "Sem valor"),
            "valor_declarado": traduzir(valor.get("valor_declarado")) if valor.get("valor_declarado") is not None else "",
            "estado": valor.get("estado", "declarada"), "fonte": fonte}


def _evidencias_tela(evidencias):
    registros = evidencias.get("registros_locais", {}) if isinstance(evidencias, dict) else {}
    rotulos = (("aulas_concluidas", "Aulas concluídas neste site"),
               ("entregas", "Entregas neste site"), ("comentarios", "Comentários neste site"),
               ("ultima_entrega", "Última entrega neste site"))
    return [{"rotulo": rotulo, "valor": registros.get(chave) if registros.get(chave) is not None else "Não disponível"}
            for chave, rotulo in rotulos] if isinstance(registros, dict) else []


def _pergunta_esclarecimento(pergunta):
    return {"id": pergunta.get("id"), "texto": pergunta.get("texto") or pergunta.get("id"),
            "multipla": pergunta.get("tipo") == "multipla", "opcoes": pergunta.get("opcoes") or [],
            "texto_livre": pergunta.get("tipo") in ("texto", "nota")}


def _texto(valor, limite=128):
    return valor.strip()[:limite] if isinstance(valor, str) else ""


def _site(request):
    informado = _texto(request.GET.get("site_id"), 100)
    if informado:
        return informado
    site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
    return str(site.get("id", "")) if isinstance(site, dict) else ""


def _linhas_legiveis(avaliacao):
    prontas = avaliacao.get("respostas_legiveis")
    if isinstance(prontas, list):
        return [
            {"pergunta": _texto(item.get("pergunta") or item.get("texto"), 500),
             "resposta": item.get("resposta") or item.get("valor") or "Não respondido"}
            for item in prontas if isinstance(item, dict)
        ]
    if isinstance(prontas, dict):
        return [{"pergunta": chave, "resposta": valor} for chave, valor in prontas.items()]
    documento = avaliacao.get("config_documento") or avaliacao.get("config_snapshot") or {}
    perguntas = documento.get("perguntas", {}) if isinstance(documento, dict) else {}
    respostas = avaliacao.get("respostas", {})
    if not isinstance(respostas, dict):
        return []
    linhas = []
    for chave, valor in respostas.items():
        pergunta = perguntas.get(chave, {}) if isinstance(perguntas, dict) else {}
        opcoes = pergunta.get("opcoes", []) if isinstance(pergunta, dict) else []
        legenda = next((o.get("texto") for o in opcoes if isinstance(o, dict) and o.get("valor") == valor), None)
        linhas.append({"pergunta": pergunta.get("texto", chave) if isinstance(pergunta, dict) else chave,
                       "resposta": legenda or valor})
    return linhas


def preparar_avaliacoes(historico):
    acoes = {"exibida": "Pergunta exibida", "respondida": "Resposta enviada", "voltar": "Voltou à pergunta", "ramo_abandonado": "Caminho anterior abandonado", "concluida": "Avaliação concluída"}
    for avaliacao in historico.get("avaliacoes", []):
        if isinstance(avaliacao, dict):
            curso = avaliacao.get("curso") or avaliacao.get("produto")
            avaliacao["curso_nome"] = (
                curso.get("nome") or curso.get("name") or "Curso não identificado"
                if isinstance(curso, dict) else str(curso or "Curso não identificado")
            )
            aluno = avaliacao.get("aluno") or {}
            avaliacao["aluno_nome"] = (aluno.get("nome") or aluno.get("email") or "Aluno") if isinstance(aluno, dict) else "Aluno"
            avaliacao["respostas_tela"] = _linhas_legiveis(avaliacao)
            documento = avaliacao.get("config_documento") or {}
            avaliacao["roteiro_revisado"] = isinstance(documento, dict) and documento.get("roteiro") == "revisado"
            perguntas = documento.get("perguntas", {}) if isinstance(documento, dict) else {}
            situacoes = documento.get("situacoes", {}) if isinstance(documento, dict) else {}
            respostas = avaliacao.get("respostas", {})
            marcadas = set()
            if isinstance(respostas, dict):
                resposta_situacoes = respostas.get("A3") or respostas.get("R3") or []
                if isinstance(resposta_situacoes, dict):
                    resposta_situacoes = resposta_situacoes.get("valor") or []
                if isinstance(resposta_situacoes, list):
                    marcadas.update(str(item) for item in resposta_situacoes)
            avaliacao["outras_situacoes"] = [
                {"id": item.get("id"), "texto": item.get("texto")}
                for lista in situacoes.values() if isinstance(lista, list)
                for item in lista if isinstance(item, dict) and item.get("id") in marcadas
                and ("outra" in str(item.get("id", "")).lower() or str(item.get("texto", "")).lower().startswith("outra"))
            ] if isinstance(situacoes, dict) else []
            avaliacao["perguntas_a_esclarecer"] = []
            if isinstance(respostas, dict) and isinstance(perguntas, dict):
                for chave, resposta in respostas.items():
                    valor = resposta.get("valor") if isinstance(resposta, dict) else resposta
                    if valor != "__nao_entendi__":
                        continue
                    pergunta = perguntas.get(chave, {})
                    if not isinstance(pergunta, dict):
                        continue
                    opcoes = pergunta.get("opcoes", [])
                    if chave == "A3" and isinstance(situacoes, dict):
                        opcoes = [{"valor": item.get("id"), "texto": item.get("texto")}
                                  for lista in situacoes.values() if isinstance(lista, list)
                                  for item in lista if isinstance(item, dict)]
                    elif chave == "R4" and isinstance(situacoes, dict):
                        opcoes = [{"valor": item.get("id"), "texto": item.get("texto")}
                                  for lista in situacoes.values() if isinstance(lista, list)
                                  for item in lista if isinstance(item, dict) and item.get("id") in marcadas
                                  and item.get("tipo") == "escola"]
                    avaliacao["perguntas_a_esclarecer"].append({
                        "id": chave, "texto": pergunta.get("texto", chave),
                        "multipla": pergunta.get("tipo") == "multipla", "opcoes": opcoes,
                        "texto_livre": pergunta.get("tipo") in ("texto", "nota"),
                    })
            registros = avaliacao.get("respostas_registro") or []
            avaliacao["registros_tela"] = []
            for registro in registros if isinstance(registros, list) else []:
                if not isinstance(registro, dict):
                    continue
                chave = registro.get("pergunta_id")
                pergunta = perguntas.get(chave, {}) if isinstance(perguntas, dict) else {}
                opcoes = pergunta.get("opcoes", []) if isinstance(pergunta, dict) else []
                valor = registro.get("valor")
                resposta = next((opcao.get("texto") for opcao in opcoes if isinstance(opcao, dict) and opcao.get("valor") == valor), valor)
                avaliacao["registros_tela"].append({
                    "quando": registro.get("registrado_em"),
                    "pergunta": pergunta.get("texto", chave) if isinstance(pergunta, dict) else chave,
                    "resposta": resposta,
                    "editada": registro.get("valor_anterior") is not None,
                })
            qualidade = avaliacao.get("qualidade") or {}
            evidencias = qualidade.get("evidencias", {}) if isinstance(qualidade, dict) else {}
            registros_locais = evidencias.get("registros_locais", {}) if isinstance(evidencias, dict) else {}
            avaliacao["evidencias_tela"] = _evidencias_tela(evidencias)
            avaliacao["evidencias_observacao"] = evidencias.get("observacao", "") if isinstance(evidencias, dict) else ""
            avaliacao["eventos_tela"] = []
            for evento in qualidade.get("eventos", []) if isinstance(qualidade, dict) else []:
                if not isinstance(evento, dict):
                    continue
                chave = evento.get("pergunta_id")
                pergunta = perguntas.get(chave, {}) if isinstance(perguntas, dict) else {}
                avaliacao["eventos_tela"].append({
                    "quando": evento.get("registrado_em"),
                    "acao": acoes.get(evento.get("acao"), evento.get("acao")),
                    "pergunta": pergunta.get("texto") if isinstance(pergunta, dict) else "",
                })
            avaliacao["tempos_tela"] = []
            for tempo in qualidade.get("tempos_perguntas", []) if isinstance(qualidade, dict) else []:
                if not isinstance(tempo, dict):
                    continue
                chave = tempo.get("pergunta_id")
                pergunta = perguntas.get(chave, {}) if isinstance(perguntas, dict) else {}
                avaliacao["tempos_tela"].append({
                    "pergunta": pergunta.get("texto", chave) if isinstance(pergunta, dict) else chave,
                    "segundos": tempo.get("duracao_segundos"),
                    "quando": tempo.get("respondida_em"),
                })
            resultado_original = avaliacao.get("resultado") or {}
            resultado = avaliacao.get("resultado_atual") or resultado_original
            if not resultado and type(respostas.get("R12")) is int:
                resultado = {"nps": respostas["R12"], "pessoa_respondente": "aluno_pagante"}
            avaliacao["resultado_exibido"] = resultado
            avaliacao["retrato_original"] = resultado_original.get("retrato") if isinstance(resultado_original, dict) else ""
            if isinstance(resultado, dict):
                avaliacao["retrato_tela"] = resultado.get("retrato") or resultado.get("classificacao") or "A conferir"
                respondente = resultado.get("pessoa_respondente") or avaliacao.get("pessoa_respondente")
                avaliacao["respondente_tela"] = {
                    "aluno": "Aluno", "responsavel": "Responsável", "aluno_pagante": "Aluno que pagou o curso",
                }.get(respondente, "Não informado")
                avaliacao["nps_disponivel"] = respondente in ("responsavel", "aluno_pagante") and type(resultado.get("nps")) is int
                leituras = resultado.get("leituras") or {}
                avaliacao["leituras_tela"] = [
                    _leitura_tela(chave, valor)
                    for chave, valor in leituras.items() if isinstance(valor, dict)
                ] if isinstance(leituras, dict) else []
                sinais = resultado.get("sinais") or []
                avaliacao["sinais_tela"] = [
                    {"motivo": sinal.get("motivo") or sinal.get("codigo") or "Sinal a conferir",
                     "tipo": sinal.get("tipo") or sinal.get("estado") or ""}
                    for sinal in sinais if isinstance(sinal, dict)
                ] if isinstance(sinais, list) else []
            else:
                avaliacao["retrato_tela"] = "A conferir"
                avaliacao["respondente_tela"] = "Não informado"
                avaliacao["leituras_tela"] = []
                avaliacao["sinais_tela"] = []
            motivos = resultado.get("motivos") if isinstance(resultado, dict) else None
            avaliacao["motivos_tela"] = (
                [str(item) for item in motivos] if isinstance(motivos, list)
                else [f"{k}: {v}" for k, v in motivos.items()] if isinstance(motivos, dict)
                else [motivos] if isinstance(motivos, str) and motivos else []
            )
    return historico


def anexar_progresso_manual(historico, site_id, email_consultado=""):
    """Anexa só registros manuais que identificam o mesmo site, aluno e produto."""
    from .acompanhamento_modelo import RegistroAcompanhamentoAluno

    for avaliacao in historico.get("avaliacoes", []):
        avaliacao["evidencias_externas_tela"] = []
        aluno = avaliacao.get("aluno") or {}
        produto = avaliacao.get("produto") or {}
        matricula = avaliacao.get("matricula") or {}
        email = (aluno.get("email") if isinstance(aluno, dict) else "") or email_consultado
        product_id = ((produto.get("id") if isinstance(produto, dict) else "") or
                      (matricula.get("product_id") if isinstance(matricula, dict) else ""))
        if not (site_id and email and product_id):
            continue
        try:
            registros = RegistroAcompanhamentoAluno.objects.filter(
                site_id=site_id, email__iexact=email, product_id=str(product_id),
            ).exclude(fonte="").exclude(progresso_externo="").order_by("-criado_em")[:20]
            avaliacao["evidencias_externas_tela"] = [
                {"progresso": registro.progresso_externo, "fonte": registro.fonte,
                 "criado_em": registro.criado_em}
                for registro in registros
            ]
        except DatabaseError:
            # A pesquisa remota continua legível mesmo se esta tabela local não responder.
            continue
    return historico


def _editor_do_documento(documento):
    perguntas = documento.get("perguntas", {}) if isinstance(documento, dict) else {}
    caminhos = documento.get("caminhos", {}) if isinstance(documento, dict) else {}
    situacoes = documento.get("situacoes", {}) if isinstance(documento, dict) else {}
    itens = []
    for chave, pergunta in perguntas.items():
        if not isinstance(pergunta, dict):
            continue
        variantes = pergunta.get("variantes", {})
        itens.append({"id": chave, "texto": pergunta.get("texto", ""), "opcoes": [
            {"valor": opcao.get("valor"), "texto": opcao.get("texto", "")}
            for opcao in pergunta.get("opcoes", []) if isinstance(opcao, dict)
        ], "variantes": [
            {"id": etapa, "rotulo": {
                "nenhuma": "Ainda não começou", "recente": "Viu aula recentemente",
                "antiga": "Viu aula há mais tempo", "todas": "Concluiu as aulas",
                "__nao_entendi__": "Não entendeu a pergunta inicial",
            }.get(etapa, etapa), "texto": variante.get("texto", ""), "opcoes": [
                {"valor": opcao.get("valor"), "texto": opcao.get("texto", "")}
                for opcao in variante.get("opcoes", []) if isinstance(opcao, dict)
            ]}
            for etapa, variante in variantes.items() if isinstance(variante, dict)
        ] if isinstance(variantes, dict) else []})
    faixas = []
    titulos = {"9-10": "Notas 9 e 10", "7-8": "Notas 7 e 8", "0-6": "Notas de 0 a 6"}
    for faixa in ("9-10", "7-8", "0-6"):
        sequencia = caminhos.get(faixa, [])
        if not isinstance(sequencia, list):
            continue
        posicoes = []
        for indice, selecionada in enumerate(sequencia):
            posicoes.append({"indice": indice, "fixa": indice == len(sequencia) - 1 or (faixa == "9-10" and indice == 0), "selecionada": perguntas.get(selecionada, {}).get("texto", selecionada), "id_selecionada": selecionada, "opcoes": [
                {"id": chave, "texto": perguntas.get(chave, {}).get("texto", chave), "selecionada": chave == selecionada}
                for chave in sequencia if isinstance(perguntas.get(chave), dict)
            ]})
        faixas.append({"id": faixa, "titulo": titulos[faixa], "posicoes": posicoes})
    situacoes_editor = [
        {"grupo": grupo, "itens": [
            {"id": item.get("id"), "texto": item.get("texto", ""), "tipo": item.get("tipo", ""), "bloco": item.get("bloco", "")}
            for item in lista if isinstance(item, dict) and item.get("id")
        ]}
        for grupo, lista in situacoes.items() if isinstance(lista, list)
    ] if isinstance(situacoes, dict) else []
    settings_editor = []
    for bloco in ("textos",):
        valores = documento.get(bloco, {}) if isinstance(documento, dict) else {}
        if isinstance(valores, dict):
            for chave, valor in valores.items():
                if isinstance(valor, (str, bool, int, float)) and not any(
                    termo in chave.lower() for termo in ("peso", "classificacao", "calculo", "id")
                ):
                    settings_editor.append({"bloco": bloco, "chave": chave, "valor": valor,
                                            "booleano": isinstance(valor, bool)})
    return itens, faixas, situacoes_editor, settings_editor


def _atendimento_selecionado(historico, identificador):
    if not identificador:
        return {}
    for atendimento in historico.get("atendimentos", []):
        if atendimento.get("id") != identificador:
            continue
        selecionado = dict(atendimento)
        prazo = parse_datetime(atendimento.get("prazo") or "")
        selecionado["prazo_form"] = (
            timezone.localtime(prazo).strftime("%Y-%m-%dT%H:%M")
            if prazo and timezone.is_aware(prazo) else ""
        )
        return selecionado
    return {}


@require_GET
def crm_satisfacao(request):
    site_id = _site(request)
    aluno_id = _texto(request.GET.get("aluno_id"))
    email = _texto(request.GET.get("email"), 254).lower()
    cliente = NPSClient()
    estado_config, config = (cliente.configuracao(site_id) if site_id else ("sem-site", None))
    estado_historico, historico = (
        cliente.historico(site_id, aluno_id=aluno_id, email=email)
        if site_id and (aluno_id or email) else ("sem-aluno", None)
    )
    if estado_historico == cliente.OK and (
        not isinstance(historico.get("avaliacoes"), list)
        or not isinstance(historico.get("atendimentos"), list)
    ):
        estado_historico, historico = cliente.INDISPONIVEL, None
    if historico:
        historico = preparar_avaliacoes(historico)
        historico = anexar_progresso_manual(historico, site_id, email)
    documento = config.get("documento") if estado_config == cliente.OK else None
    if historico and not aluno_id:
        aluno_id = _texto(historico.get("aluno_id"))
        if not aluno_id and historico.get("avaliacoes"):
            aluno_id = _texto(historico["avaliacoes"][0].get("aluno_id"))
    config_json = json.dumps(documento, ensure_ascii=False, indent=2) if isinstance(documento, dict) else ""
    perguntas_editor, caminhos_editor, situacoes_editor, settings_editor = _editor_do_documento(documento)
    atendimento_edicao = _atendimento_selecionado(historico or {}, _texto(request.GET.get("atendimento"), 100))
    if historico:
        for atendimento in historico.get("atendimentos", []):
            params = {"site_id": site_id, "atendimento": atendimento.get("id", "")}
            if email:
                params["email"] = email
            elif aluno_id:
                params["aluno_id"] = aluno_id
            atendimento["editar_url"] = reverse("crm_satisfacao") + "?" + urlencode(params)
    revisao_selecionada = None
    revisao_estado = "sem-selecao"
    revisao_dados = {}
    revisao_id = _texto(request.GET.get("revisao"), 100)
    if historico and revisao_id:
        revisao_selecionada = next((a for a in historico.get("avaliacoes", []) if a.get("id") == revisao_id), None)
        if revisao_selecionada and revisao_selecionada.get("roteiro_revisado"):
            revisao_estado, revisao_dados = cliente.revisao(site_id, revisao_selecionada.get("aluno_id", ""), revisao_id)
            if revisao_estado != cliente.OK or not isinstance(revisao_dados, dict):
                revisao_dados = {}
            else:
                revisao_dados["fatos_tela"] = _evidencias_tela(revisao_dados.get("fatos_disponiveis"))
                revisao_dados["fatos_observacao"] = (revisao_dados.get("fatos_disponiveis") or {}).get("observacao", "")
                ja_listadas = {item["id"] for item in revisao_selecionada["perguntas_a_esclarecer"]}
                for pergunta in revisao_dados.get("perguntas_pendentes_revisao", []):
                    if isinstance(pergunta, dict) and pergunta.get("id") and pergunta["id"] not in ja_listadas:
                        revisao_selecionada["perguntas_a_esclarecer"].append(_pergunta_esclarecimento(pergunta))
                        ja_listadas.add(pergunta["id"])
        else:
            revisao_estado = "invalida"
    if historico:
        for avaliacao in historico.get("avaliacoes", []):
            if not avaliacao.get("roteiro_revisado"):
                continue
            params = {"site_id": site_id, "revisao": avaliacao["id"]}
            if email:
                params["email"] = email
            elif aluno_id:
                params["aluno_id"] = aluno_id
            avaliacao["revisao_url"] = reverse("crm_satisfacao") + "?" + urlencode(params) + "#revisao"
    return render(request, "admin/crm_satisfacao.html", {
        "admin": request.admin,
        "site_id": site_id,
        "aluno_id": aluno_id,
        "email": email,
        "estado_config": estado_config,
        "config": config or {},
        "config_json": config_json,
        "perguntas_editor": perguntas_editor,
        "caminhos_editor": caminhos_editor,
        "situacoes_editor": situacoes_editor,
        "settings_editor": settings_editor,
        "atendimento_edicao": atendimento_edicao,
        "revisao_selecionada": revisao_selecionada,
        "revisao_estado": revisao_estado,
        "revisao_dados": revisao_dados,
        "fatos_editor": [
            {"id": chave, "titulo": valores[0], "opcoes": [
                {"valor": valor, "rotulo": {
                    "nenhuma": "Não assistiu a nenhuma aula", "recente": "Viu aula no último mês",
                    "antiga": "Viu aula, mas faz mais de um mês", "todas": "Concluiu todas as aulas",
                }.get(valor, valor)} for valor in valores[1:]
            ]}
            for chave, valores in FATOS_OPCOES.items()
        ],
        "estado_historico": estado_historico,
        "historico": historico or {},
        "salvo": request.GET.get("salvo") == "1",
        "atendido": request.GET.get("atendido") == "1",
    })


@require_POST
def crm_satisfacao_config_salvar(request):
    site_id = _texto(request.POST.get("site_id"), 100)
    if not site_id:
        return _erro(request, "Informe o site antes de salvar a configuração.")
    modo = request.POST.get("modo")
    texto = ""
    if modo == "perguntas":
        estado_config, config = NPSClient().configuracao(site_id)
        if estado_config != NPSClient.OK or not isinstance(config.get("documento"), dict):
            return _erro(request, "Não foi possível ler a configuração atual para salvar as perguntas.", site_id=site_id)
        documento = copy.deepcopy(config["documento"])
        for chave, pergunta in documento.get("perguntas", {}).items():
            campo = "pergunta__" + chave
            texto = _texto(request.POST.get(campo), 1000)
            if not texto:
                return _erro(request, "Todas as perguntas precisam de texto.", site_id=site_id)
            pergunta["texto"] = texto
            for opcao in pergunta.get("opcoes", []):
                campo_opcao = "opcao__" + chave + "__" + str(opcao["valor"])
                texto_opcao = _texto(request.POST.get(campo_opcao), 500)
                if not texto_opcao:
                    return _erro(request, "Todas as alternativas precisam de texto.", site_id=site_id)
                opcao["texto"] = texto_opcao
            for etapa, variante in pergunta.get("variantes", {}).items():
                if not isinstance(variante, dict):
                    continue
                texto_variante = _texto(request.POST.get(f"pergunta_variante__{chave}__{etapa}"), 1000)
                if not texto_variante:
                    return _erro(request, "Todas as versões da pergunta precisam de texto.", site_id=site_id)
                variante["texto"] = texto_variante
                for opcao in variante.get("opcoes", []):
                    campo_opcao = f"opcao_variante__{chave}__{etapa}__{opcao['valor']}"
                    texto_opcao = _texto(request.POST.get(campo_opcao), 500)
                    if not texto_opcao:
                        return _erro(request, "Todas as alternativas precisam de texto.", site_id=site_id)
                    opcao["texto"] = texto_opcao
        for faixa, sequencia in documento.get("caminhos", {}).items():
            novas = [_texto(request.POST.get(f"caminho__{faixa}__{indice}"), 100) for indice in range(len(sequencia))]
            if len(novas) != len(sequencia) or set(novas) != set(sequencia):
                return _erro(request, "Escolha cada pergunta uma vez em cada caminho.", site_id=site_id)
            if novas[-1] != "comentario" or (faixa == "9-10" and novas[0] != "repercussao"):
                return _erro(request, "Mantenha o comentário no final e a repercussão no início das notas 9 e 10.", site_id=site_id)
            documento["caminhos"][faixa] = novas
        for grupo, lista in documento.get("situacoes", {}).items():
            if not isinstance(lista, list):
                continue
            for situacao in lista:
                if not isinstance(situacao, dict) or not situacao.get("id"):
                    continue
                campo = "situacao__" + grupo + "__" + str(situacao["id"])
                texto_situacao = _texto(request.POST.get(campo), 500)
                if not texto_situacao:
                    return _erro(request, "Todas as situações precisam de texto.", site_id=site_id)
                situacao["texto"] = texto_situacao
        for bloco in ("textos",):
            valores = documento.get(bloco, {})
            if not isinstance(valores, dict):
                continue
            for chave, valor in valores.items():
                if not isinstance(valor, (str, bool, int, float)) or any(
                    termo in chave.lower() for termo in ("peso", "classificacao", "calculo", "id")
                ):
                    continue
                campo = "ajuste__" + bloco + "__" + chave
                novo = request.POST.get(campo)
                if isinstance(valor, bool):
                    valores[chave] = novo == "sim"
                elif isinstance(valor, str):
                    valores[chave] = _texto(novo, 1000)
                elif isinstance(valor, int):
                    try:
                        valores[chave] = int(novo)
                    except (ValueError, TypeError):
                        return _erro(request, "Um ajuste numérico está inválido.", site_id=site_id)
                elif isinstance(valor, float):
                    try:
                        valores[chave] = float(novo)
                    except (ValueError, TypeError):
                        return _erro(request, "Um ajuste numérico está inválido.", site_id=site_id)
    else:
        texto = request.POST.get("documento") or ""
        try:
            documento = json.loads(texto)
        except (ValueError, TypeError):
            return _erro(request, "O documento precisa ser JSON válido.", site_id=site_id, documento=texto)
        if not isinstance(documento, dict):
            return _erro(request, "O documento precisa ser um objeto JSON.", site_id=site_id, documento=texto)
    estado, detalhe = NPSClient().salvar_configuracao(site_id, documento)
    if estado != NPSClient.OK:
        return _erro(request, detalhe if isinstance(detalhe, str) else "Não foi possível salvar a configuração.", site_id=site_id, documento=texto)
    return HttpResponseRedirect(reverse("crm_satisfacao") + "?" + urlencode({"site_id": site_id, "salvo": "1"}))


@require_POST
def crm_satisfacao_atendimento_salvar(request):
    site_id = _texto(request.POST.get("site_id"), 100)
    aluno_id = _texto(request.POST.get("aluno_id"))
    if not site_id or not aluno_id:
        return _erro(request, "Informe o site e o ID do aluno para registrar o atendimento.")
    corpo = {
        "site_id": site_id,
        "aluno_id": aluno_id,
        "tentativa_id": _texto(request.POST.get("tentativa_id"), 100) or None,
        "responsavel": _texto(request.POST.get("responsavel"), 120),
        "proximo_passo": _texto(request.POST.get("proximo_passo"), 2000),
        "prazo": None,
        "solucao": _texto(request.POST.get("solucao"), 2000),
        "status": _texto(request.POST.get("status"), 40),
    }
    prazo_texto = _texto(request.POST.get("prazo"), 40)
    if prazo_texto:
        prazo = parse_datetime(prazo_texto)
        if prazo is None:
            return _erro(request, "O prazo informado não é uma data válida.", site_id=site_id, aluno_id=aluno_id)
        if timezone.is_naive(prazo):
            prazo = timezone.make_aware(prazo, timezone.get_default_timezone())
        corpo["prazo"] = prazo.isoformat()
    atendimento_id = _texto(request.POST.get("atendimento_id"), 100)
    if atendimento_id:
        corpo["id"] = atendimento_id
    estado, detalhe = NPSClient().salvar_atendimento(corpo)
    if estado != NPSClient.OK:
        return _erro(request, detalhe if isinstance(detalhe, str) else "Não foi possível registrar o atendimento.", site_id=site_id, aluno_id=aluno_id)
    email = _texto(request.POST.get("email"), 254).lower()
    params = {"site_id": site_id, "atendido": "1"}
    params["email" if email else "aluno_id"] = email or aluno_id
    return HttpResponseRedirect(reverse("crm_satisfacao") + "?" + urlencode(params))


@require_POST
def crm_satisfacao_revisao_salvar(request):
    site_id = _texto(request.POST.get("site_id"), 100)
    aluno_id = _texto(request.POST.get("aluno_id"))
    tentativa_id = _texto(request.POST.get("tentativa_id"), 100)
    situacao_id = _texto(request.POST.get("situacao_id"), 100)
    tipo = _texto(request.POST.get("tipo"), 30)
    if not all((site_id, aluno_id, tentativa_id, situacao_id)) or tipo not in ("escola", "opiniao", "pessoal", "nenhum", "fato", "esclarecimento"):
        return _erro(request, "Escolha a situação e o tipo da revisão.", site_id=site_id, aluno_id=aluno_id)
    fonte = _texto(request.POST.get("fonte"), 300)
    referencia = _texto(request.POST.get("referencia"), 1000)
    corpo = {"site_id": site_id, "aluno_id": aluno_id, "tentativa_id": tentativa_id,
             "situacao_id": situacao_id, "tipo": tipo}
    if tipo == "fato":
        valor = _texto(request.POST.get("valor"), 100)
        if situacao_id not in FATOS_OPCOES or valor not in FATOS_OPCOES[situacao_id][1:] or not fonte or not referencia:
            return _erro(request, "Informe a leitura, o fato, a fonte e a referência da prova.", site_id=site_id, aluno_id=aluno_id)
        corpo["prova"] = {"fonte": fonte, "referencia": referencia, "valor": valor}
    elif tipo == "esclarecimento":
        if not referencia:
            return _erro(request, "Informe a referência da conversa em que a pergunta foi esclarecida.", site_id=site_id, aluno_id=aluno_id)
        valores = request.POST.getlist("valor")
        valor = valores if situacao_id in ("A3", "R11") else (valores[0] if valores else "")
        if not valor:
            return _erro(request, "Informe a resposta esclarecida na conversa.", site_id=site_id, aluno_id=aluno_id)
        corpo["prova"] = {"fonte": "entrevista", "referencia": referencia, "valor": valor}
        complemento = _texto(request.POST.get("complemento"), 3000)
        if complemento:
            corpo["prova"]["complemento"] = complemento
    else:
        if bool(fonte) != bool(referencia):
            return _erro(request, "Para registrar um fato, informe a fonte e a referência juntas.", site_id=site_id, aluno_id=aluno_id)
        if fonte and referencia:
            corpo["prova"] = {"fonte": fonte, "referencia": referencia}
    estado, detalhe = NPSClient().salvar_revisao(corpo)
    if estado != NPSClient.OK:
        return _erro(request, detalhe if isinstance(detalhe, str) else "Não foi possível salvar a revisão.", site_id=site_id, aluno_id=aluno_id)
    email = _texto(request.POST.get("email"), 254).lower()
    params = {"site_id": site_id, "revisao": tentativa_id, "revisado": "1"}
    params["email" if email else "aluno_id"] = email or aluno_id
    return HttpResponseRedirect(reverse("crm_satisfacao") + "?" + urlencode(params) + "#revisao")


def _erro(request, mensagem, *, site_id="", aluno_id="", documento=""):
    return render(request, "admin/crm_satisfacao.html", {
        "admin": request.admin, "site_id": site_id, "aluno_id": aluno_id,
        "erro": mensagem, "config_json": documento,
        "estado_config": "indisponivel", "estado_historico": "indisponivel",
        "config": {}, "historico": {},
    }, status=400)
