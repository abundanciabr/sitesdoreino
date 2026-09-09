"""Recusa conclusões novas que deixam a entrega do mesmo PR em alerta.

O livro continua imutável. A dívida histórica não bloqueia outro trabalho:
só registros novos são examinados. Pedidos ao dono precisam explicar a decisão.
O vínculo usa responde_a escalar e relacao explícita. Comentário não encerra ocorrência.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from _nucleo import ErroDeInstrumentacao, configurar_saida, executar, raiz_do_repo
from verificar_painel import Painel, ids_no_git, registros_da_fonte


def prs_citados(evidencia: object) -> set[tuple[str, str, int]]:
    """Identidade completa: organização, repositório e número, nunca substring."""
    prs = set()
    for texto in re.findall(r"https?://[^\s<>\"']+", str(evidencia or "")):
        try:
            url = urlsplit(texto.rstrip(".,;:)"))
        except ValueError:
            continue
        if url.netloc.lower() != "github.com":
            continue
        caminho = re.fullmatch(
            r"/([^/]+)/([^/]+)/pull/([1-9][0-9]*)(?:/(?:files|commits|checks))?/?",
            url.path,
        )
        if caminho:
            dono, repo, numero = caminho.groups()
            prs.add((dono.lower(), repo.lower(), int(numero)))
    return prs


def entrega_em_alerta(registro: dict) -> bool:
    return (registro.get("tipo") == "entrega" and registro.get("gravidade") in ("ambar", "vermelho")
            and not (registro.get("relacao") is not None and isinstance(registro.get("responde_a"), str)))


def prova_posterior(resposta: dict, alerta: dict) -> bool:
    if not isinstance(resposta.get("evidencia"), str) or not resposta["evidencia"].strip():
        return False
    formato = r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))?"
    if any(not isinstance(valor, str) or not re.fullmatch(formato, valor) for valor in (resposta.get("verificado_em"), alerta.get("quando"))):
        return False
    try:
        conferida = datetime.fromisoformat(resposta.get("verificado_em") or "")
        fato = datetime.fromisoformat(alerta.get("quando") or "")
        conferida = conferida.replace(tzinfo=timezone.utc) if conferida.tzinfo is None else conferida
        fato = fato.replace(tzinfo=timezone.utc) if fato.tzinfo is None else fato
        return conferida >= fato
    except (ValueError, TypeError):
        return False


def baixa_comprovada(resposta: dict, alerta: dict) -> bool:
    """Espelho independente de LOGICA.resolucaoComprovada, com exemplos comuns."""
    if resposta.get("arquivo") == alerta.get("arquivo") or resposta.get("responde_a") != alerta.get("arquivo") or (alerta.get("relacao") and alerta.get("responde_a")) or not prova_posterior(resposta, alerta):
        return False
    if resposta.get("relacao") not in (None, "resolucao"):
        return False
    if alerta.get("tarefa") and resposta.get("tarefa") != alerta["tarefa"]:
        return False
    legado_conferido = resposta.get("relacao") is None and resposta.get("tipo") == "resposta" and resposta.get("gravidade") == "info"
    if resposta.get("gravidade") != "verde" and not legado_conferido:
        return False
    prs = prs_citados(alerta.get("evidencia")) if resposta.get("relacao") is None and alerta.get("tipo") == "entrega" else set()
    return not prs or bool(prs & prs_citados(resposta.get("evidencia")))


def complementos_comprovados(registros: dict[str, dict]) -> dict[str, str]:
    candidatos, ambiguos = {}, set()
    for r in registros.values():
        if r.get("relacao") != "complemento":
            continue
        origem, destino = r.get("responde_a"), r.get("ocorrencia")
        if not isinstance(origem, str) or not isinstance(destino, str):
            continue
        alvo, principal = registros.get(origem), registros.get(destino)
        if not alvo or not principal or len({r.get("arquivo"), origem, destino}) != 3:
            continue
        if (alvo.get("relacao") and alvo.get("responde_a")) or (principal.get("relacao") and principal.get("responde_a")):
            continue
        if r.get("precisa_do_dono") or r.get("gravidade") != "info" or (alvo.get("tarefa") and r.get("tarefa") != alvo["tarefa"]):
            continue
        if not prova_posterior(r, alvo) or not prova_posterior(r, principal):
            continue
        if origem in candidatos and candidatos[origem] != destino:
            ambiguos.add(origem)
        candidatos[origem] = destino
    return {origem: destino for origem, destino in candidatos.items() if origem not in ambiguos and destino not in candidatos and origem not in candidatos.values()}


def conferir_registros(registros: dict[str, dict], novos: set[str]) -> list[str]:
    entregas = {ident: r for ident, r in registros.items() if entrega_em_alerta(r)}
    baixados = {
        r.get("responde_a") for ident, r in registros.items()
        if isinstance(r.get("responde_a"), str)
        and r["responde_a"] in entregas
        and (ident not in novos or r.get("relacao") == "resolucao")
        and baixa_comprovada(r, entregas[r["responde_a"]])
    }
    complementos = complementos_comprovados(registros)
    problemas = []
    for ident in sorted(novos):
        registro = registros[ident]
        if registro.get("precisa_do_dono") is True:
            for campo in ("porque_so_voce", "proximo_passo", "se_eu_nao_decidir", "recomendacao"):
                valor = registro.get(campo)
                if not isinstance(valor, str) or not valor.strip():
                    problemas.append(
                        f"{ident}: pedido novo ao dono exige {campo} com texto claro. "
                        "Preencha conforme painel/LEIA-ME.md. Falha técnica reparável pelo robô "
                        "é alerta com precisa_do_dono false e diagnóstico no detalhe."
                    )
            if type(registro.get("reversivel")) is not bool:
                problemas.append(f"{ident}: pedido novo exige reversivel true ou false; veja painel/LEIA-ME.md.")
            if registro.get("impacto") not in ("alto", "medio", "baixo"):
                problemas.append(f"{ident}: pedido novo exige impacto alto, medio ou baixo; veja painel/LEIA-ME.md.")
        alvo_id = registro.get("responde_a")
        relacao = registro.get("relacao")
        if alvo_id is not None and not isinstance(alvo_id, str):
            problemas.append(f"{ident}: responde_a precisa ser um identificador em texto ou null; use uma baixa por alerta.")
            continue
        alvo = registros.get(alvo_id)
        if relacao == "complemento":
            destino = registro.get("ocorrencia")
            principal = registros.get(destino) if isinstance(destino, str) else None
            if not alvo or not principal or complementos.get(alvo_id) != destino or complementos_comprovados({alvo_id: alvo, destino: principal, ident: registro}).get(alvo_id) != destino or not prova_posterior(registro, alvo) or not prova_posterior(registro, principal) or registro.get("gravidade") != "info" or registro.get("precisa_do_dono"):
                problemas.append(f"{ident}: complemento sem vínculo comprovado; indique alvo e canônico distintos existentes, prova dos dois e elimine ciclos ou ambiguidades.")
        if relacao == "historico":
            if alvo_id is not None or registro.get("tipo") != "incidente" or registro.get("precisa_do_dono") or registro.get("gravidade") != "verde" or not prova_posterior(registro, registro):
                problemas.append(f"{ident}: historico sem prova ou com alvo; use incidente verde comprovado sem responde_a, ou resolucao para encerrar ocorrência existente.")
        if relacao == "resolucao" and (not alvo or not baixa_comprovada(registro, alvo)):
            problemas.append(f"{ident}: baixa de {alvo_id} sem prova. Use gravidade verde, a mesma tarefa, verificado_em a partir do alerta e evidencia do PR da entrega e da conferência realizada.")
        if alvo and relacao is None and (alvo.get("precisa_do_dono") or baixa_comprovada(registro, alvo)):
            problemas.append(f"{ident}: resposta nova exige relacao comentario, decisao ou resolucao; o adaptador legado não autoriza novos encerramentos implícitos.")
        if relacao not in (None, "resolucao") or registro.get("gravidade") != "verde":
            continue
        prs = prs_citados(registro.get("evidencia"))
        for alerta_id, alerta in sorted(entregas.items()):
            if alerta_id == ident or alerta_id in baixados or (alerta_id in complementos and complementos[alerta_id] in baixados):
                continue
            if prs & prs_citados(alerta.get("evidencia")):
                problemas.append(
                    f"{ident}: conclusão verde deixa {alerta_id} em alerta. "
                    f'Acrescente no mesmo PR uma baixa com responde_a: "{alerta_id}", '
                    'relacao: "resolucao", gravidade verde, evidencia do PR e da conferência, e verificado_em. '
                    "O próprio registro de conclusão pode ser essa baixa. "
                    "Preserve o registro anterior; molde em painel/LEIA-ME.md."
                )
    return problemas


def conferir(painel: Painel, base: str) -> list[str]:
    try:
        anteriores = executar(
            ["git", "ls-tree", "-r", "--name-only", base, "--", "painel/registros/"],
            cwd=painel.raiz, descricao=f"ler registros anteriores em {base}",
        )
    except ErroDeInstrumentacao as erro:
        raise ErroDeInstrumentacao(
            f"não consegui ler a base {base!r}",
            f"{erro.detalhe}\nConfira BASE_REF e faça git fetch origin antes de medir.",
        ) from erro
    no_git = ids_no_git(painel)
    novos = no_git - {Path(linha).stem for linha in anteriores.stdout.splitlines()}
    fonte = registros_da_fonte(painel)
    ilegíveis = sorted(ident for ident in no_git if ident not in fonte or "__erro" in fonte[ident])
    if ilegíveis:
        return [f"{ident}: registro ilegível; corrija o arquivo antes de conferir a baixa." for ident in ilegíveis]
    return conferir_registros({ident: fonte[ident] for ident in no_git}, novos)


def main() -> int:
    configurar_saida()
    try:
        problemas = conferir(
            Painel(raiz_do_repo(Path(__file__).resolve().parent)),
            os.environ.get("BASE_REF") or "origin/main",
        )
    except ErroDeInstrumentacao as erro:
        print(f"ERROR encerramento-alertas: {erro.resumo}\n{erro.detalhe}")
        return 2
    if problemas:
        print("FAIL encerramento-alertas:\n" + "\n".join(problemas))
        return 1
    print("PASS encerramento-alertas: pedidos novos completos; conclusões novas não deixam entregas relacionadas sem baixa comprovada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
