"""Calcula o placar local; votos e provas permanecem em arquivos separados."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


PARTICIPANTES = {"codex": "Codex", "claude": "Claude Code", "antigravity": "Antigravity"}
PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parents[3]


def assinatura(registro: dict) -> str:
    texto = json.dumps(registro, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise ValueError(mensagem)


def texto(registro: dict, campo: str) -> str:
    valor = registro.get(campo)
    exigir(isinstance(valor, str) and bool(valor.strip()), f"Faltou {campo}. Preencha o campo com a fonte ou o fato observado.")
    return valor


def numero(valor: object, campo: str) -> float:
    exigir(type(valor) in (int, float) and math.isfinite(valor) and valor >= 0,
           f"{campo} inválido. Informe um número observado, finito e não negativo.")
    return float(valor)


def momento(registro: dict) -> datetime:
    try:
        data = datetime.fromisoformat(texto(registro, "registrado_em"))
    except ValueError as erro:
        raise ValueError("Data inválida. Use registrado_em em ISO 8601 com fuso horário.") from erro
    exigir(data.tzinfo is not None, "Data sem fuso. Informe registrado_em com +00:00 ou o fuso local.")
    return data


def apurar(registros: list[dict]) -> dict:
    propostas, votos, implementacoes, verificacoes = {}, {}, {}, {}
    for registro in registros:
        exigir(isinstance(registro, dict), "Registro inválido. Use um objeto JSON por arquivo.")
        exigir(registro.get("autor") in PARTICIPANTES, "Autor desconhecido. Use codex, claude ou antigravity.")
        momento(registro)
        tipo = registro.get("tipo")
        exigir(tipo in {"proposta", "voto", "implementacao", "verificacao"},
               "Tipo desconhecido. Use proposta, voto, implementacao ou verificacao.")
        if tipo == "proposta":
            identificador = texto(registro, "id")
            exigir(identificador not in propostas, f"Proposta duplicada: {identificador}. Preserve um único ID por revisão.")
            for campo in ("problema", "titulo", "baseline", "aceite"):
                texto(registro, campo)
            propostas[identificador] = registro

    chaves = set()
    for registro in registros:
        tipo = registro["tipo"]
        if tipo == "proposta":
            continue
        identificador = texto(registro, "proposta")
        exigir(identificador in propostas, f"Proposta ausente: {identificador}. Inclua a proposta antes de registrar pareceres.")
        proposta = propostas[identificador]
        chave = (tipo, identificador, registro["autor"] if tipo != "implementacao" else "")
        exigir(chave not in chaves, f"Registro duplicado para {identificador}. Resolva a duplicação sem apagar parecer alheio.")
        chaves.add(chave)
        exigir(momento(registro) > momento(proposta), "Registro anterior à proposta. Confira datas e a revisão referenciada.")
        if tipo in {"voto", "implementacao"}:
            exigir(registro.get("proposta_sha256") == assinatura(proposta),
                   f"A proposta {identificador} mudou. Obtenha novos votos para o SHA256 atual.")
        if tipo in {"voto", "verificacao"}:
            exigir(registro["autor"] != proposta["autor"], "Autovoto não vale. Solicite parecer das outras duas IAs.")
            texto(registro, "justificativa")
        if tipo == "voto":
            decisao = registro.get("decisao")
            exigir(decisao in {"aprovar", "reprovar", "abster"}, "Voto inválido. Declare aprovar, reprovar ou abster com motivo.")
            importancia = registro.get("importancia")
            exigir(type(importancia) is int and importancia in ((1, 2, 3) if decisao == "aprovar" else (0,)),
                   "Importância inválida. Aprovação recebe 1, 2 ou 3; reprovação e abstenção recebem 0.")
            votos.setdefault(identificador, {})[registro["autor"]] = registro
        elif tipo == "implementacao":
            texto(registro, "prova")
            texto(registro, "resultado")
            numero(registro.get("minutos_totais"), "minutos_totais")
            exigir("custo_reais" in registro, "Faltou custo_reais. Use null quando não houver fonte monetária.")
            if registro["custo_reais"] is not None:
                numero(registro["custo_reais"], "custo_reais")
                texto(registro, "fonte_custo")
            else:
                exigir(registro.get("fonte_custo", "") == "", "Custo não medido com fonte preenchida. Informe o valor comprovado ou deixe fonte_custo vazia.")
            implementacoes[identificador] = registro
        else:
            exigir(registro.get("decisao") in {"confirmar", "recusar", "abster"},
                   "Verificação inválida. Declare confirmar, recusar ou abster com motivo.")
            texto(registro, "prova")
            verificacoes.setdefault(identificador, {})[registro["autor"]] = registro

    for identificador, pareceres in verificacoes.items():
        exigir(identificador in implementacoes, "Verificação sem implementação. Inclua primeiro a implementação examinada.")
        implementacao = implementacoes[identificador]
        for parecer in pareceres.values():
            exigir(parecer.get("implementacao_sha256") == assinatura(implementacao),
                   "A implementação mudou. Obtenha verificações para seu SHA256 atual.")
            exigir(momento(parecer) > momento(implementacao), "Verificação anterior à implementação. Execute a conferência e registre sua data real.")

    totais = {autor: {"id": autor, "pontos": 0, "contribuicoes": 0, "implementacoes": 0, "minutos_totais": 0.0,
                      "custo_reais": None, "custo_conhecido_reais": 0.0} for autor in PARTICIPANTES}
    custos = {autor: [] for autor in PARTICIPANTES}
    resultados, problemas_pontuados = [], set()
    for identificador, proposta in sorted(propostas.items()):
        pares = set(PARTICIPANTES) - {proposta["autor"]}
        aprovadores = votos.get(identificador, {})
        revisores = verificacoes.get(identificador, {})
        implementacao = implementacoes.get(identificador)
        pontos, estado = 0, "aguarda_votos"
        if any(v["decisao"] == "reprovar" for v in aprovadores.values()):
            estado = "reprovada"
        elif set(aprovadores) == pares and all(v["decisao"] == "aprovar" for v in aprovadores.values()):
            estado = "aguarda_implementacao"
            if implementacao:
                if implementacao["autor"] != proposta["autor"]:
                    estado = "autoria_pendente"
                elif not all(momento(v) < momento(implementacao) for v in aprovadores.values()):
                    estado = "aguarda_votos"
                elif any(v["decisao"] == "recusar" for v in revisores.values()):
                    estado = "recusada"
                elif set(revisores) == pares and all(v["decisao"] == "confirmar" for v in revisores.values()):
                    estado = "pontua"
                    pontos = min(v["importancia"] for v in aprovadores.values())
                    problema = proposta["problema"].strip().casefold()
                    exigir(problema not in problemas_pontuados, "Duas propostas pontuam pelo mesmo problema. Consolide a autoria antes de classificar.")
                    problemas_pontuados.add(problema)
                else:
                    estado = "aguarda_verificacao"
        total = totais[proposta["autor"]]
        total["pontos"] += pontos
        total["contribuicoes"] += int(estado == "pontua")
        if implementacao:
            executora = totais[implementacao["autor"]]
            executora["implementacoes"] += 1
            executora["minutos_totais"] += implementacao["minutos_totais"]
            custos[implementacao["autor"]].append(implementacao["custo_reais"])
        resultados.append({"id": identificador, "estado": estado, "pontos": pontos,
                           "sha256": assinatura(proposta)})
    for autor, valores in custos.items():
        totais[autor]["custo_conhecido_reais"] = sum(v for v in valores if v is not None)
        if valores and all(v is not None for v in valores):
            totais[autor]["custo_reais"] = sum(valores)
    participantes = sorted(totais.values(), key=lambda p: (-p["pontos"], PARTICIPANTES[p["id"]]))
    pontos = [p["pontos"] for p in participantes]
    return {"participantes": participantes, "propostas": resultados,
            "ranking_definido": len(set(pontos)) == len(PARTICIPANTES) and max(pontos) > 0}


def carregar(pasta: Path) -> list[dict]:
    registros = []
    for arquivo in sorted(pasta.glob("*.json")):
        try:
            registro = json.loads(arquivo.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as erro:
            raise ValueError(f"Não foi possível ler {arquivo.name}. Corrija o JSON e execute novamente.") from erro
        if isinstance(registro, dict) and registro.get("tipo") in {"implementacao", "verificacao"}:
            relativo = texto(registro, "prova")
            prova = (RAIZ / relativo).resolve()
            exigir(not Path(relativo).is_absolute() and prova.is_relative_to(RAIZ),
                   "Prova fora do projeto. Guarde a evidência na pasta local e use caminho relativo.")
            exigir(prova.is_file() and prova.stat().st_size > 0,
                   f"Prova ausente ou vazia: {relativo}. Salve a saída real antes de pontuar.")
            exigir(registro.get("prova_sha256") == hashlib.sha256(prova.read_bytes()).hexdigest(),
                   f"Prova com SHA256 ausente ou divergente: {relativo}. Registre o hash da saída real e obtenha novas conferências.")
        registros.append(registro)
    return registros


def renderizar(placar: dict) -> str:
    linhas = ["# Placar local da Fase 4", "", "Calculado dos registros locais. Não atribui cargos nem cancela assinaturas.", "",
              "| Participante | Pontos | Contribuições verificadas | Minutos observados | Custo monetário |",
              "|---|---:|---:|---:|---|"]
    for participante in placar["participantes"]:
        custo = participante["custo_reais"]
        conhecido = participante["custo_conhecido_reais"]
        custo_texto = f"R$ {custo:.2f}" if custo is not None else (
            f"R$ {conhecido:.2f} conhecidos; total não medido" if conhecido else "não medido"
        )
        minutos = f"{participante['minutos_totais']:g}" if participante["implementacoes"] else "não medido"
        linhas.append(f"| {PARTICIPANTES[participante['id']]} | {participante['pontos']} | {participante['contribuicoes']} | "
                      f"{minutos} | {custo_texto} |")
    linhas.extend(["", "Ordem numérica distinta; classificação ainda provisória." if placar["ranking_definido"] else
                   "Classificação inconclusiva: faltam contribuições verificadas ou há empate.", "",
                   "Zero contribuição não prova incompetência. Ausência de medição não é custo zero.", "",
                   "## Propostas", ""])
    if not placar["propostas"]:
        linhas.append("Nenhuma proposta no formato de votação. As sugestões anteriores permanecem nos documentos originais, com sua autoria.")
    for proposta in placar["propostas"]:
        linhas.extend([f"- {proposta['id']}: {proposta['estado']}, {proposta['pontos']} ponto(s).",
                       f"  SHA256: `{proposta['sha256']}`"])
    return "\n".join(linhas) + "\n"


def main() -> int:
    destino = PASTA / "PLACAR.md"
    try:
        placar = apurar(carregar(PASTA / "registros"))
        texto_placar = renderizar(placar)
    except (ValueError, OSError) as erro:
        texto_placar = f"# Placar indisponível\n\nNão use uma classificação anterior.\n\n{erro}\n"
        destino.write_text(texto_placar, encoding="utf-8")
        print(f"ERROR: {erro}")
        return 1
    destino.write_text(texto_placar, encoding="utf-8")
    print(f"PASS: {len(placar['propostas'])} proposta(s); placar salvo em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
