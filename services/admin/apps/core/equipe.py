"""`/admin/equipe/`: o painel da equipe, o trabalho das quatro pessoas numa tela.

Pedido do mantenedor em 01/10/2026: *"abrir o site, enxergar o trabalho da
equipe, criar uma tarefa, definir quem responde por ela e acompanhar a execução
até a conclusão"*. É o MVP do painel de gestão; objetivos, compromissos
semanais e placar virão por cima desta base.

## Duas visões do mesmo trabalho

"Minhas tarefas" e "Equipe" leem a mesma tabela. A primeira filtra pela pessoa
da sessão, reconhecida pelo E-MAIL da conta (`MembroDaEquipe.email`), nunca
pelo nome: nome é quem responde pela tarefa na tela, conta é quem entrou.
Quem entra com uma conta que não está associada a ninguém da equipe vê isso
escrito, e vê a visão da equipe inteira.

## Quem entra

A porta (`porta.py`) deixa passar por aqui dois crachás: o de administrador,
que abre a área toda, e o de equipe, que abre SÓ este prefixo. A tela de
pessoas (`/equipe/pessoas`), que associa uma conta a uma pessoa, é só do
administrador: quem decide quem é da equipe é o mantenedor.

## O que a tela guarda, e o que não guarda

Quem criou, quem alterou e quando concluiu moram na própria tarefa, como
texto. Não há sistema de auditoria separado, porque o pedido foi ver o rastro,
não guardá-lo para sempre.

## A segunda camada (01/10/2026)

* **Objetivos** (`/equipe/objetivos`): a tarefa pode apontar para um objetivo,
  e o painel filtra por ele. É a base para ligar as tarefas à MCI depois.
  Objetivo não se apaga; desativa.
* **Compromissos da semana** (`/equipe/semana`): uma tarefa aberta, com
  responsável, pode ser assumida como compromisso da semana corrente, ou
  tirada, por qualquer pessoa da equipe (e pelo robô dela). A visão
  "Esta semana" mostra, por pessoa, o que foi cumprido (concluído até o
  domingo) e o que ficou. Semana que já passou não se mexe: só se lê.
* **Comentários**: um texto curto por vez, com quem e quando, na ficha da
  tarefa. Não se editam nem se apagam.

## A terceira camada: o placar (01/10/2026)

* **O que o objetivo move** (`Objetivo.move`): a MCI nº 1 ou uma das duas
  medidas de direção, pelo nome do cartão com que `placar.py` as lê. A tarefa
  herda do objetivo dela; não há segundo campo na tarefa.
* **A aba Placar** (`/equipe/placar`): a MCI e as duas medidas da semana, com
  os números de `placar.montar_o_placar` (a mesma montagem de `/admin/placar/`,
  nunca uma conta nova), e embaixo de cada número o lado da equipe: que
  objetivos dizem movê-lo, quantas tarefas abertas eles têm e quantos
  compromissos desta semana foram cumpridos por ele.

## Ver a tarefa (02/10/2026)

Clicar numa tarefa abre `/equipe/<id>/ver`, a ficha para LER: o prazo como
contador (dias, horas, minutos e segundos até o fim do dia do prazo, na hora
de Brasília), os detalhes, o robô e os comentários. Editar é um botão dali,
e `/equipe/<id>/editar` ficou só com o formulário.
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.agentes import painel as painel_dos_robos
from apps.agentes.models import Execucao

from . import equipe_operacoes as operacoes
from .models import Compromisso, MembroDaEquipe, Objetivo, Tarefa

Situacao = Tarefa.Situacao

# As quatro colunas, na ordem em que o trabalho anda. A frase vazia de cada uma
# é escrita aqui porque "nenhuma tarefa" significa coisa diferente em cada
# coluna: zero bloqueada é notícia boa; zero em andamento é a semana parada.
COLUNAS = (
    (Situacao.A_FAZER, "A fazer", "Nada na fila."),
    (Situacao.EM_ANDAMENTO, "Em andamento", "Ninguém está com nada em andamento."),
    (Situacao.BLOQUEADA, "Bloqueada", "Nenhuma tarefa bloqueada."),
    (Situacao.CONCLUIDA, "Concluída", "Nada concluído ainda."),
)

FILTROS_DE_PRAZO = (
    ("", "Qualquer prazo"),
    ("atrasadas", "Atrasadas"),
    ("hoje", "Para hoje"),
    ("semana", "Nos próximos 7 dias"),
    ("sem_prazo", "Sem prazo"),
)

# As frases que a tela mostra depois de um gesto. Viajam na URL como código
# (`?resultado=criada`) e viram frase aqui, nunca o contrário: texto que viaja
# na URL vira texto que qualquer um escreve na barra de endereço.
RESULTADOS = {
    "criada": "Tarefa criada.",
    "salva": "Tarefa salva.",
    "situacao": "Situação atualizada.",
    "concluida": "Tarefa concluída.",
    "reaberta": "Tarefa reaberta: voltou para A fazer.",
    "situacao_desconhecida": "Não conheço essa situação. Nada mudou.",
    "associada": "Conta associada.",
    "desassociada": "Conta desassociada.",
    "email_invalido": "Esse e-mail não parece um e-mail. Nada mudou.",
    "email_em_uso": "Esse e-mail já está associado a outra pessoa. Nada mudou.",
    "objetivo_criado": "Objetivo criado.",
    "objetivo_salvo": "Objetivo salvo.",
    "objetivo_desativado": (
        "Objetivo desativado: some das escolhas de tarefa nova. As tarefas "
        "que já apontam para ele continuam mostrando o nome."
    ),
    "objetivo_reativado": "Objetivo reativado.",
    "compromisso_marcado": "Tarefa assumida como compromisso desta semana.",
    "compromisso_tirado": "Tarefa tirada dos compromissos desta semana.",
    "compromisso_concluida": (
        "Tarefa já concluída não vira compromisso: compromisso é o que ainda "
        "vai ser feito. Nada mudou."
    ),
    "compromisso_sem_responsavel": (
        "Compromisso é de alguém: escolha antes quem responde pela tarefa. "
        "Nada mudou."
    ),
    "aparelho_conectado": (
        "Pronto: este aparelho ficou conectado a você e continua conectado. "
        "Quando quiser, preencha nome, e-mail e senha em Meu perfil."
    ),
    "perfil_salvo": "Perfil salvo.",
    "saiu": "Este aparelho foi desconectado.",
    "aparelho_desconectado": "Aparelho desconectado. Os outros continuam.",
    "aparelhos_desconectados": (
        "Todos os aparelhos desconectados, e o link que ainda não tinha sido "
        "usado foi cancelado."
    ),
    "pessoa_retirada": (
        "Pessoa retirada da equipe: os aparelhos foram desconectados, e as "
        "tarefas, comentários e compromissos continuam guardados."
    ),
    "pessoa_de_volta": (
        "Pessoa de volta à equipe. Para ela entrar de novo, gere um link."
    ),
    "robo_delegado": (
        "Trabalho delegado ao seu robô. Ele roda no servidor e continua mesmo "
        "com o navegador fechado; o andamento aparece aqui e na página do robô."
    ),
    "robo_ja_rodando": "Seu robô já tem um panorama em andamento. Acompanhe na página dele.",
    "comentado": "Comentário publicado.",
    "comentario_vazio": "O comentário estava vazio. Nada foi publicado.",
    "comentario_longo": (
        "O comentário passou de 500 letras. Encurte e publique de novo; "
        "nada foi publicado."
    ),
}

TAMANHO_DO_COMENTARIO = operacoes.TAMANHO_DO_COMENTARIO


# ---------------------------------------------------------------- utilitários


_hoje = operacoes.hoje


def _quem(request) -> str:
    """Quem está agindo, como a tela mostra: nome e conta (quando há conta).

    Quem entrou por aparelho conectado pode não ter e-mail ainda: aí é só o
    nome."""
    admin = request.admin
    nome = (admin.get("nome") or "").strip()
    email = (admin.get("email") or "").strip().lower()
    if nome and email and nome != email:
        texto = f"{nome} ({email})"
    else:
        texto = nome or email
    return texto[:200]


def _membro_da_sessao(request) -> MembroDaEquipe | None:
    """A pessoa da equipe que está usando a tela.

    Quem entrou por aparelho conectado é reconhecido pelo IDENTIFICADOR da
    pessoa, que a porta põe em `membro_id`; quem entrou com a conta Google,
    pelo e-mail que o mantenedor conferiu."""
    membro_id = request.admin.get("membro_id")
    if membro_id:
        return MembroDaEquipe.objects.filter(ativo=True, pk=membro_id).first()
    email = (request.admin.get("email") or "").strip().lower()
    if not email:
        return None
    return MembroDaEquipe.objects.filter(
        ativo=True, email=email, email_a_conferir=False
    ).first()


_membros = operacoes.membros_ativos
_objetivos_para_escolher = operacoes.objetivos_para_escolher
_segunda = operacoes.segunda
_ler_prazo = operacoes.ler_prazo
_dados_de = operacoes.dados_de


_cumprido = operacoes.cumprido


def _marcar(tarefa: Tarefa, hoje: date) -> Tarefa:
    """Acende na tarefa o que a tela precisa saber sobre o prazo."""
    aberta = tarefa.situacao != Situacao.CONCLUIDA
    tarefa.atrasada = bool(tarefa.prazo and aberta and tarefa.prazo < hoje)
    tarefa.vence_hoje = bool(tarefa.prazo and aberta and tarefa.prazo == hoje)
    return tarefa


def _destino_seguro(request, padrao: str) -> str:
    """O `next` do formulário, só se for um endereço desta mesma tela."""
    destino = request.POST.get("next") or ""
    base = reverse("painel_da_equipe")
    if destino.startswith(base) and "//" not in destino and "\n" not in destino:
        return destino
    return padrao


def _sem_resultado(endereco: str) -> str:
    """O mesmo endereço, sem o `resultado` de um gesto anterior: a frase de um
    gesto não pode ficar colada na URL e reaparecer no gesto seguinte."""
    caminho, _, consulta = endereco.partition("?")
    pares = [p for p in consulta.split("&") if p and not p.startswith("resultado=")]
    return caminho + ("?" + "&".join(pares) if pares else "")


def _com_resultado(destino: str, resultado: str) -> HttpResponseRedirect:
    destino = _sem_resultado(destino)
    separador = "&" if "?" in destino else "?"
    return HttpResponseRedirect(f"{destino}{separador}resultado={resultado}")


def _ler_formulario(request, membros, objetivos) -> tuple[dict, list[str]]:
    """Lê o formulário de criar/editar. Devolve os dados crus e os erros."""
    dados = operacoes.limpar_dados(request.POST)
    return dados, operacoes.validar_tarefa(dados, membros, objetivos)


def _aplicar(tarefa: Tarefa, dados: dict, membros, objetivos, quem: str) -> None:
    """Grava os dados lidos na tarefa, e cuida de conclusão e impedimento."""
    operacoes.gravar_tarefa(tarefa, dados, membros, objetivos, quem)


def _nao_existe(request):
    """A mesma resposta da porta para quem não é administrador: 404."""
    return render(request, "admin/404.html", status=404)


# ---------------------------------------------------------------- as telas


@require_GET
def painel_da_equipe(request):
    """A tela principal: as tarefas por situação, em duas visões."""
    hoje = _hoje()
    membros = _membros()
    membro = _membro_da_sessao(request)

    visao = request.GET.get("visao") or ("minhas" if membro else "equipe")
    if visao not in ("minhas", "equipe"):
        visao = "equipe"

    tarefas = Tarefa.objects.select_related("responsavel", "objetivo").annotate(
        n_comentarios=Count("comentarios")
    )

    responsavel_escolhido = (request.GET.get("responsavel") or "").strip()
    if visao == "minhas":
        if membro is None:
            tarefas = tarefas.none()
        else:
            tarefas = tarefas.filter(responsavel=membro)
    elif responsavel_escolhido == "sem":
        tarefas = tarefas.filter(responsavel__isnull=True)
    elif responsavel_escolhido.isdigit():
        tarefas = tarefas.filter(responsavel_id=int(responsavel_escolhido))
    else:
        responsavel_escolhido = ""

    prazo_escolhido = (request.GET.get("prazo") or "").strip()
    if prazo_escolhido == "atrasadas":
        tarefas = tarefas.filter(prazo__lt=hoje).exclude(situacao=Situacao.CONCLUIDA)
    elif prazo_escolhido == "hoje":
        tarefas = tarefas.filter(prazo=hoje)
    elif prazo_escolhido == "semana":
        tarefas = tarefas.filter(prazo__gte=hoje, prazo__lte=hoje + timedelta(days=7))
    elif prazo_escolhido == "sem_prazo":
        tarefas = tarefas.filter(prazo__isnull=True)
    else:
        prazo_escolhido = ""

    situacao_escolhida = (request.GET.get("situacao") or "").strip()
    if situacao_escolhida not in Situacao.values:
        situacao_escolhida = ""

    objetivo_escolhido = (request.GET.get("objetivo") or "").strip()
    if objetivo_escolhido == "sem":
        tarefas = tarefas.filter(objetivo__isnull=True)
    elif objetivo_escolhido.isdigit():
        tarefas = tarefas.filter(objetivo_id=int(objetivo_escolhido))
    else:
        objetivo_escolhido = ""

    compromissos_da_semana = set(
        Compromisso.objects.filter(semana=_segunda(hoje)).values_list(
            "tarefa_id", flat=True
        )
    )
    por_situacao = {codigo: [] for codigo, _, _ in COLUNAS}
    tarefas = list(tarefas)
    ids = [t.id for t in tarefas]
    trabalhos = painel_dos_robos.trabalhos_das_tarefas(ids)
    entregas = painel_dos_robos.entregas_das_tarefas(ids)
    for tarefa in tarefas:
        tarefa.compromisso_da_semana = tarefa.id in compromissos_da_semana
        tarefa.trabalho_do_robo = trabalhos.get(tarefa.id)
        tarefa.entregas_do_robo = entregas.get(tarefa.id, [])[:1]
        por_situacao[tarefa.situacao].append(_marcar(tarefa, hoje))

    def ordem(tarefa):
        # Atrasada primeiro, depois o prazo mais perto, e sem prazo por último.
        return (
            not tarefa.atrasada,
            tarefa.prazo is None,
            tarefa.prazo or date.max,
            -tarefa.id,
        )

    colunas = []
    for codigo, rotulo, vazia in COLUNAS:
        if situacao_escolhida and codigo != situacao_escolhida:
            continue
        lista = por_situacao[codigo]
        if codigo == Situacao.CONCLUIDA:
            lista.sort(key=lambda t: (t.concluida_em or t.alterada_em), reverse=True)
        else:
            lista.sort(key=ordem)
        colunas.append(
            {"codigo": codigo, "rotulo": rotulo, "vazia": vazia, "tarefas": lista}
        )

    total = sum(len(c["tarefas"]) for c in colunas)
    atrasadas = sum(1 for c in colunas for t in c["tarefas"] if t.atrasada)
    peneirando = bool(
        responsavel_escolhido
        or prazo_escolhido
        or situacao_escolhida
        or objetivo_escolhido
    )

    return render(
        request,
        "admin/equipe.html",
        {
            "admin": request.admin,
            "hoje": hoje,
            "visao": visao,
            "membro": membro,
            "sem_pessoa": visao == "minhas" and membro is None,
            "membros": membros,
            "colunas": colunas,
            "total": total,
            "atrasadas": atrasadas,
            "peneirando": peneirando,
            "responsavel_escolhido": responsavel_escolhido,
            "prazo_escolhido": prazo_escolhido,
            "situacao_escolhida": situacao_escolhida,
            "objetivo_escolhido": objetivo_escolhido,
            "objetivos": list(Objetivo.objects.all()),
            "filtros_de_prazo": FILTROS_DE_PRAZO,
            "situacoes": Situacao.choices,
            "primeiro_uso": not Tarefa.objects.exists(),
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
            "endereco_atual": _sem_resultado(request.get_full_path()),
            "pode_gerir_pessoas": not request.admin.get("equipe_apenas"),
        },
    )


def _tela_do_formulario(request, dados, erros, objetivos, tarefa=None, status=200):
    """O formulário de criar e de editar. O robô e os comentários moram na
    ficha de ver (`tarefa_ver`), não aqui."""
    return render(
        request,
        "admin/equipe_tarefa.html",
        {
            "admin": request.admin,
            "tarefa": tarefa,
            "dados": dados,
            "erros": erros,
            "membros": _membros(),
            "objetivos": objetivos,
            "situacoes": Situacao.choices,
            "hoje": _hoje(),
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
        },
        status=status,
    )


DIAS_DA_SEMANA = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)


def _contador_do_prazo(tarefa: Tarefa, agora: datetime) -> dict | None:
    """O prazo como contador: quanto falta, ou há quanto passou.

    O prazo é um DIA; ele vence no fim desse dia, na hora de Brasília (a
    mesma conta do cartão, que só chama de atrasada no dia seguinte). Tarefa
    concluída ou sem prazo não tem contador.
    """
    if tarefa.prazo is None or tarefa.situacao == Situacao.CONCLUIDA:
        return None
    fim = timezone.make_aware(datetime.combine(tarefa.prazo + timedelta(days=1), time.min))
    falta = math.floor((fim - agora).total_seconds())
    resto = abs(falta)
    dias, resto = divmod(resto, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segundos = divmod(resto, 60)
    return {
        "atrasada": falta < 0,
        "dias": dias,
        "horas": horas,
        "minutos": minutos,
        "segundos": segundos,
        # Em milissegundos, para o script: ele conta a partir da hora do
        # servidor, porque o relógio do aparelho pode estar errado.
        "fim_ms": int(fim.timestamp() * 1000),
        "agora_ms": int(agora.timestamp() * 1000),
    }


@require_GET
def tarefa_ver(request, id: int):
    """A ficha da tarefa para ler: prazo em contador, detalhes, robô e
    comentários. Editar é um botão daqui."""
    from .equipe_acesso import _com_csp_do_script

    tarefa = get_object_or_404(
        Tarefa.objects.select_related("objetivo", "responsavel"), pk=id
    )
    membro = _membro_da_sessao(request)
    hoje = _hoje()
    concluida_no_prazo = None
    if tarefa.concluida_em and tarefa.prazo:
        concluida_no_prazo = timezone.localdate(tarefa.concluida_em) <= tarefa.prazo
    resposta = render(
        request,
        "admin/equipe_tarefa_ver.html",
        {
            "admin": request.admin,
            "membro": membro,
            "tarefa": tarefa,
            "hoje": hoje,
            "contador": _contador_do_prazo(tarefa, timezone.now()),
            "concluida_no_prazo": concluida_no_prazo,
            "dia_do_prazo": DIAS_DA_SEMANA[tarefa.prazo.weekday()] if tarefa.prazo else "",
            "compromisso_da_semana": Compromisso.objects.filter(
                tarefa=tarefa, semana=_segunda(hoje)
            ).exists(),
            "e_responsavel": membro is not None and tarefa.responsavel_id == membro.id,
            "endereco_atual": reverse("tarefa_ver", args=[tarefa.id]),
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
            "comentarios": list(tarefa.comentarios.select_related("autor_membro")),
            "tamanho_do_comentario": TAMANHO_DO_COMENTARIO,
            "trabalhos_do_robo": list(
                Execucao.objects.select_related("robo")
                .filter(tarefa_id=tarefa.id)
                .exclude(tipo=Execucao.Tipo.CONVERSA)[:10]
            ),
            "entregas_do_robo": painel_dos_robos.entregas_das_tarefas([tarefa.id]).get(
                tarefa.id, []
            ),
            "pode_delegar": bool(
                membro is not None
                and tarefa.responsavel_id == membro.id
                and tarefa.situacao != Situacao.CONCLUIDA
            ),
            "chave_de_envio": uuid.uuid4().hex,
        },
    )
    return _com_csp_do_script(resposta)


@require_http_methods(["GET", "POST"])
def tarefa_nova(request):
    """Criar uma tarefa. Responsável e objetivo vêm pré-escolhidos quando dá."""
    membros = _membros()
    objetivos = _objetivos_para_escolher()
    if request.method == "GET":
        membro = _membro_da_sessao(request)
        objetivo = (request.GET.get("objetivo") or "").strip()
        dados = {
            "titulo": "",
            "descricao": "",
            "responsavel": str(membro.id) if membro else "",
            "objetivo": objetivo if objetivo in {str(o.id) for o in objetivos} else "",
            "prazo": "",
            "situacao": Situacao.A_FAZER,
            "impedimento": "",
        }
        return _tela_do_formulario(request, dados, [], objetivos)

    dados, erros = _ler_formulario(request, membros, objetivos)
    if erros:
        return _tela_do_formulario(request, dados, erros, objetivos, status=400)
    tarefa = Tarefa(criada_por=_quem(request))
    _aplicar(tarefa, dados, membros, objetivos, _quem(request))
    return _com_resultado(reverse("painel_da_equipe"), "criada")


@require_http_methods(["GET", "POST"])
def tarefa_editar(request, id: int):
    tarefa = get_object_or_404(Tarefa.objects.select_related("objetivo"), pk=id)
    membros = _membros()
    objetivos = _objetivos_para_escolher(tarefa.objetivo)
    if request.method == "GET":
        return _tela_do_formulario(
            request, _dados_de(tarefa), [], objetivos, tarefa=tarefa
        )

    dados, erros = _ler_formulario(request, membros, objetivos)
    if erros:
        return _tela_do_formulario(
            request, dados, erros, objetivos, tarefa=tarefa, status=400
        )
    _aplicar(tarefa, dados, membros, objetivos, _quem(request))
    return _com_resultado(reverse("tarefa_ver", args=[tarefa.id]), "salva")


@require_POST
def tarefa_situacao(request, id: int):
    """Mudar a situação por um controle simples, direto do cartão."""
    tarefa = get_object_or_404(Tarefa, pk=id)
    destino = _destino_seguro(request, reverse("painel_da_equipe"))
    situacao = (request.POST.get("situacao") or "").strip()
    impedimento = request.POST.get("impedimento") or ""
    resultado = operacoes.mudar_situacao(tarefa, situacao, impedimento, _quem(request))
    return _com_resultado(destino, resultado)


@require_POST
def tarefa_compromisso(request, id: int):
    """Assumir a tarefa como compromisso da semana corrente, ou tirá-la.

    Só a semana CORRENTE se mexe: o que ficou numa semana que já passou é o
    registro dela, e tirar dali seria reescrever o resultado. Qualquer pessoa
    da equipe assume ou tira.
    """
    tarefa = get_object_or_404(Tarefa, pk=id)
    destino = _destino_seguro(request, reverse("painel_da_equipe"))
    resultado = operacoes.marcar_compromisso(
        tarefa, _quem(request), tirar=request.POST.get("acao") == "tirar"
    )
    return _com_resultado(destino, resultado)


@require_POST
def tarefa_comentar(request, id: int):
    """Publica um comentário curto na ficha da tarefa."""
    tarefa = get_object_or_404(Tarefa, pk=id)
    resultado, _ = operacoes.comentar(
        tarefa,
        request.POST.get("texto") or "",
        _quem(request),
        _membro_da_sessao(request),
    )
    ficha = reverse("tarefa_ver", args=[tarefa.id])
    return HttpResponseRedirect(f"{ficha}?resultado={resultado}#comentarios")


@require_GET
def semana_da_equipe(request):
    """A visão "Esta semana": os compromissos de cada pessoa, cumpridos e não.

    Cumprido é a tarefa concluída até o domingo da semana. Tarefa reaberta
    deixa de estar concluída, e por isso deixa de contar como cumprida.
    """
    hoje = _hoje()
    corrente = _segunda(hoje)
    pedida, _ = _ler_prazo(request.GET.get("semana") or "")
    segunda = min(_segunda(pedida), corrente) if pedida else corrente
    domingo = segunda + timedelta(days=6)
    e_corrente = segunda == corrente

    # Toda pessoa ativa aparece, mesmo sem compromisso: "nada assumido nesta
    # semana" é informação, não ausência dela.
    grupos = {
        membro.id: {"pessoa": membro, "cumpridos": [], "abertos": []}
        for membro in _membros()
    }
    compromissos = Compromisso.objects.filter(semana=segunda).select_related(
        "tarefa", "tarefa__responsavel", "tarefa__objetivo"
    )
    for compromisso in compromissos:
        tarefa = compromisso.tarefa
        tarefa.compromisso = compromisso
        grupo = grupos.setdefault(
            tarefa.responsavel_id,
            {"pessoa": tarefa.responsavel, "cumpridos": [], "abertos": []},
        )
        tarefa.concluida_no_dia = (
            timezone.localdate(tarefa.concluida_em) if tarefa.concluida_em else None
        )
        if _cumprido(tarefa, domingo):
            grupo["cumpridos"].append(tarefa)
        else:
            grupo["abertos"].append(_marcar(tarefa, hoje))
    pessoas = list(grupos.values())
    for grupo in pessoas:
        grupo["total"] = len(grupo["cumpridos"]) + len(grupo["abertos"])

    membro = _membro_da_sessao(request)
    return render(
        request,
        "admin/equipe_semana.html",
        {
            "admin": request.admin,
            "hoje": hoje,
            "visao": "semana",
            "membro": membro,
            "segunda": segunda,
            "domingo": domingo,
            "e_corrente": e_corrente,
            "anterior": (segunda - timedelta(days=7)).isoformat(),
            "seguinte": (
                None if e_corrente else (segunda + timedelta(days=7)).isoformat()
            ),
            "pessoas": pessoas,
            "total": sum(g["total"] for g in pessoas),
            "cumpridos": sum(len(g["cumpridos"]) for g in pessoas),
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
            "endereco_atual": _sem_resultado(request.get_full_path()),
            "pode_gerir_pessoas": not request.admin.get("equipe_apenas"),
        },
    )


# ---------------------------------------------------------------- objetivos


def _ler_objetivo(request) -> tuple[dict, list[str]]:
    post = request.POST
    dados = {
        "titulo": (post.get("titulo") or "").strip()[:200],
        "descricao": (post.get("descricao") or "").strip()[:5000],
        "prazo": (post.get("prazo") or "").strip(),
        "move": (post.get("move") or "").strip(),
    }
    erros = []
    if not dados["titulo"]:
        erros.append("O objetivo precisa de um título.")
    _, erro_prazo = _ler_prazo(dados["prazo"])
    if erro_prazo:
        erros.append(erro_prazo)
    if dados["move"] and dados["move"] not in Objetivo.Move.values:
        erros.append("Não conheço esse número do placar. Escolha um da lista.")
    return dados, erros


def _gravar_objetivo(objetivo: Objetivo, dados: dict) -> None:
    objetivo.titulo = dados["titulo"]
    objetivo.descricao = dados["descricao"]
    objetivo.prazo, _ = _ler_prazo(dados["prazo"])
    objetivo.move = dados["move"]
    objetivo.save()


def _tela_do_objetivo(request, dados, erros, objetivo=None, status=200):
    return render(
        request,
        "admin/equipe_objetivo.html",
        {
            "admin": request.admin,
            "objetivo": objetivo,
            "dados": dados,
            "erros": erros,
            "o_que_pode_mover": Objetivo.Move.choices,
        },
        status=status,
    )


@require_GET
def objetivos_da_equipe(request):
    """Os objetivos, ativos em cima, com quantas tarefas cada um tem."""
    hoje = _hoje()
    concluida = Q(tarefas__situacao=Situacao.CONCLUIDA)
    objetivos = list(
        Objetivo.objects.annotate(
            abertas=Count("tarefas", filter=~concluida),
            concluidas=Count("tarefas", filter=concluida),
        )
    )
    for objetivo in objetivos:
        objetivo.vencido = bool(
            objetivo.ativo and objetivo.prazo and objetivo.prazo < hoje
        )
    return render(
        request,
        "admin/equipe_objetivos.html",
        {
            "admin": request.admin,
            "visao": "objetivos",
            "ativos": [o for o in objetivos if o.ativo],
            "inativos": [o for o in objetivos if not o.ativo],
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
        },
    )


@require_http_methods(["GET", "POST"])
def objetivo_novo(request):
    if request.method == "GET":
        return _tela_do_objetivo(
            request, {"titulo": "", "descricao": "", "prazo": "", "move": ""}, []
        )
    dados, erros = _ler_objetivo(request)
    if erros:
        return _tela_do_objetivo(request, dados, erros, status=400)
    _gravar_objetivo(Objetivo(criado_por=_quem(request)), dados)
    return _com_resultado(reverse("objetivos_da_equipe"), "objetivo_criado")


@require_http_methods(["GET", "POST"])
def objetivo_editar(request, id: int):
    objetivo = get_object_or_404(Objetivo, pk=id)
    if request.method == "GET":
        dados = {
            "titulo": objetivo.titulo,
            "descricao": objetivo.descricao,
            "prazo": objetivo.prazo.isoformat() if objetivo.prazo else "",
            "move": objetivo.move,
        }
        return _tela_do_objetivo(request, dados, [], objetivo=objetivo)
    dados, erros = _ler_objetivo(request)
    if erros:
        return _tela_do_objetivo(request, dados, erros, objetivo=objetivo, status=400)
    _gravar_objetivo(objetivo, dados)
    return _com_resultado(reverse("objetivos_da_equipe"), "objetivo_salvo")


@require_POST
def objetivo_ativo(request, id: int):
    """Desativar (ou reativar) um objetivo. Apagar não existe pela tela."""
    objetivo = get_object_or_404(Objetivo, pk=id)
    objetivo.ativo = request.POST.get("ativo") == "1"
    objetivo.save(update_fields=["ativo"])
    resultado = "objetivo_reativado" if objetivo.ativo else "objetivo_desativado"
    return _com_resultado(reverse("objetivos_da_equipe"), resultado)


# ---------------------------------------------------------------- o placar


@require_GET
def placar_da_equipe(request):
    """A aba Placar: a MCI, as duas medidas de direção e o que a equipe faz
    por elas nesta semana.

    Os números NÃO são calculados aqui. Vêm de `placar.montar_o_placar`, a
    montagem de `/admin/placar/`, do fechamento e dos talentos: uma segunda
    conta da mesma meta discordaria da primeira no primeiro ajuste de cartão.
    Fail-open como lá: a parte que guarda os alunos fora do ar vira "não
    consigo contar", nunca zero, e a aba abre.

    Sem site (`site_id=None`): a linha da memória fica de fora, e com ela a
    pergunta à parte que guarda os sites, que esta aba não mostra.
    """
    # Import tardio: a montagem lê os cartões e pergunta à `alunos`, e só esta
    # aba do painel precisa dela.
    from .placar import montar_o_placar

    hoje = _hoje()
    numeros = montar_o_placar(hoje)
    segunda = _segunda(hoje)
    domingo = segunda + timedelta(days=6)

    compromissos = list(
        Compromisso.objects.filter(semana=segunda).select_related("tarefa__objetivo")
    )
    abertas = dict(
        Tarefa.objects.exclude(situacao=Situacao.CONCLUIDA)
        .filter(objetivo__move__in=Objetivo.Move.values)
        .values_list("objetivo__move")
        .annotate(n=Count("id"))
        .order_by()
    )
    ativos = list(Objetivo.objects.filter(ativo=True).exclude(move=""))

    def _move(compromisso) -> str:
        objetivo = compromisso.tarefa.objetivo
        return objetivo.move if objetivo else ""

    ligacoes = {}
    for valor, rotulo in Objetivo.Move.choices:
        deste = [c for c in compromissos if _move(c) == valor]
        ligacoes[valor] = {
            "rotulo": rotulo,
            "objetivos": [o for o in ativos if o.move == valor],
            "abertas": abertas.get(valor, 0),
            "compromissos": len(deste),
            "cumpridos": sum(1 for c in deste if _cumprido(c.tarefa, domingo)),
        }
    soltos = [c for c in compromissos if not _move(c)]

    resultado = numeros["placar"] or {}
    prazo_da_meta, _ = _ler_prazo(str(resultado.get("ate") or ""))
    partida_da_meta, _ = _ler_prazo(str(resultado.get("partida_em") or ""))
    return render(
        request,
        "admin/equipe_placar.html",
        {
            "admin": request.admin,
            "hoje": hoje,
            "visao": "placar",
            "membro": _membro_da_sessao(request),
            "segunda": segunda,
            "domingo": domingo,
            "meta": numeros["meta"],
            "placar": numeros["placar"],
            "contagem": numeros["contagem"],
            "prazo_da_meta": prazo_da_meta,
            "partida_da_meta": partida_da_meta,
            "direcao": numeros["direcao"],
            "cartao_pedidos": numeros["cartao_pedidos"],
            "cartao_48h": numeros["cartao_48h"],
            "mci": ligacoes[Objetivo.Move.MCI],
            "chegadas": ligacoes[Objetivo.Move.CHEGADAS],
            "confirmacoes": ligacoes[Objetivo.Move.CONFIRMACOES],
            "total_de_compromissos": len(compromissos),
            "soltos": len(soltos),
            "soltos_cumpridos": sum(1 for c in soltos if _cumprido(c.tarefa, domingo)),
            # O placar inteiro é da administração: quem entra com o crachá de
            # equipe recebe 404 lá, e por isso nem vê o link.
            "pode_ver_o_placar_inteiro": not request.admin.get("equipe_apenas"),
            "pode_gerir_pessoas": not request.admin.get("equipe_apenas"),
        },
    )


@require_GET
def pessoas_da_equipe(request):
    """Quem é da equipe, e com que conta cada pessoa entra. Só do administrador."""
    if request.admin.get("equipe_apenas"):
        return _nao_existe(request)
    return render(
        request,
        "admin/equipe_pessoas.html",
        {
            "admin": request.admin,
            "pessoas": list(
                MembroDaEquipe.objects.annotate(
                    n_aparelhos=Count(
                        "aparelhos", filter=Q(aparelhos__desconectado_em__isnull=True)
                    )
                )
            ),
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
        },
    )


@require_POST
def pessoas_da_equipe_associar(request):
    """Associa (ou tira) a conta de uma pessoa. E-mail vazio desassocia."""
    if request.admin.get("equipe_apenas"):
        return _nao_existe(request)
    pessoa = get_object_or_404(MembroDaEquipe, pk=request.POST.get("pessoa") or 0)
    destino = reverse("ficha_da_pessoa", args=[pessoa.id])
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        pessoa.email = ""
        pessoa.email_a_conferir = False
        pessoa.save(update_fields=["email", "email_a_conferir"])
        return _com_resultado(destino, "desassociada")
    try:
        validate_email(email)
    except ValidationError:
        return _com_resultado(destino, "email_invalido")
    if MembroDaEquipe.objects.filter(email=email).exclude(pk=pessoa.pk).exists():
        return _com_resultado(destino, "email_em_uso")
    # Salvar aqui é o mantenedor conferindo: o e-mail passa a abrir a porta
    # para a conta Google dele, inclusive o que a própria pessoa escreveu.
    pessoa.email = email
    pessoa.email_a_conferir = False
    pessoa.save(update_fields=["email", "email_a_conferir"])
    return _com_resultado(destino, "associada")
