"""[INV-SUG11] O id que ATRAVESSA — toda identidade cunhada aqui guarda o dela.

Lei: `docs/notificacoes/PLANO-MESTRE.md` §2 (o nó) e a Fase 1 da §6. A resposta
de `getSessionFull` **já traz** o id da pessoa na célula `identidade`
(`SessionFull.id`, contrato congelado) e a porta desta célula o descartava. Sem
ele, todo evento que a Caixa publica carrega um id que não significa nada fora
dela, e uma caixa central de notificações não consegue endereçar ninguém.

O guarda cobre as quatro metades do invariante, e nenhuma é decorativa:

1. **cunhagem** — quem entra pela primeira vez nasce com o id;
2. **reentrada** — a linha nascida ANTES desta migration ganha o id na visita
   seguinte (é o único caminho: a migration não preenche nada, porque não há de
   onde derivar o dado sem pedir à `identidade` a lista de gente dela);
3. **não sobrescreve** — linha já casada com outro id não é reescrita;
4. **a porta não passa a depender disto** — id ausente, nulo ou já pertencente a
   outra linha local NÃO recusa ninguém. Quem autoriza continua sendo e-mail +
   (staff | matrícula).

E duas sobre a FORMA da coluna (`null=True, unique=True` + `CheckConstraint`),
porque foi essa escolha que decidiu se a migration sobe: no Postgres cada `NULL`
é distinto num índice único — mil linhas antigas sem o dado convivem — enquanto
`''` colidiria com `''` na segunda.
"""

import secrets

import httpx
import pytest

from django.db import IntegrityError, transaction
from django.test import Client

from apps.sugestoes.models import Identidade
from tests.conftest import Porta, id_da_plataforma_de


def _pessoa_com_resposta(rede, matricula, corpo: dict, *, email: str) -> Porta:
    """Alguém diante da porta, com a `identidade` respondendo EXATAMENTE `corpo`.

    A fixture `sessao_do_site` monta a resposta feliz (com `id`); aqui o teste
    precisa das respostas que o contrato permite e a fixture não produz — sem
    `id`, com `id: null`, ou com o id de outra pessoa.
    """
    rede.alunos_diz(email, [matricula])
    rede.central_responde(httpx.Response(200, json=corpo))
    cliente = Client()
    cliente.cookies["meshcraft_sessao"] = secrets.token_urlsafe(12)
    return Porta(cliente, rede, email=email)


# ---------------------------------------------------------------------------
# 1. Cunhagem
# ---------------------------------------------------------------------------


def test_quem_entra_pela_primeira_vez_nasce_com_o_id_da_plataforma(entrar_como):
    pessoa = entrar_como(email="novata@exemplo.test")

    assert pessoa.identidade.id_da_plataforma == id_da_plataforma_de(
        "novata@exemplo.test"
    )


# ---------------------------------------------------------------------------
# 2. Reentrada — as linhas que já existiam quando esta migration subiu
# ---------------------------------------------------------------------------


def test_a_linha_antiga_ganha_o_id_na_reentrada(rede, db, matricula, entrar_como):
    """O caminho de TODA linha de produção: nasceu sem o dado, e o recupera na
    visita seguinte da pessoa — sem virar uma segunda identidade."""
    veterana = Identidade.objects.create(
        email="veterana@exemplo.test", nome_exibido="Veterana"
    )
    assert veterana.id_da_plataforma is None

    pessoa = entrar_como(email="veterana@exemplo.test")

    assert pessoa.identidade.id == veterana.id, "cunhou uma segunda pessoa"
    assert pessoa.identidade.id_da_plataforma == id_da_plataforma_de(
        "veterana@exemplo.test"
    )
    assert Identidade.objects.count() == 1


def test_o_casamento_por_email_continua_sendo_a_chave(rede, db, matricula, entrar_como):
    """A recuperação NÃO passou a ser pelo id da plataforma.

    Se alguém trocar a busca de `get_or_create(email=…)` por
    `get_or_create(id_da_plataforma=…)`, este teste cai: a linha antiga (sem id
    nenhum) nunca seria encontrada, e a pessoa perderia a autoria de tudo que
    escreveu antes da mudança de casa do login (DECISAO-celula-de-identidade §3).
    """
    antiga = Identidade.objects.create(
        email="autora@exemplo.test", nome_exibido="Autora"
    )

    pessoa = entrar_como(email="autora@exemplo.test")

    assert pessoa.identidade.id == antiga.id
    assert Identidade.objects.count() == 1


# ---------------------------------------------------------------------------
# 3. Não sobrescreve
# ---------------------------------------------------------------------------


def test_linha_ja_casada_nao_e_sobrescrita_por_outro_id(
    rede, db, matricula, entrar_como
):
    """A mesma pessoa mudando de identidade da plataforma é anomalia, não rotina.

    A Caixa registra no log e segue com o primeiro: escolher em silêncio qual
    dos dois ids é o certo seria pior que ficar com o que já estava lá.
    """
    pessoa = entrar_como(email="fulana@exemplo.test")
    assert pessoa.identidade.id_da_plataforma == id_da_plataforma_de(
        "fulana@exemplo.test"
    )

    de_novo = _pessoa_com_resposta(
        rede,
        matricula,
        {
            "autenticado": True,
            "id": "idt-COMPLETAMENTE-OUTRO",
            "nome_exibido": "Fulana",
            "email": "fulana@exemplo.test",
        },
        email="fulana@exemplo.test",
    )

    assert de_novo.esta_dentro, "a anomalia derrubou a porta"
    assert de_novo.identidade.id_da_plataforma == id_da_plataforma_de(
        "fulana@exemplo.test"
    )
    assert Identidade.objects.count() == 1


# ---------------------------------------------------------------------------
# 4. A porta NÃO passa a depender disto
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "corpo, caso",
    [
        (
            {
                "autenticado": True,
                "nome_exibido": "Sem Id",
                "email": "semid@exemplo.test",
            },
            "campo ausente",
        ),
        (
            {
                "autenticado": True,
                "id": None,
                "nome_exibido": "Id Nulo",
                "email": "semid@exemplo.test",
            },
            "id nulo (o contrato permite)",
        ),
        (
            {
                "autenticado": True,
                "id": "   ",
                "nome_exibido": "Id Em Branco",
                "email": "semid@exemplo.test",
            },
            "id só com espaços",
        ),
    ],
)
def test_a_porta_abre_mesmo_sem_o_id_da_plataforma(rede, db, matricula, corpo, caso):
    """`SessionFull.id` é OPCIONAL e NULÁVEL no contrato congelado.

    Quem autoriza aqui é e-mail + (staff | matrícula) — transformar a ausência
    deste campo em recusa seria a Caixa fechando a porta por causa de um dado
    que ela acabou de passar a coletar, e para uma pessoa que não tem como
    resolver o problema. As três formas de "não veio" viram UMA no banco: `NULL`.
    """
    pessoa = _pessoa_com_resposta(rede, matricula, corpo, email="semid@exemplo.test")

    assert pessoa.esta_dentro, f"a porta recusou com {caso}"
    assert pessoa.identidade.id_da_plataforma is None


@pytest.mark.parametrize(
    "a_linha_ja_existia", [False, True], ids=["cunhagem", "reentrada"]
)
def test_id_ja_usado_por_outra_linha_local_nao_derruba_a_porta(
    rede, db, matricula, entrar_como, a_linha_ja_existia
):
    """Acontece de verdade: alguém troca de e-mail lá e vira uma segunda linha
    aqui, com o mesmo id da plataforma. O `IntegrityError` da unicidade não pode
    virar 500 para quem já foi autorizada — vai para o log e a porta segue.

    **As duas frentes precisam engolir a colisão, e por caminhos diferentes:** na
    cunhagem ela estoura no `INSERT` do `get_or_create`; na reentrada, no `UPDATE`
    de `_casar_com_a_plataforma`. Um `try` só, no lugar errado, deixaria metade
    das pessoas vendo 500 — foi este parâmetro que achou a metade que faltava.
    """
    if a_linha_ja_existia:
        Identidade.objects.create(email="depois@exemplo.test", nome_exibido="Depois")

    primeira = entrar_como(email="antes@exemplo.test")
    compartilhado = primeira.identidade.id_da_plataforma

    segunda = _pessoa_com_resposta(
        rede,
        matricula,
        {
            "autenticado": True,
            "id": compartilhado,
            "nome_exibido": "Depois",
            "email": "depois@exemplo.test",
        },
        email="depois@exemplo.test",
    )

    assert segunda.esta_dentro, "a colisão derrubou a porta"
    assert segunda.identidade.id_da_plataforma is None
    primeira.identidade.refresh_from_db()
    assert primeira.identidade.id_da_plataforma == compartilhado


# ---------------------------------------------------------------------------
# A FORMA da coluna — a escolha que decidiu se a migration sobe
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_muitas_linhas_sem_o_id_convivem():
    """`null=True` + `unique=True`: no Postgres cada `NULL` é distinto dos
    outros num índice único. É isto que permite a `0006` subir sobre uma tabela
    cheia de linhas antigas — com `default=""` ela estouraria na segunda."""
    for n in range(3):
        Identidade.objects.create(email=f"sem-id-{n}@exemplo.test")

    assert Identidade.objects.filter(id_da_plataforma__isnull=True).count() == 3


@pytest.mark.django_db
def test_string_vazia_nao_e_um_valor_possivel():
    """O outro jeito de não saber, fechado no banco (`CheckConstraint`).

    Duas formas de "vazio" na mesma coluna é o que faz dois pedaços de código
    consultarem-na de jeitos diferentes — e um deles errado.
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Identidade.objects.create(email="vazia@exemplo.test", id_da_plataforma="")
