"""A central comercial usa o par administrativo já aceito pelo serviço de contatos."""
import httpx
from urllib.parse import quote

from .clients import LeadsClient, http


class CRMClient(LeadsClient):
    RECUSADO = "recusado"

    def pedir(self, metodo, caminho="", *, params=None, corpo=None):
        config = self._configuracao()
        if config is None:
            return self.SEM_CONFIGURACAO, None
        base, token = config
        try:
            resposta = http().request(
                metodo, base + "/crm" + caminho, params=params, json=corpo,
                headers={"Authorization": "Bearer " + token}, timeout=5.0,
            )
        except httpx.HTTPError:
            return self.NAO_RESPONDEU, None
        if resposta.status_code == 404:
            return self.NAO_EXISTE, None
        if resposta.status_code in (403, 409, 422):
            try:
                detalhe = resposta.json().get("detail")
            except (ValueError, AttributeError):
                detalhe = None
            return self.RECUSADO, detalhe if isinstance(detalhe, str) else "Não foi possível salvar esta alteração."
        if resposta.status_code not in (200, 201):
            return self.NAO_RESPONDEU, None
        try:
            dados = resposta.json()
        except ValueError:
            return self.NAO_RESPONDEU, None
        if not isinstance(dados, dict):
            return self.NAO_RESPONDEU, None
        return self.OK, dados

    def quadro(self, **filtros):
        estado, dados = self.pedir("GET", params={k: v for k, v in filtros.items() if v != ""})
        if estado == self.OK and (
            not isinstance(dados.get("itens"), list)
            or not isinstance(dados.get("resumo"), dict)
            or not isinstance(dados.get("total"), int)
        ):
            return self.NAO_RESPONDEU, None
        return estado, dados

    def oportunidade(self, chave):
        estado, dados = self.pedir("GET", "/" + quote(str(chave), safe=""))
        if estado == self.OK and (not dados.get("id") or not isinstance(dados.get("historico"), list)):
            return self.NAO_RESPONDEU, None
        return estado, dados

    def alterar(self, chave, metodo, gesto, corpo):
        return self.pedir(metodo, "/" + quote(str(chave), safe="") + gesto, corpo=corpo)
