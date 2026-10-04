"""Inclui matrículas no CRM usando os pares internos que o painel já possui."""

from .clients import AlunosClient, LeadsClient, http


def sincronizar(matricula_id="", site_id=""):
    matriculas = AlunosClient().alunos()
    if matriculas is None:
        raise RuntimeError("Não foi possível consultar os alunos para incluir no CRM")
    if matricula_id:
        matriculas = [
            m
            for m in matriculas
            if str(m.get("id")) == str(matricula_id)
            and str(m.get("site_id")) == str(site_id)
        ]
    cliente = LeadsClient()
    config = cliente._configuracao()
    if config is None:
        raise RuntimeError("A conexão do CRM com os contatos ainda não está disponível")
    base, token = config
    resposta = http().post(
        base + "/alunos/sincronizar",
        json={"matriculas": matriculas},
        headers={"Authorization": "Bearer " + token},
        timeout=30,
    )
    resposta.raise_for_status()
    return resposta.json()


def ao_matricula_situacao_alterada(envelope):
    data = envelope.get("data") or {}
    matricula_id, site_id = data.get("matricula_id"), data.get("site_id")
    if not matricula_id or not site_id:
        return None
    return sincronizar(matricula_id, site_id)
