"""Estados de outras células para a escolha individual da escola.

Uma falha de rede aparece como indisponibilidade, nunca como portfólio vazio
ou como autorização. A decisão de autorizar continua exclusivamente local.
"""
from __future__ import annotations

import os
import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from types import SimpleNamespace
from urllib.parse import quote

import httpx
from django.db import transaction

from apps.core import sessao

logger = logging.getLogger(__name__)


def _consultar(url: str, token: str):
    try:
        resposta = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=3)
        if resposta.status_code == 404:
            return None
        resposta.raise_for_status()
        corpo = resposta.json()
        return corpo if isinstance(corpo, dict) else False
    except (httpx.HTTPError, ValueError):
        return False


def enriquecer_alunos(alunos: list, *, site_id: str) -> list:
    """Anota somente estados consultados; não modifica acesso ou matrícula."""
    pages_url = os.environ.get("PAGES_API_URL", "").rstrip("/")
    pages_token = os.environ.get("PAGES_API_TOKEN", "")
    jogo_url = os.environ.get("GAMIFICACAO_API_URL", "").rstrip("/")
    jogo_token = os.environ.get("GAMIFICACAO_API_TOKEN", "")
    for aluno in alunos:
        aluno.portfolio_situacao = "Indisponível"
        aluno.gamificacao_situacao = "Indisponível"
        if not aluno.pessoa_id:
            aluno.portfolio_situacao = "Sem conta no site"
            aluno.gamificacao_situacao = "Sem conta no site"
    if pages_url and pages_token:
        def portfolio_de(aluno):
            site = quote(str(site_id), safe="")
            pessoa = quote(str(aluno.pessoa_id), safe="")
            return _consultar(f"{pages_url}/portfolios/{site}/{pessoa}", pages_token)
        com_conta = [aluno for aluno in alunos if aluno.pessoa_id]
        with ThreadPoolExecutor(max_workers=8) as executor:
            estados = executor.map(portfolio_de, com_conta)
            for aluno, estado in zip(com_conta, estados):
                if estado is None:
                    aluno.portfolio_situacao = "Não iniciado"
                elif estado is not False:
                    etapa = estado.get("etapa_atual")
                    aluno.portfolio_situacao = (
                        "Conferido · etapa " + str(etapa) if estado.get("conferido_em") else
                        "Etapa " + str(etapa) if isinstance(etapa, int) else "Indisponível"
                    )
    if jogo_url and jogo_token:
        for inicio in range(0, len(alunos), 50):
            lote = [aluno for aluno in alunos[inicio:inicio + 50] if aluno.pessoa_id]
            if not lote:
                continue
            ids = ",".join(quote(str(aluno.pessoa_id), safe="") for aluno in lote)
            estados = _consultar(f"{jogo_url}/perfis?ids={ids}", jogo_token)
            if estados is False or estados is None:
                continue
            for aluno in lote:
                perfil = estados.get(str(aluno.pessoa_id))
                if perfil is None:
                    aluno.gamificacao_situacao = "Sem perfil"
                elif isinstance(perfil, dict) and isinstance(perfil.get("nivel"), int):
                    aluno.gamificacao_situacao = f"Nível {perfil['nivel']} · {perfil.get('titulo_slug', '')}"
    return alunos


def _matriculas_ativas(site_id: str) -> list[dict] | None:
    base = os.environ.get("ALUNOS_API_URL", "").rstrip("/")
    token = os.environ.get("ALUNOS_API_TOKEN", "")
    if not base or not token:
        return None
    try:
        resposta = httpx.get(f"{base}/matriculas", params={"site_id": site_id, "status": "ativa"},
                             headers={"Authorization": f"Bearer {token}"}, timeout=5)
        resposta.raise_for_status()
        dados = resposta.json()
        return dados if isinstance(dados, list) else None
    except (httpx.HTTPError, ValueError):
        logger.warning("não foi possível ler a lista de matrículas da escola", exc_info=True)
        return None


def alunos_para_selecao(*, site_id: str, perfis: list) -> list:
    """Matrículas atuais + perfis antigos, sem conceder autorização ou título."""
    matriculas = _matriculas_ativas(site_id)
    if matriculas is None:
        matriculas = []
        matriculas_indisponiveis = True
    else:
        matriculas_indisponiveis = False
    perfis_por_id = {str(perfil.pessoa_id): perfil for perfil in perfis}
    emails = list(dict.fromkeys(
        linha.get("email", "") for linha in matriculas
        if isinstance(linha, dict) and linha.get("site_id") == site_id and linha.get("email")
    ))
    def localizar(email):
        try:
            return sessao.pessoa_por_email(email)
        except (sessao.VizinhaIndisponivel, sessao.ConfiguracaoAusente):
            logger.warning("identidade indisponível ao localizar matrícula", exc_info=True)
            return None
    with ThreadPoolExecutor(max_workers=8) as executor:
        tarefas = [executor.submit(copy_context().run, localizar, email) for email in emails]
        pessoas = {email: tarefa.result() for email, tarefa in zip(emails, tarefas)}
    alunos = []
    vistos = set()
    emails_vistos = set()
    for linha in matriculas:
        if not isinstance(linha, dict) or linha.get("site_id") != site_id:
            continue
        email = linha.get("email", "")
        pessoa_id = pessoas.get(email)
        if not email or email in emails_vistos or (pessoa_id and pessoa_id in vistos):
            continue
        emails_vistos.add(email)
        if pessoa_id:
            vistos.add(pessoa_id)
        perfil = perfis_por_id.get(pessoa_id)
        alunos.append(SimpleNamespace(
            pessoa_id=pessoa_id or "", email=email,
            nome_exibido=linha.get("nome_completo") or pessoa_id or email,
            matricula_situacao="Ativa", perfil=perfil,
            perfil_situacao=("Perfil profissional existente" if perfil else
                             "Sem perfil profissional" if pessoa_id else "Conta não localizada no site"),
            disponibilidade_situacao=perfil.get_disponibilidade_display() if perfil else "Ainda fora da fila",
            titulo_situacao=perfil.get_titulo_banca_display() if perfil and perfil.titulo_banca else "Sem título técnico",
            entregas_aprovadas=perfil.entregas_aprovadas if perfil else None,
        ))
    for pessoa_id, perfil in perfis_por_id.items():
        if pessoa_id in vistos:
            continue
        alunos.append(SimpleNamespace(
            pessoa_id=pessoa_id, email="", nome_exibido=perfil.pessoa.nome_exibido or pessoa_id,
            matricula_situacao=("Matrículas indisponíveis" if matriculas_indisponiveis
                                else "Matrícula ativa não localizada"), perfil=perfil,
            perfil_situacao="Perfil profissional existente",
            disponibilidade_situacao=perfil.get_disponibilidade_display(),
            titulo_situacao=perfil.get_titulo_banca_display() if perfil.titulo_banca else "Sem título técnico",
            entregas_aprovadas=perfil.entregas_aprovadas,
        ))
    return enriquecer_alunos(alunos, site_id=site_id)


def preparar_perfil_sem_titulo(*, site_id: str, pessoa_id: str, email: str):
    """Gesto administrativo explícito para aluno real ainda sem perfil."""
    from apps.encomendas.models import PerfilProfissional, Pessoa
    if not email or sessao.categoria_na_escola(email) != sessao.CATEGORIA_DE_ALUNO:
        raise ValueError("este endereço não corresponde a aluno atual")
    resolvido = sessao.pessoa_por_email(email)
    if not resolvido or resolvido != pessoa_id:
        raise ValueError("identidade do aluno não confere")
    with transaction.atomic():
        Pessoa.objects.get_or_create(id_da_plataforma=pessoa_id)
        perfil, _ = PerfilProfissional.objects.get_or_create(
            pessoa_id=pessoa_id, site_id=site_id,
        )
    return perfil
