"""Par interno da administração com a satisfação guardada na célula quiz."""

import os

import httpx

from .clients import http


class NPSClient:
    OK = "ok"
    SEM_CONFIGURACAO = "sem-configuracao"
    INDISPONIVEL = "indisponivel"
    RECUSADO = "recusado"

    def pedir(self, metodo, caminho, *, params=None, corpo=None):
        base = (os.environ.get("QUIZ_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("QUIZ_API_TOKEN") or "").strip()
        if not base or not token:
            return self.SEM_CONFIGURACAO, None
        if base.endswith("/interno"):
            base = base[:-len("/interno")]
        try:
            resposta = http().request(
                metodo, base + "/interno/nps/" + caminho,
                params=params, json=corpo,
                headers={"Authorization": "Bearer " + token}, timeout=5.0,
            )
        except httpx.HTTPError:
            return self.INDISPONIVEL, None
        try:
            dados = resposta.json()
        except ValueError:
            return self.INDISPONIVEL, None
        if resposta.status_code in (400, 403, 404, 409, 422):
            detalhe = dados.get("detail") if isinstance(dados, dict) else None
            return self.RECUSADO, detalhe if isinstance(detalhe, str) else "Dados recusados pela área de satisfação."
        if resposta.status_code not in (200, 201) or not isinstance(dados, dict):
            return self.INDISPONIVEL, None
        return self.OK, dados

    def configuracao(self, site_id):
        return self.pedir("GET", "config", params={"site_id": site_id})

    def salvar_configuracao(self, site_id, documento):
        return self.pedir("POST", "config", corpo={"site_id": site_id, "documento": documento})

    def historico(self, site_id, *, aluno_id="", email=""):
        params = {"site_id": site_id}
        if aluno_id:
            params["aluno_id"] = aluno_id
        elif email:
            params["email"] = email
        return self.pedir("GET", "historico", params=params)

    def salvar_atendimento(self, corpo):
        return self.pedir("POST", "atendimentos", corpo=corpo)
