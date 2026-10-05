"""Vendas do placar: matrículas reais de quem já era contato comercial."""

import httpx
from django.utils.dateparse import parse_datetime

from .clients import LeadsClient, http


def vinculos(pessoas, *, somente_origem=False):
    if not pessoas:
        return {}
    cliente = LeadsClient()
    config = cliente._configuracao()
    if config is None:
        return None
    base, token = config
    encontrados = {}
    for inicio in range(0, len(pessoas), 500):
        lote = [{k: p.get(k) for k in ("id", "site_id", "email", "virou_aluno_em")}
                for p in pessoas[inicio:inicio + 500]]
        try:
            resposta = http().post(
                base + "/alunos/vinculos-comerciais", json={"pessoas": lote, "somente_origem": somente_origem},
                headers={"Authorization": "Bearer " + token}, timeout=cliente.TIMEOUT,
            )
            resposta.raise_for_status()
            dados = resposta.json()["vinculos"]
            if not isinstance(dados, dict) or any(
                not isinstance(v, dict) or not v.get("contato_crm_id")
                or v.get("venda_origem") not in ("quiz", "trafego", "crm", "outros", "desconhecida") for v in dados.values()
            ):
                return None
            encontrados.update(dados)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None
    return encontrados


def para_o_placar(alunos):
    if alunos is None:
        return None
    candidatas = [a for a in alunos if a.get("origem") == "comprou"]
    contatos = vinculos(candidatas)
    if contatos is None:
        return None
    resultado = []
    vistos = set()
    def ordem(aluno):
        try:
            return parse_datetime(aluno.get("virou_aluno_em") or "").timestamp()
        except (ValueError, AttributeError, TypeError):
            return float("inf")
    for aluno in sorted(alunos, key=ordem):
        copia = dict(aluno)
        if copia.get("origem") == "comprou":
            contato = contatos.get(str(copia.get("id")))
            if contato is None:
                copia["origem"] = "sem-vinculo-comercial"
            else:
                copia["contato_crm_id"] = contato["contato_crm_id"]
                copia["venda_origem"] = copia.get("venda_origem") or contato["venda_origem"]
                pessoa = (copia.get("site_id"), contato["contato_crm_id"])
                if copia.get("status") in ("ativa", "suspensa", "encerrada"):
                    if pessoa in vistos:
                        copia["origem"] = "compra-repetida"
                    vistos.add(pessoa)
        resultado.append(copia)
    return resultado
