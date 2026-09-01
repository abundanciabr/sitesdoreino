"""O fórum ganhou VOZ: o que acontece nele passa a contar para o resto da escola.

Até 01/09/2026 esta célula era muda. Tinha gente conversando, dúvidas sendo
resolvidas, e nada disso virava ponto para ninguém — a medalha "Mão amiga"
(cinco respostas aceitas) não tinha como cair, porque ninguém contava.

O QUE ESTE ARQUIVO TRAVA:

1. **Cada evento nasce DENTRO da transação do fato.** Fora dela, um rollback
   deixaria a plataforma pagando ponto por uma mensagem que não existe.
2. **Os quatro casam com o contrato congelado**, validados contra o ARQUIVO de
   `contracts/eventos/forum.*.json` — nunca contra uma cópia do formato aqui.
3. **Nenhum texto escrito por gente viaja.** `mensagem-criada` leva o TAMANHO,
   e o corpo da mensagem não sai da célula.
4. **`resposta-aceita` carrega os dois ids**, e eles são diferentes: quem marcou
   vai no envelope, quem escreveu vai no `data` e é quem recebe o prêmio.
5. **Sem site conhecido, não se emite — e o fórum continua funcionando.** A falta
   de um evento nunca pode custar a fala de um aluno.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from django.test import Client
from django.urls import reverse

from apps.forum.eventos import EventoForaDaTransacao, topico_criado
from apps.forum.models import Area, Mensagem, OutboxEvent, Pessoa, Topico

pytestmark = pytest.mark.django_db

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"
SITE = "site-de-teste"
HOST = "forum.exemplo.test"


@pytest.fixture(autouse=True)
def o_catalogo_conhece_o_host(monkeypatch):
    """O site sai do HOST, perguntando ao catálogo. Aqui ele responde na hora.

    Trocar a função onde ela é USADA (e não a rede) deixa o teste medir a
    emissão, e não o cliente HTTP — que já tem os guardas dele.
    """
    monkeypatch.setattr("apps.core.views.site_id_do_host", lambda host: SITE)
    monkeypatch.setattr("apps.core.moderacao.site_id_do_host", lambda host: SITE)


def _pessoa(id_da_plataforma="pes-aluno", email="aluno@exemplo.test") -> Pessoa:
    return Pessoa.objects.create(
        id_da_plataforma=id_da_plataforma, email=email, nome_exibido="Quem Fala"
    )


def _area(**campos) -> Area:
    base = {
        "slug": "duvidas",
        "nome": "Dúvidas",
        "visibilidade": Area.Visibilidade.ALUNOS,
        "quem_escreve": Area.QuemEscreve.ALUNO,
    }
    base.update(campos)
    return Area.objects.create(**base)


def _entrar(monkeypatch, pessoa, equipe=False):
    from apps.core.sessao import Ator

    ator = Ator(pessoa=pessoa, eh_aluno=True, eh_professor=equipe)
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: ator)
    monkeypatch.setattr("apps.core.moderacao.quem_e", lambda request: ator)
    return ator


def _eventos(nome: str | None = None) -> list[OutboxEvent]:
    fila = OutboxEvent.objects.order_by("id")
    if nome:
        fila = fila.filter(event=nome)
    return list(fila)


def _conferir_contrato(evento: OutboxEvent) -> None:
    """O envelope como o relay o monta, contra o ARQUIVO do contrato."""
    envelope = {
        "event": evento.event,
        "version": evento.version,
        "event_id": str(evento.event_id),
        "occurred_at": evento.occurred_at.isoformat(),
        "data": evento.payload,
    }
    envelope.update(evento.envelope_extra)
    esquema = json.loads(
        (CONTRATOS / f"{evento.event}.v{evento.version}.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.validate(envelope, esquema)


# ------------------------------------------- 1. abrir e responder


def test_abrir_um_topico_conta_dois_fatos(monkeypatch):
    """Abrir a conversa e a primeira fala são coisas diferentes.

    O motor de XP paga por cada uma com regras próprias; juntar as duas num
    evento só obrigaria o consumidor a adivinhar qual aconteceu.
    """
    pessoa = _pessoa()
    area = _area()
    _entrar(monkeypatch, pessoa)

    resposta = Client().post(
        reverse("novo_topico", args=[area.slug]),
        {"titulo": "Como faço a moldura?", "texto": "Travei no bisel do Blender."},
    )

    assert resposta.status_code == 302
    assert [e.event for e in _eventos()] == [
        "forum.topico-criado",
        "forum.mensagem-criada",
    ]
    for evento in _eventos():
        _conferir_contrato(evento)


def test_o_texto_da_mensagem_nao_viaja_so_o_tamanho(monkeypatch):
    """Decisão da Sessão B: `caracteres`, nunca o conteúdo.

    O motor precisa do tamanho para o teto anti-spam; o texto de um aluno não tem
    por que atravessar fila de evento nem log de servidor.
    """
    pessoa = _pessoa()
    area = _area()
    _entrar(monkeypatch, pessoa)
    segredo = "o texto exato que eu escrevi e ninguem mais precisa ver"

    Client().post(
        reverse("novo_topico", args=[area.slug]),
        {"titulo": "Uma dúvida", "texto": segredo},
    )

    (mensagem,) = _eventos("forum.mensagem-criada")
    assert mensagem.payload["caracteres"] == len(segredo)
    assert segredo not in json.dumps(mensagem.payload, ensure_ascii=False)


def test_responder_conta_uma_fala(monkeypatch):
    pessoa = _pessoa()
    area = _area()
    topico = Topico.objects.create(area=area, autor=pessoa, titulo="Dúvida")
    Mensagem.objects.create(topico=topico, autor=pessoa, texto="a pergunta")
    _entrar(monkeypatch, pessoa)

    Client().post(reverse("responder", args=[topico.pk]), {"texto": "a resposta"})

    (evento,) = _eventos("forum.mensagem-criada")
    assert evento.payload["topico_id"] == str(topico.pk)
    _conferir_contrato(evento)


# ------------------------------------------- 2. o fato mais valioso


def test_aceitar_a_resposta_diz_quem_marcou_e_quem_recebe(monkeypatch):
    """Os dois ids são diferentes, e o contrato manda não remover nenhum.

    Sem `autor_da_resposta_id` não há a aresta "A premiou B" de que a detecção de
    anéis depende; sem `marcada_por`, o motor não distingue a marca de um colega
    da marca de alguém da equipe.
    """
    autor_da_pergunta = _pessoa("pes-perguntou", "perguntou@exemplo.test")
    quem_ajudou = _pessoa("pes-ajudou", "ajudou@exemplo.test")
    area = _area()
    topico = Topico.objects.create(area=area, autor=autor_da_pergunta, titulo="Dúvida")
    Mensagem.objects.create(topico=topico, autor=autor_da_pergunta, texto="a pergunta")
    resposta = Mensagem.objects.create(
        topico=topico, autor=quem_ajudou, texto="faz assim"
    )
    _entrar(monkeypatch, autor_da_pergunta)

    Client().post(
        reverse("moderar_topico", args=[topico.pk]),
        {"acao": "aceitar", "mensagem_id": resposta.pk},
    )

    (evento,) = _eventos("forum.resposta-aceita")
    assert evento.payload["autor_da_resposta_id"] == "pes-ajudou"
    assert evento.envelope_extra["ator_id"] == "pes-perguntou"
    # Quem marcou foi o dono da pergunta: a escadinha da decisão 5 da Sessão A.
    assert evento.payload["marcada_por"] == "autor"
    _conferir_contrato(evento)


def test_a_equipe_marcando_entra_como_professor(monkeypatch):
    autor_da_pergunta = _pessoa("pes-perguntou", "perguntou@exemplo.test")
    quem_ajudou = _pessoa("pes-ajudou", "ajudou@exemplo.test")
    professor = _pessoa("pes-professor", "professor@exemplo.test")
    area = _area()
    topico = Topico.objects.create(area=area, autor=autor_da_pergunta, titulo="Dúvida")
    resposta = Mensagem.objects.create(
        topico=topico, autor=quem_ajudou, texto="faz assim"
    )
    _entrar(monkeypatch, professor, equipe=True)

    Client().post(
        reverse("moderar_topico", args=[topico.pk]),
        {"acao": "aceitar", "mensagem_id": resposta.pk},
    )

    (evento,) = _eventos("forum.resposta-aceita")
    assert evento.payload["marcada_por"] == "professor"


def test_tirar_do_ar_anuncia_o_estorno(monkeypatch):
    """Sem este evento, o ponto pago por uma mensagem removida ficaria no placar."""
    pessoa = _pessoa()
    professor = _pessoa("pes-professor", "professor@exemplo.test")
    area = _area()
    topico = Topico.objects.create(area=area, autor=pessoa, titulo="Dúvida")
    mensagem = Mensagem.objects.create(topico=topico, autor=pessoa, texto="opa")
    topico.resposta_aceita = mensagem
    topico.save(update_fields=["resposta_aceita"])
    _entrar(monkeypatch, professor, equipe=True)

    Client().post(
        reverse("moderar_mensagem", args=[mensagem.pk]), {"acao": "tirar_do_ar"}
    )

    (evento,) = _eventos("forum.mensagem-removida")
    assert evento.payload["mensagem_id"] == str(mensagem.pk)
    _conferir_contrato(evento)


# ------------------------------------------- 3. as duas recusas


@pytest.mark.django_db(transaction=True)
def test_emitir_fora_da_transacao_e_recusado():
    """A Lei 1 aplicada: a própria função recusa, em vez de confiar na memória.

    `transaction=True` é o que torna este guarda possível: o `django_db` normal
    envolve cada teste numa transação, e dentro dela `in_atomic_block` é sempre
    verdadeiro — a recusa nunca dispararia e o teste passaria por acidente.
    """
    pessoa = _pessoa()
    area = _area()
    topico = Topico.objects.create(area=area, autor=pessoa, titulo="Dúvida")

    with pytest.raises(EventoForaDaTransacao):
        topico_criado(site_id=SITE, topico=topico, ator_id="pes-aluno")


def test_sem_site_conhecido_o_forum_fala_e_nao_emite(monkeypatch):
    """Catálogo fora do ar não pode calar um aluno.

    A ordem importa: primeiro a mensagem existe, depois o evento (ou não). O
    contrário faria uma falha de rede virar uma recusa de publicação.
    """
    pessoa = _pessoa()
    area = _area()
    _entrar(monkeypatch, pessoa)
    monkeypatch.setattr("apps.core.views.site_id_do_host", lambda host: "")

    resposta = Client().post(
        reverse("novo_topico", args=[area.slug]),
        {"titulo": "Uma dúvida", "texto": "o texto da dúvida"},
    )

    assert resposta.status_code == 302
    assert Topico.objects.count() == 1
    assert Mensagem.objects.count() == 1
    assert _eventos() == []
