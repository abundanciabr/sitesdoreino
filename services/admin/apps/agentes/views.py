"""As telas dos robôs.

* `/equipe/robo/` — a página do robô da pessoa, DENTRO do painel da equipe:
  quem é o robô, a conversa, os trabalhos no servidor, as entregas, o gasto
  do mês e o que ainda não está disponível. Abre com o crachá de equipe.
* `/equipe/robo/entregas/<n>` — uma entrega, com as permissões da pessoa:
  a entrega ligada a uma tarefa é do painel (toda a equipe vê a tarefa); a
  solta é só do dono do robô e do administrador.
* `/robos/` — a visão do administrador: todos os robôs, a conexão com a
  OpenAI (onde a chave é guardada, cifrada) e a autorização de gasto.

A porta (`porta.py`) é quem decide quem entra; aqui só se decide de QUEM é
cada coisa.
"""

from __future__ import annotations

import base64
import os
import hashlib
import re
import uuid

from django.db.models import Max
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.documentos import para_html
from apps.core.equipe import _membro_da_sessao, _nao_existe, _quem
from apps.core.models import MembroDaEquipe, Tarefa

from . import ferramentas, modelo, segredo, trabalhos
from .models import Conexao, Entrega, Execucao, Mensagem, RoboPessoal, tempo_em_palavras

TAMANHO_DA_MENSAGEM = 4000

RESULTADOS = {
    "enviada": "Mensagem enviada. O robô responde no servidor; pode fechar a página.",
    "vazia": "A mensagem estava vazia. Nada foi enviado.",
    "longa": "A mensagem passou de 4000 letras. Encurte e envie de novo.",
    "delegado": (
        "Panorama delegado. Ele roda no servidor e continua mesmo com o "
        "navegador fechado; a tarefa já está no painel."
    ),
    "ja_rodando": "Já há um panorama em andamento. Acompanhe abaixo.",
    "interrompida": "Interrupção pedida.",
    "retomada": "Trabalho de volta à fila do servidor.",
    "nao_retomada": "Esse trabalho não está esperando nem falhou; nada mudou.",
    "salvo": "Robô salvo.",
    "pausado": "Robô pausado: nenhum trabalho novo começa até reativar.",
    "ativado": "Robô ativo de novo. Os trabalhos pausados voltaram à fila.",
    "chave_guardada": "Chave guardada (cifrada) e conferida na conta.",
    "chave_vazia": "A chave estava vazia. Nada mudou.",
    "chave_tirada": "Chave apagada do banco. Os robôs ficam sem modelo até guardar outra.",
    "conferida": "Conexão conferida de novo.",
    "modelos_salvos": "Modelos salvos.",
}

_SCRIPT_EMBUTIDO = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


def _com_csp_do_script(resposta):
    """O mesmo desenho de `equipe_acesso`: o script da página entra no CSP
    pelo hash exato dos bytes dele, nunca por `unsafe-inline`."""
    from apps.core.porta import PortaAdministrativa

    scripts = "".join(
        " 'sha256-" + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode() + "'"
        for m in _SCRIPT_EMBUTIDO.finditer(resposta.content)
    )
    resposta["Content-Security-Policy"] = (
        f"default-src 'self'; script-src 'self'{scripts}; "
        f"style-src 'self'{PortaAdministrativa.hashes_de_estilo(resposta)}; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'"
    )
    return resposta


def _e_admin(request) -> bool:
    return not request.admin.get("equipe_apenas")


def _resultado(request) -> str | None:
    return RESULTADOS.get(request.GET.get("resultado") or "")


def _volta(nome: str, resultado: str, ancora: str = "") -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{reverse(nome)}?resultado={resultado}{ancora}")


def _meu_robo(request) -> tuple[MembroDaEquipe | None, RoboPessoal | None]:
    membro = _membro_da_sessao(request)
    if membro is None:
        return None, None
    return membro, trabalhos.robo_de(membro)


def _marca_de_andamento(robo: RoboPessoal) -> str:
    """Muda sempre que algo que a página mostra muda: é o que a página
    pergunta a cada poucos segundos para saber se recarrega."""
    delegados = (
        robo.execucoes.exclude(tipo=Execucao.Tipo.CONVERSA).aggregate(m=Max("atualizada_em"))["m"]
    )
    # Da conversa em andamento conta só a troca de situação, não cada batida:
    # a página não pisca a cada segundo enquanto a pessoa espera a resposta.
    conversas = list(
        robo.execucoes.filter(tipo=Execucao.Tipo.CONVERSA, situacao__in=Execucao.ABERTAS)
        .order_by("id")
        .values_list("id", "situacao")
    )
    mensagens = Mensagem.objects.filter(conversa__robo=robo).aggregate(m=Max("id"))["m"]
    entregas = robo.entregas.aggregate(m=Max("atualizada_em"))["m"]
    return f"{delegados}|{conversas}|{mensagens}|{entregas}"


# De quanto em quanto tempo a página aberta pergunta se mudou algo: depressa
# enquanto a pessoa espera uma resposta, devagar para trabalho longo.
INTERVALO_DA_CONVERSA = 1000
INTERVALO_DO_TRABALHO = 4000


def _consumo_do_mes() -> dict:
    autorizacao = modelo.autorizacao_ativa()
    gasto = modelo.gasto_do_mes()
    return {
        "gasto": gasto,
        "teto": autorizacao.teto_mensal_usd if autorizacao else None,
        "autorizacao": autorizacao,
    }


# O que o plano-mestre prevê e esta versão ainda não faz. A página diz isso
# em voz alta: planejado não é disponível.
PLANEJADO = (
    "Missões com várias etapas e dependências entre trabalhos",
    "Trabalhos por horário (todo dia, toda segunda) e lembretes",
    "Avisos fora do painel: notificação, e-mail e celular",
    "Conversa com os robôs das outras pessoas e com especialistas",
    "Arquivos (planilha, apresentação) e operação das células de negócio",
    "Integrações externas e missões contínuas",
)


@require_GET
def robo_da_pessoa(request):
    membro, robo = _meu_robo(request)
    if robo is None:
        return render(
            request,
            "agentes/sem_robo.html",
            {"admin": request.admin, "visao": "robo", "e_admin": _e_admin(request)},
        )
    conversa = trabalhos.conversa_de(robo)
    mensagens = list(conversa.mensagens.select_related("execucao").order_by("-id")[:60])[::-1]
    for mensagem in mensagens:
        if mensagem.papel == Mensagem.Papel.ROBO:
            mensagem.html = para_html(mensagem.texto)
    execucoes = list(robo.execucoes.exclude(tipo=Execucao.Tipo.CONVERSA)[:15])
    respondendo = robo.execucoes.filter(
        tipo=Execucao.Tipo.CONVERSA, situacao__in=Execucao.ABERTAS
    ).first()
    tarefas = {
        t.id: t
        for t in Tarefa.objects.filter(
            pk__in=[e.tarefa_id for e in execucoes if e.tarefa_id]
        )
    }
    for execucao in execucoes:
        execucao.tarefa = tarefas.get(execucao.tarefa_id)
    ativa = any(e.situacao in (Execucao.Situacao.NA_FILA, Execucao.Situacao.EXECUTANDO) for e in execucoes)
    conexao = modelo.conexao()
    resposta = render(
        request,
        "agentes/robo.html",
        {
            "admin": request.admin,
            "visao": "robo",
            "membro": membro,
            "robo": robo,
            "conexao": conexao,
            "tem_chave": modelo.tem_chave(),
            "mensagens": mensagens,
            "respondendo": respondendo,
            "execucoes": execucoes,
            "entregas": list(robo.entregas.all()[:15]),
            "consumo": _consumo_do_mes(),
            "planejado": PLANEJADO,
            "chave_de_envio": uuid.uuid4().hex,
            "acompanhar": bool(respondendo) or ativa,
            "intervalo": (
                INTERVALO_DA_CONVERSA
                if respondendo and not respondendo.esperando
                else INTERVALO_DO_TRABALHO
            ),
            "marca": _marca_de_andamento(robo),
            "tamanho_da_mensagem": TAMANHO_DA_MENSAGEM,
            "resultado": _resultado(request),
            "e_admin": _e_admin(request),
        },
    )
    return _com_csp_do_script(resposta)


def _marca_da_execucao(execucao: Execucao) -> str:
    return f"{execucao.situacao}|{execucao.atualizada_em.isoformat()}"


@require_GET
def andamento(request):
    """A pergunta curta da página aberta: mudou alguma coisa?"""
    numero = (request.GET.get("execucao") or "").strip()
    if numero.isdigit():
        execucao = _execucao_visivel(request, int(numero))
        return JsonResponse({"marca": _marca_da_execucao(execucao) if execucao else ""})
    _, robo = _meu_robo(request)
    if robo is None:
        return JsonResponse({"marca": ""})
    return JsonResponse({"marca": _marca_de_andamento(robo)})


@require_POST
def mensagem(request):
    membro, robo = _meu_robo(request)
    if robo is None:
        return _nao_existe(request)
    texto = (request.POST.get("texto") or "").replace("\r\n", "\n").strip()
    if not texto:
        return _volta("robo_da_pessoa", "vazia", "#conversa")
    if len(texto) > TAMANHO_DA_MENSAGEM:
        return _volta("robo_da_pessoa", "longa", "#conversa")
    trabalhos.pedir_resposta(
        robo, membro, texto, chave=request.POST.get("chave") or "", autor=_quem(request)
    )
    return _volta("robo_da_pessoa", "enviada", "#conversa")


@require_POST
def delegar(request):
    membro, robo = _meu_robo(request)
    if robo is None:
        return _nao_existe(request)
    tarefa_id = (request.POST.get("tarefa") or "").strip()
    tarefa = None
    if tarefa_id.isdigit():
        tarefa = Tarefa.objects.filter(pk=int(tarefa_id)).first()
    _, nova = trabalhos.delegar_panorama(
        robo,
        membro,
        pedido_por=_quem(request),
        origem="painel",
        observacao=(request.POST.get("observacao") or "").strip()[:1000],
        tarefa_id=tarefa.id if tarefa else None,
        chave=(request.POST.get("chave") or "")[:64],
    )
    destino = (request.POST.get("next") or "").strip()
    resultado = "delegado" if nova else "ja_rodando"
    if tarefa is not None and destino == reverse("tarefa_editar", args=[tarefa.id]):
        return HttpResponseRedirect(f"{destino}?resultado=robo_{resultado}#robo")
    return _volta("robo_da_pessoa", resultado, "#trabalhos")


def _execucao_visivel(request, id: int) -> Execucao | None:
    execucao = Execucao.objects.select_related("robo", "robo__membro").filter(pk=id).first()
    if execucao is None:
        return None
    if _e_admin(request):
        return execucao
    membro = _membro_da_sessao(request)
    if membro is not None and execucao.robo.membro_id == membro.id:
        return execucao
    # Trabalho ligado a uma tarefa é do painel: a equipe vê a tarefa e o
    # andamento dela, sem ver a conversa do dono.
    if execucao.tarefa_id and execucao.tipo != Execucao.Tipo.CONVERSA:
        return execucao
    return None


@require_GET
def execucao_detalhe(request, id: int):
    execucao = _execucao_visivel(request, id)
    if execucao is None:
        return _nao_existe(request)
    tarefa = Tarefa.objects.filter(pk=execucao.tarefa_id).first() if execucao.tarefa_id else None
    membro = _membro_da_sessao(request)
    dono = _e_admin(request) or (membro is not None and execucao.robo.membro_id == membro.id)
    registros = list(execucao.registros.all())
    for registro in registros:
        registro.desde = tempo_em_palavras((registro.momento - execucao.criada_em).total_seconds())
    chamadas = list(execucao.chamadas.all()) if dono else []
    for chamada in chamadas:
        chamada.rotulo = ferramentas.ROTULOS.get(chamada.nome, chamada.nome)
    resposta = render(
        request,
        "agentes/execucao.html",
        {
            "admin": request.admin,
            "visao": "robo",
            "execucao": execucao,
            "tarefa": tarefa,
            "registros": registros,
            "chamadas": chamadas,
            "consumos": list(execucao.consumos.all()) if dono else [],
            "entregas": list(execucao.entregas.all()),
            "dono": dono,
            "acompanhar": execucao.situacao in (Execucao.Situacao.NA_FILA, Execucao.Situacao.EXECUTANDO),
            "intervalo": (
                INTERVALO_DA_CONVERSA
                if execucao.tipo == Execucao.Tipo.CONVERSA
                else INTERVALO_DO_TRABALHO
            ),
            "marca": _marca_da_execucao(execucao),
            "resultado": _resultado(request),
        },
    )
    return _com_csp_do_script(resposta)


@require_POST
def execucao_interromper(request, id: int):
    execucao = _execucao_visivel(request, id)
    if execucao is None:
        return _nao_existe(request)
    membro = _membro_da_sessao(request)
    if not (_e_admin(request) or (membro and execucao.robo.membro_id == membro.id)):
        return _nao_existe(request)
    trabalhos.pedir_cancelamento(execucao, _quem(request))
    return HttpResponseRedirect(
        reverse("execucao_do_robo", args=[execucao.id]) + "?resultado=interrompida"
    )


@require_POST
def execucao_retomar(request, id: int):
    execucao = _execucao_visivel(request, id)
    if execucao is None:
        return _nao_existe(request)
    membro = _membro_da_sessao(request)
    if not (_e_admin(request) or (membro and execucao.robo.membro_id == membro.id)):
        return _nao_existe(request)
    resultado = "retomada" if trabalhos.retomar(execucao, _quem(request)) else "nao_retomada"
    return HttpResponseRedirect(
        reverse("execucao_do_robo", args=[execucao.id]) + f"?resultado={resultado}"
    )


@require_GET
def entrega_detalhe(request, id: int):
    entrega = get_object_or_404(Entrega.objects.select_related("robo", "robo__membro"), pk=id)
    membro = _membro_da_sessao(request)
    dono = membro is not None and entrega.robo.membro_id == membro.id
    if not (_e_admin(request) or dono or entrega.tarefa_id):
        return _nao_existe(request)
    tarefa = Tarefa.objects.filter(pk=entrega.tarefa_id).first() if entrega.tarefa_id else None
    return render(
        request,
        "agentes/entrega.html",
        {
            "admin": request.admin,
            "visao": "robo",
            "entrega": entrega,
            "tarefa": tarefa,
            "corpo": para_html(entrega.conteudo),
        },
    )


@require_POST
def configurar(request):
    """A pessoa ajusta o próprio robô: nome, responsabilidades, instruções,
    pausar e reativar. O robô continua o mesmo; a versão das instruções sobe."""
    _, robo = _meu_robo(request)
    if robo is None:
        return _nao_existe(request)
    acao = request.POST.get("acao") or "salvar"
    if acao == "pausar":
        robo.situacao = RoboPessoal.Situacao.PAUSADO
        robo.save()
        return _volta("robo_da_pessoa", "pausado")
    if acao == "ativar":
        robo.situacao = RoboPessoal.Situacao.ATIVO
        robo.save()
        for execucao in robo.execucoes.filter(situacao=Execucao.Situacao.PAUSADA):
            trabalhos.retomar(execucao, _quem(request))
        return _volta("robo_da_pessoa", "ativado")
    nome = (request.POST.get("nome") or "").strip()[:120]
    responsabilidades = (request.POST.get("responsabilidades") or "").strip()[:2000]
    instrucoes = (request.POST.get("instrucoes") or "").strip()[:4000]
    if nome:
        robo.nome = nome
    if (responsabilidades, instrucoes) != (robo.responsabilidades, robo.instrucoes):
        robo.versao_das_instrucoes += 1
    robo.responsabilidades = responsabilidades
    robo.instrucoes = instrucoes
    robo.save()
    return _volta("robo_da_pessoa", "salvo", "#identidade")


# ---------------------------------------------------------------- administrador


@require_http_methods(["GET", "POST"])
def robos_admin(request):
    """Todos os robôs e a conexão com a OpenAI. Só o administrador chega aqui
    (a porta barra o crachá de equipe fora de `/equipe`)."""
    if request.method == "POST":
        return _conexao_post(request)
    conexao = modelo.conexao()
    robos = list(RoboPessoal.objects.select_related("membro").order_by("membro__ordem", "id"))
    for robo in robos:
        robo.abertas = robo.execucoes.filter(situacao__in=Execucao.ABERTAS).count()
        robo.ultima = robo.execucoes.first()
    return render(
        request,
        "agentes/admin.html",
        {
            "admin": request.admin,
            "conexao": conexao,
            "chave_do_ambiente": bool((os.environ.get("OPENAI_API_KEY") or "").strip()),
            "chave_ilegivel": bool(conexao.segredo_cifrado) and segredo.decifrar(conexao.segredo_cifrado) is None,
            "robos": robos,
            "membros_sem_robo": MembroDaEquipe.objects.filter(ativo=True, robo__isnull=True),
            "execucoes": list(Execucao.objects.select_related("robo")[:20]),
            "consumo": _consumo_do_mes(),
            "precos": modelo.PRECOS,
            "resultado": _resultado(request),
        },
    )


def _conexao_post(request):
    acao = request.POST.get("acao") or ""
    conexao = modelo.conexao()
    quem = _quem(request)
    if acao == "guardar":
        chave = (request.POST.get("chave") or "").strip()
        if not chave:
            return _volta("robos_admin", "chave_vazia")
        conexao.segredo_cifrado = segredo.cifrar(chave)
        conexao.final_da_chave = chave[-4:]
        conexao.situacao = Conexao.Situacao.A_CONFERIR
        conexao.alterada_por = quem[:200]
        conexao.save()
        del chave
        modelo.conferir_conexao(quem)
        _reacordar()
        return _volta("robos_admin", "chave_guardada")
    if acao == "tirar":
        conexao.segredo_cifrado = ""
        conexao.final_da_chave = ""
        conexao.situacao = Conexao.Situacao.SEM_CHAVE
        conexao.detalhe = ""
        conexao.alterada_por = quem[:200]
        conexao.save()
        return _volta("robos_admin", "chave_tirada")
    if acao == "modelos":
        rapido = (request.POST.get("modelo_rapido") or "").strip()[:60]
        forte = (request.POST.get("modelo_forte") or "").strip()[:60]
        if rapido:
            conexao.modelo_rapido = rapido
        if forte:
            conexao.modelo_forte = forte
        conexao.alterada_por = quem[:200]
        conexao.save()
        modelo.conferir_conexao(quem)
        _reacordar()
        return _volta("robos_admin", "modelos_salvos")
    modelo.conferir_conexao(quem)
    _reacordar()
    return _volta("robos_admin", "conferida")


def _reacordar() -> None:
    from .executor import reacordar

    reacordar()
