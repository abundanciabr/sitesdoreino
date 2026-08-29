"""CONTRATO ADITIVO — acrescentar é livre; remover exige autorização explícita.

Onda 5 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (P4, O7 e B7 da
consultoria, os três convergindo). É a peça que substitui parte do que a cerca
"1 PR = 1 célula" comprava por proibição.

O QUE ISTO **NÃO** É
--------------------
Não é o `ci/contract_freeze.py`. Aquele responde *"o código derivou do contrato
congelado?"* — a célula não pode mudar o próprio contrato sem rito. Este
responde outra pergunta, que ninguém fazia: **quando o CONTRATO muda, a mudança
quebra quem já depende dele?**

A diferença importa porque as duas falham em direções opostas. O freeze reprova
QUALQUER divergência entre código e contrato. Este aqui deixa o contrato CRESCER
(campo novo, operação nova, resposta nova documentada) e trava exatamente o que
faz um consumidor parar de funcionar: remoção e aperto de exigência.

O QUE ELE CONSIDERA QUEBRA (a lista é fechada e declarada)
----------------------------------------------------------
1. caminho removido
2. operação removida (um método sob um caminho)
3. resposta removida de uma operação
4. componente removido (`components/*`)
5. propriedade removida de um schema
6. propriedade que passou a ser exigida (`required`) — quebra QUEM ENVIA
7. parâmetro novo já nascendo exigido — quebra quem chama sem ele

Tudo o mais é adição, e adição passa.

O QUE ELE NÃO PEGA, dito na cara
--------------------------------
Mudança de TIPO de um campo, aperto de formato/enum, semântica que muda sem o
documento mudar. Isto é um **lint de compatibilidade**, não uma prova. Ele
existe para tornar caro o erro comum — não para dizer "está seguro".

A AUTORIZAÇÃO
-------------
Quebra não é proibida: é DELIBERADA. Com a etiqueta `contrato-remocao` no PR, o
portão registra a quebra e passa — mas o veredito fica escrito no log, com o
nome de cada item removido. O rito de contrato (RITOS.md §3) continua valendo
por inteiro: PR só de `contracts/`, etiqueta `contrato`, sessão com o
mantenedor.

Uso (o wrapper da muralha passa BASE_REF e PR_LABELS):

    python ci/contrato_aditivo.py

Exit codes: 0 PASS/SKIP · 1 quebra sem autorização · 2 ERROR (não medi).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    executar,
    raiz_do_repo,
)

PASTA = "contracts"
ETIQUETA_DE_QUEBRA = "contrato-remocao"
METODOS = (
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
)


def _yaml():
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise ErroDeInstrumentacao(
            "PyYAML indisponível",
            "Os contratos são YAML. Sem o leitor, este portão NÃO comparou "
            "nada — e isso não é um OK.",
        ) from exc
    return yaml


def arquivos_de_contrato_no_diff(raiz: Path, base: str) -> list[str]:
    """Os contratos que este PR toca. Falha do git é ERROR, não lista vazia."""
    saida = executar(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=raiz,
        descricao=f"listar os arquivos tocados contra '{base}'",
        exigir_stdout=False,
    ).stdout
    return sorted(
        linha.strip().replace("\\", "/")
        for linha in saida.splitlines()
        if linha.strip().replace("\\", "/").startswith(f"{PASTA}/")
        and linha.strip().endswith((".yaml", ".yml", ".json"))
    )


def versao_da_base(raiz: Path, base: str, caminho: str) -> str | None:
    """O conteúdo do arquivo NA BASE — ou None se ele não existia lá.

    `git show` devolve exit != 0 quando o caminho não existe naquela árvore, e
    esse é um caso legítimo (contrato NOVO, que é adição pura). Por isso aqui a
    chamada não passa por `executar`: ela precisa distinguir "não existia" de
    "não consegui ler", e `executar` transforma as duas em ERROR.
    """
    import subprocess  # noqa: PLC0415

    proc = subprocess.run(
        ["git", "show", f"{base}:{caminho}"],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if proc.returncode == 0:
        return proc.stdout
    erro = (proc.stderr or "").lower()
    if "does not exist" in erro or "exists on disk, but not in" in erro:
        return None
    raise ErroDeInstrumentacao(
        f"não consegui ler {caminho} em {base}",
        f"exit {proc.returncode}\n{proc.stderr.strip()[:600]}\n\n"
        "Sem a versão anterior não há como dizer se a mudança remove algo — e "
        "'não sei' não pode virar 'não remove'.",
    )


def _doc(texto: str, origem: str) -> dict[str, Any]:
    try:
        doc = _yaml().safe_load(texto)
    except Exception as exc:  # noqa: BLE001
        raise ErroDeInstrumentacao(f"{origem} não é YAML válido", str(exc)) from exc
    if not isinstance(doc, dict) or "paths" not in doc:
        raise ErroDeInstrumentacao(
            f"{origem} não tem forma de OpenAPI",
            "Faltou a chave `paths`. Comparar dois documentos sem forma "
            "conhecida diria 'nada removido' sobre qualquer coisa.",
        )
    return doc


def _propriedades(schema: Any) -> dict[str, Any]:
    return schema.get("properties", {}) if isinstance(schema, dict) else {}


def _exigidos(schema: Any) -> set[str]:
    if not isinstance(schema, dict):
        return set()
    req = schema.get("required")
    return set(req) if isinstance(req, list) else set()


def quebras(antes: dict[str, Any], depois: dict[str, Any], arquivo: str) -> list[str]:
    """A lista de quebras. Vazia = a mudança é aditiva."""
    achados: list[str] = []
    paths_antes = antes.get("paths") or {}
    paths_depois = depois.get("paths") or {}

    for caminho in sorted(paths_antes):
        if caminho not in paths_depois:
            achados.append(f"{arquivo}: o caminho `{caminho}` foi REMOVIDO")
            continue
        ops_antes = paths_antes[caminho] or {}
        ops_depois = paths_depois[caminho] or {}
        for metodo in METODOS:
            if metodo not in ops_antes:
                continue
            if metodo not in ops_depois:
                achados.append(
                    f"{arquivo}: a operação `{metodo.upper()} {caminho}` foi REMOVIDA"
                )
                continue
            op_a, op_d = ops_antes[metodo] or {}, ops_depois[metodo] or {}

            # respostas declaradas: tirar uma é tirar um contrato de quem trata
            for codigo in sorted(map(str, (op_a.get("responses") or {}))):
                if codigo not in map(str, (op_d.get("responses") or {})):
                    achados.append(
                        f"{arquivo}: `{metodo.upper()} {caminho}` deixou de "
                        f"declarar a resposta {codigo}"
                    )

            # parâmetro NOVO já exigido quebra quem chama sem ele
            nomes_antes = {
                p.get("name")
                for p in (op_a.get("parameters") or [])
                if isinstance(p, dict)
            }
            for parametro in op_d.get("parameters") or []:
                if not isinstance(parametro, dict):
                    continue
                if parametro.get("name") in nomes_antes:
                    continue
                if parametro.get("required") is True:
                    achados.append(
                        f"{arquivo}: `{metodo.upper()} {caminho}` ganhou o "
                        f"parâmetro OBRIGATÓRIO `{parametro.get('name')}`"
                    )

    comp_antes = (antes.get("components") or {}) if isinstance(antes, dict) else {}
    comp_depois = (depois.get("components") or {}) if isinstance(depois, dict) else {}
    for familia in sorted(comp_antes):
        itens_antes = comp_antes.get(familia) or {}
        itens_depois = comp_depois.get(familia) or {}
        if not isinstance(itens_antes, dict):
            continue
        for nome in sorted(itens_antes):
            if nome not in itens_depois:
                achados.append(
                    f"{arquivo}: o componente `{familia}/{nome}` foi REMOVIDO"
                )
                continue
            if familia != "schemas":
                continue
            props_antes = _propriedades(itens_antes[nome])
            props_depois = _propriedades(itens_depois[nome])
            for prop in sorted(props_antes):
                if prop not in props_depois:
                    achados.append(
                        f"{arquivo}: `{nome}.{prop}` foi REMOVIDO do schema"
                    )
            # Exigir o que antes era opcional quebra QUEM ENVIA — é o caso que
            # passa despercebido, porque "só acrescentei um required".
            novos_exigidos = _exigidos(itens_depois[nome]) - _exigidos(itens_antes[nome])
            for prop in sorted(novos_exigidos):
                achados.append(
                    f"{arquivo}: `{nome}.{prop}` passou a ser OBRIGATÓRIO "
                    "(quebra quem já envia sem ele)"
                )
    return achados


def rodar(raiz: Path | None = None) -> Relatorio:
    raiz = raiz or raiz_do_repo()
    base = os.environ.get("BASE_REF", "").strip() or "origin/main"
    etiquetas = {
        e.strip() for e in os.environ.get("PR_LABELS", "").split(",") if e.strip()
    }
    relatorio = Relatorio(titulo="CONTRATO ADITIVO — acrescentar sim, remover não")

    tocados = arquivos_de_contrato_no_diff(raiz, base)
    if not tocados:
        relatorio.registrar(
            Resultado(
                "contratos",
                Estado.SKIP,
                "este PR não toca contracts/",
            )
        )
        return relatorio

    todas: list[str] = []
    for caminho in tocados:
        antes_texto = versao_da_base(raiz, base, caminho)
        if antes_texto is None:
            relatorio.registrar(
                Resultado(
                    caminho,
                    Estado.PASS,
                    "contrato NOVO — adição pura, nada a remover",
                )
            )
            continue
        atual = (raiz / caminho)
        if not atual.is_file():
            todas.append(f"{caminho}: o arquivo INTEIRO foi removido")
            continue
        try:
            achados = quebras(
                _doc(antes_texto, f"{caminho}@{base}"),
                _doc(atual.read_text(encoding="utf-8"), caminho),
                caminho,
            )
        except ErroDeInstrumentacao as erro:
            relatorio.registrar(Resultado.de_erro(caminho, erro))
            continue
        if achados:
            todas.extend(achados)
        else:
            relatorio.registrar(
                Resultado(caminho, Estado.PASS, "mudança aditiva — nada removido")
            )

    if todas:
        detalhe = "\n".join(f"  - {q}" for q in todas)
        if ETIQUETA_DE_QUEBRA in etiquetas:
            # IMPRESSO, e não só guardado no detalhe: o `render()` do relatório
            # mostra detalhe apenas de quem reprova, e uma quebra AUTORIZADA
            # que não aparecesse no log seria uma quebra silenciosa com
            # carimbo — exatamente o que esta etiqueta não pode virar.
            print("QUEBRAS AUTORIZADAS por `" + ETIQUETA_DE_QUEBRA + "`:")
            print(detalhe)
            relatorio.registrar(
                Resultado(
                    "quebras autorizadas",
                    Estado.PASS,
                    f"{len(todas)} quebra(s), com a etiqueta `{ETIQUETA_DE_QUEBRA}`",
                    detalhe
                    + "\n\nAutorizado de propósito. Fica registrado aqui, com "
                    "nome e sobrenome de cada item — quebra deliberada é "
                    "legítima; quebra silenciosa é que não.",
                )
            )
        else:
            relatorio.registrar(
                Resultado(
                    "quebras",
                    Estado.FAIL,
                    f"{len(todas)} mudança(s) que quebram quem consome",
                    detalhe
                    + "\n\nContrato cresce por ADIÇÃO (expandir-e-contrair): "
                    "acrescente o novo, mantenha o velho, migre os consumidores, "
                    "e só então remova — noutro PR.\n"
                    f"Se a quebra é deliberada e combinada, ponha a etiqueta "
                    f"`{ETIQUETA_DE_QUEBRA}` no PR: ela não apaga o achado, "
                    "registra a autorização.",
                )
            )
    return relatorio


def main() -> int:
    configurar_saida()
    try:
        relatorio = rodar()
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR contrato_aditivo: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        print("   A compatibilidade NÃO foi medida. Isto NÃO é um OK.")
        return 2
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
