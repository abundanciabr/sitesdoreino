"""ROLLBACK PELO PIPELINE — a válvula de emergência do RITOS §4, mecanizada.

O rito diz que a resposta canônica a QUALQUER emergência é rollback, em
segundos: `CHECKOUT_TAG=<sha-anterior> docker compose up -d checkout`. Só que
esse comando só existia para quem tem chave SSH — e agente não tem (Lei 5,
inexistência, não proibição). Na prática o caminho mais rápido dependia de
acordar o mantenedor e fazê-lo colar comando em terminal, que é exatamente o
que a Lei das 2h da Manhã existe para evitar.

Este portão é a validação que roda ANTES de qualquer SSH. Ele não decide
mergear nem deployar código novo: decide se é seguro **voltar** a uma imagem
que a produção JÁ rodou.

Por que este é o único caminho para a VPS com `workflow_dispatch` (os dois
workflows de deploy o recusam de propósito): eles ENTREGAM código; este só
ANDA PARA TRÁS, dentro do conjunto de commits que já passaram pelo portão de
deploy. É o que as três checagens abaixo provam, e é por isso que elas são
fail-closed:

    celula      nome declarado no manifesto — nunca texto livre indo para o SSH
    alvo        `main` ou um sha de 40 hex QUE É ANCESTRAL da main (um commit
                que realmente viveu na linha principal; branch de rascunho,
                commit de PR não mergeado e sha inventado reprovam aqui)
    imagem      a tag existe no registry — ou seja, aquele commit chegou a ser
                construído e publicado por um deploy de verdade

Sem as três, `workflow_dispatch` seria um caminho para rodar QUALQUER imagem
em produção sem revisão — o buraco que o portão de deploy fechou.

Exit codes (mesmo contrato dos outros portões, _nucleo.Estado):

    PASS  (0) medi e o alvo é seguro      -> o job de aplicar roda
    FAIL  (1) medi e o alvo reprovou      -> o job de aplicar é pulado
    ERROR (2) não consegui medir          -> o job de aplicar é pulado

Ambiente esperado (fiação em .github/workflows/rollback.yml):

    ROLLBACK_CELULA   célula a voltar (uma das 8 do manifesto)
    ROLLBACK_ALVO     `main` ou sha de 40 hex
    ROLLBACK_MOTIVO   texto livre, obrigatório — é a trilha de auditoria
    ROLLBACK_BASE     ref contra a qual a ancestralidade é medida (padrão HEAD)
    ROLLBACK_IMAGEM_PREFIXO  padrão ghcr.io/abundanciabr/plataforma-
    ROLLBACK_DOCKER / ROLLBACK_GIT / ROLLBACK_RAIZ  costuras de teste; o teste
        de forma afirma que o workflow real NÃO as define. As duas primeiras
        são a lista json do comando; a terceira é a raiz a medir, e ela passa
        por `raiz_declarada` — diretório sem as marcas do repositório é ERROR,
        nunca uma subida silenciosa até o repositório de verdade.

Saídas em GITHUB_OUTPUT, consumidas pelo job de aplicar:

    celula · tag · var_tag (ex.: CHECKOUT_TAG)

===========================================================================
O CONGELAMENTO DA CÉLULA — o outro lado do RITOS §4, mecanizado

    python ci/rollback.py congelar <celula> --motivo "..."
    python ci/rollback.py congelados
    python ci/rollback.py descongelar <celula>

Voltar a imagem é metade do trabalho. A outra metade é o rollback CONTINUAR
de pé, e até 18/09/2026 ela não existia em lugar nenhum: o RITOS §4 pedia
"enquanto o rollback estiver ATIVO, não mergeie nada que toque `infra/`" numa
época em que mergear era gesto humano. Desde 13/09/2026 quem integra é
`ci/mergear.py --automatico`, acordado por cron de 15 em 15 minutos, sem
etiqueta, sem revisor e sem ninguém no circuito. Medido antes desta mudança,
`git grep -ic "rollback\\|revers" -- ci/mergear.py ci/portao_de_deploy.py`
devolvia ZERO nos dois: nada no caminho de integração sabia que existia um
rollback ativo, e um rollback das 2h da manhã podia ser desfeito em silêncio,
com o run verde, antes de o mantenedor acordar.

O estado mora numa REFERÊNCIA no servidor do GitHub (`refs/congelamentos/
<celula>`), no mesmo molde do `ci/reservar.py`, e não num arquivo versionado.
Arquivo versionado exigiria um PR para ligar, e PR leva minutos que a
emergência não tem; a referência é uma escrita atômica, some do clone de
ninguém e é lida pelo pouso direto do servidor.

O PRAZO mora dentro do congelamento de propósito. Congelamento sem prazo é
uma casa parada para sempre no dia em que alguém esquecer de descongelar, e
esta casa não tem vigia para cobrar. Seis horas atravessam o resto de uma
madrugada; incidente mais longo se renova com o mesmo comando.

O QUE O CONGELAMENTO FECHA: os PRs que tocam a célula congelada (mergear a
célula dispara o `deploy-celula` dela, que republica `:main` por cima da
imagem para a qual ela voltou) e os PRs que tocam `infra/`, para qualquer
célula congelada, porque o `deploy-infra` termina com `docker compose up -d`
sem argumento e devolve TODAS as células ao `:main` de uma vez.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    executar,
    raiz_declarada,
    raiz_do_repo,
)
from reservar import criar_ref_atomica  # noqa: E402

SHA_COMPLETO = re.compile(r"^[0-9a-f]{40}$")
ALVO_LINHA_PRINCIPAL = "main"
PREFIXO_PADRAO = "ghcr.io/abundanciabr/plataforma-"
MOTIVO_MINIMO = 10

# Onde o congelamento mora no servidor, e por quanto tempo vale sem renovação.
NS_CONGELAMENTO = "refs/congelamentos"
HORAS_DE_CONGELAMENTO = 6

# Trechos que o registry usa para dizer "essa tag não existe". Distinguem um
# alvo errado (FAIL — quem disparou digitou um sha que nunca virou imagem) de
# um registry fora do ar ou sem login (ERROR — não medimos nada). Tratar os
# dois como a mesma coisa devolveria "reprovado" para uma falha nossa, e
# mandaria quem lê investigar o lugar errado.
MANIFESTO_AUSENTE = (
    "manifest unknown",
    "manifest_unknown",
    "no such manifest",
)


@dataclass
class Contexto:
    raiz: Path
    celula: str
    alvo: str
    motivo: str
    base: str
    prefixo: str
    docker: list[str]
    git: list[str]

    @property
    def tag(self) -> str:
        return self.alvo

    @property
    def imagem(self) -> str:
        return f"{self.prefixo}{self.celula}:{self.tag}"

    @property
    def var_tag(self) -> str:
        return f"{self.celula.upper()}_TAG"


def _comando(env: str, padrao: list[str]) -> list[str]:
    """Lê uma costura de teste do ambiente, ou devolve o comando real."""
    bruto = os.environ.get(env, "").strip()
    if not bruto:
        return list(padrao)
    try:
        valor = json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(
            f"{env} não é json válido",
            f"Valor recebido:\n  {bruto}\n\n{exc}",
        ) from exc
    if not isinstance(valor, list) or not all(isinstance(p, str) for p in valor):
        raise ErroDeInstrumentacao(
            f"{env} precisa ser uma lista json de strings",
            f"Valor recebido:\n  {bruto}",
        )
    return valor


def _raiz() -> Path:
    declarada = os.environ.get("ROLLBACK_RAIZ", "").strip()
    return raiz_declarada(Path(declarada)) if declarada else raiz_do_repo()


def contexto_do_ambiente() -> Contexto:
    return Contexto(
        raiz=_raiz(),
        celula=os.environ.get("ROLLBACK_CELULA", "").strip(),
        alvo=os.environ.get("ROLLBACK_ALVO", "").strip(),
        motivo=os.environ.get("ROLLBACK_MOTIVO", "").strip(),
        base=os.environ.get("ROLLBACK_BASE", "").strip() or "HEAD",
        prefixo=os.environ.get("ROLLBACK_IMAGEM_PREFIXO", "").strip() or PREFIXO_PADRAO,
        docker=_comando("ROLLBACK_DOCKER", ["docker"]),
        git=_comando("ROLLBACK_GIT", ["git"]),
    )


def celulas_declaradas(raiz: Path) -> list[str]:
    """A lista autoritativa de células é o manifesto, não o disco.

    Ler `services/*` daria o mesmo resultado hoje e um resultado diferente no
    dia em que alguém criar um diretório lá sem declarar a célula — e o nome
    lido aqui viaja para dentro de um comando na VPS.
    """
    caminho = raiz / "ci" / "manifesto-de-contratos.json"
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErroDeInstrumentacao(
            "manifesto de contratos ilegível",
            f"Caminho:\n  {caminho}\n\n{exc}\n\n"
            "Sem a lista de células não há como validar o nome recebido.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(
            "manifesto de contratos não é json válido",
            f"Caminho:\n  {caminho}\n\n{exc}",
        ) from exc
    celulas = dados.get("celulas")
    if not isinstance(celulas, dict) or not celulas:
        raise ErroDeInstrumentacao(
            "manifesto de contratos sem a chave 'celulas'",
            f"Caminho:\n  {caminho}\n\nLista vazia NÃO é 'qualquer nome serve'.",
        )
    return sorted(celulas)


def checar_celula(ctx: Contexto) -> Resultado:
    declaradas = celulas_declaradas(ctx.raiz)
    if not ctx.celula:
        return Resultado(
            "celula",
            Estado.FAIL,
            "nenhuma célula informada",
            "ROLLBACK_CELULA veio vazio. Escolha uma: " + ", ".join(declaradas),
        )
    if ctx.celula not in declaradas:
        return Resultado(
            "celula",
            Estado.FAIL,
            f"'{ctx.celula}' não é célula declarada",
            "Declaradas em ci/manifesto-de-contratos.json:\n"
            + "\n".join(f"  - {c}" for c in declaradas)
            + "\n\nO nome recebido entraria num comando na VPS; texto livre "
            "não passa daqui.",
        )
    return Resultado("celula", Estado.PASS, f"'{ctx.celula}' está no manifesto")


def checar_motivo(ctx: Contexto) -> Resultado:
    """O motivo é a trilha de auditoria — sem ele o run vira 'alguém mexeu'.

    Rollback é a ÚNICA porta manual para a produção; o post-mortem do RITOS §4
    depende de saber por que ela foi aberta, e depender da memória de quem
    disparou às 2h da manhã é depender de nada.
    """
    if len(ctx.motivo) < MOTIVO_MINIMO:
        return Resultado(
            "motivo",
            Estado.FAIL,
            f"motivo com {len(ctx.motivo)} caractere(s) — mínimo {MOTIVO_MINIMO}",
            "Escreva o que está acontecendo (ex.: 'checkout devolvendo 500 "
            "desde o deploy das 14h' ou 'drill cronometrado da Fase D').",
        )
    return Resultado("motivo", Estado.PASS, ctx.motivo)


def checar_alvo(ctx: Contexto) -> Resultado:
    """`main` (voltar ao normal) ou um sha ANCESTRAL da linha principal.

    A ancestralidade é a checagem que impede `workflow_dispatch` de virar um
    caminho para rodar código não revisado em produção: um commit ancestral da
    main é, por construção, um commit que já passou pelo portão de deploy.
    """
    if ctx.alvo == ALVO_LINHA_PRINCIPAL:
        return Resultado(
            "alvo",
            Estado.PASS,
            "main — desfazer o pin e voltar à linha principal",
        )
    if not SHA_COMPLETO.match(ctx.alvo):
        return Resultado(
            "alvo",
            Estado.FAIL,
            f"'{ctx.alvo}' não é 'main' nem um sha de 40 hex",
            "Sha abreviado não serve: a tag publicada pelo deploy é o sha "
            "COMPLETO, e resolver a abreviação aqui seria adivinhar.",
        )

    tipo = executar(
        [*ctx.git, "cat-file", "-t", ctx.alvo],
        cwd=ctx.raiz,
        descricao=f"git cat-file do alvo {ctx.alvo}",
        exigir_stdout=True,
    ).stdout.strip()
    if tipo != "commit":
        return Resultado(
            "alvo",
            Estado.FAIL,
            f"'{ctx.alvo}' existe no repositório, mas é um {tipo}, não um commit",
        )

    base = executar(
        [*ctx.git, "rev-parse", ctx.base],
        cwd=ctx.raiz,
        descricao=f"git rev-parse da base {ctx.base}",
        exigir_stdout=True,
    ).stdout.strip()
    ancestral = executar(
        [*ctx.git, "merge-base", ctx.alvo, base],
        cwd=ctx.raiz,
        descricao=f"git merge-base entre {ctx.alvo} e {ctx.base}",
        exigir_stdout=True,
    ).stdout.strip()
    # merge-base(A, B) == A  <=>  A é ancestral de B. Escolhido no lugar de
    # `merge-base --is-ancestor` porque aquele responde por exit code, e exit
    # code 1 ali seria indistinguível de "o git falhou" dentro de `executar`.
    if ancestral != ctx.alvo:
        return Resultado(
            "alvo",
            Estado.FAIL,
            f"'{ctx.alvo}' NÃO é ancestral de {ctx.base}",
            f"merge-base devolveu {ancestral}.\n\n"
            "Rollback só anda para trás dentro da linha principal. Commit de "
            "branch não mergeada nunca passou pelo portão de deploy — rodá-lo "
            "em produção por aqui seria o buraco que o portão fechou.",
        )
    return Resultado(
        "alvo",
        Estado.PASS,
        f"{ctx.alvo[:12]} é ancestral de {ctx.base}",
    )


def checar_imagem(ctx: Contexto) -> Resultado:
    """A tag precisa existir no registry — commit ancestral não basta.

    Nem todo commit da main virou imagem: o deploy só constrói a célula tocada
    pelo push. Pedir um sha que nunca foi construído deixaria a VPS puxando uma
    tag inexistente e o serviço parado — o oposto de um rollback.
    """
    try:
        executar(
            [*ctx.docker, "manifest", "inspect", ctx.imagem],
            cwd=ctx.raiz,
            descricao=f"docker manifest inspect {ctx.imagem}",
            exigir_stdout=True,
            timeout=120,
        )
    except ErroDeInstrumentacao as erro:
        texto = f"{erro.resumo}\n{erro.detalhe}".lower()
        if any(marca in texto for marca in MANIFESTO_AUSENTE):
            return Resultado(
                "imagem",
                Estado.FAIL,
                f"{ctx.imagem} não existe no registry",
                "Esse commit nunca virou imagem desta célula — o deploy só "
                "constrói a célula tocada pelo push. Escolha um sha do "
                "histórico do workflow deploy-celula em que ESTA célula "
                "aparece.\n\n" + erro.detalhe,
            )
        raise
    return Resultado("imagem", Estado.PASS, ctx.imagem)


def publicar_saidas(ctx: Contexto) -> None:
    """Escreve o plano em GITHUB_OUTPUT — o job de aplicar não recalcula nada.

    Deixar o job de SSH remontar o nome da imagem a partir dos inputs crus
    reabriria, no YAML, a porta que este portão fecha no Python.
    """
    destino = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not destino:
        return
    # `imagem` NÃO entra: o job de aplicar usa var_tag+tag e deixa o compose
    # resolver o nome. Publicar um valor que ninguém lê é convite para alguém
    # começar a lê-lo amanhã por um caminho que este portão não cobre.
    linhas = {
        "celula": ctx.celula,
        "tag": ctx.tag,
        "var_tag": ctx.var_tag,
    }
    with open(destino, "a", encoding="utf-8") as saida:
        for chave, valor in linhas.items():
            saida.write(f"{chave}={valor}\n")


def agora_utc() -> datetime:
    """O relógio, num lugar só — é o que os guardas conseguem parar."""
    return datetime.now(timezone.utc)


def _decodificar(ref: str, mensagem: str) -> dict:
    """O corpo de um congelamento, conferido. Ilegível é ERROR, nunca ausência.

    Fail-closed na origem: "não consegui ler a referência" e "não há rollback
    ativo" levariam o pouso a decisões opostas, e confundir as duas é
    exatamente como o rollback seria desfeito em silêncio.
    """
    celula = ref.rsplit("/", 1)[-1]
    try:
        corpo = json.loads(mensagem)
        if corpo.get("tipo") != "congelamento" or corpo.get("celula") != celula:
            raise ValueError(f"o corpo não é o congelamento de '{celula}'")
        datetime.fromisoformat(corpo["expira_em"])
    except (json.JSONDecodeError, ValueError, TypeError, KeyError, AttributeError) as erro:
        raise ErroDeInstrumentacao(
            f"congelamento ilegível em {ref}",
            f"{erro}\n\nMensagem lida:\n  {mensagem.strip()[:400]}\n\n"
            "Isto NÃO é 'então não há rollback ativo'. Confira a referência no "
            "servidor antes de deixar qualquer coisa ser integrada.",
        ) from erro
    return corpo


def congelamentos_vivos(
    pares: list[tuple[str, str]], agora: datetime | None = None
) -> dict[str, dict]:
    """Quais células estão congeladas AGORA, a partir de (referência, mensagem).

    Puro de propósito: quem escreve o congelamento fala com o servidor por
    `git` (roda numa bancada com credencial); quem lê é o pouso, que fala por
    `gh` (o checkout dele não guarda credencial de git). O significado do
    congelamento não pode morar nos dois lugares, só o fio.
    """
    agora = agora or agora_utc()
    vivos: dict[str, dict] = {}
    for ref, mensagem in pares:
        corpo = _decodificar(ref, mensagem)
        if datetime.fromisoformat(corpo["expira_em"]) > agora:
            vivos[corpo["celula"]] = corpo
    return vivos


def _sha_da_ref(raiz: Path, ref: str) -> str:
    saida = executar(
        ["git", "ls-remote", "origin", ref],
        cwd=raiz,
        descricao=f"conferir {ref} no servidor",
    ).stdout.strip()
    return saida.split()[0] if saida else ""


def _mensagem_do_commit(raiz: Path, sha: str) -> str:
    executar(
        ["git", "fetch", "--no-tags", "origin", sha],
        cwd=raiz,
        descricao="baixar o comprovante do congelamento",
    )
    return executar(
        ["git", "show", "-s", "--format=%B", sha],
        cwd=raiz,
        descricao="ler o congelamento",
        exigir_stdout=True,
    ).stdout


def _sha_do_congelamento(raiz: Path, celula: str) -> str:
    """O sha do congelamento que já existe para esta célula, ou "".

    Só o sha, e de propósito: ele é o lease da renovação, e o corpo não decide
    nada aqui. Um congelamento ilegível não pode impedir alguém de congelar no
    meio de uma emergência; quem recusa integrar nesse caso é o pouso, que já
    trata ilegível como ERROR.
    """
    return _sha_da_ref(raiz, f"{NS_CONGELAMENTO}/{celula}")


def congelar(raiz: Path, celula: str, motivo: str) -> tuple[bool, str]:
    """Liga o congelamento da célula por `HORAS_DE_CONGELAMENTO`. (ganhou?, recado)

    Chamar de novo numa célula já congelada RENOVA o prazo, em uma operação só,
    com lease no sha observado. É o caminho de um incidente que passa das seis
    horas, e ele não pode ter um instante sequer em que a casa fica destravada.
    """
    declaradas = celulas_declaradas(raiz)
    if celula not in declaradas:
        raise ErroDeInstrumentacao(
            f"'{celula}' não é célula declarada",
            "Declaradas em ci/manifesto-de-contratos.json:\n"
            + "\n".join(f"  - {c}" for c in declaradas)
            + "\n\nCongelar um nome digitado errado congelaria o nada, em "
            "silêncio, justo quando o silêncio custa mais caro.",
        )
    if len(motivo) < MOTIVO_MINIMO:
        raise ErroDeInstrumentacao(
            f"motivo com {len(motivo)} caractere(s) — mínimo {MOTIVO_MINIMO}",
            "Quem vir a integração recusada daqui a três horas precisa ler o "
            "que está acontecendo, sem acordar ninguém para perguntar.",
        )

    existente = _sha_do_congelamento(raiz, celula)
    agora = agora_utc()
    expira = agora + timedelta(hours=HORAS_DE_CONGELAMENTO)
    ganhou = criar_ref_atomica(
        raiz,
        f"{NS_CONGELAMENTO}/{celula}",
        {
            "tipo": "congelamento",
            "celula": celula,
            "motivo": motivo,
            "criado_em": agora.isoformat(),
            "expira_em": expira.isoformat(),
        },
        lease=existente,
    )
    if not ganhou:
        return False, (
            f"NÃO congelei '{celula}': a referência mudou no servidor entre a "
            "leitura e a escrita. Rode o comando de novo e confira com "
            "`python ci/rollback.py congelados`."
        )
    verbo = "renovado" if existente else "ligado"
    return True, (
        f"Congelamento {verbo}: '{celula}' não é integrada até "
        f"{expira.isoformat()}.\n"
        "A correção viaja por PR e só entra depois de "
        f"`python ci/rollback.py descongelar {celula}`."
    )


def descongelar(raiz: Path, celula: str) -> None:
    """Desliga o congelamento. Falha do servidor é ERROR, nunca silêncio."""
    executar(
        ["git", "push", "origin", f":{NS_CONGELAMENTO}/{celula}"],
        cwd=raiz,
        descricao=f"soltar o congelamento de {celula}",
    )


def congelados(raiz: Path) -> dict[str, dict]:
    """O que está congelado agora, lido do servidor."""
    saida = executar(
        ["git", "ls-remote", "origin", f"{NS_CONGELAMENTO}/*"],
        cwd=raiz,
        descricao="listar os congelamentos",
    ).stdout
    pares = []
    for linha in saida.splitlines():
        if "\t" not in linha:
            continue
        sha, ref = linha.split("\t", 1)
        pares.append((ref.strip(), _mensagem_do_commit(raiz, sha.strip())))
    return congelamentos_vivos(pares)


def _comandar(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python ci/rollback.py",
        description="Congelar e descongelar a célula enquanto o rollback está ativo",
    )
    sub = parser.add_subparsers(dest="acao", required=True)
    p_congelar = sub.add_parser("congelar", help="recusa integrar esta célula")
    p_congelar.add_argument("celula")
    p_congelar.add_argument("--motivo", required=True)
    sub.add_parser("congelados", help="o que está congelado agora")
    sub.add_parser("descongelar", help="solta a célula").add_argument("celula")
    args = parser.parse_args(argv)

    try:
        raiz = raiz_do_repo()
        if args.acao == "congelar":
            ganhou, recado = congelar(raiz, args.celula, args.motivo)
            print(recado)
            return 0 if ganhou else 1
        if args.acao == "descongelar":
            descongelar(raiz, args.celula)
            print(
                f"'{args.celula}' descongelada: a integração automática volta a "
                "aceitar PRs dela."
            )
            return 0
        vivos = congelados(raiz)
        if not vivos:
            print("Nenhuma célula congelada.")
            return 0
        for celula, corpo in sorted(vivos.items()):
            print(f"{celula}  até {corpo['expira_em']}  {corpo.get('motivo', '')}")
        return 0
    except ErroDeInstrumentacao as erro:
        print(f"\nPAROU POR SEGURANÇA: {erro.resumo}\n")
        if erro.detalhe:
            print(erro.detalhe)
        return 2


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        return _comandar(argv)
    relatorio = Relatorio(titulo="ROLLBACK — validação do alvo (RITOS §4)")
    ctx: Contexto | None = None
    try:
        ctx = contexto_do_ambiente()
        print(f"Célula:  {ctx.celula or '(vazio)'}")
        print(f"Alvo:    {ctx.alvo or '(vazio)'}")
        print(f"Imagem:  {ctx.imagem}")
        print("")

        resultado_celula = relatorio.registrar(checar_celula(ctx))
        relatorio.registrar(checar_motivo(ctx))
        resultado_alvo = relatorio.registrar(checar_alvo(ctx))
        # A imagem só é consultada com célula e alvo já provados: montar o nome
        # a partir de um deles inválido perguntaria ao registry por uma coisa
        # que não existe, e a resposta "não existe" apontaria para o sintoma
        # errado.
        if resultado_celula.estado is Estado.PASS and resultado_alvo.estado is Estado.PASS:
            relatorio.registrar(checar_imagem(ctx))
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("rollback", erro))

    print(relatorio.render())
    if ctx is not None and relatorio.estado is Estado.PASS:
        publicar_saidas(ctx)
        print("")
        print(f"PLANO: {ctx.var_tag}={ctx.tag} docker compose up -d {ctx.celula}")
        if ctx.alvo != ALVO_LINHA_PRINCIPAL:
            # Voltar a imagem sem congelar deixa o rollback de pé por, no
            # máximo, os 15 minutos até o próximo cron do pouso.
            print("")
            print(
                "DEPOIS DE APLICAR, segure o rollback de pé:\n"
                f'  python ci/rollback.py congelar {ctx.celula} --motivo "{ctx.motivo}"'
            )
    return relatorio.exit_code


def _blindar(rotulo: str, funcao):
    """Exceção não prevista vira ERROR (2), nunca FAIL (1) — igual ci/ci.py."""

    def blindada(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except SystemExit:
            raise
        except BaseException:  # noqa: BLE001 - a fronteira do processo é aqui
            import traceback

            print("")
            print(f"ERROR {rotulo}: exceção não tratada dentro do próprio portão.")
            print(traceback.format_exc())
            print(
                "A validação NÃO foi concluída. Este resultado NÃO é um PASS "
                "nem um FAIL: nada foi provado sobre o alvo pedido."
            )
            return 2

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar("rollback", main)())
