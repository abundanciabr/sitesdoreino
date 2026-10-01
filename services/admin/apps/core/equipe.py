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
  responsável, pode ser assumida como compromisso da semana corrente. A visão
  "Esta semana" mostra, por pessoa, o que foi cumprido (concluído até o
  domingo) e o que ficou. Semana que já passou não se mexe: só se lê.
* **Comentários**: um texto curto por vez, com quem e quando, na ficha da
  tarefa. Não se editam nem se apagam.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import Comentario, Compromisso, MembroDaEquipe, Objetivo, Tarefa

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
    "sem_impedimento": ("Para bloquear uma tarefa, escreva o impedimento. Nada mudou."),
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
    "comentado": "Comentário publicado.",
    "comentario_vazio": "O comentário estava vazio. Nada foi publicado.",
    "comentario_longo": (
        "O comentário passou de 500 letras. Encurte e publique de novo; "
        "nada foi publicado."
    ),
}

# "Curto" é o pedido. O campo do formulário avisa no navegador; o servidor
# confere de novo, porque o navegador não é a porta.
TAMANHO_DO_COMENTARIO = 500


# ---------------------------------------------------------------- utilitários


def _hoje() -> date:
    return timezone.localdate()


def _quem(request) -> str:
    """Quem está agindo, como a tela mostra: nome e conta."""
    admin = request.admin
    nome = (admin.get("nome") or "").strip()
    email = (admin.get("email") or "").strip().lower()
    texto = f"{nome} ({email})" if nome and nome != email else email
    return texto[:200]


def _membro_da_sessao(request) -> MembroDaEquipe | None:
    email = (request.admin.get("email") or "").strip().lower()
    if not email:
        return None
    return MembroDaEquipe.objects.filter(ativo=True, email=email).first()


def _membros():
    return list(MembroDaEquipe.objects.filter(ativo=True))


def _objetivos_para_escolher(atual: Objetivo | None = None) -> list[Objetivo]:
    """Os objetivos que a tarefa pode escolher: os ativos, e o que ela já tem
    mesmo desativado, para que salvar a ficha não largue o objetivo por baixo
    dos panos."""
    escolhiveis = list(Objetivo.objects.filter(ativo=True))
    if atual is not None and not atual.ativo:
        escolhiveis.append(atual)
    return escolhiveis


def _segunda(dia: date) -> date:
    """A segunda-feira da semana de `dia`: é ela que dá nome à semana."""
    return dia - timedelta(days=dia.weekday())


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


def _ler_prazo(cru: str):
    """`(data ou None, erro ou None)` a partir do campo de data."""
    cru = (cru or "").strip()
    if not cru:
        return None, None
    try:
        return date.fromisoformat(cru), None
    except ValueError:
        return None, "O prazo precisa ser uma data válida."


def _ler_formulario(request, membros, objetivos) -> tuple[dict, list[str]]:
    """Lê o formulário de criar/editar. Devolve os dados crus e os erros."""
    post = request.POST
    dados = {
        "titulo": (post.get("titulo") or "").strip()[:200],
        "descricao": (post.get("descricao") or "").strip()[:5000],
        "responsavel": (post.get("responsavel") or "").strip(),
        "objetivo": (post.get("objetivo") or "").strip(),
        "prazo": (post.get("prazo") or "").strip(),
        "situacao": (post.get("situacao") or Situacao.A_FAZER).strip(),
        "impedimento": (post.get("impedimento") or "").strip()[:2000],
    }
    erros = []
    if not dados["titulo"]:
        erros.append("A tarefa precisa de um título.")
    if dados["responsavel"] and dados["responsavel"] not in {
        str(m.id) for m in membros
    }:
        erros.append("Não conheço essa pessoa. Escolha alguém da equipe.")
    if dados["objetivo"] and dados["objetivo"] not in {str(o.id) for o in objetivos}:
        erros.append("Não conheço esse objetivo. Escolha um dos objetivos ativos.")
    _, erro_prazo = _ler_prazo(dados["prazo"])
    if erro_prazo:
        erros.append(erro_prazo)
    if dados["situacao"] not in Situacao.values:
        erros.append("Não conheço essa situação.")
    if dados["situacao"] == Situacao.BLOQUEADA and not dados["impedimento"]:
        erros.append("Para bloquear uma tarefa, escreva o impedimento.")
    return dados, erros


def _aplicar(tarefa: Tarefa, dados: dict, membros, objetivos, quem: str) -> None:
    """Grava os dados lidos na tarefa, e cuida de conclusão e impedimento."""
    tarefa.titulo = dados["titulo"]
    tarefa.descricao = dados["descricao"]
    por_id = {str(m.id): m for m in membros}
    tarefa.responsavel = por_id.get(dados["responsavel"])
    tarefa.objetivo = {str(o.id): o for o in objetivos}.get(dados["objetivo"])
    tarefa.prazo, _ = _ler_prazo(dados["prazo"])
    _mudar_situacao(tarefa, dados["situacao"], dados["impedimento"])
    tarefa.alterada_por = quem
    tarefa.save()


def _mudar_situacao(tarefa: Tarefa, situacao: str, impedimento: str) -> None:
    """A regra da situação: concluir marca a hora; sair da conclusão limpa;
    só a bloqueada carrega impedimento."""
    tarefa.situacao = situacao
    if situacao == Situacao.CONCLUIDA:
        if tarefa.concluida_em is None:
            tarefa.concluida_em = timezone.now()
    else:
        tarefa.concluida_em = None
    tarefa.impedimento = impedimento if situacao == Situacao.BLOQUEADA else ""


def _dados_de(tarefa: Tarefa) -> dict:
    return {
        "titulo": tarefa.titulo,
        "descricao": tarefa.descricao,
        "responsavel": str(tarefa.responsavel_id or ""),
        "objetivo": str(tarefa.objetivo_id or ""),
        "prazo": tarefa.prazo.isoformat() if tarefa.prazo else "",
        "situacao": tarefa.situacao,
        "impedimento": tarefa.impedimento,
    }


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
    for tarefa in tarefas:
        tarefa.compromisso_da_semana = tarefa.id in compromissos_da_semana
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
            "comentarios": list(tarefa.comentarios.all()) if tarefa else [],
            "tamanho_do_comentario": TAMANHO_DO_COMENTARIO,
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
        },
        status=status,
    )


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
    return _com_resultado(reverse("painel_da_equipe"), "salva")


@require_POST
def tarefa_situacao(request, id: int):
    """Mudar a situação por um controle simples, direto do cartão."""
    tarefa = get_object_or_404(Tarefa, pk=id)
    destino = _destino_seguro(request, reverse("painel_da_equipe"))
    situacao = (request.POST.get("situacao") or "").strip()
    impedimento = (request.POST.get("impedimento") or "").strip()[:2000]
    if situacao not in Situacao.values:
        return _com_resultado(destino, "situacao_desconhecida")
    if situacao == Situacao.BLOQUEADA and not impedimento:
        return _com_resultado(destino, "sem_impedimento")

    estava_concluida = tarefa.situacao == Situacao.CONCLUIDA
    _mudar_situacao(tarefa, situacao, impedimento)
    tarefa.alterada_por = _quem(request)
    tarefa.save()

    if situacao == Situacao.CONCLUIDA:
        resultado = "concluida"
    elif estava_concluida:
        resultado = "reaberta"
    else:
        resultado = "situacao"
    return _com_resultado(destino, resultado)


@require_POST
def tarefa_compromisso(request, id: int):
    """Assumir a tarefa como compromisso da semana corrente, ou tirá-la.

    Só a semana CORRENTE se mexe: o que ficou numa semana que já passou é o
    registro dela, e tirar dali seria reescrever o resultado.
    """
    tarefa = get_object_or_404(Tarefa, pk=id)
    destino = _destino_seguro(request, reverse("painel_da_equipe"))
    semana = _segunda(_hoje())
    if request.POST.get("acao") == "tirar":
        Compromisso.objects.filter(tarefa=tarefa, semana=semana).delete()
        return _com_resultado(destino, "compromisso_tirado")
    if tarefa.situacao == Situacao.CONCLUIDA:
        return _com_resultado(destino, "compromisso_concluida")
    if tarefa.responsavel_id is None:
        return _com_resultado(destino, "compromisso_sem_responsavel")
    Compromisso.objects.get_or_create(
        tarefa=tarefa, semana=semana, defaults={"marcado_por": _quem(request)}
    )
    return _com_resultado(destino, "compromisso_marcado")


@require_POST
def tarefa_comentar(request, id: int):
    """Publica um comentário curto na ficha da tarefa."""
    tarefa = get_object_or_404(Tarefa, pk=id)
    # O navegador conta a quebra de linha como uma letra e a envia como duas;
    # contar do jeito dele é o que impede recusar o que ele deixou escrever.
    texto = (request.POST.get("texto") or "").replace("\r\n", "\n").strip()
    if not texto:
        resultado = "comentario_vazio"
    elif len(texto) > TAMANHO_DO_COMENTARIO:
        resultado = "comentario_longo"
    else:
        Comentario.objects.create(tarefa=tarefa, texto=texto, autor=_quem(request))
        resultado = "comentado"
    ficha = reverse("tarefa_editar", args=[tarefa.id])
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
        if tarefa.concluida_no_dia and tarefa.concluida_no_dia <= domingo:
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
    }
    erros = []
    if not dados["titulo"]:
        erros.append("O objetivo precisa de um título.")
    _, erro_prazo = _ler_prazo(dados["prazo"])
    if erro_prazo:
        erros.append(erro_prazo)
    return dados, erros


def _gravar_objetivo(objetivo: Objetivo, dados: dict) -> None:
    objetivo.titulo = dados["titulo"]
    objetivo.descricao = dados["descricao"]
    objetivo.prazo, _ = _ler_prazo(dados["prazo"])
    objetivo.save()


def _tela_do_objetivo(request, dados, erros, objetivo=None, status=200):
    return render(
        request,
        "admin/equipe_objetivo.html",
        {"admin": request.admin, "objetivo": objetivo, "dados": dados, "erros": erros},
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
            request, {"titulo": "", "descricao": "", "prazo": ""}, []
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
            "pessoas": list(MembroDaEquipe.objects.all()),
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
        },
    )


@require_POST
def pessoas_da_equipe_associar(request):
    """Associa (ou tira) a conta de uma pessoa. E-mail vazio desassocia."""
    if request.admin.get("equipe_apenas"):
        return _nao_existe(request)
    destino = reverse("pessoas_da_equipe")
    pessoa = get_object_or_404(MembroDaEquipe, pk=request.POST.get("pessoa") or 0)
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        pessoa.email = ""
        pessoa.save(update_fields=["email"])
        return _com_resultado(destino, "desassociada")
    try:
        validate_email(email)
    except ValidationError:
        return _com_resultado(destino, "email_invalido")
    if MembroDaEquipe.objects.filter(email=email).exclude(pk=pessoa.pk).exists():
        return _com_resultado(destino, "email_em_uso")
    pessoa.email = email
    pessoa.save(update_fields=["email"])
    return _com_resultado(destino, "associada")
