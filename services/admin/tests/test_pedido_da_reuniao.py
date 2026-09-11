"""Pedido privado e autorização não são execução nem recebimento remoto."""

import datetime as dt
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import DatabaseError, connections, transaction

from apps.auditoria.models import Registro
from apps.core.models import Documento, VersaoDoDocumento
from apps.core import pedido_da_reuniao as pedidos

DONO = {"id": "dono-local", "email": "dono@exemplo.com"}
HOJE = dt.date(2026, 9, 9)


def criar(identidade=None, campos=None):
    identidade = identidade or uuid.uuid4()
    return pedidos.salvar_inicial(
        str(identidade),
        campos or {"decisoes": "Confirmar a meta."},
        HOJE,
        "alunos=3",
        DONO,
    )


def test_salva_privado_e_repete_sem_reinterpretar_foto_ou_data():
    ident = str(uuid.uuid4())
    doc, versao = criar(ident, {"tirar_foto": "sim"})
    repetido, outra = pedidos.salvar_inicial(
        ident, {"tirar_foto": "sim"}, HOJE + dt.timedelta(days=1), "alunos=999", DONO
    )
    assert (repetido.pk, outra.pk) == (doc.pk, versao.pk)
    assert not doc.publico and not versao.publico
    assert "09/09/2026" in doc.corpo and "alunos=3" in doc.corpo
    assert "999" not in doc.corpo
    assert doc.versoes.count() == 1
    assert Registro.objects.filter(alvo=doc.nome).count() == 1


def test_mesmo_uuid_com_outro_conteudo_e_conflito_sem_sobrescrever():
    ident = str(uuid.uuid4())
    doc, original = criar(ident)
    with pytest.raises(pedidos.ConflitoDoPedido):
        criar(ident, {"decisoes": "Outro gesto"})
    doc.refresh_from_db()
    assert doc.corpo == original.corpo and doc.versoes.count() == 1


@pytest.mark.parametrize("ponto", ["versao", "auditoria"])
def test_falha_entre_escritas_reverte_tudo(ponto):
    ident = str(uuid.uuid4())
    alvo = VersaoDoDocumento.objects if ponto == "versao" else Registro.objects
    with patch.object(alvo, "create", side_effect=DatabaseError("falha fictícia")):
        with pytest.raises(DatabaseError):
            criar(ident)
    assert not Documento.objects.filter(nome=pedidos.nome_do_pedido(ident)).exists()
    assert not Registro.objects.filter(alvo=pedidos.nome_do_pedido(ident)).exists()


def test_edicao_exige_versao_e_retry_reaproveita_efeito():
    doc, anterior = criar()
    atual = pedidos.editar(doc.nome, anterior.pk, "Texto revisado", DONO)
    assert pedidos.editar(doc.nome, anterior.pk, "Texto revisado", DONO).pk == atual.pk
    with pytest.raises(pedidos.ConflitoDoPedido):
        pedidos.editar(doc.nome, anterior.pk, "Outra revisão", DONO)
    assert doc.versoes.count() == 2


def test_autorizacao_explicita_da_versao_exata_e_idempotente():
    doc, versao = criar()
    assert pedidos.envelope_autorizado(doc, versao) is None
    primeiro = pedidos.autorizar(doc.nome, versao.pk, DONO, texto_exibido=versao.corpo)
    assert (
        pedidos.autorizar(doc.nome, versao.pk, DONO, texto_exibido=versao.corpo).pk
        == primeiro.pk
    )
    envelope = pedidos.envelope_autorizado(doc, versao)
    assert envelope["pedido"]["documento"] == doc.pk
    assert envelope["pedido"]["versao"] == versao.pk
    assert doc.corpo in envelope["tarefa"]["despacho"]
    assert (
        Registro.objects.filter(acao=Registro.AUTORIZAR_PEDIDO, alvo=doc.nome).count()
        == 1
    )
    nova = pedidos.editar(doc.nome, versao.pk, "Revisão sem autorização", DONO)
    doc.refresh_from_db()
    assert pedidos.envelope_autorizado(doc, nova) is None
    assert pedidos.envelope_autorizado(doc, versao) is None
    with pytest.raises(pedidos.ConflitoDoPedido):
        pedidos.autorizar(doc.nome, versao.pk, DONO, texto_exibido=versao.corpo)


@pytest.mark.parametrize("alteracao", ["corpo", "salvo_por", "documento"])
def test_versao_adulterada_nao_herda_autorizacao(alteracao):
    doc, versao = criar()
    pedidos.autorizar(doc.nome, versao.pk, DONO, texto_exibido=versao.corpo)
    valores = {
        "corpo": "Adulterado",
        "salvo_por": "outra@exemplo.com",
        "documento": criar()[0],
    }
    VersaoDoDocumento.objects.filter(pk=versao.pk).update(
        **{alteracao: valores[alteracao]}
    )
    versao.refresh_from_db()
    assert pedidos.envelope_autorizado(doc, versao) is None
    with pytest.raises(pedidos.ConflitoDoPedido):
        criar(doc.nome.removeprefix(pedidos.PREFIXO))


def test_edicao_e_autorizacao_revertem_se_auditoria_falha():
    doc, versao = criar()
    with patch.object(
        Registro.objects, "create", side_effect=DatabaseError("falha fictícia")
    ):
        with pytest.raises(DatabaseError):
            pedidos.editar(doc.nome, versao.pk, "Texto novo", DONO)
        with pytest.raises(DatabaseError):
            pedidos.autorizar(doc.nome, versao.pk, DONO, texto_exibido=versao.corpo)
    doc.refresh_from_db()
    assert doc.corpo == versao.corpo and doc.versoes.count() == 1
    assert pedidos.envelope_autorizado(doc, versao) is None


@pytest.mark.django_db(transaction=True, available_apps=["apps.core"])
@pytest.mark.parametrize("diferente", [False, True])
def test_concorrencia_inicial_tem_um_vencedor(diferente):
    ident = str(uuid.uuid4())
    barreira = Barrier(2)

    def gravar(n):
        connections.close_all()
        try:
            barreira.wait(timeout=10)
            return criar(ident, {"decisoes": f"Texto {n if diferente else 0}"})[1].pk
        except pedidos.ConflitoDoPedido:
            return "conflito"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(gravar, [0, 1]))
    assert len(set(resultados)) == (2 if diferente else 1)
    assert resultados.count("conflito") == int(diferente)
    assert (
        Documento.objects.filter(nome=pedidos.nome_do_pedido(ident))
        .get()
        .versoes.count()
        == 1
    )


import base64
import hashlib
import httpx
import respx
from django.test import Client
from django.urls import reverse
from apps.core import fila_no_github, reuniao
from tests.test_reuniao import _dentro, _a_escola_responde, ambiente, SESSAO, COOKIE


@pytest.fixture
def fonte_remota(request):
    doc, versao = criar()
    dados = pedidos.envelope(doc, versao)
    numero = getattr(request, "param", "987")
    tarefa_id = "TAR-" + numero
    chave = hashlib.sha256(("pedido:" + dados["pedido"]["id"]).encode()).hexdigest()
    reserva = {
        "numero": numero,
        "ramo": "agent/painel/reuniao",
        "superficie": "tarefa",
        "chave": chave,
        "pedido": dados["pedido"],
        "dia": "20260909",
        "criado_em": "2026-09-09T12:00:00+00:00",
    }
    stem = numero + "-pedido-da-reuniao-de-09-09-2026"
    evento = "20260909-120000-" + tarefa_id + "-explicada"
    tarefa = {
        "arquivo": stem,
        "id": tarefa_id,
        **dados["tarefa"],
        "pedido": dados["pedido"],
        "criada_em": "2026-09-09",
    }
    explicacao = {
        "arquivo": evento,
        "tarefa": tarefa_id,
        "evento": "explicada",
        "quando": reserva["criado_em"],
        "quem": dados["tarefa"]["origem"],
        **dados["explicacao"],
    }

    def arvore(path, sha, tipo="tree"):
        return {
            "path": path,
            "sha": sha * 40,
            "type": tipo,
            "mode": "040000" if tipo == "tree" else "100644",
        }

    def blob(valor, sha):
        bruto = (
            json.dumps(valor, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
        return {
            "sha": sha * 40,
            "encoding": "base64",
            "content": base64.b64encode(bruto).decode(),
        }

    respostas = {
        "/git/ref/chaves-numero/tarefa/"
        + chave: {
            "ref": "refs/chaves-numero/tarefa/" + chave,
            "object": {"type": "commit", "sha": "a" * 40},
        },
        "/git/commits/" + "a" * 40: {"sha": "a" * 40, "message": json.dumps(reserva)},
        "/git/ref/heads/agent/painel/reuniao": {
            "ref": "refs/heads/agent/painel/reuniao",
            "object": {"type": "commit", "sha": "b" * 40},
        },
        "/git/trees/" + "b" * 40: {"truncated": False, "tree": [arvore("fila", "c")]},
        "/git/trees/"
        + "c"
        * 40: {
            "truncated": False,
            "tree": [arvore("tarefas", "d"), arvore("eventos", "e")],
        },
        "/git/trees/"
        + "d" * 40: {"truncated": False, "tree": [arvore(stem + ".json", "f", "blob")]},
        "/git/trees/"
        + "e"
        * 40: {"truncated": False, "tree": [arvore(evento + ".json", "1", "blob")]},
        "/git/blobs/" + "f" * 40: blob(tarefa, "f"),
        "/git/blobs/" + "1" * 40: blob(explicacao, "1"),
        "/pulls": [],
    }
    return dados, reserva, respostas


def consultar(fonte, monkeypatch):
    dados, _, respostas = fonte
    monkeypatch.setenv("GITHUB_TOKEN_FILA", "somente-teste")

    def resposta(request):
        assert request.method == "GET"
        assert request.url.host == "api.github.com"
        caminho = request.url.path.removeprefix("/repos/abundanciabr/sitesdoreino")
        dado = respostas[caminho]
        if isinstance(dado, httpx.Response):
            return dado
        return httpx.Response(200, json=dado)

    with respx.mock(assert_all_called=False) as rotas:
        rotas.route(host="api.github.com").mock(side_effect=resposta)
        recibo = fila_no_github.consultar_recibo_reuniao(dados)
        assert len(rotas.calls) <= 32
        return recibo


def test_recibo_so_confirma_dois_artefatos_no_mesmo_sha(fonte_remota, monkeypatch):
    recibo = consultar(fonte_remota, monkeypatch)
    assert recibo.estado == "recebido" and recibo.tarefa == "TAR-987"
    assert recibo.revisao == "b" * 40 and len(recibo.artefatos) == 2
    assert not recibo.inicio


@pytest.mark.parametrize("fonte_remota", ["1000"], indirect=True)
def test_recibo_aceita_tarefa_com_quatro_digitos(fonte_remota, monkeypatch):
    recibo = consultar(fonte_remota, monkeypatch)
    assert recibo.estado == "recebido" and recibo.tarefa == "TAR-1000"


@respx.mock
def test_fila_indisponivel_explica_quando_acionar_o_robo(fonte_remota, monkeypatch):
    dados = fonte_remota[0]
    monkeypatch.setenv("GITHUB_TOKEN_FILA", "somente-teste")
    respx.get(host="api.github.com").mock(return_value=httpx.Response(503))
    recibo = fila_no_github.consultar_recibo_reuniao(dados)
    assert recibo.estado == "incerto"
    assert "Consulte novamente" in recibo.detalhe
    assert "consulta continuar indisponível, acione o robô" in recibo.detalhe


@pytest.mark.parametrize(
    "defeito",
    [
        "truncada",
        "duplicada",
        "falta_explicacao",
        "blob_divergente",
        "utf8",
        "sha",
        "reserva",
        "ramo",
        "redirecionamento",
        "paginacao",
        "data",
    ],
)
def test_fonte_incompleta_ou_adulterada_nunca_vira_recibo(
    fonte_remota, monkeypatch, defeito
):
    _, reserva, respostas = fonte_remota
    if defeito == "truncada":
        respostas["/git/trees/" + "e" * 40]["truncated"] = True
    if defeito == "duplicada":
        respostas["/git/trees/" + "d" * 40]["tree"].append(
            {
                "path": "987-outra.json",
                "sha": "2" * 40,
                "type": "blob",
                "mode": "100644",
            }
        )
    if defeito == "falta_explicacao":
        respostas["/git/trees/" + "e" * 40]["tree"] = []
    if defeito in ("blob_divergente", "utf8"):
        respostas["/git/blobs/" + "1" * 40]["content"] = base64.b64encode(
            b"{}" if defeito == "blob_divergente" else b"\xff"
        ).decode()
    if defeito == "sha":
        respostas["/git/blobs/" + "1" * 40]["sha"] = "2" * 40
    if defeito == "reserva":
        reserva["chave"] = "0" * 64
    if defeito == "ramo":
        reserva["ramo"] = "agent/../../secreto"
    if defeito == "data":
        reserva["dia"] = "20260908"
    respostas["/git/commits/" + "a" * 40]["message"] = json.dumps(reserva)
    if defeito == "redirecionamento":
        respostas["/git/trees/" + "b" * 40] = httpx.Response(
            302, headers={"Location": "https://outra.invalid/"}
        )
    if defeito == "paginacao":
        respostas["/pulls"] = httpx.Response(
            200, json=[], headers={"Link": '<https://api.github.com/next>; rel="next"'}
        )
    assert consultar(fonte_remota, monkeypatch).estado == "incerto"


def test_outra_versao_preserva_a_tarefa_reservada(fonte_remota, monkeypatch):
    _, reserva, respostas = fonte_remota
    reserva["pedido"] = {**reserva["pedido"], "versao": 9999}
    respostas["/git/commits/" + "a" * 40]["message"] = json.dumps(reserva)
    recibo = consultar(fonte_remota, monkeypatch)
    assert recibo.estado == "divergente" and recibo.tarefa == "TAR-987"
    assert not recibo.artefatos


def test_ramo_sumiu_confere_mesmos_bytes_na_main(fonte_remota, monkeypatch):
    respostas = fonte_remota[2]
    respostas["/git/ref/heads/agent/painel/reuniao"] = httpx.Response(404)
    respostas["/git/ref/heads/main"] = {
        "ref": "refs/heads/main",
        "object": {"type": "commit", "sha": "b" * 40},
    }
    assert consultar(fonte_remota, monkeypatch).estado == "recebido"


def test_recebimento_aceita_somente_crlf_como_variacao(fonte_remota, monkeypatch):
    blob = fonte_remota[2]["/git/blobs/" + "1" * 40]
    original = base64.b64decode(blob["content"])
    blob["content"] = base64.b64encode(original.replace(b"\n", b"\r\n")).decode()
    assert consultar(fonte_remota, monkeypatch).estado == "recebido"
    blob["content"] = base64.b64encode(original.replace(b"\n", b"\r")).decode()
    assert consultar(fonte_remota, monkeypatch).estado == "incerto"


@respx.mock
def test_tela_salvar_reabrir_autorizar_sem_enviar(monkeypatch):
    _a_escola_responde()
    cliente = _dentro()
    url = reverse("reuniao")
    formulario = cliente.get(url).context["formulario"]
    post = {"formulario": formulario, "decisoes": "Decisão privada"}
    resposta = cliente.post(url, post)
    assert resposta.status_code == 302
    assert cliente.post(url, post).url == resposta.url
    pagina = cliente.get(resposta.url)
    assert "Decisão privada" in pagina.content.decode()
    assert 'id="envelope"' not in pagina.content.decode()
    versao = pagina.context["versao"].pk
    assert (
        cliente.post(resposta.url, {"acao": "autorizar", "versao": versao}).status_code
        == 409
    )
    assert (
        cliente.post(
            resposta.url,
            {
                "acao": "autorizar",
                "versao": versao,
                "publicacao_publica": "sim",
                "texto": pagina.context["texto"],
            },
        ).status_code
        == 302
    )
    pagina = cliente.get(resposta.url)
    assert json.loads(pagina.context["envelope"])["pedido"]["versao"] == versao
    assert "Copiar não é recibo" in pagina.content.decode()
    assert all(c.request.method == "GET" for c in respx.calls)
    assert not any(c.request.url.host == "api.github.com" for c in respx.calls)
    assert cliente.get(pagina.context["documento"].endereco).status_code == 404
    assert cliente.get(resposta.url + "?autorizado=1&pr=123").context["recibo"] is None


@respx.mock
@pytest.mark.parametrize(
    ("rota", "metodo"),
    [
        ("doc_publico", "get"),
        ("documento_admin", "get"),
        ("documento_editar", "get"),
        ("documento_versoes", "get"),
        ("documento_salvar", "post"),
        ("documento_arquivar", "post"),
        ("documento_desarquivar", "post"),
        ("documento_restaurar", "post"),
        ("documento_apagar", "post"),
    ],
)
def test_pedido_privado_nao_abre_nem_muda_pela_biblioteca(rota, metodo):
    _a_escola_responde()
    cliente = _dentro()
    doc, versao = criar()
    Documento.objects.filter(pk=doc.pk).update(publico=True)
    url = reverse(rota, args=[doc.nome])
    dados = {
        "titulo": "Texto exposto",
        "corpo": "Não pode entrar",
        "versao": versao.pk,
        "confirmacao": doc.nome,
    }
    resposta = getattr(cliente, metodo)(url, dados)
    assert resposta.status_code == 404
    doc.refresh_from_db()
    assert doc.corpo == versao.corpo


@respx.mock
def test_pedido_privado_nao_aparece_nas_listas_da_biblioteca():
    _a_escola_responde()
    cliente = _dentro()
    doc, _ = criar()
    Documento.objects.filter(pk=doc.pk).update(publico=True)
    for rota in ("docs_publicos", "documentos_admin"):
        resposta = cliente.get(reverse(rota))
        assert resposta.status_code == 200
        assert doc.nome not in resposta.content.decode()


@respx.mock
def test_biblioteca_recusa_criar_no_prefixo_dos_pedidos():
    _a_escola_responde()
    cliente = _dentro()
    nome = pedidos.nome_do_pedido(str(uuid.uuid4()))
    resposta = cliente.post(
        reverse("documento_criar"),
        {"titulo": "Documento comum", "nome": nome, "corpo": "Texto"},
    )
    assert resposta.status_code == 422
    assert "reservado aos pedidos da reunião" in resposta.content.decode()
    assert not Documento.objects.filter(nome=nome).exists()


@respx.mock
def test_falha_de_gravacao_mantem_texto_e_identidade(monkeypatch):
    _a_escola_responde()
    cliente = _dentro()
    url = reverse("reuniao")
    formulario = cliente.get(url).context["formulario"]
    with patch.object(
        Registro.objects, "create", side_effect=DatabaseError("falha fictícia")
    ):
        pagina = cliente.post(
            url, {"formulario": formulario, "decisoes": "Não perder este texto"}
        )
    assert pagina.status_code == 503
    assert "Não perder este texto" in pagina.content.decode()
    assert pagina.context["formulario"] == formulario


@respx.mock
def test_csrf_e_porta_protegem_pedido_salvo():
    _a_escola_responde()
    cliente = _dentro()
    doc, versao = criar()
    url = reverse(
        "pedido_reuniao", kwargs={"identidade": doc.nome.removeprefix(pedidos.PREFIXO)}
    )
    seguro = Client(enforce_csrf_checks=True, HTTP_COOKIE=COOKIE)
    assert (
        seguro.post(
            url, {"acao": "autorizar", "versao": versao.pk, "publicacao_publica": "sim"}
        ).status_code
        == 403
    )
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    assert cliente.get(url).status_code == 302
    assert not Registro.objects.filter(
        alvo=doc.nome, acao=Registro.AUTORIZAR_PEDIDO
    ).exists()


@pytest.mark.django_db(transaction=True, available_apps=["apps.core"])
def test_edicao_concorrente_so_uma_versao_e_salva():
    doc, versao = criar()
    barreira = Barrier(2)

    def gravar(n):
        connections.close_all()
        try:
            barreira.wait(timeout=10)
            return pedidos.editar(doc.nome, versao.pk, f"Revisão {n}", DONO).pk
        except pedidos.ConflitoDoPedido:
            return "conflito"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(gravar, [0, 1]))
    assert resultados.count("conflito") == 1
    assert doc.versoes.count() == 2


def test_migracao_de_autorizacao_so_muda_estado_e_preserva_append_only():
    from importlib import import_module
    from django.db.migrations.operations.special import SeparateDatabaseAndState

    migracao = import_module(
        "apps.auditoria.migrations.0029_autorizar_pedido"
    ).Migration
    assert len(migracao.operations) == 1
    assert isinstance(migracao.operations[0], SeparateDatabaseAndState)
    assert migracao.operations[0].database_operations == []
    doc, versao = criar()
    registro = pedidos.autorizar(doc.nome, versao.pk, DONO, texto_exibido=versao.corpo)
    with pytest.raises(DatabaseError), transaction.atomic():
        Registro.objects.filter(pk=registro.pk).update(detalhe="adulteração")


def test_conclusao_legada_e_fila_antiga_nao_viram_aplicacao(
    fonte_remota, monkeypatch, tmp_path
):
    dados = fonte_remota[0]
    recibo = consultar(fonte_remota, monkeypatch)
    monkeypatch.setattr(reuniao.robos, "diretorio_da_fila", lambda: tmp_path)
    (tmp_path / "estados.json").write_text("{}", encoding="utf-8")
    assert "ainda não confirma" in reuniao._publicado(dados, recibo)["detalhe"]
    estado = {"TAR-987": {"estado": "concluída", "pedido": dados["pedido"]}}
    (tmp_path / "estados.json").write_text(json.dumps(estado), encoding="utf-8")
    resultado = reuniao._publicado(dados, recibo)
    assert (
        resultado["tarefa"] == "TAR-987"
        and resultado["situacao"] == "Conclusões registradas"
    )
    assert "não consegui confirmar os mesmos artefatos" in resultado["detalhe"]
    for caminho, bruto in recibo.artefatos:
        arquivo = tmp_path / caminho.removeprefix("fila/")
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_bytes(bruto)
    resultado = reuniao._publicado(dados, recibo)
    assert "também constam nesta cópia publicada" in resultado["detalhe"]
    assert "não comprova aqui a aplicação" in resultado["detalhe"]
    estado["TAR-986"] = estado["TAR-987"]
    (tmp_path / "estados.json").write_text(json.dumps(estado), encoding="utf-8")
    assert reuniao._publicado(dados, recibo)["erro"] is True


def test_fila_publicada_indisponivel_explica_quando_acionar_o_robo(monkeypatch):
    dados = pedidos.envelope(*criar())
    monkeypatch.setattr(reuniao.robos, "ler_estados", lambda _: None)
    resultado = reuniao._publicado(dados, None)
    assert "Consulte novamente" in resultado["detalhe"]
    assert "fila continuar indisponível, acione o robô" in resultado["detalhe"]


def test_inicio_exige_evento_da_mesma_tarefa(fonte_remota, monkeypatch):
    respostas = fonte_remota[2]
    arquivo = "20260909-130000-TAR-987-iniciada"
    evento = {
        "arquivo": arquivo,
        "tarefa": "TAR-987",
        "evento": "iniciada",
        "quando": "2026-09-09T13:00:00+00:00",
        "quem": "robo-ficticio",
    }
    respostas["/git/trees/" + "e" * 40]["tree"].append(
        {"path": arquivo + ".json", "sha": "2" * 40, "type": "blob", "mode": "100644"}
    )
    blob = {
        "sha": "2" * 40,
        "encoding": "base64",
        "content": base64.b64encode(json.dumps(evento).encode()).decode(),
    }
    respostas["/git/blobs/" + "2" * 40] = blob
    assert consultar(fonte_remota, monkeypatch).inicio == evento["quando"]
    evento["tarefa"] = "TAR-986"
    blob["content"] = base64.b64encode(json.dumps(evento).encode()).decode()
    assert consultar(fonte_remota, monkeypatch).estado == "incerto"


@respx.mock
def test_conflito_na_tela_nao_transforma_retry_em_sobrescrita():
    _a_escola_responde()
    cliente = _dentro()
    doc, versao = criar()
    url = reverse(
        "pedido_reuniao", kwargs={"identidade": doc.nome.removeprefix(pedidos.PREFIXO)}
    )
    pedidos.editar(doc.nome, versao.pk, "Texto vencedor", DONO)
    post = {"acao": "salvar", "versao": versao.pk, "texto": "Texto concorrente"}
    resposta = cliente.post(url, post)
    assert resposta.status_code == 409
    assert str(resposta.context["versao_editada"]) == str(versao.pk)
    assert "Texto concorrente" in resposta.content.decode()
    assert cliente.post(url, post).status_code == 409
    doc.refresh_from_db()
    assert doc.corpo == "Texto vencedor"


@pytest.mark.parametrize(
    "campos",
    [
        {"decisoes": "x" * 1001},
        {"compromisso1": "x" * 201},
        {"decisoes": "texto\x00"},
        {"tirar_foto": "nao"},
    ],
)
def test_campos_invalidos_nao_criam_metade_do_pedido(campos):
    identidade = str(uuid.uuid4())
    with pytest.raises(pedidos.ConflitoDoPedido, match="Confira os campos"):
        criar(identidade, campos)
    assert not Documento.objects.filter(
        nome=pedidos.nome_do_pedido(identidade)
    ).exists()


@respx.mock
def test_placar_ausente_mantem_campos_e_versao_invalida_explica_como_retomar(
    monkeypatch,
):
    cliente = _dentro()
    monkeypatch.setattr(
        reuniao, "montar_o_placar", lambda *args: {"recusas": ["meta ausente"]}
    )
    pagina = cliente.get(reverse("reuniao"))
    formulario = pagina.context["formulario"]
    with patch.object(
        Registro.objects, "create", side_effect=DatabaseError("falha fictícia")
    ):
        resposta = cliente.post(
            reverse("reuniao"),
            {"formulario": formulario, "decisoes": "Preservar sem placar"},
        )
    assert resposta.status_code == 503
    assert "Preservar sem placar" in resposta.content.decode()
    assert resposta.context["formulario"] == formulario
    doc, _ = criar()
    url = reverse(
        "pedido_reuniao", kwargs={"identidade": doc.nome.removeprefix(pedidos.PREFIXO)}
    )
    resposta = cliente.post(
        url, {"acao": "salvar", "versao": "xyz", "texto": "Preservar também"}
    )
    assert resposta.status_code == 409
    assert (
        "A versão enviada é inválida. Reabra o pedido salvo"
        in resposta.content.decode()
    )
    assert "Preservar também" in resposta.content.decode()


@pytest.mark.parametrize("campo", ["documento", "versao"])
@pytest.mark.parametrize("valor", [True, 1.0])
def test_identidade_remota_nao_aceita_booleano_ou_decimal_como_inteiro(
    fonte_remota, monkeypatch, campo, valor
):
    dados, reserva, respostas = fonte_remota
    dados["pedido"][campo] = 1
    reserva["pedido"] = {**dados["pedido"], campo: valor}
    respostas["/git/commits/" + "a" * 40]["message"] = json.dumps(reserva)
    blob = respostas["/git/blobs/" + "f" * 40]
    tarefa = json.loads(base64.b64decode(blob["content"]))
    tarefa["pedido"] = dados["pedido"]
    blob["content"] = base64.b64encode(
        (
            json.dumps(tarefa, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
    ).decode()
    assert consultar(fonte_remota, monkeypatch).estado == "divergente"


@pytest.mark.parametrize("valor", [True, 1.0])
def test_snapshot_nao_aceita_booleano_ou_decimal_como_identidade(
    fonte_remota, monkeypatch, tmp_path, valor
):
    dados = fonte_remota[0]
    dados["pedido"]["documento"] = 1
    estado = {
        "TAR-987": {
            "estado": "na fila",
            "pedido": {**dados["pedido"], "documento": valor},
        }
    }
    (tmp_path / "estados.json").write_text(json.dumps(estado), encoding="utf-8")
    monkeypatch.setattr(reuniao.robos, "diretorio_da_fila", lambda: tmp_path)
    assert reuniao._publicado(dados, None).get("erro") is True


@respx.mock
def test_conflito_so_autoriza_apos_reabrir_e_conferir_o_texto_vencedor():
    _a_escola_responde()
    cliente = _dentro()
    doc, anterior = criar()
    atual = pedidos.editar(doc.nome, anterior.pk, "SEGREDO VENCEDOR NAO EXIBIDO", DONO)
    url = reverse(
        "pedido_reuniao", kwargs={"identidade": doc.nome.removeprefix(pedidos.PREFIXO)}
    )
    perdedor = "TEXTO PERDEDOR EXIBIDO"
    resposta = cliente.post(
        url, {"acao": "salvar", "versao": anterior.pk, "texto": perdedor}
    )
    assert resposta.status_code == 409
    assert perdedor in resposta.content.decode()
    assert atual.corpo in resposta.content.decode()
    assert 'id="texto-salvo"' in resposta.content.decode()
    for versao in (anterior.pk, atual.pk):
        tentativa = cliente.post(
            url,
            {
                "acao": "autorizar",
                "versao": versao,
                "texto": perdedor,
                "publicacao_publica": "sim",
            },
        )
        assert tentativa.status_code == 409
    assert not Registro.objects.filter(
        acao=Registro.AUTORIZAR_PEDIDO, alvo=doc.nome
    ).exists()
    assert doc.versoes.count() == 2
    pagina = cliente.get(url)
    assert pagina.context["texto"] == atual.corpo
    assert (
        cliente.post(
            url,
            {
                "acao": "autorizar",
                "versao": atual.pk,
                "texto": pagina.context["texto"],
                "publicacao_publica": "sim",
            },
        ).status_code
        == 302
    )
    assert (
        json.loads(cliente.get(url).context["envelope"])["tarefa"]["despacho"]
        == atual.corpo
    )


@respx.mock
@pytest.mark.parametrize("texto", ["Edicao ainda nao salva", None])
def test_autorizacao_nao_aceita_edicao_nao_salva_ou_texto_ausente(texto):
    _a_escola_responde()
    cliente = _dentro()
    doc, versao = criar()
    url = reverse(
        "pedido_reuniao", kwargs={"identidade": doc.nome.removeprefix(pedidos.PREFIXO)}
    )
    post = {"acao": "autorizar", "versao": versao.pk, "publicacao_publica": "sim"}
    if texto is not None:
        post["texto"] = texto
    resposta = cliente.post(url, post)
    assert resposta.status_code == 409
    if texto:
        assert texto in resposta.content.decode()
    assert doc.versoes.count() == 1
    assert not Registro.objects.filter(
        acao=Registro.AUTORIZAR_PEDIDO, alvo=doc.nome
    ).exists()


@respx.mock
def test_autorizacao_com_resposta_perdida_retoma_so_o_mesmo_texto():
    _a_escola_responde()
    cliente = _dentro()
    doc, versao = criar()
    url = reverse(
        "pedido_reuniao", kwargs={"identidade": doc.nome.removeprefix(pedidos.PREFIXO)}
    )
    post = {
        "acao": "autorizar",
        "versao": versao.pk,
        "texto": versao.corpo,
        "publicacao_publica": "sim",
    }
    autorizar = pedidos.autorizar

    def perder_resposta(*args, **kwargs):
        autorizar(*args, **kwargs)
        raise DatabaseError("resposta perdida ficticia")

    with patch.object(pedidos, "autorizar", side_effect=perder_resposta):
        resposta = cliente.post(url, post)
    assert resposta.status_code == 503
    assert resposta.context["texto"] == versao.corpo
    assert cliente.post(url, post).status_code == 302
    assert (
        Registro.objects.filter(acao=Registro.AUTORIZAR_PEDIDO, alvo=doc.nome).count()
        == 1
    )
    atual = pedidos.editar(doc.nome, versao.pk, "Vencedor apos resposta perdida", DONO)
    assert cliente.post(url, post).status_code == 409
    assert pedidos.envelope_autorizado(doc, atual) is None
    assert doc.versoes.count() == 2


@respx.mock
@pytest.mark.parametrize("selecionada", [True, False])
def test_retry_sem_placar_preserva_foto_data_texto_e_selecao_originais(
    monkeypatch, selecionada
):
    from html.parser import HTMLParser

    class Formulario(HTMLParser):
        foto = False

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "input" and attrs.get("name") == "tirar_foto":
                self.foto = "checked" in attrs

    _a_escola_responde()
    cliente = _dentro()
    url = reverse("reuniao")
    monkeypatch.setattr(reuniao.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(
        reuniao,
        "montar_o_placar",
        lambda *a: {"mudancas": {"foto_de_hoje": "alunos=3"}},
    )
    formulario = cliente.get(url).context["formulario"]
    post = {"formulario": formulario, "decisoes": "Decisao a preservar"}
    if selecionada:
        post["tirar_foto"] = "sim"
    monkeypatch.setattr(
        reuniao.timezone, "localdate", lambda: HOJE + dt.timedelta(days=1)
    )
    monkeypatch.setattr(
        reuniao, "montar_o_placar", lambda *a: {"recusas": ["meta ausente"]}
    )
    with patch.object(
        Registro.objects, "create", side_effect=DatabaseError("falha ficticia")
    ):
        erro = cliente.post(url, post)
    assert erro.status_code == 503
    assert erro.context["formulario"] == formulario
    assert 'name="tirar_foto"' in erro.content.decode()
    assert (
        "Este pedido mantém a foto registrada quando você abriu a pauta."
        in erro.content.decode()
    )
    assert "alunos=3" not in erro.content.decode()
    campos = Formulario()
    campos.feed(erro.content.decode())
    assert campos.foto == selecionada
    retry = {
        "formulario": erro.context["formulario"],
        "decisoes": erro.context["campos"]["decisoes"],
    }
    if campos.foto:
        retry["tirar_foto"] = "sim"
    retorno = cliente.post(url, retry)
    assert retorno.status_code == 302
    salvo = Documento.objects.get(nome__startswith=pedidos.PREFIXO)
    esperado = reuniao.montar_o_pedido(post, HOJE, "alunos=3")
    assert salvo.corpo == esperado
    assert salvo.versoes.count() == 1
    assert ("alunos=3" in salvo.corpo) == selecionada


def fonte_integrada(fonte, apagado=False):
    from copy import deepcopy

    respostas = fonte[2]
    head = "4" * 40 if apagado else "b" * 40
    respostas["/pulls"] = [
        {
            "number": 123,
            "html_url": "https://github.com/abundanciabr/sitesdoreino/pull/123",
            "state": "closed",
            "merged_at": "2026-09-09T15:00:00Z",
            "merge_commit_sha": "3" * 40,
            "head": {
                "ref": "agent/painel/reuniao",
                "sha": head,
                "repo": {"full_name": "abundanciabr/sitesdoreino"},
            },
            "base": {"ref": "main", "repo": {"full_name": "abundanciabr/sitesdoreino"}},
        }
    ]
    respostas["/git/ref/heads/main"] = {
        "ref": "refs/heads/main",
        "object": {"type": "commit", "sha": "5" * 40},
    }
    for sha in ("3", "4", "5"):
        respostas["/git/trees/" + sha * 40] = deepcopy(
            respostas["/git/trees/" + "b" * 40]
        )
    respostas["/compare/" + "5" * 40 + "..." + "3" * 40] = {
        "status": "behind",
        "base_commit": {"sha": "5" * 40},
        "merge_base_commit": {"sha": "3" * 40},
    }
    if apagado:
        respostas["/git/ref/heads/agent/painel/reuniao"] = httpx.Response(404)
    return respostas


@pytest.mark.parametrize("apagado", [False, True])
def test_integracao_comprova_artefatos_no_pr_merge_e_historia_da_main(
    fonte_remota, monkeypatch, apagado
):
    fonte_integrada(fonte_remota, apagado)
    recibo = consultar(fonte_remota, monkeypatch)
    assert recibo.estado == "integrado" and recibo.pr == 123
    assert recibo.revisao == ("5" if apagado else "b") * 40
    assert len(recibo.artefatos) == 2


@pytest.mark.parametrize(
    "defeito",
    [
        "head",
        "merge_sem_artefatos",
        "main_ausente",
        "historia",
        "base",
        "ancestral",
        "head_apagado_sem_artefatos",
        "merge_bytes",
        "head_apagado_bytes",
    ],
)
def test_pr_com_mesmo_ramo_nao_promove_recibo_sem_prova_da_integracao(
    fonte_remota, monkeypatch, defeito
):
    respostas = fonte_integrada(fonte_remota, defeito.startswith("head_apagado"))
    comparacao = respostas["/compare/" + "5" * 40 + "..." + "3" * 40]
    if defeito == "head":
        respostas["/pulls"][0]["head"]["sha"] = "4" * 40
    if defeito == "merge_sem_artefatos":
        respostas["/git/trees/" + "3" * 40]["tree"] = []
    if defeito == "head_apagado_sem_artefatos":
        respostas["/git/trees/" + "4" * 40]["tree"] = []
    if defeito in ("merge_bytes", "head_apagado_bytes"):
        from copy import deepcopy

        sha = "4" if defeito == "head_apagado_bytes" else "3"
        respostas["/git/trees/" + sha * 40]["tree"][0]["sha"] = "8" * 40
        respostas["/git/trees/" + "8" * 40] = deepcopy(
            respostas["/git/trees/" + "c" * 40]
        )
        respostas["/git/trees/" + "8" * 40]["tree"][0]["sha"] = "9" * 40
        respostas["/git/trees/" + "9" * 40] = deepcopy(
            respostas["/git/trees/" + "d" * 40]
        )
        respostas["/git/trees/" + "9" * 40]["tree"][0]["sha"] = "2" * 40
        respostas["/git/blobs/" + "2" * 40] = {
            "sha": "2" * 40,
            "encoding": "base64",
            "content": base64.b64encode(b"outro pedido").decode(),
        }
    if defeito == "main_ausente":
        respostas["/git/ref/heads/main"] = httpx.Response(503)
    if defeito == "historia":
        comparacao["status"] = "diverged"
    if defeito == "base":
        comparacao["base_commit"]["sha"] = "6" * 40
    if defeito == "ancestral":
        comparacao["merge_base_commit"]["sha"] = "6" * 40
    recibo = consultar(fonte_remota, monkeypatch)
    assert recibo.estado == "recebido"
    assert "integração não foi confirmada" in recibo.detalhe.lower()
    assert len(recibo.artefatos) == 2 and recibo.pr == 123
