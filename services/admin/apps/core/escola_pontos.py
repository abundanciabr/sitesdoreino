# apps/core/escola_pontos.py
"""`/admin/escola/pontos/` — o quadro de pontos: quem tem quanto, e quem parou.

Pedido do mantenedor em 03/09/2026: a turma ordenada por XP, com nível e
título de cada um, as medalhas e marcos de cada um, e quem está ativo contra
quem parou. Custou um Rito de Contrato (a porta da gamificação não deixava
sair XP de outra pessoa) — ver `contracts/gamificacao.openapi.yaml`, operação
`listStudentStandings`.

## Onde o dado mora, e por que não aqui

Em TRÊS células, e esta tela não guarda nada de nenhuma: `alunos` sabe quem é
aluno (nome, e-mail, turma), `gamificacao` sabe quanto cada um tem e o que
concedeu, `identidade` sabe o e-mail de um id opaco de plataforma. Guardar
cópia de qualquer uma seria o mesmo fato em dois lugares — a lei
anti-duplicação do `CLAUDE.md`.

## Por que a resolução de e-mail é limitada a QUEM JÁ TEM PONTO

A porta da gamificação fala em `pessoa_id` (o invariante 1 do contrato dela
continua inteiro: nunca e-mail). Esta tela precisa de e-mail para casar cada
linha com a ficha de matrícula — e o caminho é `IdentidadeClient.pessoa_por_id`,
uma chamada por pessoa. Resolver a escola INTEIRA custaria uma chamada por
aluno matriculado; resolver só quem aparece em `GamificacaoClient().quadro()`
custa uma chamada por aluno que JÁ jogou — o `PerfilJogador` é preguiçoso (Lei
7 da gamificação), então logo depois de a economia ser ligada esse número é
pequeno, e cresce com o uso real, não com o tamanho da matrícula.

## Fail-open por METADE, como a tela de economia

Alunos, pontos e os nomes (degraus/conquistas) vêm de três perguntas
separadas, e cada uma pode falhar sozinha: a lista de alunos continua
completa mesmo se a gamificação estiver fora do ar — só aparece sem pontos,
com um aviso — e vice-versa. Uma tela que caísse inteira porque uma célula
vizinha está fora do ar seria o oposto do que a área administrativa serve
para fazer (`PLANO-AREA-ADMIN.md` §5).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .clients import AlunosClient, GamificacaoClient, IdentidadeClient

#: Sem atividade dentro desta janela, a linha aparece como "parado". O número
#: é chute honesto, não medição: a economia foi ligada há poucos dias e ainda
#: não há histórico para calibrar contra. Mudar é uma linha, não uma migração.
DIAS_PARA_CONSIDERAR_PARADO = 7


def _instante(iso: "str | None") -> "datetime | None":
    """Uma data que o Python sabe comparar, ou `None`.

    As duas células que alimentam esta tela mandam texto ISO; comparar string
    contra `timezone.now()` sem conversão nunca erra em teste (chega vazio
    nele) e sempre erra em produção. Guarda o mesmo defeito de `views.py::_dia`.
    """
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _mapa_de_titulos(degraus: "list | None") -> "dict[int, str]":
    """`{nível: título}`, dos degraus que a economia conhece — ligados ou não.

    Um aluno pode estar num nível cujo degrau foi desligado depois (a porta de
    máquina não filtra por `ativa` aqui — o mesmo motivo do `_titulos_por_nivel`
    dela: o nível de alguém não muda porque o mantenedor recalibrou a escada).
    Nível sem degrau nenhum fica de fora do mapa, e a linha mostra o número sem
    título — nunca uma string vazia que se leria como "existe título, é vazio".
    """
    if not degraus:
        return {}
    return {int(d.get("nivel") or 0): str(d.get("titulo") or "") for d in degraus}


def _mapa_de_conquistas(conquistas: "list | None") -> "dict[str, dict]":
    """`{slug: definição}`, para traduzir o slug que a porta do quadro devolve
    no nome em português que só `listAchievementSwitches` conhece."""
    if not conquistas:
        return {}
    return {str(c.get("slug")): c for c in conquistas if c.get("slug")}


def _emails_por_pessoa_id(quadro: "list[dict]") -> "dict[str, dict]":
    """`{e-mail em minúsculas: a linha do quadro}` — só de quem resolveu.

    Pessoa cujo id a identidade não reconhece (ou que a identidade não
    respondeu) fica de fora do mapa: a linha do aluno aparece sem pontos, como
    se ele nunca tivesse jogado — falha aberta, nunca página quebrada.
    """
    identidade = IdentidadeClient()
    mapa: "dict[str, dict]" = {}
    for entrada in quadro:
        pessoa_id = entrada.get("pessoa_id")
        if not pessoa_id:
            continue
        email = identidade.pessoa_por_id(pessoa_id)
        if email:
            mapa[email.strip().lower()] = entrada
    return mapa


def _linha(
    aluno: dict,
    entrada: "dict | None",
    *,
    titulos: "dict[int, str]",
    nomes_de_conquista: "dict[str, dict]",
    agora: datetime,
) -> dict:
    """Uma linha do quadro: o aluno, cruzado com o que a gamificação sabe
    dele — ou os valores de quem nunca pontuou, se `entrada` for `None`."""
    xp = int(entrada.get("xp") or 0) if entrada else 0
    nivel = int(entrada.get("nivel") or 1) if entrada else 1
    ultima = _instante(entrada.get("ultima_atividade_em")) if entrada else None

    dias_parado = (agora - ultima).days if ultima else None

    conquistas = []
    for c in (entrada.get("conquistas") if entrada else None) or []:
        definicao = nomes_de_conquista.get(str(c.get("slug")), {})
        conquistas.append(
            {
                "slug": c.get("slug"),
                "nome": str(definicao.get("nome") or c.get("slug") or ""),
                "e_marco": c.get("classe") == "marco",
                "concedida_em": _instante(c.get("concedida_em")),
            }
        )
    conquistas.sort(key=lambda c: c["concedida_em"] or agora, reverse=True)

    return {
        "id": aluno.get("id"),
        "nome": aluno.get("nome_completo") or "",
        "email": aluno.get("email") or "",
        "turma": aluno.get("turma"),
        "xp": xp,
        "nivel": nivel,
        "titulo": titulos.get(nivel, ""),
        "conquistas": conquistas,
        # Três estados, não dois: quem nunca jogou não é o mesmo que quem
        # jogou e parou — a tela precisa dizer qual das duas coisas é verdade,
        # e "0 XP" sozinho não distingue.
        "nunca_pontuou": entrada is None,
        "dias_parado": dias_parado,
        "esta_parado": dias_parado is None or dias_parado > DIAS_PARA_CONSIDERAR_PARADO,
    }


@require_GET
def escola_pontos(request):
    """A tela: a turma ordenada por XP, com nível, título, conquistas e quem
    parou. Só alunos ATIVOS aparecem — ex-aluno não compete no quadro."""
    alunos = AlunosClient().alunos(status="ativa")
    if alunos is None:
        return render(
            request,
            "admin/escola_pontos.html",
            {"admin": request.admin, "nao_consigo_ver_alunos": True},
        )

    cliente = GamificacaoClient()
    quadro = cliente.quadro()
    degraus = cliente.degraus()
    conquistas_definicoes = cliente.conquistas()

    titulos = _mapa_de_titulos(degraus)
    nomes_de_conquista = _mapa_de_conquistas(conquistas_definicoes)
    por_email = _emails_por_pessoa_id(quadro) if quadro is not None else {}
    agora = timezone.now()

    linhas = [
        _linha(
            aluno,
            por_email.get((aluno.get("email") or "").strip().lower()),
            titulos=titulos,
            nomes_de_conquista=nomes_de_conquista,
            agora=agora,
        )
        for aluno in alunos
    ]
    # Pontos primeiro (o pedido: "ordenada por pontos"); nome como critério de
    # desempate, para a lista não trocar de ordem sozinha entre duas visitas
    # de dois alunos empatados em zero.
    linhas.sort(key=lambda linha: (-linha["xp"], linha["nome"].lower()))

    return render(
        request,
        "admin/escola_pontos.html",
        {
            "admin": request.admin,
            "alunos": linhas,
            "total": len(linhas),
            "ativos": sum(1 for linha in linhas if not linha["esta_parado"]),
            "parados": sum(1 for linha in linhas if linha["esta_parado"]),
            "dias_para_considerar_parado": DIAS_PARA_CONSIDERAR_PARADO,
            # As três perguntas podem falhar cada uma por si — a tela avisa
            # qual faltou, sem derrubar as outras duas.
            "nao_consigo_ver_pontos": quadro is None,
            "nao_consigo_ver_titulos": degraus is None,
            "nao_consigo_ver_nomes_de_conquista": conquistas_definicoes is None,
        },
    )
