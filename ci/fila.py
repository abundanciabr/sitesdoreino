"""A FILA DE TRABALHO — tarefa é coisa registrada, e estado é uma conta.

    python ci/fila.py criar --titulo "..." --toca admin --evidencia-exigida "..." \
        --despacho "..." [--depende-de TAR-001] [--origem "..."]
    python ci/fila.py listar [--ao-vivo]     # estados calculados; --ao-vivo soma reservas e PRs
    python ci/fila.py pegar TAR-001 --quem "sessao-x"    # trava no servidor + evento
    python ci/fila.py soltar TAR-001 --quem "sessao-x"   # devolve à fila
    python ci/fila.py concluir TAR-001 --quem "sessao-x" --evidencia URL
    python ci/fila.py validar                # fail-closed; roda na muralha

Nascida da fase 2 do plano aprovado em 29/08/2026 (veredito em
`docs/consultorias/central-de-orquestracao/VEREDITO.md`). O que os três
consultores pediram e aqui vira mecanismo:

- **Estado calculado, nunca campo editado.** Não existe campo `status` em
  lugar nenhum: o arquivo da tarefa nunca muda depois de criado, e a coluna
  do quadro é sempre calculada da cadeia de eventos + reservas + PRs.
- **Trava atômica com prazo.** `pegar` NÃO inventa trava própria: chama o
  almoxarife (`ci/reservar.py`), que cria uma referência no servidor do
  GitHub — quem chega segundo recebe recusa DO SERVIDOR, na hora, e a
  reserva expira sozinha se a sessão morrer.
- **Concluir exige evidência.** Sem prova, `concluir` recusa — a mesma lei
  do verde do livro (`painel/LEIA-ME.md`).

O molde é o do livro: fonte multiescritor (um arquivo por tarefa em
`fila/tarefas/`, um arquivo por acontecimento em `fila/eventos/` — imune a
conflito por construção), nada se edita, corrigir é acrescentar.

Dialeto de exit (RETROSPECTIVA-FASE-D §1): 0 = OK · 1 = recusa/violação ·
2 = ERROR (não consegui medir — e não medir nunca é passar).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import reservar  # noqa: E402
from _nucleo import ErroDeInstrumentacao, configurar_saida, raiz_do_repo  # noqa: E402

# O ciclo de vida inteiro. Fechado de propósito: evento fora desta lista é
# arquivo inválido, não "vocabulário novo" — vocabulário muda por PR, aqui.
EVENTOS_DE_CICLO = ("reivindicada", "devolvida", "bloqueada")
EVENTOS_TERMINAIS = ("concluida", "cancelada")
EVENTOS_VALIDOS = EVENTOS_DE_CICLO + EVENTOS_TERMINAIS

# Os estados que `listar` calcula. Ninguém escreve isto em arquivo nenhum.
NA_FILA = "na fila"
REIVINDICADA = "reivindicada"
EM_EXECUCAO = "em execução"
BLOQUEADA = "bloqueada"
CONCLUIDA = "concluída"
CANCELADA = "cancelada"

CAMPOS_DA_TAREFA = {
    "arquivo": str,
    "id": str,
    "titulo": str,
    "toca": list,
    "evidencia_exigida": str,
    "despacho": str,
    "origem": str,
    "criada_em": str,
}
CAMPOS_OPCIONAIS_DA_TAREFA = {"depende_de": list, "notas": str}

CAMPOS_DO_EVENTO = {
    "arquivo": str,
    "tarefa": str,
    "evento": str,
    "quando": str,
    "quem": str,
}
CAMPOS_OPCIONAIS_DO_EVENTO = {"detalhe": str, "evidencia": str, "verificado_em": str}

RE_ID = re.compile(r"^TAR-(\d{3,})$")
RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PREFIXO_DA_RESERVA = "tarefa-"  # refs/reservas/tarefa-TAR-001


def pasta_tarefas(raiz: Path) -> Path:
    return raiz / "fila" / "tarefas"


def pasta_eventos(raiz: Path) -> Path:
    return raiz / "fila" / "eventos"


def _ler_json(caminho: Path, erros: list[str]) -> dict | None:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        erros.append(f"{caminho.name}: não é JSON válido ({erro})")
        return None
    if not isinstance(dados, dict):
        erros.append(f"{caminho.name}: o conteúdo precisa ser um objeto JSON")
        return None
    return dados


def _conferir_campos(
    nome: str,
    dados: dict,
    obrigatorios: dict,
    opcionais: dict,
    erros: list[str],
) -> None:
    for campo, tipo in obrigatorios.items():
        if campo not in dados:
            erros.append(f"{nome}: falta o campo obrigatório '{campo}'")
        elif not isinstance(dados[campo], tipo):
            erros.append(f"{nome}: '{campo}' deveria ser {tipo.__name__}")
        elif tipo is str and not str(dados[campo]).strip():
            erros.append(f"{nome}: '{campo}' está vazio")
    conhecidos = set(obrigatorios) | set(opcionais)
    for campo in dados:
        if campo not in conhecidos:
            erros.append(
                f"{nome}: campo desconhecido '{campo}' — vocabulário novo entra "
                "por PR neste arquivo, não por invenção num JSON"
            )
    for campo, tipo in opcionais.items():
        if campo in dados and dados[campo] is not None and not isinstance(dados[campo], tipo):
            erros.append(f"{nome}: '{campo}' deveria ser {tipo.__name__} ou null")


def carregar_tarefas(raiz: Path, erros: list[str]) -> dict[str, dict]:
    """Todas as tarefas, validadas uma a uma. Erro entra em `erros`, não explode."""
    pasta = pasta_tarefas(raiz)
    tarefas: dict[str, dict] = {}
    numeros: dict[str, str] = {}
    if not pasta.is_dir():
        return tarefas
    for caminho in sorted(pasta.glob("*.json")):
        dados = _ler_json(caminho, erros)
        if dados is None:
            continue
        nome = caminho.name
        _conferir_campos(nome, dados, CAMPOS_DA_TAREFA, CAMPOS_OPCIONAIS_DA_TAREFA, erros)
        stem = caminho.stem
        if dados.get("arquivo") != stem:
            erros.append(f"{nome}: campo 'arquivo' ({dados.get('arquivo')!r}) ≠ nome do arquivo")
        numero = stem.split("-", 1)[0]
        if not numero.isdigit():
            erros.append(f"{nome}: o nome precisa começar com o número (NNN-slug.json)")
            continue
        esperado = f"TAR-{numero}"
        if dados.get("id") != esperado:
            erros.append(f"{nome}: 'id' ({dados.get('id')!r}) ≠ {esperado} (o número vem do nome)")
        if numero in numeros:
            erros.append(
                f"{nome}: número {numero} repetido (já usado por {numeros[numero]}) — "
                "o número vem do almoxarife, nunca de palpite"
            )
            continue
        numeros[numero] = nome
        toca = dados.get("toca")
        if isinstance(toca, list) and (not toca or not all(isinstance(t, str) and t.strip() for t in toca)):
            erros.append(f"{nome}: 'toca' precisa ser lista não vazia de textos")
        criada = dados.get("criada_em")
        if isinstance(criada, str) and not RE_DATA.match(criada):
            erros.append(f"{nome}: 'criada_em' precisa ser AAAA-MM-DD")
        tarefas[esperado] = dados
    # Dependências só se conferem com o mapa completo em mãos.
    for tid, dados in tarefas.items():
        for dep in dados.get("depende_de") or []:
            if dep == tid:
                erros.append(f"{tid}: depende de si mesma")
            elif dep not in tarefas:
                erros.append(f"{tid}: depende de {dep!r}, que não existe na fila")
    _conferir_ciclos(tarefas, erros)
    return tarefas


def _conferir_ciclos(tarefas: dict[str, dict], erros: list[str]) -> None:
    VISITANDO, PRONTO = 1, 2
    marca: dict[str, int] = {}

    def visitar(tid: str, trilha: list[str]) -> None:
        marca[tid] = VISITANDO
        for dep in tarefas.get(tid, {}).get("depende_de") or []:
            if dep not in tarefas:
                continue
            if marca.get(dep) == VISITANDO:
                ciclo = " → ".join(trilha + [tid, dep])
                erros.append(f"ciclo de dependências: {ciclo} — ninguém sairia da fila")
            elif dep not in marca:
                visitar(dep, trilha + [tid])
        marca[tid] = PRONTO

    for tid in tarefas:
        if tid not in marca:
            visitar(tid, [])


def carregar_eventos(raiz: Path, tarefas: dict[str, dict], erros: list[str]) -> list[dict]:
    """Todos os eventos, validados e em ordem cronológica (quando, arquivo)."""
    pasta = pasta_eventos(raiz)
    eventos: list[dict] = []
    if not pasta.is_dir():
        return eventos
    for caminho in sorted(pasta.glob("*.json")):
        dados = _ler_json(caminho, erros)
        if dados is None:
            continue
        nome = caminho.name
        _conferir_campos(nome, dados, CAMPOS_DO_EVENTO, CAMPOS_OPCIONAIS_DO_EVENTO, erros)
        if dados.get("arquivo") != caminho.stem:
            erros.append(f"{nome}: campo 'arquivo' ≠ nome do arquivo")
        tipo = dados.get("evento")
        if tipo not in EVENTOS_VALIDOS:
            erros.append(f"{nome}: evento {tipo!r} não existe (válidos: {', '.join(EVENTOS_VALIDOS)})")
            continue
        if tarefas and dados.get("tarefa") not in tarefas:
            erros.append(f"{nome}: fala da tarefa {dados.get('tarefa')!r}, que não existe")
        quando = dados.get("quando")
        try:
            dados["_quando"] = datetime.fromisoformat(str(quando))
        except (TypeError, ValueError):
            erros.append(f"{nome}: 'quando' precisa ser data-hora ISO (veio {quando!r})")
            continue
        if tipo == "concluida":
            if not str(dados.get("evidencia") or "").strip():
                erros.append(
                    f"{nome}: concluída SEM evidência não existe — a mesma lei do "
                    "verde do livro. Registre o que provou, ou não conclua."
                )
            if not RE_DATA.match(str(dados.get("verificado_em") or "")):
                erros.append(f"{nome}: concluída exige 'verificado_em' (AAAA-MM-DD)")
        if tipo in ("bloqueada", "cancelada") and not str(dados.get("detalhe") or "").strip():
            erros.append(f"{nome}: '{tipo}' sem 'detalhe' não conta a história — diga o motivo")
        eventos.append(dados)
    eventos.sort(key=lambda e: (e["_quando"].isoformat(), e["arquivo"]))
    # Depois do fim, silêncio: evento após concluída/cancelada é história dupla.
    fim: dict[str, str] = {}
    for ev in eventos:
        tid = ev.get("tarefa")
        if tid in fim:
            erros.append(
                f"{ev['arquivo']}: a tarefa {tid} já terminou ({fim[tid]}) — "
                "evento depois do fim reescreveria a história"
            )
        elif ev["evento"] in EVENTOS_TERMINAIS:
            fim[tid] = ev["evento"]
    return eventos


def calcular_estados(
    tarefas: dict[str, dict],
    eventos: list[dict],
    reservas_ativas: set[str] | None = None,
    prs_abertos: dict[str, str] | None = None,
) -> dict[str, dict]:
    """O quadro inteiro, calculado. Função pura: quem quiser outra vista, chama.

    `reservas_ativas` = ids com referência viva no almoxarife (só ao vivo);
    `prs_abertos` = id → "PR #N" para tarefas citadas em PR aberto (só ao vivo).
    """
    reservas_ativas = reservas_ativas or set()
    prs_abertos = prs_abertos or {}
    por_tarefa: dict[str, list[dict]] = {tid: [] for tid in tarefas}
    for ev in eventos:
        if ev.get("tarefa") in por_tarefa:
            por_tarefa[ev["tarefa"]].append(ev)

    estados: dict[str, dict] = {}

    def estado_de(tid: str) -> dict:
        if tid in estados:
            return estados[tid]
        cadeia = por_tarefa[tid]
        resultado = {"estado": NA_FILA, "motivo": "ninguém pegou ainda", "quem": None}
        terminal = next((e for e in cadeia if e["evento"] in EVENTOS_TERMINAIS), None)
        if terminal is not None:
            resultado = {
                "estado": CONCLUIDA if terminal["evento"] == "concluida" else CANCELADA,
                "motivo": terminal.get("evidencia") or terminal.get("detalhe") or "",
                "quem": terminal.get("quem"),
            }
            estados[tid] = resultado
            return resultado
        ultimo_ciclo = next(
            (e for e in reversed(cadeia) if e["evento"] in EVENTOS_DE_CICLO), None
        )
        if ultimo_ciclo is not None and ultimo_ciclo["evento"] == "bloqueada":
            resultado = {
                "estado": BLOQUEADA,
                "motivo": ultimo_ciclo.get("detalhe") or "",
                "quem": ultimo_ciclo.get("quem"),
            }
            estados[tid] = resultado
            return resultado
        reivindicada = (
            ultimo_ciclo is not None and ultimo_ciclo["evento"] == "reivindicada"
        ) or tid in reservas_ativas
        # Dependência aberta bloqueia por conta, sem ninguém escrever nada.
        estados[tid] = resultado  # quebra ciclos que a validação deixou passar
        deps_abertas = [
            dep
            for dep in tarefas[tid].get("depende_de") or []
            if dep in tarefas and estado_de(dep)["estado"] != CONCLUIDA
        ]
        if deps_abertas and not reivindicada:
            resultado = {
                "estado": BLOQUEADA,
                "motivo": "esperando " + ", ".join(deps_abertas),
                "quem": None,
            }
        elif tid in prs_abertos:
            resultado = {
                "estado": EM_EXECUCAO,
                "motivo": prs_abertos[tid],
                "quem": (ultimo_ciclo or {}).get("quem"),
            }
        elif reivindicada:
            quem = (ultimo_ciclo or {}).get("quem") or "reserva ativa no almoxarife"
            resultado = {"estado": REIVINDICADA, "motivo": "", "quem": quem}
        estados[tid] = resultado
        return resultado

    for tid in tarefas:
        estado_de(tid)
    return estados


# ---------------------------------------------------------------------------
# As leituras ao vivo — servidor e PRs. Só `listar --ao-vivo` e `pegar` usam.
# ---------------------------------------------------------------------------


def reservas_no_servidor(raiz: Path) -> set[str]:
    """Ids de tarefa com referência viva em refs/reservas/tarefa-*."""
    ativos: set[str] = set()
    for ref in reservar.refs_existentes(raiz, reservar.NS_RESERVA):
        cauda = ref.rsplit("/", 1)[-1]
        if cauda.startswith(PREFIXO_DA_RESERVA):
            ativos.add(cauda[len(PREFIXO_DA_RESERVA):])
    return ativos


def prs_citando_tarefas(raiz: Path) -> dict[str, str]:
    """id → 'PR #N' para todo PR ABERTO cujo título ou ramo cita TAR-NNN."""
    proc = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--json", "number,title,headRefName"],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise ErroDeInstrumentacao(
            "não consegui listar os PRs abertos",
            proc.stderr.strip()[:400] + "\nSem essa leitura, 'em execução' viraria chute.",
        )
    achados: dict[str, str] = {}
    for pr in json.loads(proc.stdout or "[]"):
        texto = f"{pr.get('title', '')} {pr.get('headRefName', '')}"
        for tid in re.findall(r"TAR-\d{3,}", texto):
            achados.setdefault(tid, f"PR #{pr['number']}")
    return achados


# ---------------------------------------------------------------------------
# Os gestos
# ---------------------------------------------------------------------------


def _slug(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    plano = re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")
    return plano[:60] or "tarefa"


def _escrever_json(caminho: Path, dados: dict) -> None:
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _escrever_evento(
    raiz: Path,
    tid: str,
    evento: str,
    quem: str,
    detalhe: str | None = None,
    evidencia: str | None = None,
    verificado_em: str | None = None,
    agora: datetime | None = None,
) -> Path:
    agora = agora or datetime.now(timezone.utc)
    pasta = pasta_eventos(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    stem = f"{agora.strftime('%Y%m%d-%H%M%S')}-{tid}-{evento}"
    dados: dict = {
        "arquivo": stem,
        "tarefa": tid,
        "evento": evento,
        "quando": agora.isoformat(timespec="seconds"),
        "quem": quem,
    }
    if detalhe:
        dados["detalhe"] = detalhe
    if evidencia:
        dados["evidencia"] = evidencia
    if verificado_em:
        dados["verificado_em"] = verificado_em
    caminho = pasta / f"{stem}.json"
    _escrever_json(caminho, dados)
    return caminho


def _carregar_ou_parar(raiz: Path) -> tuple[dict[str, dict], list[dict]]:
    erros: list[str] = []
    tarefas = carregar_tarefas(raiz, erros)
    eventos = carregar_eventos(raiz, tarefas, erros)
    if erros:
        raise ErroDeInstrumentacao(
            "a fila está inválida — conserte antes de mexer nela",
            "\n".join(f"  - {e}" for e in erros),
        )
    return tarefas, eventos


def cmd_criar(raiz: Path, args) -> int:
    despacho = args.despacho
    if args.despacho_arquivo:
        despacho = Path(args.despacho_arquivo).read_text(encoding="utf-8").strip()
    if not (despacho or "").strip():
        print("RECUSADO: tarefa sem despacho pronto não entra na fila —")
        print("é o prompt de colar que os três consultores pediram. Use --despacho.")
        return 1
    tarefas, _ = _carregar_ou_parar(raiz)
    for dep in args.depende_de:
        if dep not in tarefas:
            print(f"RECUSADO: --depende-de {dep} não existe na fila.")
            return 1
    numero = reservar.alocar_numero(raiz, "tarefa")
    tid = f"TAR-{numero}"
    stem = f"{numero}-{_slug(args.titulo)}"
    pasta = pasta_tarefas(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {
        "arquivo": stem,
        "id": tid,
        "titulo": args.titulo,
        "toca": args.toca,
        "depende_de": args.depende_de,
        "evidencia_exigida": args.evidencia_exigida,
        "despacho": despacho,
        "origem": args.origem,
        "criada_em": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    caminho = pasta / f"{stem}.json"
    _escrever_json(caminho, dados)
    print(f"{tid} criada: {caminho.relative_to(raiz)}")
    return 0


def cmd_listar(raiz: Path, args) -> int:
    tarefas, eventos = _carregar_ou_parar(raiz)
    reservas: set[str] = set()
    prs: dict[str, str] = {}
    if args.ao_vivo:
        reservas = reservas_no_servidor(raiz)
        prs = prs_citando_tarefas(raiz)
    estados = calcular_estados(tarefas, eventos, reservas, prs)
    if args.json:
        visao = {
            tid: {**estados[tid], "titulo": tarefas[tid]["titulo"], "toca": tarefas[tid]["toca"]}
            for tid in sorted(tarefas)
        }
        print(json.dumps(visao, ensure_ascii=False, indent=2))
        return 0
    if not tarefas:
        print("a fila está vazia.")
        return 0
    modo = "ao vivo (arquivos + reservas + PRs)" if args.ao_vivo else "só arquivos (use --ao-vivo para reservas e PRs)"
    print(f"A FILA DE TRABALHO — {len(tarefas)} tarefa(s) · {modo}\n")
    for tid in sorted(tarefas):
        t, e = tarefas[tid], estados[tid]
        extra = f" · {e['quem']}" if e.get("quem") else ""
        motivo = f" — {e['motivo']}" if e.get("motivo") else ""
        print(f"  {tid}  [{e['estado']}{extra}]{motivo}")
        print(f"         {t['titulo']}  (toca: {', '.join(t['toca'])})")
    return 0


def cmd_pegar(raiz: Path, args) -> int:
    tarefas, eventos = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    reservas = reservas_no_servidor(raiz)
    prs = prs_citando_tarefas(raiz)
    estado = calcular_estados(tarefas, eventos, reservas, prs)[tid]
    if estado["estado"] != NA_FILA:
        print(f"RECUSADO: {tid} está '{estado['estado']}'" + (f" ({estado['motivo']})" if estado["motivo"] else "") + ".")
        print("Só tarefa NA FILA se pega. Veja o quadro: python ci/fila.py listar --ao-vivo")
        return 1
    ganhou, recado = reservar.reservar_intencao(
        raiz, f"{PREFIXO_DA_RESERVA}{tid}", objetivo=tarefas[tid]["titulo"]
    )
    if not ganhou:
        print(f"RECUSADO PELO SERVIDOR: {recado}")
        return 1
    caminho = _escrever_evento(raiz, tid, "reivindicada", args.quem)
    print(f"✅ {tid} é sua — {recado}")
    print(f"   evento: {caminho.relative_to(raiz)} (commite-o no seu PR)")
    print(f"   evidência exigida para concluir: {tarefas[tid]['evidencia_exigida']}\n")
    print("── DESPACHO ────────────────────────────────────────────────")
    print(tarefas[tid]["despacho"])
    print("────────────────────────────────────────────────────────────")
    return 0


def cmd_soltar(raiz: Path, args) -> int:
    tarefas, _ = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    _soltar_reserva_se_houver(raiz, tid)
    caminho = _escrever_evento(raiz, tid, "devolvida", args.quem, detalhe=args.motivo)
    print(f"{tid} devolvida à fila. Evento: {caminho.relative_to(raiz)}")
    return 0


def cmd_concluir(raiz: Path, args) -> int:
    tarefas, eventos = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    estado = calcular_estados(tarefas, eventos)[tid]
    if estado["estado"] in (CONCLUIDA, CANCELADA):
        print(f"RECUSADO: {tid} já terminou ({estado['estado']}).")
        return 1
    if not (args.evidencia or "").strip():
        print("RECUSADO: concluir sem evidência não existe — a mesma lei do verde do livro.")
        print(f"O que esta tarefa exige: {tarefas[tid]['evidencia_exigida']}")
        return 1
    _soltar_reserva_se_houver(raiz, tid)
    caminho = _escrever_evento(
        raiz,
        tid,
        "concluida",
        args.quem,
        evidencia=args.evidencia,
        verificado_em=args.verificado_em or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
    print(f"✅ {tid} concluída. Evento: {caminho.relative_to(raiz)} (commite-o no seu PR)")
    return 0


def _soltar_reserva_se_houver(raiz: Path, tid: str) -> None:
    """Solta a referência no servidor; se ela não existir, não é erro."""
    try:
        reservar.soltar(raiz, f"{PREFIXO_DA_RESERVA}{tid}")
    except ErroDeInstrumentacao as erro:
        texto = f"{erro.resumo}\n{erro.detalhe or ''}"
        if "remote ref does not exist" in texto or "unable to delete" in texto:
            return
        raise


def cmd_validar(raiz: Path) -> int:
    if not (raiz / "fila").is_dir():
        print("❌ FILA: a pasta fila/ não existe.")
        print("   A fila de trabalho faz parte do repositório desde 29/08/2026 —")
        print("   apagá-la (ou movê-la) não pode passar verde.")
        return 1
    erros: list[str] = []
    tarefas = carregar_tarefas(raiz, erros)
    eventos = carregar_eventos(raiz, tarefas, erros)
    if erros:
        print(f"❌ FILA INVÁLIDA — {len(erros)} problema(s):")
        for erro in erros:
            print(f"   - {erro}")
        return 1
    estados = calcular_estados(tarefas, eventos)
    contagem: dict[str, int] = {}
    for e in estados.values():
        contagem[e["estado"]] = contagem.get(e["estado"], 0) + 1
    resumo = " · ".join(f"{k}: {v}" for k, v in sorted(contagem.items())) or "vazia"
    print(f"✅ Fila válida — {len(tarefas)} tarefa(s), {len(eventos)} evento(s) ({resumo}).")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A fila de trabalho: tarefa registrada, estado calculado, trava no servidor."
    )
    sub = parser.add_subparsers(dest="acao", required=True)

    p = sub.add_parser("criar", help="registra uma tarefa nova (número vem do almoxarife)")
    p.add_argument("--titulo", required=True, help="uma linha, para leigo, sem sigla")
    p.add_argument("--toca", required=True, nargs="+", help="o que ela mexe (ex.: admin painel)")
    p.add_argument("--depende-de", nargs="*", default=[], metavar="TAR-NNN")
    p.add_argument("--evidencia-exigida", required=True, help="que prova fecha esta tarefa")
    p.add_argument("--despacho", default="", help="o prompt pronto para colar")
    p.add_argument("--despacho-arquivo", default="", help="ou um arquivo com o despacho")
    p.add_argument("--origem", default="despacho do mantenedor", help="de onde a tarefa veio")

    p = sub.add_parser("listar", help="o quadro, com estados calculados")
    p.add_argument("--ao-vivo", action="store_true", help="soma reservas do servidor e PRs abertos")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("pegar", help="trava a tarefa no servidor e escreve o evento")
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True, help="quem está pegando (ex.: sessao-fila-2908)")

    p = sub.add_parser("soltar", help="devolve a tarefa à fila")
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True)
    p.add_argument("--motivo", default="", help="por que está devolvendo")

    p = sub.add_parser("concluir", help="fecha a tarefa — exige evidência")
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True)
    p.add_argument("--evidencia", required=True, help="a prova (URL de PR, saída de teste…)")
    p.add_argument("--verificado-em", default="", help="quando a prova foi conferida (AAAA-MM-DD)")

    sub.add_parser("validar", help="fail-closed; é o que a muralha roda")
    return parser


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    args = construir_parser().parse_args(argv)
    try:
        raiz = raiz_do_repo()
        if args.acao == "criar":
            return cmd_criar(raiz, args)
        if args.acao == "listar":
            return cmd_listar(raiz, args)
        if args.acao == "pegar":
            return cmd_pegar(raiz, args)
        if args.acao == "soltar":
            return cmd_soltar(raiz, args)
        if args.acao == "concluir":
            return cmd_concluir(raiz, args)
        return cmd_validar(raiz)
    except ErroDeInstrumentacao as erro:
        print(f"\nPAROU POR SEGURANÇA: {erro.resumo}\n")
        if erro.detalhe:
            print(erro.detalhe)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
