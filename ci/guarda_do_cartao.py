"""GUARDA DO CARTÃO — as nove leis do cartão pela Appmax, medidas em disco.

    services/ contracts/ infra/  ──(leitura)──►  guarda_do_cartao  ──►  FAIL/ERROR
                                                        │
                                                 INV-CARD-A1..A9

POR QUE ELE NASCE ANTES DA INTEGRAÇÃO
-------------------------------------
`INVARIANTES.md` abre dizendo que invariante de dinheiro nasce ANTES da
primeira feature, com guarda no mesmo PR, porque a lei precisa existir antes da
primeira oportunidade de violá-la. Este portão é o guarda das nove leis do
cartão pela Appmax, escrito enquanto a integração ainda não existe.

Sete das nove leis medem a SUPERFÍCIE APPMAX: os arquivos que nomeiam a
Appmax. Hoje essa superfície é vazia e as sete passam sem ter o que reprovar.
Isso não é um portão desligado, é um portão à espera: o dia em que o primeiro
arquivo Appmax entrar no repositório, as nove regras já estão medindo. As
outras duas (A2 e A7) medem a árvore inteira desde já.

Um portão que só sabe passar é indistinguível de um portão desligado, então
cada regra tem, em `ci/tests/test_guarda_do_cartao.py`, uma árvore falsa que a
faz reprovar, e a linha que a decide é provada por
`python ci/provar_guardas.py ci/tests/test_guarda_do_cartao.py`: comentada, a
regra para de morder e o teste dela reprova.

FAIL vs ERROR (INV-CI01)
------------------------
FAIL (1) = medi e encontrei violação. ERROR (2) = não consegui medir: raiz não
resolvida, árvore obrigatória ausente, arquivo ilegível, zero arquivos lidos.
Não existe caminho "não consegui medir ⇒ PASS".
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from _nucleo import (
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    raiz_declarada,
    raiz_do_repo,
)

# As três árvores que a integração do cartão pode tocar. Ausência de qualquer
# uma é ERROR: medir duas de três e chamar de PASS é afirmar mais do que se viu.
ARVORES = ("services", "contracts", "infra")

SUFIXOS = frozenset(
    {
        ".py", ".js", ".mjs", ".ts", ".json", ".yml", ".yaml", ".sh",
        ".html", ".sql", ".toml", ".cfg", ".ini", ".txt", ".conf", ".env", ".exemplo",
    }
)
NOMES = frozenset({"Dockerfile", "Makefile"})

# Linha só de comentário fica fora de toda regra de conteúdo: o comentário que
# EXPLICA a lei ("autorizado não é aprovado") não pode ser lido como a violação
# que ela proíbe.
ABERTURAS_DE_COMENTARIO = ("#", "//", "*", "<!--", "/*")

CELULA_DONA_DO_SEGREDO = "services/pagamentos/"

CAMINHO_DO_PIX = re.compile(r"(?:^|/)pix(?:[/._-]|$)")

CHAVE_QUE_ESCOLHE_PROVEDOR = re.compile(
    r"\b(?:PIX|CARTAO|CARD|CREDITO|CREDIT)[A-Z0-9_]*"
    r"_(?:PROVIDER|PROVEDOR|GATEWAY|BACKEND|ADAPTER)\b"
    r"|\b(?:PROVIDER|PROVEDOR|GATEWAY|BACKEND|ADAPTER)"
    r"_(?:PIX|CARTAO|CARD|CREDITO|CREDIT)\b"
)

DADO_DO_CARTAO = re.compile(
    r"\b(?:card_number|cardnumber|numero_do_cartao|numero_cartao|card_pan"
    r"|cvv|cvc|card_cvv|security_code|codigo_de_seguranca"
    r"|exp_month|exp_year|expiry_month|expiry_year"
    r"|expiration_month|expiration_year|card_expiry|validade_do_cartao"
    r"|tokenizar_cartao|tokenize_card|card_tokenization)\b",
    re.IGNORECASE,
)

_AUTORIZADO = r"(?:authorized|authorization|autorizad[ao]|autorizacao)"
_APROVADO = r"(?:approved|aprovad[ao]|paid|pago|captured|capturado)"
CONFUNDE_AUTORIZADO_COM_APROVADO = re.compile(
    rf"\b{_AUTORIZADO}\b.*\b{_APROVADO}\b|\b{_APROVADO}\b.*\b{_AUTORIZADO}\b",
    re.IGNORECASE,
)

DECIDE_DINHEIRO = re.compile(
    r"\b(?:aprovar|aprovado|approve|approved|capturar|capture"
    r"|matricular|enroll|marcar_pago|confirmar_pagamento|liberar_acesso)\b",
    re.IGNORECASE,
)

RETRY_CEGO = re.compile(
    r"\btenacity\b|\bbackoff\.on_exception\b|\bRetry\s*\(|@\s*retry\b"
    r"|\bmax_retries\b|\bretries\s*=|\bnum_retries\b|\bautoretry\b",
    re.IGNORECASE,
)

SEGREDO_APPMAX = re.compile(
    r"\bAPPMAX_(?:CLIENT_SECRET|CLIENT_ID|SECRET|ACCESS_TOKEN|REFRESH_TOKEN"
    r"|API_KEY|TOKEN|PASSWORD)\b"
)

ESCRITA_NA_OUTBOX = re.compile(
    r"\bOutbox\w*\.objects\.(?:create|bulk_create)\(|\bOutbox\w*\("
)

APPMAX_NOMEADO = re.compile(r"\bappmax\b", re.IGNORECASE)

MERCADO_PAGO = re.compile(
    r"\bmercado[\s_-]?pago\b|\bmercadopago\b|\bmp_payment_id\b|\bMP_ACCESS_TOKEN\b",
    re.IGNORECASE,
)

LEITURA_TOLERANTE = re.compile(
    r"\b(?:resposta|response|payload|corpo|body|dados|data|json|conteudo)\w*"
    r"\.get\(\s*[\"'](?:id|status|order_id|pedido_id|customer_id|transaction_id"
    r"|access_token|token|expires_in|total|amount|total_cents)[\"']",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Arquivo:
    """Um arquivo lido uma vez: o texto inteiro e só as linhas que decidem."""

    caminho: str
    texto: str
    uteis: tuple[tuple[int, str], ...]


def _e_comentario(linha: str) -> bool:
    despido = linha.strip()
    return despido.startswith(ABERTURAS_DE_COMENTARIO)


def ler_arvores(raiz: Path) -> list[Arquivo]:
    """Lê as três árvores. Qualquer tropeço é ERROR, nunca lista curta."""
    arquivos: list[Arquivo] = []
    for arvore in ARVORES:
        pasta = raiz / arvore
        if not pasta.is_dir():
            raise ErroDeInstrumentacao(
                f"árvore obrigatória ausente: {arvore}",
                f"Esperada em:\n  {pasta}\n\n"
                "Medir duas árvores de três e devolver PASS seria afirmar mais\n"
                "do que foi visto. Confira a raiz informada em --raiz.",
            )
        for caminho in sorted(pasta.rglob("*")):
            if not caminho.is_file():
                continue
            if caminho.suffix not in SUFIXOS and caminho.name not in NOMES:
                continue
            try:
                texto = caminho.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as erro:
                raise ErroDeInstrumentacao(
                    f"arquivo ilegível: {caminho.relative_to(raiz).as_posix()}",
                    f"{type(erro).__name__}: {erro}\n\n"
                    "Um arquivo que não abre não foi medido, e não medir nunca\n"
                    "é passar. Conserte a codificação ou tire o arquivo da árvore.",
                )
            uteis = tuple(
                (numero, linha)
                for numero, linha in enumerate(texto.splitlines(), start=1)
                if linha.strip() and not _e_comentario(linha)
            )
            arquivos.append(
                Arquivo(caminho.relative_to(raiz).as_posix(), texto, uteis)
            )
    if not arquivos:
        raise ErroDeInstrumentacao(
            "nenhum arquivo lido nas três árvores",
            "As pastas existem e nenhum arquivo casou com os sufixos medidos.\n"
            "Zero arquivos lidos não é 'nada a corrigir', é o instrumento\n"
            "medindo a coisa errada (raiz? worktree vazio?).",
        )
    return arquivos


def superficie_appmax(arquivos: list[Arquivo]) -> list[Arquivo]:
    """Os arquivos que nomeiam a Appmax. Sete das nove leis vivem aqui."""
    return [arquivo for arquivo in arquivos if "appmax" in arquivo.texto.lower()]


def _citar(arquivo: Arquivo, numero: int, linha: str, achado: str) -> str:
    return f"{arquivo.caminho}:{numero}  [{achado}]  {linha.strip()[:90]}"


def _citar_arquivo(arquivo: Arquivo, motivo: str) -> str:
    return f"{arquivo.caminho}  {motivo}"


def a1_provedor_por_construcao(todos: list[Arquivo], _: list[Arquivo]) -> list[str]:
    """Nenhum nome de ajuste ou variável pareia método de pagamento com provedor."""
    achados: list[str] = []
    for arquivo in todos:
        for numero, linha in arquivo.uteis:
            for encontro in CHAVE_QUE_ESCOLHE_PROVEDOR.finditer(linha):
                achados.append(_citar(arquivo, numero, linha, encontro.group(0)))
    return achados


def a2_dado_do_cartao_fora(todos: list[Arquivo], _: list[Arquivo]) -> list[str]:
    """Número, validade e código de segurança não são nomeados em lugar nenhum."""
    achados: list[str] = []
    for arquivo in todos:
        for numero, linha in arquivo.uteis:
            for encontro in DADO_DO_CARTAO.finditer(linha):
                achados.append(_citar(arquivo, numero, linha, encontro.group(0)))
    return achados


def a3_autorizado_nao_e_aprovado(_: list[Arquivo], superficie: list[Arquivo]) -> list[str]:
    """Autorização e aprovação não se encontram na mesma expressão."""
    achados: list[str] = []
    for arquivo in superficie:
        for numero, linha in arquivo.uteis:
            for encontro in CONFUNDE_AUTORIZADO_COM_APROVADO.finditer(linha):
                achados.append(_citar(arquivo, numero, linha, encontro.group(0)))
    return achados


def a4_webhook_nao_decide_dinheiro(_: list[Arquivo], superficie: list[Arquivo]) -> list[str]:
    """O arquivo de webhook da Appmax não contém verbo que mexa em dinheiro."""
    achados: list[str] = []
    for arquivo in superficie:
        if "webhook" not in arquivo.caminho.lower():
            continue
        for numero, linha in arquivo.uteis:
            for encontro in DECIDE_DINHEIRO.finditer(linha):
                achados.append(_citar(arquivo, numero, linha, encontro.group(0)))
    return achados


def a5_sem_retry_cego(_: list[Arquivo], superficie: list[Arquivo]) -> list[str]:
    """Nenhuma repetição automática e genérica na superfície Appmax."""
    achados: list[str] = []
    for arquivo in superficie:
        for numero, linha in arquivo.uteis:
            for encontro in RETRY_CEGO.finditer(linha):
                achados.append(_citar(arquivo, numero, linha, encontro.group(0)))
    return achados


def a6_outbox_na_mesma_transacao(_: list[Arquivo], superficie: list[Arquivo]) -> list[str]:
    """Quem CRIA linha de outbox na superfície Appmax o faz dentro da transação.

    A medição é da escrita, nunca da palavra: o módulo que só cita a outbox num
    comentário, na dependência de uma migração ou no nome do relay não escreve
    nada. Publicar por `transaction.on_commit` DEPOIS de a linha existir é o
    padrão certo do INV-P6, e por isso não entra aqui.
    """
    achados: list[str] = []
    for arquivo in superficie:
        if "transaction.atomic" in arquivo.texto:
            continue
        for numero, linha in arquivo.uteis:
            if linha.lstrip().startswith("class "):
                continue
            for encontro in ESCRITA_NA_OUTBOX.finditer(linha):
                achados.append(_citar(arquivo, numero, linha, encontro.group(0)))
    return achados


def a7_segredo_so_em_pagamentos(todos: list[Arquivo], _: list[Arquivo]) -> list[str]:
    """Nome de segredo Appmax só aparece dentro da célula pagamentos."""
    achados: list[str] = []
    for arquivo in todos:
        if not arquivo.caminho.startswith("services/"):
            continue
        if arquivo.caminho.startswith(CELULA_DONA_DO_SEGREDO):
            continue
        for numero, linha in arquivo.uteis:
            for encontro in SEGREDO_APPMAX.finditer(linha):
                achados.append(_citar(arquivo, numero, linha, encontro.group(0)))
    return achados


def a8_provedores_sem_destino_comum(_: list[Arquivo], superficie: list[Arquivo]) -> list[str]:
    """O caminho do Pix ignora a Appmax, e o caminho da Appmax ignora o outro.

    A medição é do CÓDIGO de cada caminho. Contrato que ENUMERA os provedores
    aceitos, e teste que compara os dois, são declaração, não acoplamento: o que
    derruba um método junto com o outro é o módulo de um provedor chamando o
    outro.
    """
    achados: list[str] = []
    for arquivo in superficie:
        caminho = arquivo.caminho.lower()
        if CAMINHO_DO_PIX.search(caminho):
            proibido, lado = APPMAX_NOMEADO, "o caminho do Pix nomeia a Appmax"
        elif "appmax" in caminho:
            proibido, lado = MERCADO_PAGO, "o caminho da Appmax nomeia o Mercado Pago"
        else:
            continue
        for numero, linha in arquivo.uteis:
            for encontro in proibido.finditer(linha):
                achados.append(_citar(arquivo, numero, linha, f"{lado}: {encontro.group(0)}"))
    return achados


def a9_payload_incompleto_e_erro(_: list[Arquivo], superficie: list[Arquivo]) -> list[str]:
    """Campo obrigatório de resposta Appmax não é lido com leitura tolerante."""
    achados: list[str] = []
    for arquivo in superficie:
        for numero, linha in arquivo.uteis:
            for encontro in LEITURA_TOLERANTE.finditer(linha):
                achados.append(_citar(arquivo, numero, linha, encontro.group(0)))
    return achados


CHECAGENS = (
    (
        "INV-CARD-A1",
        a1_provedor_por_construcao,
        "Pix é Mercado Pago e cartão é Appmax por construção",
        "Apague o ajuste que escolhe provedor e deixe a escolha no código. "
        "A única trava prevista é APPMAX_CARD_ENABLED_SITES, que desliga "
        "tentativas novas de cartão e nunca troca de provedor.",
    ),
    (
        "INV-CARD-A2",
        a2_dado_do_cartao_fora,
        "número, validade e código de segurança não existem no nosso código",
        "Tire o campo. A tokenização é do Appmax JS, no navegador; "
        "nomear o dado aqui já é pedir escopo PCI-DSS, que está proibido.",
    ),
    (
        "INV-CARD-A3",
        a3_autorizado_nao_e_aprovado,
        "autorizado não significa aprovado",
        "Separe as duas palavras em estados diferentes. Quem decide o estado "
        "financeiro é a consulta autenticada do pedido, e mais ninguém. "
        "Se a linha apenas EXPLICA a lei, escreva a explicação em comentario "
        "de linha, que fica fora da medição, e não em docstring.",
    ),
    (
        "INV-CARD-A4",
        a4_webhook_nao_decide_dinheiro,
        "o webhook da Appmax é sinal, nunca decisão",
        "Deixe o webhook só agendar a consulta autenticada do pedido. "
        "A Appmax não assina webhook nenhum, então ele não prova nada. "
        "Se a linha apenas EXPLICA a lei, escreva a explicação em comentario "
        "de linha, que fica fora da medição, e não em docstring.",
    ),
    (
        "INV-CARD-A5",
        a5_sem_retry_cego,
        "escrita externa com resultado ambíguo não recebe repetição automática",
        "Apague a repetição genérica e trate cada operação por escrito: "
        "GET seguro repete com limite; POST ambíguo consulta e se resolve, "
        "nunca reenvia.",
    ),
    (
        "INV-CARD-A6",
        a6_outbox_na_mesma_transacao,
        "toda aprovação cria outbox na mesma transação",
        "Crie a linha de outbox dentro do mesmo transaction.atomic() da "
        "mudança de estado. Publicar no Redis depois do commit continua certo; "
        "o que não pode é a linha nascer fora da transação.",
    ),
    (
        "INV-CARD-A7",
        a7_segredo_so_em_pagamentos,
        "o segredo da Appmax existe somente na célula pagamentos",
        "Tire o nome do segredo desta célula. Quem precisa do resultado "
        "chama a célula pagamentos pelo contrato dela.",
    ),
    (
        "INV-CARD-A8",
        a8_provedores_sem_destino_comum,
        "o caminho de cada provedor ignora o outro",
        "Separe os arquivos: um provedor por módulo. Módulo de um provedor que "
        "chama o outro é o ponto por onde a queda de um derruba o método do outro.",
    ),
    (
        "INV-CARD-A9",
        a9_payload_incompleto_e_erro,
        "resposta 2xx incompleta é erro, nunca sucesso parcial",
        "Leia o campo obrigatório de um jeito que estoure quando ele faltar, "
        "ou valide a resposta inteira antes de usá-la.",
    ),
)


def rodar(raiz: Path | None = None) -> Relatorio:
    """O portão inteiro. Devolve `Relatorio`, e o pior estado vence."""
    relatorio = Relatorio("GUARDA DO CARTÃO — as nove leis do cartão pela Appmax")
    try:
        raiz = raiz_declarada(raiz) if raiz is not None else raiz_do_repo()
        arquivos = ler_arvores(raiz)
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("guarda-do-cartao", erro))
        return relatorio

    superficie = superficie_appmax(arquivos)
    relatorio.titulo += (
        f"  ({len(arquivos)} arquivos lidos, {len(superficie)} na superfície Appmax)"
    )
    for codigo, checagem, lei, como_corrigir in CHECAGENS:
        try:
            achados = checagem(arquivos, superficie)
        except Exception as erro:  # a regra não rodou, e isso nunca é PASS
            relatorio.registrar(
                Resultado.de_erro(
                    codigo,
                    ErroDeInstrumentacao(
                        f"a regra não pôde ser medida: {type(erro).__name__}",
                        f"{erro}\n\nLei: {lei}",
                    ),
                )
            )
            continue
        if achados:
            relatorio.registrar(
                Resultado(
                    codigo,
                    Estado.FAIL,
                    f"{lei} — {len(achados)} violação(ões)",
                    "\n".join(f"  {achado}" for achado in achados)
                    + f"\n\nO CERTO: {como_corrigir}",
                )
            )
        else:
            relatorio.registrar(Resultado(codigo, Estado.PASS, lei))
    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Guarda do cartão — as nove leis da Appmax [INV-CI01]"
    )
    parser.add_argument(
        "--raiz", default=None, help="raiz do repositório (padrão: detectar)"
    )
    args = parser.parse_args(argv)
    relatorio = rodar(Path(args.raiz).resolve() if args.raiz else None)
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
