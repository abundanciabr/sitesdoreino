"""Teste-guarda [INV-MET-P1]: o livro de fatos da `metricas` nunca recebe
dado pessoal.

Esta célula é um livro de fatos, não um cadastro. Um fato pode dizer QUE
alguém completou o quiz, escreveu no fórum ou virou aluna — sempre por um id
OPACO da plataforma, do jeito que `INV-P12`/`test_inv_metricas_nao_assina_sessao`
já garante para sessão. Ele nunca pode dizer o e-mail, o nome, o telefone ou o
CPF dessa pessoa: uma fila de eventos replicada, um log de consumidor preso e
um `EventoMorto` guardado para inspeção (`apps/fatos/recepcao.py`) são,
todos, lugares onde dado pessoal NÃO tem como ser apagado depois — e o
`event_id` já circulou por Redis Streams antes de chegar aqui.

A régua não é o código de recepção (que guarda o que chegar, de propósito —
ver o docstring de `consume_eventos.py`): é o CONTRATO. `receber()` grava o
envelope inteiro; a única cerca que existe é a `metricas` só assinar streams
cujo contrato NÃO declare campo pessoal em lugar nenhum do esquema. Por isso
este guarda lê `contracts/eventos/`, não o banco.

Lista de nomes de campo tratados como dado pessoal, em qualquer nível do
esquema (`properties`, dentro de `anyOf`/`oneOf`/`allOf`, dentro de `items` de
array, dentro de `$defs`/`definitions`): `customer`, `cliente`, `email`,
`e-mail`, `nome`, `name`, `telefone`, `phone`, `cpf`, `documento`, `endereco`,
`ip`.

**Achado real, registrado aqui e não escondido (armadilhas/INDICE.md e
`fila/tarefas/` têm a tarefa aberta):** `contracts/eventos/quiz.completado.v1.json`
declara `data.properties.lead` com `email`, `name` e `phone` — e
`eventos.quiz.completado` está em `STREAMS`
(`services/metricas/apps/fatos/management/commands/consume_eventos.py`,
degrau "A jornada de aprendizado (`quiz`)"). Isto é uma violação de verdade,
não uma bobagem do exemplo: enquanto ninguém abrir um Rito de Contrato para
tirar `lead` do esquema ou parar de assinar o assunto, este guarda fica
vermelho DE PROPÓSITO — `INVARIANTES.md` regra 2 proíbe afrouxar um
teste-guarda para passar, e a lista de campos acima não ganha exceção para
este caso.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.fatos.management.commands.consume_eventos import STREAMS

RAIZ_CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"

#: Nomes de campo tratados como dado pessoal, comparados em minúsculas.
CAMPOS_PESSOAIS = frozenset(
    {
        "customer",
        "cliente",
        "email",
        "e-mail",
        "nome",
        "name",
        "telefone",
        "phone",
        "cpf",
        "documento",
        "endereco",
        "ip",
    }
)


def assuntos_de(streams: list[str]) -> list[str]:
    """`"eventos.forum.topico-criado"` -> `"forum.topico-criado"` (nome do
    arquivo de contrato, sem o prefixo do envelope de stream)."""
    return [stream.removeprefix("eventos.") for stream in streams]


def esquemas_do_assunto(assunto: str, raiz: Path = RAIZ_CONTRATOS) -> list[Path]:
    """Todo arquivo de contrato congelado do assunto, em toda versão publicada
    (`assunto.v1.json`, `assunto.v2.json`, ...) — uma célula pode assinar mais
    de uma versão viva ao mesmo tempo, e cada uma precisa da mesma prova."""
    return sorted(raiz.glob(f"{assunto}.v*.json"))


def campos_pessoais_do_esquema(no: object, caminho: str = "") -> list[str]:
    """Caminho (`data.lead.email`) de cada propriedade do esquema cujo NOME
    é dado pessoal, percorrendo `properties`, `anyOf`/`oneOf`/`allOf`,
    `items` (objeto ou tupla) e `$defs`/`definitions` — em qualquer nível."""
    achados: list[str] = []
    if not isinstance(no, dict):
        return achados

    propriedades = no.get("properties")
    if isinstance(propriedades, dict):
        for chave, subesquema in propriedades.items():
            novo_caminho = f"{caminho}.{chave}" if caminho else chave
            if chave.strip().lower() in CAMPOS_PESSOAIS:
                achados.append(novo_caminho)
            achados.extend(campos_pessoais_do_esquema(subesquema, novo_caminho))

    for combinador in ("anyOf", "oneOf", "allOf"):
        for subesquema in no.get(combinador) or []:
            achados.extend(campos_pessoais_do_esquema(subesquema, caminho))

    itens = no.get("items")
    if isinstance(itens, dict):
        achados.extend(campos_pessoais_do_esquema(itens, f"{caminho}[]"))
    elif isinstance(itens, list):
        for subesquema in itens:
            achados.extend(campos_pessoais_do_esquema(subesquema, f"{caminho}[]"))

    for chave_defs in ("$defs", "definitions"):
        definicoes = no.get(chave_defs)
        if isinstance(definicoes, dict):
            for nome_def, subesquema in definicoes.items():
                achados.extend(
                    campos_pessoais_do_esquema(
                        subesquema, f"{caminho}#{chave_defs}.{nome_def}"
                    )
                )

    return achados


def violacoes_de(streams: list[str], raiz: Path = RAIZ_CONTRATOS) -> list[str]:
    """Uma mensagem por (assunto, arquivo, campo) que viola a regra — vazio
    quando `streams` está limpo. Núcleo do guarda, testável sem depender do
    `STREAMS` real (usado pela prova de mutação abaixo)."""
    mensagens: list[str] = []
    for assunto in assuntos_de(streams):
        esquemas = esquemas_do_assunto(assunto, raiz)
        if not esquemas:
            mensagens.append(
                f"{assunto}: nenhum esquema encontrado em contracts/eventos/ "
                f"({assunto}.v*.json) — sem contrato congelado não dá para "
                "provar que o stream não carrega dado pessoal."
            )
            continue
        for esquema_path in esquemas:
            esquema = json.loads(esquema_path.read_text(encoding="utf-8"))
            for achado in campos_pessoais_do_esquema(esquema):
                mensagens.append(
                    f"{assunto} ({esquema_path.name}): campo pessoal "
                    f"'{achado}'"
                )
    return mensagens


# --------------------------------------------------- o guarda sobre o STREAMS real


@pytest.mark.parametrize("assunto", assuntos_de(STREAMS))
def test_stream_assinado_tem_esquema_congelado(assunto: str) -> None:
    """Espelha `test_recepcao.test_o_consumidor_assina_so_o_que_tem_contrato_e_alguem_publica`,
    aqui como pré-condição da checagem de privacidade: sem esquema em disco,
    o campo abaixo não teria como ser conferido."""
    esquemas = esquemas_do_assunto(assunto)
    assert esquemas, (
        f"'{assunto}' está em STREAMS (consume_eventos.py) mas não tem "
        f"nenhum esquema '{assunto}.v*.json' em contracts/eventos/ — sem "
        "contrato congelado não há como provar que o stream não carrega "
        "dado pessoal. Congele o contrato antes de assinar, ou pare de "
        "assinar o assunto."
    )


@pytest.mark.parametrize("assunto", assuntos_de(STREAMS))
def test_stream_assinado_nao_tem_campo_pessoal_no_contrato(assunto: str) -> None:
    """O CORPO do guarda: nenhuma versão congelada de um assunto assinado tem,
    em qualquer nível do esquema, uma propriedade cujo nome é dado pessoal."""
    achados: list[str] = []
    for esquema_path in esquemas_do_assunto(assunto):
        esquema = json.loads(esquema_path.read_text(encoding="utf-8"))
        for caminho in campos_pessoais_do_esquema(esquema):
            achados.append(f"{esquema_path.name}: campo '{caminho}'")
    assert not achados, (
        f"'{assunto}' tem campo pessoal no contrato congelado: "
        f"{'; '.join(sorted(achados))}. A metricas assina este assunto "
        "(STREAMS em consume_eventos.py) — o livro de fatos não pode "
        "receber dado pessoal. Não afrouxe este guarda: abra um Rito de "
        "Contrato para tirar o campo do esquema, ou pare de assinar o "
        "assunto (fila/tarefas/)."
    )


# ------------------------------------------------------------- prova por mutação


def test_mutacao_stream_com_customer_e_pego() -> None:
    """Sem a checagem, `STREAMS + ["eventos.pedido.criado"]` passaria batido:
    `pedido.criado.v1.json` declara `data.customer` com `email`, `name` e
    `phone` obrigatórios (contrato do checkout — nunca assinado pela
    `metricas` hoje). Isto prova o guarda VERMELHO sobre uma cópia da lista,
    sem tocar `consume_eventos.py` (fora do alcance desta tarefa) nem o
    `STREAMS` real."""
    streams_mutados = list(STREAMS) + ["eventos.pedido.criado"]

    violacoes = violacoes_de(streams_mutados)

    assert any("customer" in v for v in violacoes), (
        "a mutação deveria ter sido pega: 'pedido.criado' leva 'customer' "
        f"(email/name/phone) e a checagem devolveu {violacoes!r}"
    )


def test_sem_a_mutacao_pedido_criado_nao_e_avaliado() -> None:
    """Contraprova: `pedido.criado` não é assinado hoje, então não entra na
    lista de assuntos avaliados pelo guarda real — a mutação acima É o que
    força a avaliação dele."""
    assert "pedido.criado" not in assuntos_de(STREAMS)
