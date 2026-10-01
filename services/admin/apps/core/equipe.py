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
"""

from __future__ import annotations

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import MembroDaEquipe, Tarefa

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
}


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


def _ler_formulario(request, membros) -> tuple[dict, list[str]]:
    """Lê o formulário de criar/editar. Devolve os dados crus e os erros."""
    post = request.POST
    dados = {
        "titulo": (post.get("titulo") or "").strip()[:200],
        "descricao": (post.get("descricao") or "").strip()[:5000],
        "responsavel": (post.get("responsavel") or "").strip(),
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
    _, erro_prazo = _ler_prazo(dados["prazo"])
    if erro_prazo:
        erros.append(erro_prazo)
    if dados["situacao"] not in Situacao.values:
        erros.append("Não conheço essa situação.")
    if dados["situacao"] == Situacao.BLOQUEADA and not dados["impedimento"]:
        erros.append("Para bloquear uma tarefa, escreva o impedimento.")
    return dados, erros


def _aplicar(tarefa: Tarefa, dados: dict, membros, quem: str) -> None:
    """Grava os dados lidos na tarefa, e cuida de conclusão e impedimento."""
    tarefa.titulo = dados["titulo"]
    tarefa.descricao = dados["descricao"]
    por_id = {str(m.id): m for m in membros}
    tarefa.responsavel = por_id.get(dados["responsavel"])
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

    tarefas = Tarefa.objects.select_related("responsavel")

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

    por_situacao = {codigo: [] for codigo, _, _ in COLUNAS}
    for tarefa in tarefas:
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
    peneirando = bool(responsavel_escolhido or prazo_escolhido or situacao_escolhida)

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
            "filtros_de_prazo": FILTROS_DE_PRAZO,
            "situacoes": Situacao.choices,
            "primeiro_uso": not Tarefa.objects.exists(),
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
            "endereco_atual": _sem_resultado(request.get_full_path()),
            "pode_gerir_pessoas": not request.admin.get("equipe_apenas"),
        },
    )


def _tela_do_formulario(request, dados, erros, tarefa=None, status=200):
    return render(
        request,
        "admin/equipe_tarefa.html",
        {
            "admin": request.admin,
            "tarefa": tarefa,
            "dados": dados,
            "erros": erros,
            "membros": _membros(),
            "situacoes": Situacao.choices,
            "hoje": _hoje(),
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
def tarefa_nova(request):
    """Criar uma tarefa. O responsável vem pré-escolhido quando dá."""
    membros = _membros()
    if request.method == "GET":
        membro = _membro_da_sessao(request)
        dados = {
            "titulo": "",
            "descricao": "",
            "responsavel": str(membro.id) if membro else "",
            "prazo": "",
            "situacao": Situacao.A_FAZER,
            "impedimento": "",
        }
        return _tela_do_formulario(request, dados, [])

    dados, erros = _ler_formulario(request, membros)
    if erros:
        return _tela_do_formulario(request, dados, erros, status=400)
    tarefa = Tarefa(criada_por=_quem(request))
    _aplicar(tarefa, dados, membros, _quem(request))
    return _com_resultado(reverse("painel_da_equipe"), "criada")


@require_http_methods(["GET", "POST"])
def tarefa_editar(request, id: int):
    tarefa = get_object_or_404(Tarefa, pk=id)
    membros = _membros()
    if request.method == "GET":
        return _tela_do_formulario(request, _dados_de(tarefa), [], tarefa=tarefa)

    dados, erros = _ler_formulario(request, membros)
    if erros:
        return _tela_do_formulario(request, dados, erros, tarefa=tarefa, status=400)
    _aplicar(tarefa, dados, membros, _quem(request))
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
