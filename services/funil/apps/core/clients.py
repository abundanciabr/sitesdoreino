# apps/core/clients.py  # [RECEITA:R2 v1]
# Fala SÓ o que está nos contratos congelados de catalogo e leads.
# Em dev, aponte CATALOGO_API_URL/LEADS_API_URL para os mocks prism
# (make mocks) — nunca suba a outra célula, nunca leia o banco dela.
import os

import httpx


class CatalogoClient:
    """contracts/catalogo.openapi.yaml (somente-leitura)."""

    def __init__(self) -> None:
        self.base = os.environ["CATALOGO_API_URL"].rstrip("/")
        self.token = os.environ["TOKEN_CATALOGO"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def obter_site_por_host(self, host: str) -> dict | None:
        """[INV-P11] 404 do catálogo é 'site desconhecido', nunca um site padrão."""
        r = httpx.get(
            f"{self.base}/sites/by-host/{host}",
            headers=self._headers(),
            timeout=5.0,  # timeout SEMPRE explícito
        )
        return r.json() if r.status_code == 200 else None

    def obter_oferta(self, site_id: str, slug: str) -> dict | None:
        """Slugs são únicos POR site — o site_id na rota é o que impede vazamento."""
        r = httpx.get(
            f"{self.base}/sites/{site_id}/ofertas/{slug}",
            headers=self._headers(),
            timeout=5.0,
        )
        return r.json() if r.status_code == 200 else None


class LeadsClient:
    """contracts/leads.openapi.yaml (somente-escrita, do ponto de vista do funil)."""

    def __init__(self) -> None:
        self.base = os.environ["LEADS_API_URL"].rstrip("/")
        self.token = os.environ["TOKEN_LEADS"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def upsert_lead(self, payload: dict) -> dict:
        r = httpx.post(
            f"{self.base}/leads",
            json=payload,
            headers=self._headers(),
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()
