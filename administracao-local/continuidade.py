from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

NOME_DA_VIGILIA = "Triade - vigilia do painel local"
LIMITE_DE_ITERACOES = 10
LIMITE_DE_TOKENS = 300_000
MINUTOS_DE_TRAVA_VIVA = 60
ARQUIVO_DE_ESTADO = "estado-da-continuidade.json"
ARQUIVO_DE_TRAVA = "continuidade.lock"


def agora() -> datetime:
    return datetime.now(timezone.utc)


def raiz_do_repositorio() -> Path:
    return Path(__file__).resolve().parents[1]


def pasta_do_plano() -> Path:
    configurada = os.environ.get("ADMIN_PLANOS_DIR", "").strip()
    if configurada:
        return Path(configurada)
    return raiz_do_repositorio().parent / "sitesdoreino-docs" / "administracao-local"


def caminho_estado() -> Path:
    return pasta_do_plano() / ARQUIVO_DE_ESTADO


def estado_inicial() -> dict:
    return {
        "tarefa_corrente": "TAR-316",
        "passo": "inicio",
        "iteracoes_gastas": 0,
        "sessoes_rodadas": 0,
        "tarefas_fechadas": [],
        "bloqueios": [],
        "ultima_sessao": "",
        "ultimo_handoff": "",
        "ultima_saida": "",
        "ultima_sequencia_lida": 0,
        "lista_autorizada": [
            "TAR-316",
            "TAR-319 / PR #1621",
            "TAR-412 / PR #1640",
            "PR #1656",
            "proxima costura do 37-BANCADA-VIVA",
        ],
    }


def carregar_estado() -> dict:
    arquivo = caminho_estado()
    if not arquivo.exists():
        return estado_inicial()
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise RuntimeError(
            f"PAROU POR SEGURANCA: o estado em {arquivo} não é JSON válido. "
            "Corrija ou remova o arquivo e rode novamente."
        ) from None
    if not isinstance(dados, dict):
        raise RuntimeError(
            f"PAROU POR SEGURANCA: o estado em {arquivo} não é um objeto JSON. "
            "Corrija ou remova o arquivo e rode novamente."
        )
    base = estado_inicial()
    base.update(dados)
    return base


def salvar_estado(estado: dict) -> None:
    pasta = pasta_do_plano()
    pasta.mkdir(parents=True, exist_ok=True)
    caminho_estado().write_text(
        json.dumps(estado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _rodar_radio(argumentos: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "ci/radio.py", *argumentos],
        cwd=raiz_do_repositorio(),
        text=True,
        capture_output=True,
        timeout=30,
    )


def falar_no_radio(texto: str, tipo: str = "boletim") -> bool:
    try:
        resultado = _rodar_radio(
            ["dizer", texto[:2000], "--autor", "codex", "--tipo", tipo]
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return resultado.returncode == 0


def ler_radio(desde: int = 0) -> dict:
    try:
        resultado = _rodar_radio(["ler", "--desde", str(desde)])
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError(
            "PAROU POR SEGURANCA: não consegui falar com o rádio. "
            "Ligue o site com python ci/ligar_administracao.py e rode novamente."
        ) from None
    if resultado.returncode != 0:
        detalhe = (resultado.stderr or resultado.stdout).strip()
        raise RuntimeError(
            "PAROU POR SEGURANCA: o rádio recusou a leitura. "
            f"{detalhe or 'Confira o servidor local e tente novamente.'}"
        )
    primeira_linha = (resultado.stdout or "").splitlines()[0:1]
    try:
        dados = json.loads(primeira_linha[0])
    except (IndexError, json.JSONDecodeError):
        raise RuntimeError(
            "PAROU POR SEGURANCA: o rádio respondeu fora do formato esperado. "
            "Abra a página do rádio e tente novamente."
        ) from None
    if not isinstance(dados, dict):
        raise RuntimeError(
            "PAROU POR SEGURANCA: o rádio respondeu fora do formato esperado. "
            "Abra a página do rádio e tente novamente."
        )
    return dados


def mantenedor_mandou_parar() -> bool:
    mensagens = ler_radio(0).get("mensagens", [])
    do_mantenedor = [
        item
        for item in mensagens
        if isinstance(item, dict) and item.get("autor") == "mantenedor"
    ]
    if not do_mantenedor:
        return False
    return (do_mantenedor[-1].get("texto") or "").strip().casefold() == "parar"


def freio_de_mao_acionado() -> str:
    if (pasta_do_plano() / "PARAR").exists():
        return "arquivo PARAR presente na pasta do plano mestre"
    if mantenedor_mandou_parar():
        return "última fala do mantenedor no rádio foi parar"
    return ""


def _pid_vivo(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _ler_json(caminho: Path) -> dict:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


@contextmanager
def instancia_unica():
    pasta = pasta_do_plano()
    pasta.mkdir(parents=True, exist_ok=True)
    trava = pasta / ARQUIVO_DE_TRAVA
    if trava.exists():
        dados = _ler_json(trava)
        pid = int(dados.get("pid") or 0)
        sinal = dados.get("sinal_em") or dados.get("iniciada_em") or ""
        try:
            idade = (agora() - datetime.fromisoformat(sinal)).total_seconds()
        except ValueError:
            idade = MINUTOS_DE_TRAVA_VIVA * 60 + 1
        if _pid_vivo(pid) and idade <= MINUTOS_DE_TRAVA_VIVA * 60:
            print(f"continuidade já em andamento: PID {pid}, sinal em {sinal}")
            yield False
            return
        trava.unlink(missing_ok=True)

    ativo = True
    inicio = agora().isoformat()

    def escrever_sinal():
        conteudo = {
            "pid": os.getpid(),
            "iniciada_em": inicio,
            "sinal_em": agora().isoformat(),
        }
        trava.write_text(
            json.dumps(conteudo, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    escrever_sinal()

    def bater():
        while ativo:
            time.sleep(30)
            try:
                escrever_sinal()
            except OSError:
                return

    thread = threading.Thread(target=bater, daemon=True)
    thread.start()
    try:
        yield True
    finally:
        ativo = False
        trava.unlink(missing_ok=True)


def prompt_de_retomada(estado: dict) -> str:
    caminho = (
        raiz_do_repositorio() / "administracao-local" / "prompt-da-continuidade.md"
    )
    try:
        base = caminho.read_text(encoding="utf-8")
    except OSError:
        raise RuntimeError(
            f"PAROU POR SEGURANCA: não encontrei {caminho}. "
            "Restaure o prompt da continuidade e rode novamente."
        ) from None
    contexto = json.dumps(estado, ensure_ascii=False, indent=2)
    return (
        f"{base.strip()}\n\n"
        "Estado atual lido pelo motor antes desta sessão:\n"
        f"```json\n{contexto}\n```\n"
    )


def _tokens_aproximados(texto: str) -> int:
    return max(1, len(texto) // 4)


def rodar_claude(prompt: str) -> subprocess.CompletedProcess:
    if shutil.which("claude") is None:
        raise RuntimeError(
            "PAROU POR SEGURANCA: claude não está no PATH. "
            "Abra um terminal onde Claude Code esteja disponível e rode novamente."
        )
    return subprocess.run(
        [
            "claude",
            "-p",
            "--model",
            "sonnet",
            "--permission-mode",
            "acceptEdits",
        ],
        cwd=raiz_do_repositorio(),
        input=prompt,
        text=True,
        capture_output=True,
        timeout=60 * 60,
    )


def atualizar_estado_apos_sessao(
    estado: dict, resultado: subprocess.CompletedProcess
) -> dict:
    saida = ((resultado.stdout or "") + "\n" + (resultado.stderr or "")).strip()
    tokens = _tokens_aproximados(saida)
    estado["sessoes_rodadas"] = int(estado.get("sessoes_rodadas") or 0) + 1
    estado["iteracoes_gastas"] = min(
        LIMITE_DE_ITERACOES, int(estado.get("iteracoes_gastas") or 0) + 1
    )
    estado["tokens_gastos_na_ultima_sessao"] = tokens
    estado["ultima_sessao"] = agora().isoformat()
    estado["ultima_saida"] = saida[-4000:]
    estado["ultimo_handoff"] = saida[-700:] if saida else "sessão sem saída textual"
    if estado["iteracoes_gastas"] >= LIMITE_DE_ITERACOES:
        estado["passo"] = "limite de 10 passos atingido"
    return estado


def parar_por_seguranca(mensagem: str, codigo: int = 2) -> int:
    print(mensagem)
    falar_no_radio(mensagem)
    return codigo


def main() -> int:
    try:
        pasta = pasta_do_plano()
        if not pasta.exists():
            return parar_por_seguranca(
                f"PAROU POR SEGURANCA: a pasta do plano mestre não existe em {pasta}. "
                "Crie a pasta ou defina ADMIN_PLANOS_DIR e rode novamente."
            )

        motivo = freio_de_mao_acionado()
        if motivo:
            texto = f"continuidade parada pelo freio de mão: {motivo}"
            print(texto)
            falar_no_radio(texto)
            return 0

        with instancia_unica() as pode_trabalhar:
            if not pode_trabalhar:
                return 0
            estado = carregar_estado()
            if int(estado.get("iteracoes_gastas") or 0) >= LIMITE_DE_ITERACOES:
                estado["iteracoes_gastas"] = 0
                estado["passo"] = "nova sessão após handoff do limite anterior"
            prompt = prompt_de_retomada(estado)
            if _tokens_aproximados(prompt) > LIMITE_DE_TOKENS:
                return parar_por_seguranca(
                    "PAROU POR SEGURANCA: o prompt de retomada passou de 300.000 tokens. "
                    "Encurte o estado da continuidade e rode novamente."
                )
            resultado = rodar_claude(prompt)
            estado = atualizar_estado_apos_sessao(estado, resultado)
            salvar_estado(estado)
            resumo = (
                "continuidade rodou sessão "
                f"{estado['sessoes_rodadas']}: {estado['ultimo_handoff'][:300]}"
            )
            falar_no_radio(resumo)
            print(resumo)
            if resultado.returncode != 0:
                return parar_por_seguranca(
                    "PAROU POR SEGURANCA: Claude Code encerrou com erro. "
                    "Leia o estado da continuidade e a saída acima antes de rodar de novo."
                )
            if estado["tokens_gastos_na_ultima_sessao"] > LIMITE_DE_TOKENS:
                return parar_por_seguranca(
                    "PAROU POR SEGURANCA: a última sessão passou de 300.000 tokens. "
                    "Leia o handoff no estado antes de rodar de novo."
                )
            return 0
    except RuntimeError as erro:
        return parar_por_seguranca(str(erro))


if __name__ == "__main__":
    raise SystemExit(main())
