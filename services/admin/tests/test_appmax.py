"""A vista Appmax lê o retrato publicado da fila sem criar outro estado."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import appmax, robos


DONO = "dono@exemplo.com"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
SESSAO = "http://identidade:8000/interno/sessao/completa"


@pytest.fixture
def fila_appmax(tmp_path, monkeypatch):
    pasta = tmp_path / "fila_embutida"
    (pasta / "tarefas").mkdir(parents=True)
    (pasta / "eventos").mkdir(parents=True)
    dados = {
        tarefa: {
            "estado": "na fila",
            "motivo": "sem registro",
            "quem": None,
        }
        for tarefa, _ in appmax.SEQUENCIA_APPMAX
    }
    dados.update(
        {
            "TAR-558": {
                "estado": "concluída",
                "motivo": "https://github.com/abundanciabr/sitesdoreino/pull/2002",
                "quem": "agent/admin/vista-appmax",
            },
            "TAR-559": {
                "estado": "cancelada",
                "motivo": "substituída pelo reconciliador",
                "quem": "fila",
            },
            "TAR-554": {
                "estado": "cancelada",
                "motivo": "escopo histórico cancelado",
                "quem": "fila",
            },
            "TAR-641": {
                "estado": "concluída",
                "motivo": "https://github.com/abundanciabr/sitesdoreino/pull/2097",
                "quem": "agent/admin",
            },
            "TAR-555": {
                "estado": "cancelada",
                "motivo": "substituída pela tela atual",
                "quem": "fila",
            },
            "TAR-560": {
                "estado": "bloqueada",
                "motivo": "esperando TAR-559",
                "quem": None,
            },
            "TAR-565": {
                "estado": "bloqueada",
                "motivo": "aguardando medição",
                "quem": "fila",
            },
            "TAR-566": {
                "estado": "bloqueada",
                "motivo": "esperando TAR-565",
                "quem": None,
            },
            "TAR-615": {
                "estado": "concluída",
                "motivo": "entrega=https://github.com/abundanciabr/sitesdoreino/pull/2012;publicacao=https://github.com/abundanciabr/sitesdoreino/actions/runs/36000000000",
                "quem": "agent/checkout/appmax-tela-cartao-real",
            },
            "TAR-731": {
                "estado": "concluída",
                "motivo": "aceite conferido",
                "quem": "agent/admin/vista-appmax",
            },
        }
    )
    raiz = Path(__file__).resolve().parents[3]
    for tarefa, _ in appmax.SEQUENCIA_APPMAX:
        candidatas = list((raiz / "fila" / "tarefas").glob(f"{tarefa[4:]}-*.json"))
        if not candidatas:
            continue
        origem = candidatas[0]
        documento = json.loads(origem.read_text(encoding="utf-8"))
        if tarefa == "TAR-560":
            documento["depende_de"] = ["TAR-559"]
        (pasta / "tarefas" / origem.name).write_text(
            json.dumps(documento, ensure_ascii=False), encoding="utf-8"
        )
    evento = next((raiz / "fila" / "eventos").glob("*-TAR-731-concluida.json"))
    (pasta / "eventos" / evento.name).write_bytes(evento.read_bytes())
    (pasta / "estados.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
    return pasta, dados


@pytest.fixture
def dentro(monkeypatch, settings):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={"autenticado": True, "email": DONO, "nome_exibido": "Dono"},
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


@respx.mock
def test_vista_appmax_mostra_sequencia_estado_dependencia_prova_e_fontes(
    fila_appmax, dentro
):
    resposta = dentro.get(reverse("appmax"))
    html = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Vista Appmax" in html
    assert "Retrato publicado" in html
    assert "Consulta viva" in html
    assert "TAR-558" in html
    assert "concluída" in html
    assert "TAR-559" in html
    assert "cancelada" in html
    assert "TAR-554" in html
    assert "TAR-641" in html
    assert "TAR-555" in html
    assert "TAR-560" in html
    assert "TAR-565" in html
    assert "TAR-566" in html
    assert "TAR-711" in html
    assert "TAR-735" in html
    assert "TAR-736" in html
    assert "TAR-739" in html
    assert "TAR-731" in html
    assert "TAR-730" in html
    assert "TAR-732" in html
    assert "TAR-641" in html
    assert "TAR-615" in html
    assert "Substituta" in html
    assert "<dt>Substituta</dt><dd>TAR-641</dd>" in html
    assert "<dt>Substituta</dt><dd>TAR-644</dd>" in html
    assert "<dt>Substituta</dt><dd>TAR-615</dd>" in html
    assert 'href="https://github.com/abundanciabr/sitesdoreino/pull/2002"' in html
    assert "PR #2002" in html
    assert 'href="https://github.com/abundanciabr/sitesdoreino/pull/2012"' in html
    assert "Publicação #36000000000" in html
    assert 'href="https://github.com/abundanciabr/sitesdoreino/pull/2097"' in html
    assert "data-consulta-viva" in html
    assert "/git/matching-refs/reservas" in html
    assert "Array.isArray(reservas)" in html
    cartao_560 = html.split('<p class="id-tarefa">TAR-560</p>', 1)[1].split("</li>", 1)[
        0
    ]
    assert "TAR-559" in cartao_560
    cartao_566 = html.split('<p class="id-tarefa">TAR-566</p>', 1)[1].split("</li>", 1)[
        0
    ]
    assert "TAR-565" in cartao_566
    assert "nenhuma impeditiva" not in cartao_566


@respx.mock
@pytest.mark.parametrize("metadado", ["ausente", "sem-id"])
def test_metadado_de_dependencia_ausente_e_nao_medido(fila_appmax, dentro, metadado):
    pasta, _ = fila_appmax
    arquivo = next((pasta / "tarefas").glob("566-*.json"))
    if metadado == "ausente":
        arquivo.unlink()
    else:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        dados.pop("id")
        arquivo.write_text(json.dumps(dados), encoding="utf-8")

    html = dentro.get(reverse("appmax")).content.decode()
    cartao_566 = html.split('<p class="id-tarefa">TAR-566</p>', 1)[1].split("</li>", 1)[
        0
    ]

    assert "não medido" in cartao_566
    assert "nenhuma impeditiva" not in cartao_566


@respx.mock
def test_vista_appmax_mostra_transicoes_apos_nova_leitura(fila_appmax, dentro):
    pasta, dados = fila_appmax
    dados["TAR-615"]["estado"] = "reivindicada"
    (pasta / "estados.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8"
    )
    primeira = dentro.get(reverse("appmax")).content.decode()
    assert "TAR-615" in primeira and "reivindicada" in primeira

    dados["TAR-615"]["estado"] = "bloqueada"
    dados["TAR-615"]["motivo"] = "aguardando prova"
    (pasta / "estados.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8"
    )
    segunda = dentro.get(reverse("appmax")).content.decode()
    assert "TAR-615" in segunda
    assert "bloqueada" in segunda
    assert "aguardando prova" in segunda

    dados["TAR-615"]["estado"] = "na fila"
    dados["TAR-615"]["motivo"] = "devolvida para a fila após a tentativa"
    (pasta / "estados.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8"
    )
    devolvida = dentro.get(reverse("appmax")).content.decode()
    assert "na fila" in devolvida
    assert "devolvida para a fila" in devolvida

    dados["TAR-615"]["estado"] = "concluída"
    dados["TAR-615"]["motivo"] = "aceite conferido"
    (pasta / "estados.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8"
    )
    terceira = dentro.get(reverse("appmax")).content.decode()
    assert "concluída" in terceira
    assert "aceite conferido" in terceira


@respx.mock
def test_fonte_ausente_vira_nao_medido_com_recarregar(tmp_path, monkeypatch, dentro):
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path / "ausente",))
    resposta = dentro.get(reverse("appmax"))
    html = re.sub(r"\s+", " ", resposta.content.decode())

    assert resposta.status_code == 200
    assert "não medido" in html
    assert "Recarregar" in html
    assert "Nenhuma tarefa Appmax encontrada" not in html


@respx.mock
def test_consulta_viva_falha_sem_apagar_retrato(fila_appmax, dentro):
    html = dentro.get(reverse("appmax")).content.decode()

    assert "retrato publicado" in html.lower()
    assert "consulta viva" in html.lower()
    assert "não medido" in html.lower()
    assert "recarregar" in html.lower()


def test_prova_de_conclusao_vem_do_evento_canonico(fila_appmax):
    # guarda: services/admin/apps/core/appmax.py:128
    pasta, dados = fila_appmax
    metadados, eventos = appmax._metadados_da_fila(pasta)
    cartao = appmax._tarefa("TAR-731", dados["TAR-731"], dados, metadados, eventos)
    assert cartao["provas"] == [
        {
            "url": "https://github.com/abundanciabr/sitesdoreino/pull/2097",
            "rotulo": "PR #2097",
        }
    ]


def test_dependencia_bloqueada_permanece_impeditiva(fila_appmax):
    # guarda: services/admin/apps/core/appmax.py:95
    pasta, dados = fila_appmax
    metadados, _ = appmax._metadados_da_fila(pasta)
    tarefa = {**metadados["TAR-566"], "depende_de": ["TAR-565", "TAR-558"]}
    assert appmax._dependencias(tarefa, dados) == (["TAR-565"], True)


@pytest.mark.parametrize(
    "tarefa", [None, {}, {"depende_de": "TAR-565"}, {"depende_de": ["TAR-999999"]}]
)
def test_dependencia_ausente_invalida_ou_desconhecida_nao_e_medida(tarefa):
    # guarda: services/admin/apps/core/appmax.py:97
    assert appmax._dependencias(tarefa, {}) == ([], False)


@respx.mock
@pytest.mark.parametrize(
    "cenario",
    [
        "normal",
        "vazio",
        "http",
        "json",
        "rede",
        "reservas-invalidas",
        "prs-invalidos",
        "sem-elementos",
    ],
)
def test_consulta_viva_executa_javascript_do_template(fila_appmax, dentro, cenario):
    html = dentro.get(reverse("appmax")).content.decode()
    script = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)[-1]
    node = shutil.which("node")
    assert (
        node
    ), "Node ausente: instale o runtime já usado pelo painel e rode novamente."
    programa = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const script = process.argv[1];
const cenario = process.argv[2];
let callback;
const urls = [];
const botao = {disabled: false, addEventListener: (nome, fn) => {assert.equal(nome, 'click'); callback = fn;}};
const status = {textContent: 'não medido'};
const bloco = {dataset: {url: 'https://api.github.com/repos/abundanciabr/sitesdoreino'}};
const contexto = {
  document: {
    querySelector: () => cenario === 'sem-elementos' ? null : bloco,
    getElementById: id => id === 'consultar-viva' ? botao : status
  },
  fetch: async url => {
    urls.push(url);
    if (cenario === 'rede') throw new Error('rede indisponível');
    const reserva = url.endsWith('/git/matching-refs/reservas');
    const prs = url.endsWith('/pulls?state=open&per_page=100');
    return {
      ok: (reserva || prs) && cenario !== 'http',
      json: async () => {
        if (cenario === 'json') throw new SyntaxError('JSON inválido');
        if ((reserva && cenario === 'reservas-invalidas') || (prs && cenario === 'prs-invalidos')) return {};
        if (cenario === 'vazio') return [];
        return reserva ? [{}, {}] : [{}, {}, {}];
      }
    };
  },
  Date
};
vm.runInNewContext(script, contexto);
(async () => {
  if (cenario === 'sem-elementos') {
    assert.equal(callback, undefined);
    return;
  }
  const execucao = callback();
  assert.equal(botao.disabled, true);
  assert.equal(status.textContent, 'medindo...');
  await execucao;
  assert.equal(botao.disabled, false);
  assert.equal(urls.length, 2);
  assert.ok(urls[0].endsWith('/git/matching-refs/reservas'));
  if (cenario === 'normal' || cenario === 'vazio') {
    assert.ok(status.textContent.startsWith('medido em '));
    const quantidade = cenario === 'normal' ? '2 referências de reserva e 3 PRs abertos.' : '0 referências de reserva e 0 PRs abertos.';
    assert.ok(status.textContent.endsWith(quantidade));
  } else {
    assert.ok(status.textContent.startsWith('não medido.'));
    assert.ok(status.textContent.includes('Recarregue'));
  }
})().catch(erro => {console.error(erro.message); process.exitCode = 1;});
"""
    resultado = subprocess.run(
        [node, "-e", programa, script, cenario],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert resultado.returncode == 0, resultado.stderr


@pytest.mark.parametrize("estado", [{}, {"estado": None}, {"estado": ""}])
def test_dependencia_sem_estado_publicado_nao_e_medida(estado):
    assert appmax._dependencias({"depende_de": ["TAR-565"]}, {"TAR-565": estado}) == (
        [],
        False,
    )
