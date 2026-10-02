# apps/core/clients.py  # [RECEITA:R2 v1]
"""Clientes HTTP das células `identidade` e `alunos`, com Bearer do par.
A configuração é lida no ponto de uso, nunca no import."""

import os
from urllib.parse import quote

import httpx

# Timeout explícito e curto: falha fechado depressa em vez de pendurar a página.
TIMEOUT = 5.0

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, reaproveitado entre chamadas."""
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(timeout=TIMEOUT)
    return _cliente


class ConfiguracaoAusente(RuntimeError):
    """Falta uma variável de ambiente que este caminho precisa."""


class IdentidadeIndisponivel(RuntimeError):
    """A `identidade` não respondeu ou respondeu fora do contrato.
    Fecha a participação; nunca vira "ninguém entrou"."""


class AlunosIndisponivel(RuntimeError):
    """A `alunos` não respondeu ou respondeu fora do contrato.
    Quem trata a exceção fecha a porta; nunca vira "deixa entrar"."""


def exigir(nome: str) -> str:
    """Lê uma variável de ambiente NO PONTO DE USO, ou falha fechado e alto."""
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise ConfiguracaoAusente(
            f"variável de ambiente ausente: {nome}. "
            "A entrada pela Caixa fica FECHADA até ela existir no env desta célula."
        )
    return valor


class IdentidadeClient:
    """`getSessionFull` da `identidade`: Bearer do par mais o cookie repassado opaco."""

    def sessao_completa(self, cookie: str) -> dict:
        """Quem é a pessoa desta requisição, ou `IdentidadeIndisponivel`.
        Visitante é `autenticado: false`; falha de rede ou de contrato é exceção."""
        base = exigir("IDENTIDADE_API_URL").rstrip("/")
        token = exigir("IDENTIDADE_API_TOKEN")
        try:
            resposta = http().get(
                f"{base}/sessao/completa",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Cookie": cookie,
                },
            )
        except httpx.RequestError as erro:
            raise IdentidadeIndisponivel(
                f"não deu para falar com a célula identidade: {erro}"
            ) from erro

        if resposta.status_code != 200:
            raise IdentidadeIndisponivel(
                f"a célula identidade respondeu HTTP {resposta.status_code}"
            )

        try:
            corpo = resposta.json()
        except ValueError as erro:
            # `200` com corpo que não é JSON (proxy, resposta truncada) fecha o caminho.
            raise IdentidadeIndisponivel(
                f"a célula identidade respondeu fora do contrato: {erro}"
            ) from erro

        if not isinstance(corpo, dict) or "autenticado" not in corpo:
            raise IdentidadeIndisponivel(
                "a célula identidade respondeu fora do contrato"
            )
        return corpo


class AlunosClient:
    """`listEnrollments` e `createPreEnrollment` da `alunos`, pela rede interna."""

    def situacao_de(self, email: str) -> str:
        """Categoria da pessoa na `alunos`, que decide a tela da porta.
        Qualquer erro sobe como `AlunosIndisponivel`."""
        base = exigir("ALUNOS_API_URL").rstrip("/")
        token = exigir("ALUNOS_API_TOKEN")
        try:
            resposta = http().get(
                f"{base}/alunos/{quote(email, safe='@')}/situacao",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as erro:
            raise AlunosIndisponivel(
                f"não deu para falar com a célula alunos: {erro}"
            ) from erro

        # Sem 404 aqui: quem a `alunos` não conhece volta como `cadastrado`, com 200.
        if resposta.status_code != 200:
            raise AlunosIndisponivel(
                f"a célula alunos respondeu HTTP {resposta.status_code}"
            )

        corpo = resposta.json()
        if not isinstance(corpo, dict) or not corpo.get("categoria"):
            raise AlunosIndisponivel(
                "a célula alunos respondeu fora do contrato (esperava a situação)"
            )
        return corpo["categoria"]

    def matriculas_de(self, email: str) -> list[dict]:
        """As matrículas deste e-mail; 404 vira lista vazia.
        Qualquer outro erro sobe como `AlunosIndisponivel`."""
        base = exigir("ALUNOS_API_URL").rstrip("/")
        token = exigir("ALUNOS_API_TOKEN")
        try:
            resposta = http().get(
                f"{base}/alunos/{quote(email, safe='@')}/matriculas",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as erro:
            raise AlunosIndisponivel(
                f"não deu para falar com a célula alunos: {erro}"
            ) from erro

        if resposta.status_code == 404:
            return []
        if resposta.status_code != 200:
            raise AlunosIndisponivel(
                f"a célula alunos respondeu HTTP {resposta.status_code}"
            )

        corpo = resposta.json()
        if not isinstance(corpo, list):
            raise AlunosIndisponivel(
                "a célula alunos respondeu fora do contrato (esperava uma lista)"
            )
        return corpo

    # -- a fila de liberação --

    NA_FILA = "na-fila"
    JA_TEM_MATRICULA = "ja-tem-matricula"

    def pedir_entrada_na_fila(
        self,
        *,
        site_id: str,
        email: str,
        nome_completo: str,
        whatsapp: str,
        comprou_em: str = "",
        turma: str = "",
    ) -> str:
        """Pede entrada (`createPreEnrollment`): `NA_FILA` ou `JA_TEM_MATRICULA`.
        Os opcionais só vão com valor; outra resposta é `AlunosIndisponivel`."""
        base = exigir("ALUNOS_API_URL").rstrip("/")
        token = exigir("ALUNOS_API_TOKEN")
        corpo = {
            "site_id": site_id,
            "email": email,
            "nome_completo": nome_completo,
            "whatsapp": whatsapp,
        }
        if comprou_em:
            corpo["comprou_em"] = comprou_em
        if turma:
            corpo["turma"] = turma

        try:
            resposta = http().post(
                f"{base}/pre-matriculas",
                json=corpo,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as erro:
            raise AlunosIndisponivel(
                f"não deu para falar com a célula alunos: {erro}"
            ) from erro

        if resposta.status_code in (200, 201):
            return self.NA_FILA
        if resposta.status_code == 409:
            return self.JA_TEM_MATRICULA
        # 422 também é falha nossa: a tela valida antes, e nada é dado como registrado.
        raise AlunosIndisponivel(
            f"a célula alunos respondeu HTTP {resposta.status_code} ao pedido de entrada"
        )
