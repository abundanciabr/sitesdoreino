"""Central de Automações WhatsApp do site identificado pelo host."""
from __future__ import annotations

import uuid
from datetime import datetime

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .automacoes_client import AutomacoesClient
from .clients import AlunosClient, CatalogoClient
from .crm_conversas import ConversasClient
from .crm_modelos import _pedir as pedir_modelos
from .sequencias import _site_desta_requisicao


LISTA = "admin/automacoes.html"
DETALHE = "admin/automacao.html"
ACOES = {
    "ativar": "Automação ativada.",
    "fechar_entrada": "Entrada fechada. Quem já entrou continua.",
    "pausar": "Envios pausados.",
    "retomar": "Envios retomados.",
    "encerrar": "Automação encerrada.",
    "retomar_falhas": "Retomada das falhas solicitada. Confira os resultados abaixo.",
}
ESTADOS_PARTICIPANTE = {"andando": "Recebendo", "concluida": "Terminou", "saiu": "Saiu", "cancelada": "Encerrada"}
ESTADOS_ENTREGA = {"pendente": "Aguardando envio", "enviada": "Enviada, entrega não confirmada",
    "aceita_pelo_gateway": "Aceita pelo provedor, entrega não confirmada", "entregue": "Entrega confirmada",
    "lida": "Leitura confirmada", "falhou": "Falhou", "resultado_desconhecido": "Resultado desconhecido",
    "barrada_pela_regua": "Aguardando janela de envio", "barrada_por_preferencia": "Não enviada por preferência",
    "pulada": "Passo pulado"}
ESTADOS_TESTE = {
    "pendente": "Aguardando envio",
    "reservado": "Preparando envio",
    "aceito": "Aceita pelo provedor; entrega ainda não confirmada",
    "enviado": "Enviada; entrega ainda não confirmada",
    "enviada": "Enviada; entrega ainda não confirmada",
    "entregue": "Entrega confirmada",
    "lido": "Leitura confirmada",
    "falhou": "Falhou",
    "desconhecido": "Resultado incerto; confira a conversa antes de repetir",
    "repetida": "Pedido já registrado; confira o estado da mensagem",
}


def _opcoes_publico(site_id):
    """Somente IDs devolvidos por catálogo/alunos; nunca inventa uma turma."""
    opcoes = [{"valor": "todos", "nome": "Todos os contatos elegíveis"},
              {"valor": "alunos", "nome": "Alunos"}, {"valor": "contatos", "nome": "Contatos"}]
    produtos = CatalogoClient().listar_produtos()
    for produto in produtos or []:
        if produto.get("site_id") and str(produto["site_id"]) != str(site_id):
            continue
        if produto.get("id") is not None:
            opcoes.append({"valor": f"curso:{produto['id']}", "nome": "Curso: " + str(produto.get("name") or produto.get("nome") or produto["id"])})
    alunos = AlunosClient().alunos()
    turmas = {}
    for aluno in alunos or []:
        if str(aluno.get("site_id") or site_id) != str(site_id):
            continue
        turma_id = aluno.get("turma_id")
        if turma_id is not None:
            turmas[str(turma_id)] = str(aluno.get("turma_nome") or aluno.get("turma") or turma_id)
    for turma_id, nome in sorted(turmas.items()):
        opcoes.append({"valor": "turma:" + turma_id, "nome": "Turma: " + nome})
    return opcoes


def _modelos_oficiais(site_id):
    dados, _ = pedir_modelos("GET", str(site_id))
    return [m for m in (dados or {}).get("modelos") or []
        if m.get("estado") == "aprovado" and m.get("suportado") and m.get("presente_no_provedor")
        and not m.get("faltando") and not m.get("variaveis")]


def _conversas_para_inscrever(site_id):
    estado, dados = ConversasClient().listar(site_id, canal="whatsapp")
    if estado != "ok":
        return [], False
    return [{"id": str(c["id"]), "nome": c.get("endereco_mascarado") or "Conversa WhatsApp"}
        for c in dados.get("itens") or [] if c.get("id") and c.get("canal") == "whatsapp"
        and not c.get("ambigua") and not c.get("descadastrado")], True


def _inteiro(valor, nome, *, minimo=0):
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ValueError(f"Informe {nome} como número inteiro.") from None
    if numero < minimo:
        raise ValueError(f"Informe {nome} de pelo menos {minimo}.")
    return numero


def _passos_do_formulario(post, modelos_aprovados=()):
    corpos = post.getlist("passo_corpo")
    atrasos = post.getlist("passo_atraso")
    unidades = post.getlist("passo_unidade")
    condicoes = post.getlist("passo_condicao")
    interacoes = post.getlist("passo_interacao")
    modelos_ids = post.getlist("passo_modelo")
    passos = []
    for indice, corpo in enumerate(corpos):
        if not corpo.strip():
            continue
        atraso = _inteiro(atrasos[indice] if indice < len(atrasos) else "", "o intervalo", minimo=0)
        unidade = unidades[indice] if indice < len(unidades) else ""
        if unidade not in ("minutos", "dias"):
            raise ValueError("Escolha minutos ou dias para cada intervalo.")
        passo = {
            "ordem": len(passos) + 1,
            "atraso_segundos": atraso * (60 if unidade == "minutos" else 86400),
            "corpo": corpo.strip(),
            "condicao_slug": condicoes[indice].strip() if indice < len(condicoes) else "",
            "interacao": interacoes[indice].strip() if indice < len(interacoes) else "",
        }
        modelo_id = modelos_ids[indice].strip() if indice < len(modelos_ids) else ""
        if modelo_id:
            aprovado = next((m for m in modelos_aprovados if str(m.get("id")) == modelo_id), None)
            if aprovado is None:
                raise ValueError("O modelo oficial escolhido não está aprovado para uso. Consulte os modelos novamente.")
            passo["modelo_whatsapp"] = {"nome": aprovado["nome"], "idioma": aprovado.get("idioma") or "pt_BR"}
        passos.append(passo)
    if not passos:
        raise ValueError("Escreva pelo menos uma mensagem.")
    return passos


def _campos_da_tela(passos, modelos=()):
    linhas = []
    for passo in passos:
        segundos = int(passo.get("atraso_segundos") or 0)
        if segundos and segundos % 86400 == 0:
            atraso, unidade = segundos // 86400, "dias"
        else:
            atraso, unidade = segundos // 60, "minutos"
        modelo = passo.get("modelo_whatsapp") or {}
        modelo_id = next((str(m.get("id")) for m in modelos
            if m.get("nome") == modelo.get("nome") and m.get("idioma") == modelo.get("idioma")), "")
        linhas.append({**passo, "atraso": atraso, "unidade": unidade, "modelo_id": modelo_id})
    return linhas


def _contexto(request, site, **extra):
    return {"admin": request.admin, "site": site, **extra}


def _desenhar_lista(request, site, *, erro="", recado="", status=200):
    dados = AutomacoesClient().listar(site["id"])
    if dados is None:
        return render(request, LISTA, _contexto(request, site, erro="A mensageria não respondeu. Consulte novamente antes de repetir uma criação."), status=503)
    return render(request, LISTA, _contexto(request, site, **dados, erro=erro, recado=recado), status=status)


def _desenhar_detalhe(request, site, slug, *, erro="", recado="", status=200, formulario=None, configuracao=None, teste=None, versao=None, chave_teste=None, chave_inscricao=None):
    dados = AutomacoesClient().detalhe(site["id"], slug, versao=versao)
    if dados is None:
        return render(request, DETALHE, _contexto(request, site, slug=slug, erro="Não foi possível consultar esta automação. Confira o estado antes de repetir a ação."), status=503)
    modelos = _modelos_oficiais(site["id"])
    passos = formulario if formulario is not None else _campos_da_tela(dados.get("passos") or [], modelos)
    if not passos:
        passos = [{"ordem": 1, "atraso": 0, "unidade": "minutos", "corpo": ""}]
    while len(passos) < 10:
        passos.append({"ordem": len(passos) + 1, "atraso": 0, "unidade": "minutos", "corpo": ""})
    catalogos = AutomacoesClient().listar(site["id"]) or {}
    conversas, conversas_lidas = _conversas_para_inscrever(site["id"])
    dados["participantes"] = [{**p, "estado_visivel": ESTADOS_PARTICIPANTE.get(p.get("estado"), p.get("estado"))} for p in dados.get("participantes") or []]
    dados["entregas"] = [{**e, "resultado_visivel": ESTADOS_ENTREGA.get(e.get("resultado"), e.get("resultado"))} for e in dados.get("entregas") or []]
    dados["testes"] = [{**t, "estado_visivel": ESTADOS_TESTE.get(t.get("estado"), t.get("estado") or "Não informado")}
        for t in dados.get("testes") or []]
    if teste:
        teste = {**teste, "estado_visivel": ESTADOS_TESTE.get(teste.get("estado"), teste.get("estado") or "Não informado")}
    if configuracao:
        dados["automacao"] = {**(dados.get("automacao") or {}), **configuracao}
    opcoes_publico = _opcoes_publico(site["id"])
    publico_atual = (dados.get("automacao") or {}).get("publico")
    if publico_atual and publico_atual not in {o["valor"] for o in opcoes_publico}:
        opcoes_publico.append({"valor": publico_atual, "nome": "Público atual (não disponível para conferir agora)"})
    return render(request, DETALHE, _contexto(request, site, slug=slug, **catalogos, **dados,
        opcoes_publico=opcoes_publico, modelos_oficiais=modelos,
        conversas_inscricao=conversas, conversas_lidas=conversas_lidas,
        passos_form=passos, erro=erro, recado=recado, teste=teste,
        chave_teste=chave_teste or str(uuid.uuid4()), chave_inscricao=chave_inscricao or str(uuid.uuid4())), status=status)


@require_http_methods(["GET", "POST"])
def automacoes(request):
    site = _site_desta_requisicao(request)
    if site is None:
        return render(request, LISTA, {"admin": request.admin, "erro": "Não foi possível identificar o site deste endereço."}, status=503)
    if request.method == "GET":
        return _desenhar_lista(request, site)
    if request.POST.get("acao") != "criar":
        return _desenhar_lista(request, site, erro="Ação desconhecida.", status=400)
    nome = request.POST.get("nome", "").strip()
    objetivo = request.POST.get("objetivo", "").strip()
    if not nome or not objetivo:
        return _desenhar_lista(request, site, erro="Informe o nome e o objetivo da automação.", status=400)
    corpo = {"site_id": site["id"], "nome": nome, "objetivo": objetivo}
    modelo = request.POST.get("modelo", "").strip()
    if modelo:
        corpo["modelo"] = modelo
    situacao, resposta, frase = AutomacoesClient().criar(corpo)
    if situacao != AutomacoesClient.OK:
        return _desenhar_lista(request, site, erro=frase or "Não foi possível criar o rascunho.", status=422)
    slug = resposta.get("slug")
    if not slug:
        return _desenhar_lista(request, site, erro="O motor não confirmou qual rascunho criou. Consulte a lista antes de repetir.", status=502)
    return HttpResponseRedirect(reverse("automacao_whatsapp", args=[slug]))


@require_http_methods(["GET", "POST"])
def automacao(request, slug):
    site = _site_desta_requisicao(request)
    if site is None:
        return render(request, DETALHE, {"admin": request.admin, "erro": "Não foi possível identificar o site deste endereço."}, status=503)
    if request.method == "GET":
        versao = request.GET.get("versao", "").strip()
        try:
            versao = _inteiro(versao, "a versão", minimo=1) if versao else None
        except ValueError as erro:
            return _desenhar_detalhe(request, site, slug, erro=str(erro), status=400)
        return _desenhar_detalhe(request, site, slug, recado=request.GET.get("recado", ""), versao=versao)
    gesto = request.POST.get("acao", "")
    cliente = AutomacoesClient()
    if gesto == "prever":
        configuracao = {campo: request.POST.get(campo, "").strip()
            for campo in ("nome", "objetivo", "gatilho", "publico", "resposta", "roteiro")}
        try:
            passos = _passos_do_formulario(request.POST, _modelos_oficiais(site["id"]))
        except ValueError as erro:
            return _desenhar_detalhe(request, site, slug, erro=str(erro), status=400, configuracao=configuracao)
        return _desenhar_detalhe(request, site, slug, recado="Prévia atualizada com o texto digitado. Nada foi enviado ou salvo.",
            formulario=_campos_da_tela(passos, _modelos_oficiais(site["id"])), configuracao=configuracao)
    if gesto == "salvar":
        configuracao = {campo: request.POST.get(campo, "").strip()
            for campo in ("nome", "objetivo", "gatilho", "publico", "resposta", "roteiro")}
        try:
            versao_base = _inteiro(request.POST.get("versao_base"), "a versão aberta", minimo=0)
            passos = _passos_do_formulario(request.POST, _modelos_oficiais(site["id"]))
        except ValueError as erro:
            # Preserva o que foi digitado mesmo se um intervalo estiver incorreto.
            formulario = []
            for i, corpo in enumerate(request.POST.getlist("passo_corpo")):
                formulario.append({"ordem": i + 1, "corpo": corpo,
                    "atraso": (request.POST.getlist("passo_atraso") + [""] * (i + 1))[i],
                    "unidade": (request.POST.getlist("passo_unidade") + ["minutos"] * (i + 1))[i],
                    "condicao_slug": (request.POST.getlist("passo_condicao") + [""] * (i + 1))[i],
                    "interacao": (request.POST.getlist("passo_interacao") + [""] * (i + 1))[i],
                    "modelo_whatsapp": (request.POST.getlist("passo_modelo") + [""] * (i + 1))[i]})
            return _desenhar_detalhe(request, site, slug, erro=str(erro), status=400, formulario=formulario, configuracao=configuracao)
        corpo = {"site_id": site["id"], "versao_base": versao_base,
            "nome": request.POST.get("nome", "").strip(), "objetivo": request.POST.get("objetivo", "").strip(),
            "gatilho": request.POST.get("gatilho", "").strip(), "publico": request.POST.get("publico", "").strip(),
            "resposta": request.POST.get("resposta", "").strip(), "roteiro": request.POST.get("roteiro", "").strip(),
            "passos": passos}
        if not corpo["nome"] or not corpo["objetivo"]:
            return _desenhar_detalhe(request, site, slug, erro="Informe nome e objetivo.", status=400, formulario=_campos_da_tela(passos), configuracao=configuracao)
        situacao, resposta, frase = cliente.salvar(slug, corpo)
        if situacao != cliente.OK:
            return _desenhar_detalhe(request, site, slug, erro=frase or "Não foi possível salvar. Recarregue para conferir a versão atual.", status=409 if situacao == cliente.DESATUALIZADO else 422, formulario=_campos_da_tela(passos), configuracao=configuracao)
        return HttpResponseRedirect(reverse("automacao_whatsapp", args=[slug]) + "?recado=salva")
    if gesto == "teste":
        conversa_id = request.POST.get("conversa_id", "").strip()
        chave = request.POST.get("chave_idempotencia", "").strip()
        if request.POST.get("autorizado") != "sim" or not conversa_id or not chave:
            return _desenhar_detalhe(request, site, slug, erro="Informe uma conversa existente autorizada e confirme o teste.", status=400, chave_teste=chave)
        corpo = {"site_id": site["id"], "conversa_id": conversa_id, "chave_idempotencia": chave}
        if request.POST.get("versao", "").strip():
            try:
                corpo["versao"] = _inteiro(request.POST["versao"], "a versão do teste", minimo=1)
            except ValueError as erro:
                return _desenhar_detalhe(request, site, slug, erro=str(erro), status=400, chave_teste=chave)
        situacao, resposta, frase = cliente.teste(slug, corpo)
        return _desenhar_detalhe(request, site, slug, teste=resposta if situacao == cliente.OK else None,
            recado="Teste registrado no histórico abaixo; a entrega é confirmada separadamente." if situacao == cliente.OK else "",
            erro="" if situacao == cliente.OK else (frase or "Não foi possível confirmar o teste. Confira o histórico antes de repetir."),
            status=200 if situacao == cliente.OK else 422, chave_teste=chave)
    if gesto == "inscrever":
        atual = cliente.detalhe(site["id"], slug)
        resumo = (atual or {}).get("automacao") or {}
        if resumo.get("gatilho") != "manual" or not resumo.get("ativa") or not resumo.get("entrada_aberta"):
            return _desenhar_detalhe(request, site, slug, erro="A inscrição manual precisa de uma automação manual ativa com entrada aberta.", status=422)
        conversa_id = request.POST.get("conversa_id", "").strip()
        chave = request.POST.get("chave_idempotencia", "").strip()
        conversas, lidas = _conversas_para_inscrever(site["id"])
        if not lidas or conversa_id not in {c["id"] for c in conversas} or not chave:
            return _desenhar_detalhe(request, site, slug, erro="Escolha uma conversa WhatsApp existente desta lista. Consulte novamente se ela não aparecer.", status=400, chave_inscricao=chave)
        corpo = {"site_id": site["id"], "pessoas": [{"destinatario_id": "conversa:" + conversa_id,
            "conversa_id": conversa_id, "contexto": {}}], "chave_idempotencia": chave}
        horario = request.POST.get("agendado_em", "").strip()
        if horario:
            try:
                local = datetime.fromisoformat(horario)
                corpo["agendado_em"] = timezone.make_aware(local, timezone.get_current_timezone()).isoformat()
            except ValueError:
                return _desenhar_detalhe(request, site, slug, erro="Informe uma data e hora válida para iniciar.", status=400, chave_inscricao=chave)
        situacao, resposta, frase = cliente.inscrever(slug, corpo)
        if situacao != cliente.OK:
            return _desenhar_detalhe(request, site, slug, erro=frase or "A inscrição não foi confirmada. Consulte os participantes antes de repetir.", status=422, chave_inscricao=chave)
        inscritos = resposta.get("inscritos") or []
        recusados = resposta.get("recusados") or []
        return _desenhar_detalhe(request, site, slug, recado=f"{len(inscritos)} participante inscrito; {len(recusados)} recusado.", status=200)
    if gesto in ACOES:
        corpo = {"site_id": site["id"], "acao": gesto}
        if request.POST.get("versao", "").strip():
            try:
                corpo["versao"] = _inteiro(request.POST["versao"], "a versão", minimo=1)
            except ValueError as erro:
                return _desenhar_detalhe(request, site, slug, erro=str(erro), status=400)
        situacao, resposta, frase = cliente.acao(slug, corpo)
        if situacao != cliente.OK:
            return _desenhar_detalhe(request, site, slug, erro=frase or "A ação não foi confirmada. Consulte o estado antes de repetir.", status=422)
        return HttpResponseRedirect(reverse("automacao_whatsapp", args=[slug]) + "?recado=" + gesto)
    return _desenhar_detalhe(request, site, slug, erro="Ação desconhecida.", status=400)
