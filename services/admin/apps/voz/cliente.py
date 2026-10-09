"""A porta de áudio da mensageria (`/api/mensageria/audio/...`).

Mesmo par do `MensageriaClient` (MENSAGERIA_API_URL/MENSAGERIA_API_TOKEN). O
admin não lê o banco da mensageria: pergunta por aqui. `None` = não deu.
"""
from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from apps.core.clients import MensageriaClient, http

log = logging.getLogger(__name__)
TIMEOUT = 60.0


class MensageriaAudio:
    def ligado(self) -> bool:
        return MensageriaClient()._configuracao() is not None

    def _pedir(self, metodo: str, caminho: str, corpo: dict | None = None, params: dict | None = None):
        config = MensageriaClient()._configuracao()
        if config is None:
            return None
        base, token = config
        try:
            resposta = http().request(
                metodo, base + "/audio/" + caminho, json=corpo, params=params,
                headers={"Authorization": "Bearer " + token}, timeout=TIMEOUT,
            )
        except httpx.HTTPError as erro:
            log.warning("audio: a mensageria não respondeu (%s)", type(erro).__name__)
            return None
        if resposta.status_code != 200:
            log.warning("audio: a mensageria respondeu HTTP %s em %s", resposta.status_code, caminho.split("/")[-1])
            return None
        try:
            dados = resposta.json()
        except ValueError:
            return None
        return dados if isinstance(dados, dict) else None

    @staticmethod
    def _site(site_id: str) -> str:
        return quote(str(site_id), safe="")

    def pendentes(self, limite: int = 10) -> list[dict] | None:
        dados = self._pedir("GET", "pendentes", params={"limite": limite})
        return dados.get("audios") if dados and isinstance(dados.get("audios"), list) else None

    def conteudo(self, site_id: str, audio_id: int) -> dict | None:
        return self._pedir("GET", f"{self._site(site_id)}/{int(audio_id)}/conteudo")

    def guardar_transcricao(self, site_id: str, audio_id: int, corpo: dict) -> dict | None:
        return self._pedir("POST", f"{self._site(site_id)}/{int(audio_id)}/transcricao", corpo)

    def anotar_falha(self, site_id: str, audio_id: int, erro: str, definitiva: bool = False) -> dict | None:
        return self._pedir("POST", f"{self._site(site_id)}/{int(audio_id)}/falha",
                           {"erro": erro[:300], "definitiva": definitiva})

    def transcricoes(self, site_id: str, *, telefone: str = "", conversa_ref: str = "", desde_id: int = 0):
        dados = self._pedir("POST", f"{self._site(site_id)}/transcricoes",
                            {"telefone": telefone, "conversa_ref": conversa_ref}, params={"desde_id": desde_id})
        return dados.get("audios") if dados and isinstance(dados.get("audios"), list) else None

    def formato(self, site_id: str, telefone: str, canal: str = "whatsapp") -> dict | None:
        return self._pedir("POST", f"{self._site(site_id)}/formato", {"telefone": telefone, "canal": canal})

    def destino_da_conversa(self, site_id: str, conversa_ref: str) -> dict | None:
        return self._pedir("POST", f"{self._site(site_id)}/destino-da-conversa", {"conversa_ref": conversa_ref})

    def definir_preferencia(self, site_id: str, telefone: str, modo: str) -> dict | None:
        return self._pedir("POST", f"{self._site(site_id)}/preferencia", {"telefone": telefone, "modo": modo})

    def responder_em_voz(self, site_id: str, corpo: dict) -> dict | None:
        return self._pedir("POST", f"{self._site(site_id)}/responder-em-voz", corpo)

    def consumo(self, site_id: str, *, telefone: str = "", conversa_ref: str = "") -> dict | None:
        return self._pedir("POST", f"{self._site(site_id)}/consumo", {"telefone": telefone, "conversa_ref": conversa_ref})
