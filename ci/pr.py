"""Fecha a bancada com validação executada, PR aberto e recibo rastreável.

`make pr VALIDACAO=validacao.json` executa os comandos declarados como listas
JSON, sem shell. A evidência corresponde à árvore entregue. Reexecuções
consultam efeitos existentes. Revisão, integração e publicação continuam
sob responsabilidade dos mecanismos próprios, sem aprovação implícita.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import uuid
import tempfile
import subprocess
import os
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    executar,
    raiz_do_repo,
)
import telemetria
from muralha_pasta_compartilhada import raiz_do_checkout  # noqa: E402

# O vocabulário do livro. Copiado de `painel/logica.js` de propósito: o
# validador de lá é a autoridade e reprova de qualquer jeito; conferir aqui
# transforma um FAIL do gerador (passo 8, com o PR já aberto) numa recusa na
# porta (passo 1, sem nada gravado).
TIPOS = ("decisao", "pendencia", "resposta", "entrega", "incidente", "medicao", "nota")
GRAVIDADES = ("vermelho", "ambar", "info", "verde")
FRENTES = ("site", "comunidade", "curso", "vender", "fabrica")

# A frente sai dos caminhos tocados quando ninguém a declara. Prefixo mais
# longo vence; a frente com mais arquivos vence; EMPATE FICA NULO, porque
# `frente` é opcional e um chute mandaria o fato para o capítulo errado do
# mapa do mantenedor.
FRENTE_POR_CAMINHO = (
    ("services/forum/", "comunidade"),
    ("services/sugestoes/", "comunidade"),
    ("services/cursos/", "curso"),
    ("services/alunos/", "curso"),
    ("services/checkout/", "vender"),
    ("services/pagamentos/", "vender"),
    ("services/encomendas/", "vender"),
    ("services/catalogo/", "vender"),
    ("services/funil/", "vender"),
    ("services/leads/", "vender"),
    ("services/", "site"),
    ("documentos/", "site"),
    ("ci/", "fabrica"),
    (".github/", "fabrica"),
    ("Makefile", "fabrica"),
    ("painel/", "fabrica"),
    ("fila/", "fabrica"),
    ("armadilhas/", "fabrica"),
    ("docs/", "fabrica"),
    ("e2e/", "fabrica"),
    ("infra/", "fabrica"),
    ("contracts/", "fabrica"),
    ("constituicoes/", "fabrica"),
    ("celula-template/", "fabrica"),
)

# 80 caracteres é pouco para um bom `detalhe` (a mediana medida são 416) e é
# muito para "consertei o bug". O piso existe para o campo não nascer vazio,
# não para medir qualidade — isso quem lê é o mantenedor.
MINIMO_DO_DETALHE = 80

COAUTOR = "Co-Authored-By"
PRAZO_VALIDACAO_PADRAO = 900


class PrazoDeValidacaoExcedido(ErroDeInstrumentacao):
    """A prova ficou incompleta e precisa ser executada novamente."""


class ValidacaoReprovada(ErroDeInstrumentacao):
    """O comando terminou e devolveu um código diferente de zero."""


class ParouPorSeguranca(Exception):
    """Recusa na porta: o rito não começou, ou parou antes de gravar.

    Diferente de `ErroDeInstrumentacao` (o comando rodou e falhou): aqui a
    condição foi CONFERIDA e não serve. Sempre traz o que fazer.
    """

    def __init__(self, resumo: str, o_que_fazer: str) -> None:
        super().__init__(resumo)
        self.resumo = resumo
        self.o_que_fazer = o_que_fazer


@dataclass
class Pedido:
    titulo: str
    mensagem_arquivo: Path
    corpo_arquivo: Path
    arquivos: list[str]
    detalhe: str
    tipo: str = "entrega"
    gravidade: str = "info"
    frente: str | None = None
    evidencia: str = ""
    continuar: bool = False
    validacao_arquivo: Path | None = None
    tarefa: str | None = None


# ---------------------------------------------------------------- a costura --


def _sanitizar(texto: str) -> str:
    texto = re.sub(
        r"""(?i)((?:\\?["'])?authorization(?:\\?["'])?\s*[:=]\s*)(?:\\?["'])?(?:Bearer|Basic)\s+[^\s"'\\,;}]+(?:\\?["'])?""",
        r"\1<REDIGIDO>", texto,
    )
    return re.sub(
        r"""(?i)((?:\\?["'])?(?:password|senha|token|access_token|secret|api_key|authorization)(?:\\?["'])?\s*[:=]\s*)(?:\\".*?\\"|\\'.*?\\'|"[^"]*"|'[^']*'|[^\s,;]+)""",
        r"\1<REDIGIDO>", telemetria.redigir(texto),
    )


def _conferir_prazo(valor):
    if type(valor) is not int or not 1 <= valor <= 7200:
        raise ParouPorSeguranca(
            "prazo_segundos inválido; validação NÃO EXECUTADA",
            "Use um inteiro de 1 a 7200 no JSON de validação; omita o campo para usar 900 segundos por comando.",
        )
    return valor


def rodar(comando: list[str], raiz: Path, *, log: Path | None = None,
          prazo_segundos: int = PRAZO_VALIDACAO_PADRAO) -> str:
    if log is None:
        return executar(comando, cwd=raiz, descricao=f"rodar `{' '.join(comando)}`", timeout=300).stdout
    _conferir_prazo(prazo_segundos)
    cabecalho = f"Comando: {json.dumps(comando)}\nPrazo por comando: {prazo_segundos}s\nInício UTC: {datetime.now(timezone.utc).isoformat()}\n"
    ambiente = {**os.environ, "PYTHONPATH": str(raiz), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    processo = grupo = None
    expirou = False
    stdout = stderr = ''
    def encerrar():
        if grupo is not None:
            grupo.encerrar()
    try:
        if os.name == 'nt':
            from pr_processos_windows import GrupoWindows
            grupo = GrupoWindows()
        else:
            from pr_processos_linux import GrupoLinux
            grupo = GrupoLinux()
        try:
            processo = subprocess.Popen(
                comando, cwd=raiz, env=ambiente, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace',
                creationflags=0x00000004 if os.name == 'nt' else 0,
                start_new_session=os.name != 'nt',
            )
            if grupo is not None:
                grupo.associar_e_iniciar(processo)
            try:
                stdout, stderr = processo.communicate(timeout=prazo_segundos)
            except subprocess.TimeoutExpired as erro:
                expirou = True
                stdout, stderr = erro.stdout or '', erro.stderr or ''
                encerrar()
                stdout, stderr = processo.communicate(timeout=10)
        finally:
            try:
                encerrar()
            finally:
                if processo is not None:
                    if processo.poll() is None:
                        processo.kill()
                    processo.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired) as erro:
        partes = [cabecalho, f"ERROR: {type(erro).__name__}: {erro}\n"]
        for nome in ("stdout", "stderr"):
            valor = getattr(erro, nome, None) or (stdout if nome == 'stdout' else stderr)
            if isinstance(valor, bytes):
                valor = valor.decode("utf-8", errors="replace")
            partes.append(f"{nome}:\n{valor}\n")
        log.write_text(_sanitizar("".join(partes)), encoding="utf-8")
        raise ErroDeInstrumentacao("a validação não pôde executar ou encerrar seus processos", _sanitizar(f"{erro}\nConfira o executável, as permissões do sistema e o log privado {log}; execute uma nova validação.")) from erro
    estado = 'TIMEOUT' if expirou else ('PASS' if processo.returncode == 0 else 'FAIL')
    texto = f"{cabecalho}Fim UTC: {datetime.now(timezone.utc).isoformat()}\nResultado: {estado}\nExit: {processo.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    log.write_text(_sanitizar(texto), encoding="utf-8")
    if expirou:
        raise PrazoDeValidacaoExcedido(f"validação não aprovada: TIMEOUT após {prazo_segundos}s", f"Leia o log privado {log}; ajuste prazo_segundos no JSON se necessário e retome. A prova incompleta não será reutilizada.")
    if processo.returncode != 0:
        raise ValidacaoReprovada(f"validação não aprovada: exit {processo.returncode}", f"Leia o log privado {log} e corrija a causa antes de retomar.")
    return stdout + "\n" + stderr


# ------------------------------------------------------------ as derivações --


def slug_do_titulo(titulo: str) -> str:
    sem_acento = (
        unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return slug[:60].strip("-") or "registro"


def _encurtar(texto: str, limite: int) -> str:
    """Corta no espaço, nunca no meio da palavra: o assunto de um commit é lido."""
    if len(texto) <= limite:
        return texto
    cortado = texto[:limite].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cortado or texto[:limite]


def derivar_frente(caminhos: list[str]) -> str | None:
    contagem: Counter[str] = Counter()
    for caminho in caminhos:
        normal = caminho.replace("\\", "/")
        melhor = max(
            (p for p, _ in FRENTE_POR_CAMINHO if normal.startswith(p)),
            key=len,
            default=None,
        )
        if melhor is not None:
            contagem[dict(FRENTE_POR_CAMINHO)[melhor]] += 1
    if not contagem:
        return None
    mais = contagem.most_common()
    if len(mais) > 1 and mais[0][1] == mais[1][1]:
        return None
    return mais[0][0]


def montar_campos(
    *,
    arquivo: str,
    titulo: str,
    detalhe: str,
    url_do_pr: str,
    dia: date,
    tipo: str,
    gravidade: str,
    frente: str | None,
    evidencia_extra: str,
    area: str | None = None,
    tarefa: str | None = None,
) -> dict:
    """Os 14 campos do molde: 11 derivados do PR, 1 de julgamento, 2 de opção."""
    evidencia = url_do_pr
    if evidencia_extra.strip():
        evidencia = f"{url_do_pr}. {evidencia_extra.strip()}"
    iso = dia.isoformat()
    return {
        "arquivo": arquivo,
        "tipo": tipo,
        "quando": iso,
        "titulo": titulo,
        "detalhe": detalhe.strip(),
        "autoridade": "github",
        "evidencia": evidencia,
        "verificado_em": iso,
        "precisa_do_dono": False,
        "responde_a": None,
        "relacao": "comentario",
        "tarefa": tarefa,
        "gravidade": gravidade,
        "frente": frente,
        "area": area,
        "vence_em_dias": None,
        "se_eu_nao_decidir": None,
        "recomendacao": None,
        "reversivel": None,
    }


def renderizar(campos: dict) -> str:
    """O molde de `painel/LEIA-ME.md`, com cada valor escapado como JSON.

    `json.dumps` e não formatação à mão: uma aspa ou uma quebra de linha dentro
    do `detalhe` viraria um arquivo que nem carrega, e o painel morreria inteiro
    por causa de um caractere.
    """
    linhas = [
        "(function(){ (window.REGISTROS = window.REGISTROS || []).push({",
    ]
    for chave, valor in campos.items():
        linhas.append(f"  {chave}: {json.dumps(valor, ensure_ascii=False)},")
    linhas[-1] = linhas[-1].rstrip(",")
    linhas.append("}); })();")
    return "\n".join(linhas) + "\n"


def campos_lidos(texto: str) -> dict:
    """Relê um registro escrito por `renderizar`. Existe para o teste comparar
    campo a campo em vez de procurar substring."""
    corpo = texto[texto.index("push({") + len("push({") : texto.rindex("});")]
    return json.loads("{" + re.sub(r"^\s*(\w+):", r'"\1":', corpo, flags=re.M) + "}")


# ---------------------------------------------------------------- os passos --


def _conferir_o_pedido(raiz: Path, pedido: Pedido) -> None:
    """Passo 1, primeira metade: o que se confere SEM tocar no mundo."""
    if len(pedido.detalhe.strip()) < MINIMO_DO_DETALHE:
        raise ParouPorSeguranca(
            f"o `detalhe` do registro tem {len(pedido.detalhe.strip())} caracteres "
            f"(o mínimo é {MINIMO_DO_DETALHE})",
            "O `detalhe` é a ÚNICA frase que o mantenedor lê sobre esta entrega, e\n"
            "ela é julgamento: o que mudou, o que isso resolve, o que ficou de fora.\n"
            "Escreva em `--detalhe-arquivo <arquivo>` (ou `--detalhe \"...\"`) e rode\n"
            "de novo. Nada foi gravado.",
        )
    if pedido.tipo not in TIPOS:
        raise ParouPorSeguranca(
            f"tipo de registro desconhecido: {pedido.tipo!r}",
            f"Use `--tipo` com um destes: {', '.join(TIPOS)}.",
        )
    if pedido.gravidade not in GRAVIDADES:
        raise ParouPorSeguranca(
            f"gravidade desconhecida: {pedido.gravidade!r}",
            f"Use `--gravidade` com uma destas: {', '.join(GRAVIDADES)}.",
        )
    if pedido.frente is not None and pedido.frente not in FRENTES:
        raise ParouPorSeguranca(
            f"frente desconhecida: {pedido.frente!r}",
            f"Use `--frente` com uma destas: {', '.join(FRENTES)}.",
        )
    for rotulo, caminho in (
        ("--mensagem-arquivo", pedido.mensagem_arquivo),
        ("--corpo-arquivo", pedido.corpo_arquivo),
    ):
        if not Path(caminho).is_file():
            raise ParouPorSeguranca(
                f"{rotulo} aponta para um arquivo que não existe: {caminho}",
                "Escreva a mensagem e o corpo do PR em ARQUIVO, nunca inline: heredoc\n"
                "come um nível de escape e já corrompeu texto nesta casa\n"
                "(`armadilhas/070` e `093`). Nada foi gravado.",
            )
    for texto in (pedido.titulo, pedido.detalhe, Path(pedido.corpo_arquivo).read_text(encoding="utf-8"), Path(pedido.mensagem_arquivo).read_text(encoding="utf-8")):
        if _sanitizar(texto) != texto:
            raise ParouPorSeguranca("texto contém possível segredo", "Remova credenciais do texto; forneça segredos somente pelo ambiente apropriado.")
    mensagem = Path(pedido.mensagem_arquivo).read_text(encoding="utf-8")
    if COAUTOR not in mensagem:
        raise ParouPorSeguranca(
            "a mensagem de commit não termina com a linha de coautoria",
            "O rito manda toda mensagem de commit terminar com:\n"
            "  Co-Authored-By: Codex <noreply@openai.com>\n"
            f"Acrescente ao fim de {pedido.mensagem_arquivo} e rode de novo.",
        )
    checkout = raiz_do_checkout(Path(raiz))
    if checkout is None:
        raise ParouPorSeguranca(
            f"não achei um .git subindo a partir de {raiz}",
            "Rode `make pr` de dentro da sua bancada (RITOS.md §1):\n"
            "  git worktree add ../wt-<area>-<tarefa> -b agent/<area>/<tarefa> origin/main",
        )
    _, principal = checkout
    if principal:
        raise ParouPorSeguranca(
            f"isto é o CLONE PRINCIPAL ({checkout[0]}), que é espelho e não bancada",
            "Duas sessões dividindo a pasta principal já apagaram o trabalho uma da\n"
            "outra (26/08/2026, `armadilhas/135`). Crie seu worktree e rode lá:\n"
            "  git fetch origin\n"
            "  git worktree add ../wt-<area>-<tarefa> -b agent/<area>/<tarefa> origin/main\n"
            "Nada foi gravado.",
        )


def _configuracao_de_validacao(pedido: Pedido) -> tuple[list[list[str]], int]:
    try:
        dados = json.loads(Path(pedido.validacao_arquivo).read_text(encoding="utf-8"))
        comandos = dados["comandos"]
        if not isinstance(comandos, list) or not comandos or any(
            not isinstance(c, list) or not c
            or any(not isinstance(a, str) or not a.strip() for a in c)
            for c in comandos
        ):
            raise ValueError("comandos inválidos")
        return comandos, _conferir_prazo(dados.get('prazo_segundos', PRAZO_VALIDACAO_PADRAO))
    except (OSError, TypeError, ValueError, KeyError) as erro:
        raise ParouPorSeguranca(
            "validação obrigatória ausente ou inválida; NÃO EXECUTADA",
            'Informe --validacao-arquivo com {"comandos": [["python", "-m", "pytest", "ci/tests"]]}.',
        ) from erro


def _hash_git(valor: str) -> str:
    valor = valor.strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", valor):
        raise ErroDeInstrumentacao("Git não informou a revisão", "Confira git rev-parse HEAD antes de retomar.")
    return valor


EXTENSOES_DE_FONTE = frozenset({
    ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js",
    ".jsx", ".php", ".py", ".pyi", ".rb", ".rs", ".sh", ".ts", ".tsx",
})
ARQUIVOS_DE_CONFIGURACAO_DE_TESTE = frozenset({
    "conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini",
    "sitecustomize.py", "usercustomize.py",
})


def _conferir_revisao_validada(raiz, commit, rodar, arvore_esperada=None):
    revisao = _hash_git(rodar(["git", "rev-parse", "HEAD"], raiz))
    if revisao != commit:
        raise ParouPorSeguranca(
            f"a validação trocou a revisão: está em {revisao}, mas a prova exige {commit}",
            "O comando trocou a revisão isolada. A prova foi invalidada; não retome usando este resultado.",
        )
    arvore = _hash_git(rodar(["git", "rev-parse", "HEAD^{tree}"], raiz))
    if arvore_esperada is None:
        arvore_esperada = arvore
    if arvore != arvore_esperada:
        raise ParouPorSeguranca(
            f"a validação trocou a árvore: está em {arvore}, mas a prova exige {arvore_esperada}",
            "O comando trocou a árvore da revisão isolada. A prova foi invalidada; não retome usando este resultado.",
        )
    alterados = rodar(["git", "diff", "HEAD", "--name-only"], raiz).strip()
    nao_rastreados = []
    status = rodar([
        "git", "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching"
    ], raiz)
    for linha in status.splitlines():
        if len(linha) < 4 or linha[:2] not in ("??", "!!"):
            continue
        caminho = Path(linha[3:]).name.casefold()
        if caminho in ARQUIVOS_DE_CONFIGURACAO_DE_TESTE or Path(caminho).suffix in EXTENSOES_DE_FONTE:
            nao_rastreados.append(linha[3:])
    if alterados:
        raise ParouPorSeguranca(
            "a validação alterou fontes rastreadas na revisão isolada",
            "Confira os logs privados e valide novamente a revisão sem modificar fontes durante a prova.",
        )
    if nao_rastreados:
        raise ParouPorSeguranca(
            "a validação criou fontes não rastreadas na revisão isolada",
            "Remova a fonte temporária ou coloque scripts de apoio fora do checkout; a prova foi invalidada.",
        )
    return arvore_esperada


def _validar(raiz, commit, rodar, comandos, dizer, prazo_segundos=PRAZO_VALIDACAO_PADRAO, arvore_esperada=None):
    for comando in comandos:
        for argumento in comando[1:]:
            valor = argumento.split("=", 1)[1] if argumento.startswith("-") and "=" in argumento else argumento
            caminho = Path(valor)
            if caminho.is_absolute() or ".." in caminho.parts:
                raise ParouPorSeguranca("validação aponta para fora da revisão isolada", "Use caminhos relativos à revisão nos argumentos. Caminho absoluto é permitido somente para o interpretador ou executável.")
    privado = telemetria.dir_git_comum(raiz)
    if privado is None:
        raise ErroDeInstrumentacao("não achei a pasta privada das provas", "Confira a bancada antes de validar.")
    logs = privado / telemetria.PASTA / "validacoes-pr" / commit / uuid.uuid4().hex
    logs.mkdir(parents=True)
    provas = []
    with tempfile.TemporaryDirectory(prefix="validacao-pr-") as temporario:
        isolada = Path(temporario).resolve() / "arvore"
        rodar(["git", "worktree", "add", "--detach", str(isolada), commit], raiz)
        try:
            arvore_esperada = _conferir_revisao_validada(isolada, commit, rodar, arvore_esperada)
            for indice, comando in enumerate(comandos, 1):
                log = logs / f"{indice}.log"
                _conferir_revisao_validada(isolada, commit, rodar, arvore_esperada)
                try:
                    saida = rodar(comando, isolada, log=log, prazo_segundos=prazo_segundos)
                except (PrazoDeValidacaoExcedido, ValidacaoReprovada):
                    _conferir_revisao_validada(isolada, commit, rodar, arvore_esperada)
                    raise
                except ErroDeInstrumentacao as erro:
                    _conferir_revisao_validada(isolada, commit, rodar, arvore_esperada)
                    raise ErroDeInstrumentacao(
                        f"validação {indice} não aprovada",
                        f"O comando falhou ou não pôde executar. Leia o log privado {log} e retome; nenhum resultado foi aprovado.",
                    ) from erro
                _conferir_revisao_validada(isolada, commit, rodar, arvore_esperada)
                provas.append(hashlib.sha256(saida.encode("utf-8")).hexdigest())
                dizer(f"PASS validação {indice}: exit 0; log privado {log}")
        finally:
            # O caminho nasce neste processo dentro do diretório temporário.
            # Só esta árvore descartável pode ser removida, inclusive na falha.
            if not isolada.is_relative_to(Path(temporario).resolve()):
                raise ErroDeInstrumentacao("limpeza fora da pasta temporária recusada", "Confira a bancada de validação.")
            rodar(["git", "worktree", "remove", "--force", str(isolada)], raiz)
    return provas


def _submeter_fila(raiz, correr, tarefa, ramo, url, revisao, arvore):
    if tarefa is None:
        return []
    from fila import carregar_tarefas, carregar_eventos
    erros = []
    tarefas = carregar_tarefas(raiz, erros)
    eventos = carregar_eventos(raiz, tarefas, erros)
    if erros or tarefa not in tarefas:
        raise ParouPorSeguranca("tarefa ausente ou fila inválida", "Rode python ci/fila.py validar e confira a tarefa antes de retomar.")
    finais = [e for e in eventos if e["tarefa"] == tarefa and e["evento"] in ("concluida", "cancelada")]
    if finais and not any(e.get("evidencia") == url and e["evento"] == "concluida" for e in finais):
        raise ParouPorSeguranca("tarefa já encerrada por outro fato", "Confira a cadeia da fila; não sobrescreva o encerramento.")
    if not finais:
        anterior = next((e for e in reversed(eventos) if e["tarefa"] == tarefa and e["evento"] == "submetida"), None)
        if anterior and anterior.get("pr") == url:
            diferenca = correr(["git", "diff", "--name-only", anterior["revisao"], revisao]).splitlines()
            if all(c.startswith(("painel/registros/", "fila/eventos/")) for c in diferenca):
                revisao, arvore = anterior["revisao"], anterior["arvore"]
        correr([sys.executable, "ci/fila.py", "submeter", tarefa, "--quem", ramo,
                "--pr", url, "--revisao", revisao, "--arvore", arvore])
    arquivos = []
    for caminho in (raiz / "fila/eventos").glob("*.json"):
        if json.loads(caminho.read_text(encoding="utf-8")).get("tarefa") == tarefa:
            arquivos.append(caminho.relative_to(raiz).as_posix())
    return arquivos


def _fechar_medicao_fase4(raiz: Path, tarefa: str | None, tentativa: str,
                          ramo: str, commit: str, pr: int) -> bool:
    if tarefa is None:
        return True
    import registrar_tarefa_fase4

    if registrar_tarefa_fase4.classificacao_da_tarefa(raiz, tarefa) is None:
        return True
    git = telemetria.dir_git_comum(raiz)
    eventos = telemetria.ler_tudo(git) if git else []
    relacionados = [evento for evento in eventos
                    if evento.get("evento") == "tarefa_medida"
                    and evento.get("tarefa") == tarefa
                    and evento.get("tentativa") == tentativa
                    and evento.get("branch") == ramo]
    inicios = [evento.get("inicio") for evento in relacionados if evento.get("inicio")]
    if not inicios:
        return False
    inicio = min(inicios)
    contexto = [evento.get("contexto_bytes") for evento in eventos
                if evento.get("evento") == "fase_operacional"
                and evento.get("tarefa") == tarefa
                and evento.get("tentativa") == tentativa
                and evento.get("branch") == ramo
                and evento.get("fase") == "contexto"
                and evento.get("resultado") == "concluido"
                and isinstance(evento.get("contexto_bytes"), int)]
    contexto_bytes = sum(contexto) if contexto else None
    fim = datetime.now(timezone.utc).isoformat()
    registrou = registrar_tarefa_fase4.registrar_execucao_fase4(
        raiz, tarefa=tarefa, tentativa=tentativa, branch=ramo,
        commit=commit, estado="concluida", inicio=inicio, fim=fim,
        pr=pr, contexto_bytes=contexto_bytes,
    )
    return registrou


def _tentativa_da_abertura(raiz, ramo):
    try:
        pasta = telemetria.dir_git_comum(raiz)
        eventos = telemetria.ler_tudo(pasta) if pasta else []
        candidatos = []
        for evento in eventos:
            identidade = telemetria.identidade_fase(evento)
            if (not identidade or evento.get("id") != identidade or evento.get("branch") != ramo
                    or evento.get("fase") not in ("abertura", "fechamento")):
                continue
            try:
                quando = datetime.fromisoformat(evento["quando"])
                if quando.tzinfo is None:
                    continue
            except (ValueError, TypeError, KeyError):
                continue
            candidatos.append((quando, evento))
        if candidatos:
            evento = max(candidatos, key=lambda item: item[0])[1]
            return evento["tentativa"], evento["tarefa"]
    except Exception:
        pass  # Métrica ausente ou inválida não substitui as provas obrigatórias.
    return uuid.uuid4().hex, ramo.split('/')[-1]


def _identificar_tarefa(raiz, pedido, ramo, tarefa_da_abertura):
    from fila import carregar_tarefas, carregar_eventos, tarefas_citadas
    candidatos = set()
    if pedido.tarefa:
        if not re.fullmatch(r"TAR-\d{3,}", pedido.tarefa):
            raise ParouPorSeguranca("tarefa inválida", "Informe --tarefa TAR-NNN da fila existente.")
        candidatos.add(pedido.tarefa)
    if re.fullmatch(r"TAR-\d{3,}", tarefa_da_abertura):
        candidatos.add(tarefa_da_abertura)
    erros = []
    tarefas = carregar_tarefas(raiz, erros)
    eventos = carregar_eventos(raiz, tarefas, erros)
    candidatos.update(e["tarefa"] for e in eventos
                      if e.get("quem") == ramo and e.get("evento") in ("reivindicada", "submetida"))
    if not candidatos:
        candidatos.update(tarefas_citadas(ramo + " " + pedido.titulo))
    if not candidatos:
        candidatos.update(tarefas_citadas(pedido.corpo_arquivo.read_text(encoding="utf-8")))
    if not candidatos:
        return None  # Sessões legadas sem acompanhamento continuam válidas.
    if erros or len(candidatos) != 1 or not candidatos <= tarefas.keys():
        raise ParouPorSeguranca(
            "tarefa ausente, ambígua ou fila inválida",
            "Rode python ci/fila.py listar e validar; reutilize a TAR existente com --tarefa antes de publicar.",
        )
    return candidatos.pop()


def abrir(raiz: Path, pedido: Pedido, *, rodar=rodar, hoje: date | None = None, dizer=print) -> str:
    raiz = Path(raiz)
    hoje = hoje or datetime.now(timezone.utc).date()
    correr = lambda comando: rodar(comando, raiz)
    _conferir_o_pedido(raiz, pedido)
    comandos, prazo_segundos = _configuracao_de_validacao(pedido)
    ramo = correr(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if not ramo.startswith("agent/"):
        raise ParouPorSeguranca("ramo incompatível", "Use agent/<área>/<tarefa> na sua bancada.")
    sujo = correr(["git", "status", "--porcelain"]).strip()
    if not sujo and not pedido.continuar:
        raise ParouPorSeguranca("árvore sem mudanças", "Use --continuar para validar os commits existentes.")
    tentativa, tarefa_da_abertura = _tentativa_da_abertura(raiz, ramo)
    pedido.tarefa = _identificar_tarefa(raiz, pedido, ramo, tarefa_da_abertura)
    correlacao = dict(tarefa=pedido.tarefa or tarefa_da_abertura, tentativa=tentativa,
                     branch=ramo, cwd=str(raiz))
    inicial = _hash_git(correr(["git", "rev-parse", "HEAD"]))
    telemetria.registrar_fase("fechamento", "iniciado", commit=inicial, **correlacao)
    dizer(f"PASS preparação concluída: {ramo}")
    preparados = correr(["git", "diff", "--cached", "--name-only"]).splitlines()
    if set(preparados) - set(pedido.arquivos):
        raise ParouPorSeguranca("índice contém arquivos não declarados", "Confira git diff --cached; declare cada arquivo que pretende entregar.")
    correr(["git", "add", "--", *pedido.arquivos])
    if correr(["git", "diff", "--name-only"]).strip():
        raise ParouPorSeguranca("mudanças fora do índice", "Inclua os arquivos da entrega ou preserve o trabalho em outra bancada antes de validar.")
    arvore = _hash_git(correr(["git", "write-tree"]))
    if correr(["git", "diff", "--cached", "--name-only"]).strip():
        correr(["git", "commit", "-F", str(pedido.mensagem_arquivo)])
    commit = _hash_git(correr(["git", "rev-parse", "HEAD"]))
    if _hash_git(correr(["git", "rev-parse", "HEAD^{tree}"])) != arvore:
        raise ParouPorSeguranca("commit diverge da árvore validada", "Confira os hooks e valide novamente o commit efetivamente entregue.")
    try:
        provas = _validar(raiz, commit, rodar, comandos, dizer, prazo_segundos, arvore)
    except ErroDeInstrumentacao:
        telemetria.registrar_fase("validacao", "falhou", commit=commit, **correlacao)
        raise
    if correr(["git", "diff", "--name-only"]).strip() or _hash_git(correr(["git", "write-tree"])) != arvore:
        raise ParouPorSeguranca("a validação alterou a árvore", "Confira o diff e execute novamente a validação do conteúdo final.")
    telemetria.registrar("validacao_pr", {
        "arvore": arvore, "commit": commit, "branch": ramo,
        "tentativa": tentativa, "saidas_sha256": provas,
        "comandos_sha256": [hashlib.sha256(json.dumps(c).encode()).hexdigest() for c in comandos],
        "resultado": "concluido",
    }, cwd=str(raiz), sessao=tentativa)
    telemetria.registrar_fase("validacao", "concluido", commit=commit, **correlacao)
    correr(["git", "push", "-u", "origin", ramo])
    numero, url = _achar_ou_abrir_o_pr(correr, pedido, ramo)
    dizer(f"PASS PR aberto: #{numero} {url}")
    # A identidade é do fato (ramo, PR e árvore), nunca de uma tentativa.
    destino = _registro_que_cita(raiz, numero, arvore)
    if destino is None:
        anterior = _registro_que_cita(raiz, numero)
        if anterior:
            evidencia = campos_lidos(anterior.read_text(encoding="utf-8"))["evidencia"]
            origem = re.search(r"commit ([0-9a-f]{40,64})", evidencia)
            if origem:
                diferenca = set(correr(["git", "diff", "--name-only", origem[1], "HEAD"]).splitlines())
                permitidos = {anterior.relative_to(raiz).as_posix()}
                if pedido.tarefa:
                    permitidos.update(p.relative_to(raiz).as_posix() for p in (raiz / "fila/eventos").glob("*.json") if json.loads(p.read_text(encoding="utf-8")).get("tarefa") == pedido.tarefa)
                if not diferenca - permitidos:
                    destino = anterior
    chave = hashlib.sha256(f"{ramo}:{numero}:{arvore}".encode()).hexdigest()
    if destino is None:
        sequencia = correr([sys.executable, "ci/reservar.py", "numero", "registro", "--chave", chave, "--com-dia"]).strip()
        if not re.fullmatch(r"\d{8}-\d{3}", sequencia):
            raise ErroDeInstrumentacao("reserva não devolveu número válido", "Confira python ci/reservar.py listar; retome com a mesma revisão.")
        nome = f"{sequencia}-{slug_do_titulo(pedido.titulo)}"
        destino = raiz / "painel/registros" / f"{nome}.js"
        campos = montar_campos(
            arquivo=nome, titulo=pedido.titulo, detalhe=pedido.detalhe,
            url_do_pr=url, dia=hoje, tipo=pedido.tipo, gravidade=pedido.gravidade,
            frente=pedido.frente or derivar_frente(pedido.arquivos), area=ramo.split('/')[1], tarefa=pedido.tarefa,
            evidencia_extra=f"Validação local: árvore {arvore}; commit {commit}; {len(provas)} comando(s), exit 0. Revisão, integração e publicação não verificadas.",
        )
        texto = renderizar(campos)
        if len(texto.encode("utf-8")) >= 1024:
            raise ParouPorSeguranca("recibo excede 1 KB", "Encurte título e detalhe; preserve a evidência determinística.")
        if destino.exists():
            raise ParouPorSeguranca("destino do recibo já existe", "Confira o registro existente; nunca sobrescreva um fato anterior.")
        destino.write_text(texto, encoding="utf-8")
    eventos = _submeter_fila(raiz, correr, pedido.tarefa, ramo, url, commit, arvore)
    correr(["node", "painel/gerar_manifesto.js"])
    relativo = destino.relative_to(raiz).as_posix()
    correr(["git", "add", "--", relativo, *eventos])
    preparados = correr(["git", "diff", "--cached", "--name-only"]).splitlines()
    if set(preparados) - {relativo, *eventos}:
        raise ParouPorSeguranca("embarque contém mudança alheia ao recibo", "Confira git diff --cached e retome sem incluir código não validado.")
    if preparados:
        correr(["git", "commit", "-m", f"painel: {_encurtar(pedido.titulo, 60)} (PR #{numero})", "-m", "Co-Authored-By: Codex <noreply@openai.com>"])
    # O recibo não muda o código provado. Toda outra alteração exige nova validação.
    alterados = set(correr(["git", "diff", "--name-only", commit, "HEAD"]).splitlines())
    if alterados - {relativo, *eventos} or correr(["git", "diff", "HEAD", "--name-only"]).strip():
        raise ParouPorSeguranca("revisão entregue difere da validada", "Confira o diff e execute novamente o fechamento.")
    entregue = _hash_git(correr(["git", "rev-parse", "HEAD"]))
    try:
        provas_finais = _validar(raiz, entregue, rodar, comandos, dizer, prazo_segundos,
                                 _hash_git(correr(["git", "rev-parse", "HEAD^{tree}"])))
    except ErroDeInstrumentacao:
        telemetria.registrar_fase("validacao", "falhou", commit=entregue, pr=numero, **correlacao)
        raise
    if (_hash_git(correr(["git", "rev-parse", "HEAD"])) != entregue
            or correr(["git", "diff", "HEAD", "--name-only"]).strip()):
        raise ParouPorSeguranca("revisão mudou durante a prova final", "Confira o diff e valide novamente antes de publicar.")
    telemetria.registrar("validacao_pr", {
        "commit": entregue, "branch": ramo, "tentativa": tentativa,
        "saidas_sha256": provas_finais, "resultado": "concluido", "pr": numero,
        "comandos_sha256": [hashlib.sha256(json.dumps(c).encode()).hexdigest() for c in comandos],
    }, cwd=str(raiz), sessao=tentativa)
    telemetria.registrar_fase("validacao", "concluido", commit=entregue, pr=numero, **correlacao)
    correr(["git", "push", "origin", ramo])
    remoto = json.loads(correr(["gh", "pr", "view", str(numero), "--json", "headRefOid,state,isDraft"]))
    if remoto.get("headRefOid") != entregue or remoto.get("state") != "OPEN":
        raise ParouPorSeguranca("PR remoto não confirma a revisão entregue", "Confira gh pr view e retome; nenhum sucesso remoto foi declarado.")
    if remoto.get("isDraft") is True:
        correr(["gh", "pr", "ready", str(numero)])
        remoto = json.loads(correr(["gh", "pr", "view", str(numero), "--json", "headRefOid,state,isDraft"]))
    if remoto.get("headRefOid") != entregue or remoto.get("state") != "OPEN" or remoto.get("isDraft") is True:
        raise ParouPorSeguranca("PR remoto continua em rascunho", "Confira gh pr view e torne o PR pronto antes de pedir pouso.")
    if not _fechar_medicao_fase4(raiz, pedido.tarefa, tentativa, ramo, entregue, numero):
        dizer("Medição Fase 4 indisponível; os resultados operacionais continuam separados.")
    telemetria.registrar_fase("fechamento", "concluido", commit=entregue, pr=numero, **correlacao)
    dizer("PASS validação local concluída; recibo embarcado e revisão remota conferida")
    dizer("Revisão: não verificada. Integração: não verificada. Publicação: não verificada.")
    final = f"PR {numero} aberto com recibo: {url}; devolva à maestro para revisão e espera."
    dizer(final)
    return final


def _achar_ou_abrir_o_pr(correr, pedido: Pedido, ramo: str) -> tuple[int, str]:
    bruto = correr(["gh", "pr", "list", "--head", ramo, "--state", "all", "--json", "number,url,state"]).strip()
    try:
        encontrados = json.loads(bruto)
    except (TypeError, ValueError) as erro:
        raise ErroDeInstrumentacao("consulta de PR inválida", "Confira o acesso GitHub e retome antes de criar outro PR.") from erro
    if not isinstance(encontrados, list) or len(encontrados) > 1:
        raise ParouPorSeguranca("PR do ramo é ambíguo", "Confira gh pr list --head antes de retomar.")
    if encontrados:
        existente = encontrados[0]
        if existente.get("state", "OPEN") != "OPEN":
            raise ParouPorSeguranca("PR do ramo já foi encerrado", "Use uma nova bancada para um novo trabalho.")
        correr(["gh", "pr", "edit", str(existente["number"]), "--title", pedido.titulo, "--body-file", str(pedido.corpo_arquivo)])
        return int(existente["number"]), existente["url"]
    saida = correr([
        "gh", "pr", "create",
        "--base", "main",
        "--title", pedido.titulo,
        "--body-file", str(pedido.corpo_arquivo),
    ])
    achado = re.search(r"https://\S*?/pull/(\d+)", saida)
    if not achado:
        raise ErroDeInstrumentacao(
            "o `gh pr create` não devolveu a URL de um PR",
            f"saída:\n{saida.strip() or '(vazia)'}\n\n"
            "Sem o número não há como citar o PR na evidência do registro, e sem\n"
            "isso o portão de pouso cobra dívida do livro (`armadilhas/185`).",
        )
    return int(achado.group(1)), achado.group(0)


def _registro_que_cita(raiz: Path, numero: int, arvore: str | None = None) -> Path | None:
    """O recibo deste PR já está na pasta? (é o que torna `--continuar` seguro)"""
    pasta = raiz / "painel" / "registros"
    if not pasta.is_dir():
        return None
    for arquivo in sorted(pasta.glob("*.js"), reverse=True):
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        try:
            campos = campos_lidos(texto)
        except (ValueError, KeyError):
            continue
        evidencia = campos.get("evidencia") or ""
        if re.search(rf"/pull/{numero}(?![0-9])", evidencia) and (arvore is None or f"árvore {arvore}" in evidencia):
            return arquivo
    return None


# ------------------------------------------------------------------- a CLI --


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ci/pr.py",
        description="Do commit ao PR aberto com o recibo a bordo, num comando só.",
    )
    p.add_argument("--titulo", required=True, help="o título do PR (vira o do registro)")
    p.add_argument("--mensagem-arquivo", required=True, type=Path)
    p.add_argument("--corpo-arquivo", required=True, type=Path)
    p.add_argument("--arquivos", required=True, nargs="+")
    p.add_argument("--detalhe", default="", help="o julgamento, mínimo 80 caracteres")
    p.add_argument("--detalhe-arquivo", type=Path, default=None)
    p.add_argument("--tipo", default="entrega", help=f"um de: {', '.join(TIPOS)}")
    p.add_argument("--gravidade", default="info", help=f"um de: {', '.join(GRAVIDADES)}")
    p.add_argument("--frente", default=None, help=f"um de: {', '.join(FRENTES)}")
    p.add_argument("--validacao-arquivo", type=Path, required=True)
    p.add_argument("--tarefa", help="TAR-NNN da fila; submete a entrega e embarca seus eventos")
    p.add_argument("--evidencia", default="", help="a prova que soma à URL do PR")
    p.add_argument("--continuar", action="store_true", help="relê o estado e pula o feito")
    return p


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    args = construir_parser().parse_args(argv)
    detalhe = args.detalhe
    if args.detalhe_arquivo is not None:
        if not args.detalhe_arquivo.is_file():
            print("\nFAIL bancada")
            print(f"\nPAROU POR SEGURANÇA: --detalhe-arquivo não existe: "
                  f"{args.detalhe_arquivo}\n")
            return 1
        detalhe = args.detalhe_arquivo.read_text(encoding="utf-8")
    try:
        raiz = raiz_do_repo()
        pedido = Pedido(
            titulo=args.titulo,
            mensagem_arquivo=args.mensagem_arquivo,
            corpo_arquivo=args.corpo_arquivo,
            arquivos=list(args.arquivos),
            detalhe=detalhe,
            tipo=args.tipo,
            gravidade=args.gravidade,
            frente=args.frente,
            evidencia=args.evidencia,
            continuar=args.continuar,
            validacao_arquivo=args.validacao_arquivo,
            tarefa=args.tarefa,
        )
        abrir(raiz, pedido)
        return 0
    except ParouPorSeguranca as recusa:
        print("\nFAIL o rito não seguiu")
        print(f"\nPAROU POR SEGURANÇA: {recusa.resumo}\n")
        print(telemetria.redigir(recusa.o_que_fazer))
        return 1
    except ValidacaoReprovada as erro:
        print(f"\nFAIL {erro.resumo}\n{erro.detalhe}")
        return 1
    except ErroDeInstrumentacao as erro:
        print("\nFAIL o rito parou no meio")
        print(f"\nPAROU POR SEGURANÇA: {telemetria.redigir(erro.resumo)}\n")
        if erro.detalhe:
            print(telemetria.redigir(erro.detalhe))
        print(
            "\nO que já foi feito continua feito. Conserte a causa e rode de novo com\n"
            "`--continuar`: ele relê o estado (commit? PR? registro?) e pula o pronto."
        )
        return 2
    except (OSError, ValueError, TypeError, KeyError) as erro:
        print(f"ERROR fechamento: resposta ou arquivo inválido ({type(erro).__name__}).")
        print("Confira os arquivos de entrada e o acesso remoto; retome com --continuar. Nenhuma aprovação foi declarada.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
