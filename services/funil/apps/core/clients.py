# apps/core/clients.py  # [RECEITA:R2 v1]
# Fala SÓ o que está nos contratos congelados de catalogo, leads e sugestoes.
# Em dev, aponte CATALOGO_API_URL/LEADS_API_URL/SUGESTOES_API_URL para os mocks
# prism (make mocks) — nunca suba a outra célula, nunca leia o banco dela.
import logging
import os

import httpx

logger = logging.getLogger("funil.sessao")


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


class SugestoesClient:
    """`contracts/sugestoes.openapi.yaml`, operação `getSession` — leitura pura.

    Lei do assunto: `docs/decisoes/DECISAO-onde-mora-a-sessao.md`. O site não lê
    o cookie de sessão: ele **pergunta** quem é o dono dele. O cookie é assinado
    com a chave da `sugestoes` e aponta para uma linha no banco DELA — o `funil`
    não tem chave nem banco (Lei 2, Lei 3). Perguntar é a única forma legal, e é
    também a que faz a identidade poder mudar de casa um dia sem que este
    arquivo mude: troca-se o endereço no env.

    **Duas credenciais viajam juntas, e provam coisas diferentes:**

    - o `Bearer` do par prova que **quem chama** é esta célula;
    - o `Cookie` repassado prova quem é **a pessoa** do outro lado do navegador.

    Nenhuma das duas substitui a outra, e o cookie **nunca** é interpretado
    aqui — ele é carregado de um lado para o outro, opaco.
    """

    TIMEOUT = 2.0

    def __init__(self) -> None:
        self.base = os.environ["SUGESTOES_API_URL"].rstrip("/")
        self.token = os.environ["TOKEN_SUGESTOES"]

    def obter_sessao(self, cookie: str) -> dict | None:
        """Quem é a pessoa desta requisição, ou `None`.

        **Falha ⇒ `None`, e isso é DELIBERADO** (DECISAO-onde-mora-a-sessao §4:
        *reconhecer não é autorizar*). Não conseguir perguntar significa que o
        site mostra "Entrar" e a página abre normal — a vitrine não pode cair
        porque a Caixa está reiniciando. É o oposto exato do
        `AlunosIndisponivel` da outra ponta, que fecha a porta quando não
        consegue perguntar: lá a resposta decide ACESSO, aqui decide um nome no
        canto da tela.

        Quem quiser autorizar alguma coisa um dia **não pode** partir daqui:
        autorização é fail-closed, na célula dona do recurso.

        Timeout curto (2s, contra os 5s do catálogo): isto está no caminho de
        alguém esperando uma página abrir, e a resposta certa para "demorou" é
        desistir depressa e mostrar "Entrar" — nunca pendurar a página.
        """
        try:
            r = httpx.get(
                f"{self.base}/sessao",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Cookie": cookie,
                },
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            # ERROR e não silêncio: fail-open é decisão de produto, não licença
            # para a Caixa cair sem ninguém saber (RETROSPECTIVA §1).
            logger.error("sessao: não deu para perguntar à sugestoes: %s", erro)
            return None

        if r.status_code != 200:
            logger.error("sessao: a sugestoes respondeu HTTP %s", r.status_code)
            return None

        corpo = r.json()
        # O contrato garante o campo; um corpo fora do contrato é tratado como
        # visitante, nunca como "provavelmente logado".
        if not isinstance(corpo, dict) or not corpo.get("autenticado"):
            return None
        return corpo
