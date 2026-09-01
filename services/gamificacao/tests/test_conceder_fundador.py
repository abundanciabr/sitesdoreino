"""A medalha de Fundador: quem a concede, quando ela recusa, e por que repetir é seguro.

Este é o único caminho por onde o Fundador sai, e ele guarda cinco fatos que,
cada um por si, já custaram um incidente em algum lugar deste projeto:

1. **Medalha desligada não sai**, nem por linha de comando. A economia nasce
   desligada de propósito, e ligar é decisão do mantenedor, com data, na tela
   dele. Um comando que ligasse por fora tiraria a resposta de "quando isto
   entrou no ar".
2. **O padrão é ensaio.** Sem `--confirmo` o banco não recebe uma linha. Um
   comando que escreve por omissão é um comando que alguém roda por engano, e
   desfazer concessão é gesto que não existe.
3. **Conceder de verdade paga o que a medalha promete**, e paga uma vez só: os
   25 Cristais, o perfil atualizado e a carta que avisa a pessoa.
4. **Re-executar é seguro, e é o ponto.** É o `Unique(pessoa, conquista)` do
   banco que garante isso, não o cuidado de quem roda. Sem esta prova, o
   comando seria "re-executável" só na intenção.
5. **Id que o espelho não conhece não vira linha inventada.** Fabricar uma
   `Pessoa` a partir de um id opaco exigiria fabricar um e-mail, e um e-mail
   fabricado é uma segunda verdade sobre quem é a pessoa (Lei 2).
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.gamificacao.cartas import ASSUNTO_CONQUISTA
from apps.gamificacao.management.commands.conceder_fundador import ids_pedidos
from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
    LancamentoDeXP,
    MovimentoDeCristais,
    OutboxEvent,
    PerfilJogador,
    Pessoa,
)

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
VETERANA = "pes-veterana"
VETERANO = "pes-veterano"
NINGUEM = "pes-que-o-espelho-nao-conhece"


def _pessoa(id_da_plataforma: str) -> Pessoa:
    return Pessoa.objects.create(
        id_da_plataforma=id_da_plataforma,
        email=f"{id_da_plataforma}@exemplo.test",
    )


def _fundador(**campos) -> ConquistaDefinicao:
    """A medalha como `semear_economia` a planta, e LIGADA salvo se o teste disser.

    Os números são os do semeador de propósito: 0 pontos e 25 Cristais. Um teste
    que inventasse valores próprios passaria verde no dia em que a economia
    mudasse, e é justamente a economia que este comando entrega.
    """
    base = {
        "slug": "fundador",
        "site_id": SITE,
        "nome": "Fundador",
        "descricao": "Estava aqui no começo de tudo. Esta não volta.",
        "classe": ConquistaDefinicao.Classe.MEDALHA,
        "familia": ConquistaDefinicao.Familia.EPOCA,
        "criterio": {"tipo": "manual"},
        "pontos": 0,
        "cristais": 25,
        "ativa": True,
    }
    base.update(campos)
    return ConquistaDefinicao.objects.create(**base)


def _rodar(*, ids: str, confirmo: bool = False) -> str:
    saida = StringIO()
    argumentos = ["--site", SITE, "--ids", ids]
    if confirmo:
        argumentos.append("--confirmo")
    call_command("conceder_fundador", *argumentos, stdout=saida)
    return saida.getvalue()


# ------------------------------------------- 1. a recusa fail-closed


def test_medalha_desligada_recusa_e_explica_de_quem_e_a_decisao():
    """A economia nasce desligada, e nenhum comando de linha a liga.

    Este é o estado REAL de produção hoje: `semear_economia` cria tudo com
    `ativa=False`. Um agente futuro que ler esta recusa como defeito e a
    remover estará dando ao terminal um poder que a lei desta célula reserva à
    tela do mantenedor.
    """
    _pessoa(VETERANA)
    _fundador(ativa=False)

    with pytest.raises(CommandError) as recusa:
        _rodar(ids=VETERANA, confirmo=True)

    assert "PAROU POR SEGURANÇA" in str(recusa.value)
    assert "decisão do mantenedor" in str(recusa.value)
    assert "/admin/economia/" in str(recusa.value)
    assert Concessao.objects.count() == 0
    assert MovimentoDeCristais.objects.count() == 0


def test_sem_a_lista_o_comando_recusa_em_vez_de_adivinhar():
    """Quem é fundador não é derivável daqui, e o comando diz isso em vez de chutar.

    O espelho `Pessoa` desta célula é preguiçoso: uma linha nasce no primeiro XP
    ou na primeira visita a `/conquistas`. Deduzir "quem estava aqui no começo"
    dessa tabela responderia, na prática, "quem chegou por último".
    """
    _pessoa(VETERANA)
    _fundador()

    with pytest.raises(CommandError) as recusa:
        call_command("conceder_fundador", "--site", SITE, "--confirmo")

    assert "não tem como descobrir sozinho" in str(recusa.value)
    assert Concessao.objects.count() == 0


def test_sem_a_medalha_semeada_o_comando_manda_semear():
    _pessoa(VETERANA)

    with pytest.raises(CommandError, match="semear_economia"):
        _rodar(ids=VETERANA, confirmo=True)

    assert Concessao.objects.count() == 0


# ------------------------------------------- 2. o ensaio é o padrão


def test_sem_confirmo_nada_e_escrito_no_banco():
    """O padrão é olhar. Escrever exige a palavra explícita."""
    _pessoa(VETERANA)
    _fundador()

    saida = _rodar(ids=VETERANA)

    assert "ENSAIO" in saida
    assert Concessao.objects.count() == 0
    assert MovimentoDeCristais.objects.count() == 0
    assert OutboxEvent.objects.count() == 0
    assert PerfilJogador.objects.count() == 0


def test_o_ensaio_separa_quem_recebe_de_quem_ja_tem_e_de_quem_nao_existe():
    """A saída do ensaio é o que o mantenedor lê para decidir, então ela separa os três casos."""
    veterana = _pessoa(VETERANA)
    _pessoa(VETERANO)
    fundador = _fundador()
    Concessao.objects.create(pessoa=veterana, site_id=SITE, conquista=fundador)

    saida = _rodar(ids=f"{VETERANO},{VETERANA},{NINGUEM}")

    assert f"recebem a medalha (1): {VETERANO}" in saida
    assert f"já têm, e nada muda para elas (1): {VETERANA}" in saida
    assert f"não conheço esta pessoa ainda (1): {NINGUEM}" in saida


# ------------------------------------------- 3. o caminho feliz


def test_com_confirmo_a_medalha_sai_com_os_cristais_e_a_carta():
    """O que a medalha promete: 25 Cristais no saldo e uma carta avisando.

    O Fundador vale ZERO XP de propósito (é o que o semeador planta): ela
    reconhece o tempo de casa, não esforço medido. Reconhecimento que pagasse
    pontos entraria na conta do nível de quem chegou cedo, e o nível deixaria de
    medir o que a pessoa fez.
    """
    _pessoa(VETERANA)
    _fundador()

    saida = _rodar(ids=VETERANA, confirmo=True)

    assert "FEITO: 1 medalha(s) concedida(s)" in saida
    concessao = Concessao.objects.get()
    assert concessao.pessoa_id == VETERANA
    assert concessao.validador_papel == Concessao.PapelDoValidador.SISTEMA
    # Nada é exposto sem ação explícita da pessoa, nem numa concessão em bloco.
    assert concessao.consentimento == Concessao.Consentimento.PRIVADO

    movimento = MovimentoDeCristais.objects.get()
    assert movimento.delta == 25
    assert movimento.origem == MovimentoDeCristais.Origem.CONQUISTA
    assert movimento.referencia == "conquista:fundador"

    # A CÓPIA NÃO PODE MENTIR: sem o recálculo, o razão teria a moeda e a tela
    # da pessoa mostraria o saldo de antes, sem erro em lugar nenhum.
    perfil = PerfilJogador.objects.get()
    assert perfil.cristais_saldo == 25
    assert perfil.xp_total == 0
    assert LancamentoDeXP.objects.count() == 0

    carta = OutboxEvent.objects.get()
    assert carta.payload["assunto"] == ASSUNTO_CONQUISTA
    assert carta.payload["destinatario_id"] == VETERANA
    assert carta.payload["parametros"] == {
        "conquista_slug": "fundador",
        "familia": "epoca",
    }


def test_uma_lista_com_varias_pessoas_concede_a_cada_uma():
    _pessoa(VETERANA)
    _pessoa(VETERANO)
    _fundador()

    saida = _rodar(ids=f"{VETERANA},{VETERANO}", confirmo=True)

    assert "FEITO: 2 medalha(s) concedida(s)" in saida
    assert Concessao.objects.count() == 2
    assert MovimentoDeCristais.objects.count() == 2


# ------------------------------------------- 4. o coração: repetir é seguro


def test_rodar_duas_vezes_nao_concede_duas_vezes_nem_credita_de_novo():
    """O coração deste comando, e quem o garante é o BANCO, não o cuidado de quem roda.

    `Unique(pessoa, conquista)` dentro de `conceder()`. Uma segunda execução
    devolve a mesma linha, não credita Cristal de novo e não escreve segunda
    carta. É isto que permite a lista chegar em pedaços, e um id esquecido ser
    acrescentado amanhã sem ninguém precisar lembrar o que já rodou.
    """
    _pessoa(VETERANA)
    _fundador()

    primeira = _rodar(ids=VETERANA, confirmo=True)
    segunda = _rodar(ids=VETERANA, confirmo=True)

    assert "FEITO: 1 medalha(s) concedida(s)" in primeira
    assert "FEITO: 0 medalha(s) concedida(s), 1 já existia(m)" in segunda

    assert Concessao.objects.count() == 1
    assert MovimentoDeCristais.objects.count() == 1
    assert OutboxEvent.objects.count() == 1
    assert PerfilJogador.objects.get().cristais_saldo == 25


def test_a_segunda_rodada_alcanca_quem_faltava_sem_tocar_em_quem_ja_tinha():
    """A lista pode chegar em pedaços, que é como listas feitas por gente chegam."""
    _pessoa(VETERANA)
    _pessoa(VETERANO)
    _fundador()

    _rodar(ids=VETERANA, confirmo=True)
    segunda = _rodar(ids=f"{VETERANA},{VETERANO}", confirmo=True)

    assert "FEITO: 1 medalha(s) concedida(s), 1 já existia(m)" in segunda
    assert Concessao.objects.count() == 2
    assert PerfilJogador.objects.get(pessoa_id=VETERANA).cristais_saldo == 25
    assert PerfilJogador.objects.get(pessoa_id=VETERANO).cristais_saldo == 25


# ------------------------------------------- 5. quem o espelho não conhece


def test_id_desconhecido_e_reportado_e_nunca_vira_pessoa_inventada():
    """Fabricar uma `Pessoa` a partir de um id opaco exigiria fabricar um e-mail.

    E-mail fabricado é uma segunda verdade sobre quem é a pessoa, e ele
    sobreviveria à chegada da pessoa de verdade: a coluna é `unique`, então a
    linha real não conseguiria nascer depois. A pessoa aparece sozinha no
    primeiro XP ou na primeira visita, e aí basta rodar o comando de novo.
    """
    _pessoa(VETERANA)
    _fundador()

    saida = _rodar(ids=f"{VETERANA},{NINGUEM}", confirmo=True)

    assert "não conheço esta pessoa ainda" in saida
    assert "1 pessoa(s) fora do espelho local" in saida
    assert Pessoa.objects.count() == 1
    assert Concessao.objects.count() == 1
    assert Concessao.objects.get().pessoa_id == VETERANA


def test_ninguem_conhecido_na_lista_nao_e_erro_e_nao_escreve_nada():
    """Parcial (ou nada) é melhor que estourar: o comando é para ser re-executado."""
    _fundador()

    saida = _rodar(ids=NINGUEM, confirmo=True)

    assert "FEITO: 0 medalha(s) concedida(s)" in saida
    assert Concessao.objects.count() == 0
    assert Pessoa.objects.count() == 0


# ------------------------------------------- 6. a lista como uma pessoa a escreve


@pytest.mark.parametrize(
    "cruas, esperado",
    [
        (["a,b,c"], ["a", "b", "c"]),
        (["a", "b", "c"], ["a", "b", "c"]),
        (["a, b", "c"], ["a", "b", "c"]),
        (["a,a,b"], ["a", "b"]),
        (["", " , "], []),
        (None, []),
    ],
)
def test_a_lista_aceita_virgula_repeticao_e_espaco_e_nao_conta_duas_vezes(
    cruas, esperado
):
    """Quem monta a lista está copiando de uma planilha, não escrevendo código.

    E o repetido sai porque a saída do ensaio é o que o mantenedor lê para
    decidir: uma lista que conta a mesma pessoa duas vezes dá um número que não
    bate com a realidade, e número que não bate ensina a ignorar o relatório.
    """
    assert ids_pedidos(cruas) == esperado
