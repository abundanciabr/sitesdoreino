"""Rastreio privado do próprio trabalho; não consulta outros domínios ou chats."""
from __future__ import annotations

import hashlib
import json

from .super_equipe_perfis import PERFIS

VERSAO = "1"
SINTESE = "sintese_nicole"
LIMITE_TEXTO = 12000


def digest(valor):
    return hashlib.sha256(json.dumps(valor, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


def compactar_contexto(contexto):
    """Remove apenas cópias comprovadamente presentes na mesma fotografia."""
    def tamanho(valor):
        return len(json.dumps(valor, ensure_ascii=False, default=str).encode())

    antes = tamanho(contexto)
    confronto = contexto.get("confronto", {})
    fontes_confronto = confronto.get("fontes_para_confronto", {})
    fontes = dict(contexto.get("fontes", {}))
    referencias = {}
    for nome, valor in list(fontes.items()):
        if nome in fontes_confronto and valor == fontes_confronto[nome]:
            del fontes[nome]
            referencias[nome] = f"confronto.fontes_para_confronto.{nome}"
    anteriores = fontes.get("resultados_anteriores")
    pares = {par["perfil"]: par.get("texto", "")
             for par in confronto.get("pares_do_proprio_trabalho", [])}
    if anteriores and all(isinstance(texto, str) and codigo in pares
                          and pares[codigo].startswith(texto)
                          for codigo, texto in anteriores.items()):
        del fontes["resultados_anteriores"]
        referencias["resultados_anteriores"] = "confronto.pares_do_proprio_trabalho (por perfil)"
    compacto = {**contexto, "fontes": fontes}
    if referencias:
        compacto["fontes_reutilizadas_nesta_entrada"] = referencias
    depois = tamanho(compacto)
    if depois >= antes:
        compacto, depois, referencias = contexto, antes, {}
    return compacto, {"bytes_antes": antes, "bytes_enviados": depois,
                      "bytes_repetidos_evitados": antes - depois,
                      "fontes_reutilizadas": list(referencias),
                      "limite": "Mesma fotografia, sem corte de fatos; bytes não são tokens nem tempo poupado."}


def material(estado, digest_fontes, limpar):
    """Só resultados da fotografia atual, sem recuperar fontes revogadas."""
    pares, excluidos = [], []
    for codigo, resultado in estado.get("resultados", {}).items():
        if codigo not in PERFIS:
            continue
        valido = resultado.get("fontes_digest") == digest_fontes or (
            not estado.get("fontes_anteriores") and not resultado.get("fontes_digest"))
        if not valido:
            excluidos.append(codigo)
            continue
        texto = limpar(resultado.get("texto", ""))
        pares.append({"perfil": codigo, "versao_perfil": estado.get("versoes_perfil", {}).get(codigo),
                      "texto": texto[:LIMITE_TEXTO], "caracteres_originais": len(texto),
                      "truncado": len(texto) > LIMITE_TEXTO,
                      "fontes_digest": resultado.get("fontes_digest"),
                      "concluido_em": resultado.get("concluido_em"),
                      "rastreio": resultado.get("rastreio", {"estado": "nao_registrado"})})
    # Fontes já minimizadas pela coleta existente, somente nomes dos contratos
    # dos participantes. Não leva fontes_anteriores ou conversas pessoais.
    nomes = {nome for par in pares for nome in PERFIS[par["perfil"]]["fontes"]
             if nome != "resultados_anteriores"}
    fontes = {nome: estado.get("fontes", {}).get(nome, {"estado": "indisponivel"})
              for nome in sorted(nomes)}
    return {"pares_do_proprio_trabalho": pares, "fontes_para_confronto": fontes,
            "perfis_excluidos_por_fotografia": excluidos,
            "fontes_digest": digest_fontes,
            "limite": "Pareceres são alegações. Fontes/estados são fatos disponíveis, não prova de efeito externo. "
                      "População agregada e pares deste trabalho são conjuntos diferentes. "
                      "Truncamento não é ausência de toda a resposta. Concordância do mesmo modelo não é prova independente."}


def orientacao(codigo):
    if codigo == "shreya_shankar":
        return ("\nAvaliação rastreável v1: confronte os pares_do_proprio_trabalho com fontes_para_confronto. "
                "Para cada erro material ou conclusão correta examinada, escreva: perfil, alegação literal curta, "
                "nome da fonte e caminho do campo, fato/resultado verificável, sustentada/refutada/inconclusiva, "
                "limite e ajuste específico. Considere truncamento e perfis excluídos. "
                "Não diga que os textos deste trabalho estão ausentes quando há trechos. "
                "Separe sua avaliação interpretativa de cálculos e registros determinísticos; não invente nota de qualidade.")
    return ("\nSíntese final de Nicole v1, posterior aos pareceres. Use o pedido original, "
            "os pares e as fontes atuais. Compare até três alternativas concretas (agir, investigar, não agir), "
            "registre divergências, alegação e fato que sustentam a escolha, limites e o que mudaria a prioridade. "
            "A revisão de Shreya é outro parecer do modelo, não prova independente. "
            "Nenhuma ação foi executada por escrever a síntese; não crie aprovação obrigatória.")
