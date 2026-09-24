from __future__ import annotations

import re
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from django.conf import settings

_MARGEM_EXPIRACAO_SEGUNDOS = 60
_TENTATIVAS_GET = 3
_ID_EXTERNO = re.compile(r"[1-9][0-9]*\Z")


def _id_externo_valido(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    return isinstance(value, str) and _ID_EXTERNO.fullmatch(value) is not None


class AppmaxError(Exception):
    """Falha segura Appmax, com indicação se um POST pode ter sido aceito."""

    def __init__(self, message: str, *, ambiguo: bool = False) -> None:
        super().__init__(message)
        self.ambiguo = ambiguo


class AppmaxClient:
    def __init__(self) -> None:
        self._client_id = settings.APPMAX_MERCHANT_CLIENT_ID
        self._client_secret = settings.APPMAX_MERCHANT_CLIENT_SECRET
        self._auth_url = self._validar_url_sandbox(
            settings.APPMAX_AUTH_URL,
            host="auth.sandboxappmax.com.br",
            path="/oauth2/token",
        )
        self._api_url = self._validar_url_sandbox(
            settings.APPMAX_API_URL,
            host="api.sandboxappmax.com.br",
            path="",
        )
        self._timeout = httpx.Timeout(connect=3.0, read=10.0, write=5.0, pool=3.0)
        self._token: str | None = None
        self._token_expira_em = 0.0
        self._token_lock = threading.Lock()

    def _autenticar(self) -> tuple[str, float]:
        if not self._client_id or not self._client_secret:
            raise AppmaxError(
                "credenciais merchant Appmax ausentes; configure "
                "APPMAX_MERCHANT_CLIENT_ID e APPMAX_MERCHANT_CLIENT_SECRET"
            )
        falha_rede: str | None = None
        try:
            response = httpx.post(
                self._auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._timeout,
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            falha_rede = "timeout ao autenticar na Appmax; tente novamente"
        except httpx.HTTPError:
            falha_rede = "falha de rede ao autenticar na Appmax; verifique a conexão e tente novamente"
        if falha_rede:
            raise AppmaxError(falha_rede)

        self._validar_status(response, "autenticação")
        payload = self._json_objeto(response, "autenticação")
        campos_ausentes = False
        try:
            token = payload["access_token"]
            expires_in = payload["expires_in"]
            token_type = payload["token_type"]
        except KeyError:
            campos_ausentes = True
            payload = {}
            token = ""
            expires_in = 0
            token_type = ""
        if campos_ausentes:
            raise AppmaxError(
                "resposta de autenticação Appmax incompleta; confira a integração"
            )
        tipo_bearer = token_type.lower() if isinstance(token_type, str) else ""
        if (
            not isinstance(token, str)
            or not token.strip()
            or token != token.strip()
            or tipo_bearer != "bearer"
        ):
            payload = {}
            token = ""
            raise AppmaxError(
                "resposta de autenticação Appmax incompleta; confira a integração"
            )
        if (
            isinstance(expires_in, bool)
            or not isinstance(expires_in, int)
            or expires_in <= 0
        ):
            payload = {}
            token = ""
            raise AppmaxError(
                "resposta de autenticação Appmax incompleta; confira a integração"
            )
        margem = min(_MARGEM_EXPIRACAO_SEGUNDOS, max(1, expires_in // 10))
        return token, time.monotonic() + max(0, expires_in - margem)

    def _obter_token(self) -> str:
        with self._token_lock:
            if self._token and time.monotonic() < self._token_expira_em:
                return self._token
            token, expira_em = self._autenticar()
            self._token = token
            self._token_expira_em = expira_em
            return token

    def preparar(self) -> None:
        self._obter_token()

    def _renovar_token(self, token_rejeitado: str) -> str:
        with self._token_lock:
            if self._token and self._token != token_rejeitado:
                return self._token
            token, expira_em = self._autenticar()
            self._token = token
            self._token_expira_em = expira_em
            return token

    def consultar_pedido(self, order_id: int) -> dict[str, Any]:
        if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id <= 0:
            raise AppmaxError(
                "ID do pedido Appmax inválido; informe um inteiro positivo"
            )
        url = f"{self._api_url}/v1/orders/{quote(str(order_id), safe='')}"
        token = self._obter_token()
        renovou = False
        repetiu_rate_limit = False
        repetiu_5xx = False

        for tentativa in range(_TENTATIVAS_GET):
            falha_rede: str | None = None
            try:
                response = httpx.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self._timeout,
                    follow_redirects=False,
                )
            except httpx.TimeoutException:
                falha_rede = "timeout ao consultar pedido Appmax; tente novamente"
            except httpx.HTTPError:
                falha_rede = "falha de rede ao consultar pedido Appmax; verifique a conexão e tente novamente"
            if falha_rede:
                raise AppmaxError(falha_rede)

            if response.status_code == 401:
                if renovou:
                    raise AppmaxError(
                        "credencial Appmax recusada após renovar o token; confira a instalação merchant"
                    )
                token = self._renovar_token(token)
                renovou = True
                continue

            if response.status_code == 429 and not repetiu_rate_limit:
                espera = self._retry_after(response)
                if espera is not None and espera <= 1.0:
                    time.sleep(espera)
                    repetiu_rate_limit = True
                    continue

            if response.status_code >= 500 and not repetiu_5xx:
                repetiu_5xx = True
                continue

            self._validar_status(response, "consulta de pedido")
            payload = self._json_objeto(response, "consulta de pedido")
            estrutura_invalida = False
            try:
                data = payload["data"]
                pedido = data["order"]
                recebido = pedido["id"]
                status = pedido["status"]
            except (KeyError, TypeError):
                estrutura_invalida = True
                payload = {}
                data = {}
                pedido = {}
                recebido = None
                status = None
            if estrutura_invalida:
                raise AppmaxError(
                    "resposta Appmax sem data.order.id ou data.order.status; "
                    "confira a API e tente novamente"
                )
            if (
                not isinstance(pedido, dict)
                or isinstance(recebido, bool)
                or not isinstance(recebido, (str, int))
                or str(recebido) != str(order_id)
                or not isinstance(status, str)
                or not status.strip()
            ):
                raise AppmaxError(
                    "resposta Appmax incompleta ou referente a outro pedido; confira o ID e tente novamente"
                )
            campos_relacionados = ("customer", "payment", "refund")
            if any(campo in pedido for campo in campos_relacionados):
                raise AppmaxError(
                    "resposta Appmax com estrutura de pedido adulterada; confira a API"
                )
            resultado = dict(pedido)
            for campo in campos_relacionados:
                if campo not in data:
                    continue
                relacionado = data[campo]
                if not isinstance(relacionado, dict):
                    raise AppmaxError(
                        f"resposta Appmax com {campo} inválido; confira a API"
                    )
                resultado[campo] = relacionado
            return resultado

        raise AppmaxError(
            "consulta de pedido Appmax excedeu as tentativas permitidas; tente novamente"
        )

    def consultar_parcelas(self, total_value: int) -> dict[str, Any]:
        if (
            isinstance(total_value, bool)
            or not isinstance(total_value, int)
            or total_value <= 0
        ):
            raise AppmaxError(
                "valor para cálculo de parcelas inválido; use centavos inteiros positivos"
            )
        payload = self._post(
            "/v1/payments/installments",
            {"installments": 12, "total_value": total_value, "settings": True},
            "cálculo de parcelas",
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise AppmaxError(
                "Appmax cálculo de parcelas: resposta incompleta; confira a API"
            )

        parcelas_em_centavos = False
        if "installments" in data and "parcels" not in data:
            parcelas = data["installments"]
            configuracao = data.get("settings")
            if not isinstance(parcelas, dict) or not isinstance(configuracao, dict):
                raise AppmaxError(
                    "Appmax cálculo de parcelas: resposta inválida; confira a API"
                )
            modalidade = configuracao.get("modality")
            limite = configuracao.get("max_installments")
            parcelas_em_centavos = True
        elif "parcels" in data and "installments" not in data:
            parcelas = data["parcels"]
            configuracao = data.get("settings")
            if not isinstance(parcelas, dict) or not isinstance(configuracao, dict):
                raise AppmaxError(
                    "Appmax cálculo de parcelas: resposta inválida; confira a API"
                )
            modalidade = configuracao.get("type")
            taxas = configuracao.get("settings")
            if not isinstance(taxas, dict) or not taxas:
                raise AppmaxError(
                    "Appmax cálculo de parcelas: resposta incompleta; confira a API"
                )
            limite = len(taxas)
            chaves_taxas = {str(numero) for numero in range(1, limite + 1)}
            if set(taxas) != chaves_taxas:
                raise AppmaxError(
                    "Appmax cálculo de parcelas: configuração inválida; confira a API"
                )
        else:
            raise AppmaxError(
                "Appmax cálculo de parcelas: resposta ambígua; confira a API"
            )
        if (
            modalidade != "PP"
            or isinstance(limite, bool)
            or not isinstance(limite, int)
            or not 1 <= limite <= 12
        ):
            raise AppmaxError(
                "Appmax cálculo de parcelas: configuração inválida; confira a API"
            )
        totais: dict[int, int] = {}
        for chave, valor in parcelas.items():
            try:
                numero = int(chave)
                total_bruto = valor["total"] if parcelas_em_centavos else valor
            except (ValueError, TypeError, KeyError):
                opcao_invalida = True
                numero = 0
                total = 0
            else:
                opcao_invalida = False
                if not parcelas_em_centavos:
                    if type(total_bruto) not in (int, float):
                        total = 0
                        opcao_invalida = True
                    else:
                        try:
                            total_decimal = Decimal(str(total_bruto))
                            total_centavos = total_decimal * 100
                        except (InvalidOperation, ValueError, TypeError):
                            total = 0
                            opcao_invalida = True
                        else:
                            if (
                                not total_decimal.is_finite()
                                or total_centavos != total_centavos.to_integral_value()
                            ):
                                total = 0
                                opcao_invalida = True
                            else:
                                total = int(total_centavos)
                else:
                    total = total_bruto
            if opcao_invalida:
                raise AppmaxError(
                    "Appmax cálculo de parcelas: opção inválida; confira a API"
                )
            if (
                str(numero) != str(chave)
                or not 1 <= numero <= limite
                or isinstance(total, bool)
                or not isinstance(total, int)
                or total < total_value
            ):
                raise AppmaxError(
                    "Appmax cálculo de parcelas: total inválido; confira a API"
                )
            totais[numero] = total
        if not totais:
            raise AppmaxError(
                "Appmax cálculo de parcelas: opções incompletas; confira a API"
            )
        return {"totals": totais, "modality": modalidade, "max_installments": limite}

    def criar_cliente(self, body: dict[str, Any]) -> dict[str, Any]:
        payload = self._post("/v1/customers", body, "criação de cliente")
        cliente: Any = {}
        try:
            cliente = payload["data"]["customer"]
            customer_id = cliente["id"]
        except (KeyError, TypeError):
            estrutura_invalida = True
            customer_id = None
        else:
            estrutura_invalida = False
        if estrutura_invalida or not isinstance(cliente, dict):
            raise AppmaxError(
                "Appmax criação de cliente: resposta incompleta; reconciliação necessária",
                ambiguo=True,
            )
        if not _id_externo_valido(customer_id):
            raise AppmaxError(
                "Appmax criação de cliente: identificador inválido; reconciliação necessária",
                ambiguo=True,
            )
        return {"id": str(customer_id)}

    def criar_pedido(self, body: dict[str, Any]) -> dict[str, Any]:
        payload = self._post("/v1/orders", body, "criação de pedido")
        try:
            pedido = payload["data"]["order"]
            order_id = pedido["id"]
            status = pedido["status"]
        except (KeyError, TypeError):
            estrutura_invalida = True
            pedido = {}
            order_id = None
            status = None
        else:
            estrutura_invalida = False
        if estrutura_invalida or not isinstance(pedido, dict):
            raise AppmaxError(
                "Appmax criação de pedido: resposta incompleta; reconciliação necessária",
                ambiguo=True,
            )
        if (
            not _id_externo_valido(order_id)
            or not isinstance(status, str)
            or not status.strip()
        ):
            raise AppmaxError(
                "Appmax criação de pedido: resposta inválida; reconciliação necessária",
                ambiguo=True,
            )
        return {"id": str(order_id), "status": status}

    def criar_pagamento_cartao(self, body: dict[str, Any]) -> dict[str, Any]:
        payload = self._post("/v1/payments/credit-card", body, "pagamento com cartão")
        data: Any = {}
        try:
            data = payload["data"]
            pagamento = data["payment"]
        except (KeyError, TypeError):
            estrutura_invalida = True
            pagamento = {}
        else:
            estrutura_invalida = False
        if (
            estrutura_invalida
            or not isinstance(data, dict)
            or not isinstance(pagamento, dict)
        ):
            raise AppmaxError(
                "Appmax pagamento com cartão: resposta incompleta; reconciliação necessária",
                ambiguo=True,
            )
        return payload

    def criar_pagamento_pix(self, body: dict[str, Any]) -> dict[str, str]:
        payload = self._post("/v1/payments/pix", body, "pagamento Pix")
        try:
            data = payload["data"]
            if "payment" in data:
                payment = data["payment"]
                imagem = payment["pix_qrcode"]
                codigo = payment["pix_emv"]
                vencimento = payment["pix_expiration_date"]
            else:
                payment = data["pix"]
                imagem = payment["qr_code"]
                codigo = payment["emv_code"]
                vencimento = payment["expires_at"]
        except (KeyError, TypeError):
            raise AppmaxError(
                "Appmax pagamento Pix: QR, código ou vencimento ausente; reconciliação necessária",
                ambiguo=True,
            ) from None
        if not all(
            isinstance(value, str) and value.strip()
            for value in (imagem, codigo, vencimento)
        ):
            raise AppmaxError(
                "Appmax pagamento Pix: QR, código ou vencimento inválido; reconciliação necessária",
                ambiguo=True,
            )
        prefixo = "data:image/png;base64,"
        if imagem.startswith(prefixo):
            imagem = imagem[len(prefixo) :]
        if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", imagem):
            raise AppmaxError(
                "Appmax pagamento Pix: imagem QR inválida; reconciliação necessária",
                ambiguo=True,
            )
        return {"qr_code_base64": imagem, "qr_code": codigo, "expires_at": vencimento}

    def _post(self, path: str, body: dict[str, Any], operacao: str) -> dict[str, Any]:
        token = self._obter_token()
        falha_rede: str | None = None
        try:
            response = httpx.post(
                f"{self._api_url}{path}",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self._timeout,
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            falha_rede = (
                f"timeout após enviar {operacao} Appmax; reconciliação necessária"
            )
        except httpx.HTTPError:
            falha_rede = f"falha de transporte após enviar {operacao} Appmax; reconciliação necessária"
        if falha_rede:
            raise AppmaxError(falha_rede, ambiguo=True)
        if response.status_code >= 500:
            raise AppmaxError(
                f"Appmax {operacao}: serviço indisponível (HTTP {response.status_code}); reconciliação necessária",
                ambiguo=True,
            )
        self._validar_status(response, operacao)
        resposta_invalida = False
        try:
            payload = self._json_objeto(response, operacao)
        except AppmaxError:
            resposta_invalida = True
            payload = {}
        if resposta_invalida:
            raise AppmaxError(
                f"Appmax {operacao}: resposta incompleta; reconciliação necessária",
                ambiguo=True,
            )
        return payload

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After", "")
        try:
            seconds = float(value)
        except ValueError:
            return None
        return seconds if seconds >= 0 else None

    @staticmethod
    def _validar_url_sandbox(url: str, *, host: str, path: str) -> str:
        if not AppmaxClient._url_sandbox_valida(url, host=host, path=path):
            url = ""
            raise AppmaxError(
                "URL Appmax inválida; use somente os endpoints HTTPS oficiais do sandbox"
            )
        return f"https://{host}{path}"

    @staticmethod
    def _url_sandbox_valida(url: str, *, host: str, path: str) -> bool:
        try:
            partes = urlsplit(url)
            valido = partes.scheme == "https"
            valido = valido and partes.netloc == host
            valido = valido and partes.path in (
                {path, path + "/"} if not path else {path}
            )
            valido = valido and not partes.username and not partes.password
            valido = valido and not partes.query and not partes.fragment
        except ValueError:
            return False
        return valido

    @staticmethod
    def _validar_status(response: httpx.Response, operacao: str) -> None:
        if 200 <= response.status_code < 300:
            return
        motivos = {
            400: "requisição recusada",
            401: "credencial recusada",
            404: "pedido ou endpoint não encontrado",
            422: "dados rejeitados",
            429: "limite de requisições excedido",
        }
        motivo = motivos.get(response.status_code)
        if motivo is None:
            motivo = (
                "serviço indisponível"
                if response.status_code >= 500
                else "resposta inesperada"
            )
        if response.status_code == 401:
            acao = "confira as credenciais merchant"
        elif response.status_code == 429:
            espera = AppmaxClient._retry_after(response)
            acao = (
                f"aguarde {espera:g} segundos antes de tentar novamente"
                if espera is not None
                else "aguarde antes de tentar novamente"
            )
        else:
            acao = "tente novamente"
        raise AppmaxError(
            f"Appmax {operacao}: {motivo} (HTTP {response.status_code}); {acao}"
        )

    @staticmethod
    def _json_objeto(response: httpx.Response, operacao: str) -> dict[str, Any]:
        invalido = False
        try:
            payload = response.json()
        except ValueError:
            invalido = True
            payload = {}
        if invalido:
            raise AppmaxError(
                f"Appmax {operacao}: resposta não é JSON (HTTP {response.status_code}); tente novamente"
            )
        if not isinstance(payload, dict):
            raise AppmaxError(
                f"Appmax {operacao}: resposta JSON inválida; confira a API e tente novamente"
            )
        return payload
