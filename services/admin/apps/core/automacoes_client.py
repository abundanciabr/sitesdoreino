"""Porta da Central de Automações WhatsApp, sem estado duplicado no admin."""
from urllib.parse import quote

from .clients import MensageriaClient


class AutomacoesClient(MensageriaClient):
    def listar(self, site_id):
        return self._ler("automacoes", {"site_id": site_id})

    def detalhe(self, site_id, slug, versao=None):
        parametros = {"site_id": site_id}
        if versao is not None:
            parametros["versao"] = versao
        return self._ler("automacoes/" + quote(slug, safe=""), parametros)

    def criar(self, corpo):
        return self._escrever("automacoes", corpo, publicando=True)

    def salvar(self, slug, corpo):
        return self._escrever("automacoes/" + quote(slug, safe=""), corpo, publicando=True)

    def acao(self, slug, corpo):
        return self._escrever("automacoes/" + quote(slug, safe="") + "/acao", corpo, publicando=True)

    def teste(self, slug, corpo):
        return self._escrever("automacoes/" + quote(slug, safe="") + "/teste", corpo, publicando=True)

    def inscrever(self, slug, corpo):
        return self._escrever("automacoes/" + quote(slug, safe="") + "/participantes", corpo, publicando=True)
