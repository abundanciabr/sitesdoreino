"""Traduz fatos confirmados das outras células para gatilhos da Central.

Somente IDs opacos atravessam esta ponte. Um evento sem destinatário certo não
dispara uma jornada; o texto do contato nunca vira uma afirmação de pagamento.
"""
from __future__ import annotations

import os
from urllib.parse import quote

import httpx

from apps.jornadas import central
from apps.jornadas.models import EnvioDeCheckpoint, Jornada


GATILHOS = (
    {"slug": "identidade.pessoa-cadastrada", "nome": "Cadastro concluído"},
    {"slug": "pagamento.aprovado", "nome": "Compra aprovada com contato confirmado"},
    {"slug": "matricula.ativa", "nome": "Matrícula ativa"},
    {"slug": "aula.concluida", "nome": "Aula concluída"},
    {"slug": "envio.recebido", "nome": "Atividade enviada"},
    {"slug": "checkpoint.devolvido", "nome": "Atividade devolvida"},
    {"slug": "gamificacao.nivel-alcancado", "nome": "Faixa alcançada"},
    {"slug": "gamificacao.conquista-concedida", "nome": "Conquista recebida"},
    {"slug": "gamificacao.marco-validado", "nome": "Marco validado"},
    {"slug": "forum.topico-criado", "nome": "Tópico publicado no Fórum"},
    {"slug": "forum.mensagem-criada", "nome": "Mensagem publicada no Fórum"},
    {"slug": "forum.resposta-aceita", "nome": "Resposta aceita no Fórum"},
    {"slug": "forum.resposta-criada", "nome": "Resposta recebida no Fórum"},
    {"slug": "mensagem.recebida", "nome": "Mensagem recebida no WhatsApp"},
)


def _pessoa_do_email(email: str) -> str:
    """Usa a consulta de identidade existente, sem reter ou registrar o e-mail."""
    if not email:
        return ""
    from apps.conversas.descadastro import _pessoa_por_email

    pessoa, _motivo = _pessoa_por_email(email)
    return pessoa or ""


def _contexto_do_prontuario(*, site_id: str, pessoa_id: str,
                           matricula_id: str = "") -> dict:
    """Nome e turma da passagem comprovada pela API já usada pela mensageria.

    Sem ID de matrícula, só uma única passagem ativa deste site é inequívoca.
    Não guarda e-mail, telefone ou o prontuário; falha de qualquer par deixa
    os campos ausentes para o motor diagnosticar no envio.
    """
    identidade = (os.environ.get("IDENTIDADE_API_URL") or "").strip().rstrip("/")
    token_identidade = (os.environ.get("IDENTIDADE_API_TOKEN") or "").strip()
    alunos = (os.environ.get("ALUNOS_API_URL") or "").strip().rstrip("/")
    token_alunos = (os.environ.get("ALUNOS_API_TOKEN") or "").strip()
    if not all((identidade, token_identidade, alunos, token_alunos, pessoa_id)):
        return {}
    try:
        resposta = httpx.post(
            f"{identidade}/pessoas/por-id", json={"id": pessoa_id},
            headers={"Authorization": f"Bearer {token_identidade}"}, timeout=5.0,
        )
        if resposta.status_code != 200:
            return {}
        pessoa = resposta.json()
        email = pessoa.get("email") if isinstance(pessoa, dict) else None
        if not isinstance(email, str) or not email:
            return {}
        resposta = httpx.get(
            f"{alunos}/alunos/{quote(email, safe='')}/prontuario",
            headers={"Authorization": f"Bearer {token_alunos}"}, timeout=5.0,
        )
        if resposta.status_code != 200:
            return {}
        prontuario = resposta.json()
    except (httpx.HTTPError, ValueError):
        return {}
    passagens = prontuario.get("passagens") if isinstance(prontuario, dict) else None
    if not isinstance(passagens, list):
        return {}
    candidatas = [
        passagem for passagem in passagens
        if isinstance(passagem, dict) and passagem.get("site_id") == site_id
        and passagem.get("status") == "ativa"
        and (not matricula_id or str(passagem.get("id") or "") == matricula_id)
    ]
    if len(candidatas) != 1:
        return {}
    passagem = candidatas[0]
    contexto = {"aluno_id": pessoa_id}
    for campo, origem in (
        ("nome", "nome_completo"), ("turma", "turma"),
        ("produto_id", "product_id"),
    ):
        valor = passagem.get(origem)
        if isinstance(valor, str) and valor.strip():
            contexto[campo] = valor.strip()[:160]
    return contexto


def _conversa_da_compra(*, site_id: str, dados: dict, cliente: dict):
    """Conversa WhatsApp só após CRM confirmar o mesmo comprador e site.

    O pagamento isolado não prova que um telefone pertence à identidade.
    Oportunidade do CRM com site, e-mail e telefone concordantes fornece essa
    ligação. Se já há conversa ligada a outro lead, não a reaproveita.
    """
    referencia = str(dados.get("oportunidade_ref") or "")
    if not referencia:
        return None, ""
    from apps.conversas import enderecos
    from apps.conversas.models import Conversa
    from apps.jornadas import crm

    email = enderecos.email(str(cliente.get("email") or ""))
    telefone = enderecos.telefone(str(cliente.get("phone") or ""))
    if not email or not telefone:
        return None, ""
    try:
        oportunidade = crm._oportunidade(referencia)
    except crm.CrmIndisponivel:
        return None, ""
    contato = oportunidade.get("contato") if isinstance(oportunidade, dict) else None
    if not isinstance(contato, dict):
        return None, ""
    lead_id = str(contato.get("id") or "")
    if (
        not lead_id or contato.get("site_id") != site_id
        or enderecos.email(str(contato.get("email") or "")) != email
        or enderecos.telefone(str(contato.get("telefone") or "")) != telefone
        or str(oportunidade.get("lead_id") or "") != lead_id
    ):
        return None, ""
    conversa, _ = Conversa.objects.get_or_create(
        site_id=site_id, canal="whatsapp", endereco=telefone,
        defaults={"lead_id": lead_id, "ligacao": "ligada"},
    )
    if conversa.ligacao != "ligada" or conversa.lead_id != lead_id:
        return None, ""
    return conversa, lead_id


def encaminhar_mensagem(mensagem, *, event_id) -> None:
    """Fala nova da conversa, com identidade de contato distinta da pessoa.

    O UUID da conversa é uma âncora de contato neste site, nunca um ID da
    identidade da plataforma. O despacho da Central usa a própria conversa.
    """
    conversa = mensagem.conversa
    if conversa.canal != "whatsapp" or mensagem.direcao != "entrada":
        return
    contato = str(conversa.id)
    central.inscrever_evento(
        gatilho="mensagem.recebida",
        site_id=conversa.site_id,
        destinatario_id=f"conversa:{contato}",
        event_id=event_id,
        contexto={"contato_id": contato, "conversa_id": contato},
        conversa=conversa,
        momento=mensagem.ocorrida_em,
    )


def encaminhar(envelope: dict) -> None:
    """Chamada após o handler legado, na mesma transação e sob a dedup do stream."""
    evento = str(envelope.get("event") or "")
    dados = envelope.get("data") or {}
    if not isinstance(dados, dict):
        return
    site_id = str(dados.get("platform_site_id") or dados.get("site_id") or "")
    event_id = envelope.get("event_id")
    if not site_id or not event_id:
        return

    destinatario = ""
    gatilho = evento
    contexto: dict = {}
    conversa = None
    ator = str(envelope.get("ator_id") or "")
    if evento == "identidade.pessoa-cadastrada":
        destinatario = str(dados.get("pessoa_id") or "")
    elif evento == "pagamento.aprovado":
        # Identidade é chamada só quando há automação ativa para este fato.
        if not Jornada.objects.filter(site_id=site_id, gatilho=evento, ativa=True).exists():
            return
        cliente = dados.get("customer") or {}
        if isinstance(cliente, dict):
            nome = cliente.get("name")
            if isinstance(nome, str) and nome.strip():
                contexto["nome"] = nome.strip()[:160]
            conversa, lead_id = _conversa_da_compra(
                site_id=site_id, dados=dados, cliente=cliente,
            )
            # Antes de a matrícula aparecer no prontuário, só o contato
            # confirmado no CRM prova a conversa certa. Sem ele, a carta
            # de matrícula ativa é o próximo fato endereçável.
            if conversa is None:
                return
            destinatario = _pessoa_do_email(str(cliente.get("email") or ""))
            if not destinatario:
                destinatario = f"conversa:{conversa.id}"
            contexto["contato_id"] = lead_id
    elif evento == "notificacao.devida":
        assunto = str(dados.get("assunto") or "")
        parametros = dados.get("parametros") or {}
        if not isinstance(parametros, dict):
            return
        if assunto == "matricula.situacao-alterada":
            if parametros.get("situacao_nova") != "ativa":
                return
            gatilho = "matricula.ativa"
            contexto = {"matricula_id": str(parametros.get("matricula_id") or "")}
        elif assunto in {
            "gamificacao.nivel-alcancado", "gamificacao.conquista-concedida",
            "gamificacao.marco-validado",
        }:
            gatilho = assunto
        else:
            return
        destinatario = str(dados.get("destinatario_id") or "")
        if destinatario and gatilho == "matricula.ativa":
            contexto["aluno_id"] = destinatario
    elif evento in {"aula.concluida", "envio.recebido"}:
        destinatario = ator
        contexto = {
            "aluno_id": ator,
            "curso_id": str(dados.get("curso_id") or ""),
            "aula_id": str(dados.get("aula_id") or ""),
            "progresso": (
                "bloco concluído" if dados.get("e_boss") is True else "aula concluída"
            ) if evento == "aula.concluida" else "atividade enviada",
        }
        for campo, origem in (
            ("produto_id", "produto_id"), ("curso", "curso_nome"),
            ("aula", "aula_titulo"),
        ):
            valor = dados.get(origem)
            if isinstance(valor, str) and valor.strip():
                contexto[campo] = valor.strip()
    elif evento == "checkpoint.devolvido":
        envio = EnvioDeCheckpoint.objects.filter(
            site_id=site_id, envio_id=str(dados.get("envio_id") or "")
        ).first()
        destinatario = envio.aluno_id if envio else ""
        contexto = {
            "aluno_id": destinatario,
            "aula_id": str(dados.get("aula_id") or ""),
            "progresso": "atividade devolvida para ajustes",
        }
    elif evento in {"forum.topico-criado", "forum.mensagem-criada"}:
        # Estes são acontecimentos do autor da publicação, nunca um aviso
        # de que outra pessoa lhe respondeu.
        destinatario = ator
        contexto = {"topico_id": str(dados.get("topico_id") or "")}
    elif evento == "forum.resposta-aceita":
        destinatario = str(dados.get("autor_da_resposta_id") or "")
        contexto = {"topico_id": str(dados.get("topico_id") or "")}
    elif evento == "forum.resposta-criada":
        # Um evento dedicado identifica quem recebeu a resposta. O evento
        # forum.mensagem-criada identifica apenas quem escreveu, por isso não vale.
        destinatario = str(dados.get("destinatario_id") or "")
        link = str(dados.get("link") or "")
        if not link.startswith("https://"):
            return
        contexto = {
            "topico_id": str(dados.get("topico_id") or ""),
            "curso_id": str(dados.get("curso_id") or ""),
            "link": link,
        }
    else:
        return
    if not destinatario:
        return
    # As cartas de conquista podem pertencer a alguém sem matrícula; o ID de
    # identidade sozinho não é prova de que a pessoa é aluna deste site.
    if gatilho in {
        "matricula.ativa", "aula.concluida", "envio.recebido",
        "checkpoint.devolvido", "gamificacao.nivel-alcancado",
        "gamificacao.conquista-concedida", "gamificacao.marco-validado",
    } and Jornada.objects.filter(site_id=site_id, gatilho=gatilho, ativa=True).exists():
        confirmado = _contexto_do_prontuario(
            site_id=site_id, pessoa_id=destinatario,
            matricula_id=contexto.get("matricula_id", "") if gatilho == "matricula.ativa" else "",
        )
        for campo, valor in confirmado.items():
            if not contexto.get(campo):
                contexto[campo] = valor
    central.inscrever_evento(
        gatilho=gatilho,
        site_id=site_id,
        destinatario_id=destinatario,
        event_id=event_id,
        contexto=contexto,
        conversa=conversa,
    )
