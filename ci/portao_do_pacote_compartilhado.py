#!/usr/bin/env python
"""O PORTÃO DO PACOTE COMPARTILHADO — quem muda a biblioteca, entrega a wheel.

`packages/outbox-relay` é a única biblioteca compartilhada da plataforma: ela
transporta os eventos de matrícula e de cadastro, ou seja, o elo que entrega a
matrícula depois do pagamento aprovado. `alunos` e `identidade` a consomem como
wheel VENDORIZADA, e é a wheel — não o fonte — que entra na imagem no build.

O BURACO, medido em 18/09/2026 contra `origin/main` e remedido nesta bancada:

    $ python -c "... mapa_de_celulas.celulas_do_diff(['packages/outbox-relay/...'])"
    celulas do diff (so packages): []
    controle (services/alunos): ['alunos']

A fábrica inteira deriva o que testar e o que publicar da pergunta "de que
célula é este arquivo?". Para `packages/` a resposta é NENHUMA, então: o job
`rodar` do `ci-celula.yml` é pulado, o gate imprime SKIP e fica VERDE, o
`pouso.yml` integra, e o `deploy-celula.yml` nem começa (seu gatilho é
`services/**`, `painel/**`, `fila/**`, `documentos/**`, `docs/decisoes/**`).
Resultado: a correção de bug fica na `main`, a produção continua rodando a
wheel antiga, e nenhum teste rodou. Ver `armadilhas/487`.

O QUE ESTE PORTÃO FAZ, e por que é isto que fecha o buraco:

Ele prova, em TODO PR, que cada wheel vendorizada é a wheel deste fonte. Roda
pela suíte `ci/tests/`, que o `muralhas.yml` executa sem filtro de caminho
(`python ci/ci.py --apenas testador`) — o único portão que enxerga um PR que só
mexe em `packages/`. E, porque a única forma de deixá-lo verde é reconstruir as
duas wheels, o PR passa obrigatoriamente a tocar `services/**`: aí as duas
suítes de célula rodam e o `deploy-celula` dispara. Um portão, três buracos.

QUEM É CONSUMIDOR NÃO É UMA LISTA ESCRITA À MÃO. É quem tem a wheel em
`services/<célula>/vendor/`. Lista à mão envelhece em silêncio, e uma célula
nova que vendorizasse o pacote ficaria fora da conferência sem ninguém ver.

FAIL é "a wheel divergiu do fonte". ERROR é "não consegui comparar" — pacote
fora do lugar, wheel ilegível, ou ZERO consumidores encontrados. Nenhum dos
dois é PASS: um portão que não mediu nada não provou nada. [INV-CI01]
"""

from __future__ import annotations

import argparse
import base64
import csv
import difflib
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:  # pragma: no cover - fiação de import
    sys.path.insert(0, str(CI))

from _nucleo import (  # noqa: E402
    Estado,
    ErroDeInstrumentacao,
    Relatorio,
    Resultado,
    configurar_saida,
    raiz_declarada,
    raiz_do_repo,
)

PACOTE = Path("packages") / "outbox-relay"
MODULO = "outbox_relay"
PACOTE_SITE_ERRORS = Path("packages") / "site_errors"
MODULO_SITE_ERRORS = "site_errors"
CONSERTO = "python ci/portao_do_pacote_compartilhado.py --reconstruir"


def _texto(dados: bytes) -> str:
    """Decodifica normalizando a quebra de linha.

    A wheel é construída no Linux e lida no Windows (e vice-versa). Sem esta
    normalização o portão acusaria divergência em toda máquina que fizesse
    checkout com CRLF, que é ruído, não defeito.
    """
    return dados.decode("utf-8").replace("\r\n", "\n")


def fonte_do_pacote(raiz: Path) -> dict[str, str]:
    """Os módulos do fonte, indexados pelo caminho que eles têm DENTRO da wheel."""
    src = raiz / PACOTE / "src" / MODULO
    if not src.is_dir():
        raise ErroDeInstrumentacao(
            "o pacote compartilhado não está onde este portão o procura",
            f"Esperado: {src}\n"
            "Sem fonte não existe comparação, e comparar nada nunca é PASS.",
        )
    modulos = {
        f"{MODULO}/{arquivo.name}": _texto(arquivo.read_bytes())
        for arquivo in sorted(src.glob("*.py"))
    }
    if not modulos:
        raise ErroDeInstrumentacao(
            "o fonte do pacote compartilhado não tem módulo algum",
            f"Diretório: {src}\nNada a comparar significa nada provado.",
        )
    return modulos


def versao_declarada(raiz: Path) -> str:
    """A versão que o `pyproject.toml` do pacote declara."""
    pyproject = raiz / PACOTE / "pyproject.toml"
    try:
        dados = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return str(dados["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError, ValueError) as erro:
        raise ErroDeInstrumentacao(
            "não consegui ler a versão declarada do pacote",
            f"Arquivo: {pyproject}\nMotivo: {erro.__class__.__name__}: {erro}",
        ) from erro


def consumidores(raiz: Path) -> list[tuple[str, Path]]:
    """As células que vendorizam o pacote, descobertas no disco."""
    achados: list[tuple[str, Path]] = []
    for vendor in sorted((raiz / "services").glob("*/vendor")):
        wheels = sorted(vendor.glob(f"{MODULO}-*.whl"))
        if not wheels:
            continue
        if len(wheels) > 1:
            raise ErroDeInstrumentacao(
                f"a célula {vendor.parent.name} vendoriza "
                f"{len(wheels)} wheels do pacote",
                "Wheels encontradas:\n"
                + "\n".join(f"  {w}" for w in wheels)
                + "\nCom duas, qual delas a imagem instala depende do "
                "requirements.txt, e o portão não tem o que declarar correto.",
            )
        achados.append((vendor.parent.name, wheels[0]))
    if not achados:
        raise ErroDeInstrumentacao(
            "nenhuma célula vendoriza o pacote compartilhado",
            f"Procurei por services/*/vendor/{MODULO}-*.whl em:\n  {raiz}\n"
            "Zero consumidores deixaria este portão verde por não ter o que\n"
            "conferir, que é exatamente o falso-verde que ele existe para "
            "impedir.",
        )
    return achados


def _versao_na_metadata(zf: zipfile.ZipFile, wheel: Path) -> str:
    metadatas = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
    if len(metadatas) != 1:
        raise ErroDeInstrumentacao(
            f"a wheel {wheel.name} tem {len(metadatas)} arquivos METADATA",
            f"Arquivo: {wheel}\nUma wheel válida tem exatamente um.",
        )
    achado = re.search(r"^Version: (.+)$", _texto(zf.read(metadatas[0])), re.MULTILINE)
    if achado is None:
        raise ErroDeInstrumentacao(
            f"a METADATA da wheel {wheel.name} não declara versão",
            f"Arquivo: {wheel}",
        )
    return achado.group(1).strip()


def _divergencia(caminho: str, na_wheel: str, no_fonte: str) -> str:
    diff = difflib.unified_diff(
        no_fonte.splitlines(),
        na_wheel.splitlines(),
        fromfile=f"fonte/{caminho}",
        tofile=f"wheel/{caminho}",
        lineterm="",
        n=1,
    )
    return "\n".join(list(diff)[:40])


def conferir(
    celula: str, wheel: Path, fonte: dict[str, str], versao: str, raiz: Path
) -> Resultado:
    """Compara UMA wheel vendorizada com o fonte do pacote."""
    nome = f"{celula}/{wheel.name}"
    try:
        with zipfile.ZipFile(wheel) as zf:
            na_metadata = _versao_na_metadata(zf, wheel)
            na_wheel = {
                alvo: _texto(zf.read(alvo))
                for alvo in sorted(zf.namelist())
                if alvo.startswith(f"{MODULO}/") and alvo.endswith(".py")
            }
    except (zipfile.BadZipFile, KeyError, OSError, UnicodeDecodeError) as erro:
        raise ErroDeInstrumentacao(
            f"não consegui abrir a wheel vendorizada de {celula}",
            f"Arquivo: {wheel}\nMotivo: {erro.__class__.__name__}: {erro}",
        ) from erro

    problemas: list[str] = []

    no_nome = wheel.name.split("-")[1]
    if no_nome != versao:
        problemas.append(
            f"o nome do arquivo diz versão {no_nome} e o pyproject.toml "
            f"declara {versao}."
        )
    if na_metadata != versao:
        problemas.append(
            f"a METADATA dentro da wheel diz versão {na_metadata} e o "
            f"pyproject.toml declara {versao}: a wheel foi renomeada, não "
            "reconstruída."
        )

    for caminho in sorted(set(fonte) - set(na_wheel)):
        problemas.append(f"{caminho} existe no fonte e NÃO está dentro da wheel.")
    for caminho in sorted(set(na_wheel) - set(fonte)):
        problemas.append(f"{caminho} está dentro da wheel e NÃO existe no fonte.")
    for caminho in sorted(set(fonte) & set(na_wheel)):
        if fonte[caminho] != na_wheel[caminho]:
            problemas.append(
                f"{caminho} divergiu do fonte:\n"
                + _divergencia(caminho, na_wheel[caminho], fonte[caminho])
            )

    requisitos = raiz / "services" / celula / "requirements.txt"
    esperado = f"services/{celula}/vendor/{wheel.name}"
    if not requisitos.is_file():
        raise ErroDeInstrumentacao(
            f"a célula {celula} vendoriza a wheel e não tem requirements.txt",
            f"Esperado: {requisitos}\n"
            "Sem ele não dá para provar que a imagem instala a wheel que está "
            "aqui, e supor que instala seria o falso-verde de sempre.",
        )
    if esperado not in requisitos.read_text(encoding="utf-8").replace("\\", "/"):
        problemas.append(
            f"{requisitos.relative_to(raiz).as_posix()} não instala "
            f"{esperado}: a imagem publicaria outra coisa."
        )

    if problemas:
        return Resultado(
            nome=nome,
            estado=Estado.FAIL,
            resumo=f"{len(problemas)} divergência(s) entre a wheel e o fonte",
            detalhe="\n".join(problemas),
        )
    return Resultado(
        nome=nome,
        estado=Estado.PASS,
        resumo=f"{len(fonte)} módulo(s) idênticos ao fonte, versão {versao}",
    )


def rodar(raiz: Path | None = None) -> Relatorio:
    """O veredito do portão sobre a árvore inteira."""
    relatorio = Relatorio(
        titulo="PORTÃO DO PACOTE COMPARTILHADO (packages/outbox-relay)"
    )
    try:
        raiz = raiz_declarada(raiz) if raiz is not None else raiz_do_repo()
        fonte = fonte_do_pacote(raiz)
        versao = versao_declarada(raiz)
        alvos = consumidores(raiz)
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("pacote compartilhado", erro))
        return relatorio

    for celula, wheel in alvos:
        try:
            relatorio.registrar(conferir(celula, wheel, fonte, versao, raiz))
        except ErroDeInstrumentacao as erro:
            relatorio.registrar(Resultado.de_erro(f"{celula}/{wheel.name}", erro))
    if (raiz / PACOTE_SITE_ERRORS).is_dir():
        relatorio_site = rodar_site_errors(raiz)
        for resultado in relatorio_site.resultados:
            relatorio.registrar(resultado)
    return relatorio


def reconstruir(raiz: Path) -> int:
    """Constrói a wheel do fonte, entrega a TODOS os consumidores e RECONFERE.

    Devolve o veredito do portão, não "fiz alguma coisa": quem conserta precisa
    saber se ficou consertado, e o caso que sobra (versão nova, requirements
    ainda apontando a wheel antiga) é decisão de quem escolheu o número.

    Existe porque até hoje este passo não tinha comando nenhum no repositório:
    quem mexia no pacote construía e copiava à mão, e esquecer uma das duas
    cópias era a divergência que o portão acima passa a reprovar. Mensagem de
    erro que manda fazer algo precisa que esse algo exista.

    A construção acontece sobre uma CÓPIA do pacote, em diretório temporário,
    para que o `build/` e o `*.egg-info` do setuptools não sujem a árvore.
    """
    alvos = consumidores(raiz)
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "pacote"
        saida = Path(tmp) / "dist"
        shutil.copytree(raiz / PACOTE, copia)
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(saida),
                str(copia),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            raise ErroDeInstrumentacao(
                "a construção da wheel falhou",
                f"{proc.stdout}\n{proc.stderr}\n"
                "Se o módulo `build` não existe nesta máquina:\n"
                "  python -m pip install build",
            )
        produzidas = sorted(saida.glob(f"{MODULO}-*.whl"))
        if len(produzidas) != 1:
            raise ErroDeInstrumentacao(
                f"a construção produziu {len(produzidas)} wheels",
                f"{proc.stdout}\nEsperava exatamente uma em {saida}.",
            )
        nova = produzidas[0]
        print(f"Wheel construída do fonte: {nova.name}")
        for celula, antiga in alvos:
            if antiga.name != nova.name:
                antiga.unlink()
                print(f"  {celula}: removida a antiga {antiga.name}")
            shutil.copy2(nova, antiga.parent / nova.name)
            entregue = (antiga.parent / nova.name).relative_to(raiz)
            print(f"  {celula}: {entregue.as_posix()}")
    print("")
    relatorio = rodar(raiz)
    print(relatorio.render())
    if relatorio.estado is Estado.FAIL:
        print("")
        print("A cópia foi feita e ainda falta o que está acima. O caso comum é")
        print("a versão ter mudado: o requirements.txt de cada célula continua")
        print("apontando a wheel antiga pelo nome, e só você decide esse número.")
    return relatorio.exit_code


def _fonte_site_errors(raiz: Path) -> dict[str, bytes]:
    src = raiz / PACOTE_SITE_ERRORS / "src" / MODULO_SITE_ERRORS
    if not src.is_dir():
        raise ErroDeInstrumentacao(
            "o pacote site_errors não tem diretório de fonte",
            f"Esperado: {src}",
        )
    arquivos = {
        f"{MODULO_SITE_ERRORS}/{arquivo.relative_to(src).as_posix()}": _normalizar_linhas_site_errors(
            arquivo.read_bytes()
        )
        for arquivo in sorted(src.rglob("*"))
        if arquivo.is_file() and "__pycache__" not in arquivo.parts
    }
    if not arquivos:
        raise ErroDeInstrumentacao(
            "o pacote site_errors não tem arquivos de fonte",
            f"Diretório: {src}",
        )
    return arquivos


def _normalizar_linhas_site_errors(conteudo: bytes) -> bytes:
    return conteudo.replace(b"\r\n", b"\n")


def _consumidores_site_errors(raiz: Path) -> list[tuple[str, Path]]:
    achados = []
    for vendor in sorted((raiz / "services").glob("*/vendor")):
        wheels = sorted(vendor.glob("site_errors-*.whl"))
        if len(wheels) > 1:
            raise ErroDeInstrumentacao(
                f"a célula {vendor.parent.name} vendoriza várias wheels site_errors",
                "Wheels encontradas: " + ", ".join(w.name for w in wheels),
            )
        if wheels:
            achados.append((vendor.parent.name, wheels[0]))
    if not achados:
        raise ErroDeInstrumentacao(
            "nenhuma célula vendoriza site_errors",
            f"Procurei por services/*/vendor/site_errors-*.whl em {raiz}",
        )
    return achados


def _normalizar_requisito_site_errors(requisito: str) -> str:
    achado = re.match(r"\s*([A-Za-z0-9_.-]+)\s*(.*)", requisito)
    if achado is None:
        return requisito.strip().lower()
    nome = re.sub(r"[-_.]+", "-", achado.group(1)).lower()
    restricoes = sorted(
        parte.replace(" ", "") for parte in achado.group(2).split(",") if parte
    )
    return nome + ",".join(restricoes)


def conferir_site_errors(
    celula: str,
    wheel: Path,
    raiz: Path,
    fonte: dict[str, bytes],
    versao: str,
    dependencias: list[str],
) -> Resultado:
    nome = f"{celula}/{wheel.name}"
    try:
        with zipfile.ZipFile(wheel) as zf:
            metadatas = [
                item for item in zf.namelist() if item.endswith(".dist-info/METADATA")
            ]
            if len(metadatas) != 1:
                raise ErroDeInstrumentacao(
                    f"a wheel de {celula} tem {len(metadatas)} arquivos METADATA",
                    f"Arquivo: {wheel}",
                )
            metadata = _texto(zf.read(metadatas[0]))
            arquivos_wheel = {
                item: _normalizar_linhas_site_errors(zf.read(item))
                for item in sorted(zf.namelist())
                if item.startswith(f"{MODULO_SITE_ERRORS}/")
            }
            versao_wheel = _versao_na_metadata(zf, wheel)
    except ErroDeInstrumentacao:
        raise
    except (zipfile.BadZipFile, KeyError, OSError, UnicodeDecodeError) as erro:
        raise ErroDeInstrumentacao(
            f"não consegui abrir a wheel site_errors de {celula}",
            f"Arquivo: {wheel}\nMotivo: {erro.__class__.__name__}: {erro}",
        ) from erro

    problemas = []
    versao_no_nome = re.match(r"site_errors-([^-]+)-", wheel.name)
    if versao_no_nome is None or versao_no_nome.group(1) != versao:
        problemas.append(
            f"o nome {wheel.name} não corresponde à versão declarada {versao}."
        )
    if versao_wheel != versao:
        problemas.append(
            f"a METADATA declara {versao_wheel}; o pyproject.toml declara {versao}."
        )
    for caminho in sorted(set(fonte) - set(arquivos_wheel)):
        problemas.append(f"{caminho} existe no fonte e não está na wheel.")
    for caminho in sorted(set(arquivos_wheel) - set(fonte)):
        problemas.append(f"{caminho} está na wheel e não existe no fonte.")
    for caminho in sorted(set(fonte) & set(arquivos_wheel)):
        if fonte[caminho] != arquivos_wheel[caminho]:
            problemas.append(f"{caminho} divergiu do fonte, incluindo arquivos HTML.")
    requisitos_wheel = [
        linha.partition(":")[2].strip()
        for linha in metadata.splitlines()
        if linha.startswith("Requires-Dist:")
    ]
    if sorted(map(_normalizar_requisito_site_errors, requisitos_wheel)) != sorted(
        map(_normalizar_requisito_site_errors, dependencias)
    ):
        problemas.append("as dependências da METADATA divergem do pyproject.toml.")
    requisitos = raiz / "services" / celula / "requirements.txt"
    caminho_instalado = f"services/{celula}/vendor/{wheel.name}"
    if not requisitos.is_file() or caminho_instalado not in requisitos.read_text(
        encoding="utf-8"
    ).replace("\\", "/"):
        problemas.append(f"requirements.txt não instala {caminho_instalado}.")
    dockerfiles = sorted((raiz / "services" / celula).glob("Dockerfile*"))
    imagens_com_pip = []
    for dockerfile in dockerfiles:
        docker = dockerfile.read_text(encoding="utf-8")
        if "RUN pip install" in docker and "requirements.txt" in docker:
            imagens_com_pip.append((dockerfile, docker))
    if not imagens_com_pip:
        problemas.append("nenhum Dockerfile instala requirements.txt.")
    for dockerfile, docker in imagens_com_pip:
        copia = docker.find(f"COPY vendor ./services/{celula}/vendor")
        instala = docker.find("RUN pip install")
        if copia < 0 or instala < 0 or copia > instala:
            problemas.append(
                f"{dockerfile.name} não copia a wheel antes de executar pip install."
            )
    if problemas:
        return Resultado(
            nome,
            Estado.FAIL,
            f"{len(problemas)} divergência(s) entre fonte, wheel e imagem",
            "\n".join(problemas),
        )
    return Resultado(
        nome,
        Estado.PASS,
        f"{len(fonte)} arquivos idênticos ao fonte, versão {versao}",
    )


def rodar_site_errors(raiz: Path | None = None) -> Relatorio:
    relatorio = Relatorio("PORTÃO DO PACOTE COMPARTILHADO (packages/site_errors)")
    try:
        raiz = raiz_declarada(raiz) if raiz is not None else raiz_do_repo()
        fonte = _fonte_site_errors(raiz)
        projeto = tomllib.loads(
            (raiz / PACOTE_SITE_ERRORS / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]
        versao = str(projeto["version"])
        dependencias = list(projeto["dependencies"])
        alvos = _consumidores_site_errors(raiz)
    except (ErroDeInstrumentacao, OSError, KeyError, tomllib.TOMLDecodeError) as erro:
        if isinstance(erro, ErroDeInstrumentacao):
            relatorio.registrar(Resultado.de_erro("site_errors", erro))
        else:
            relatorio.registrar(
                Resultado.de_erro(
                    "site_errors",
                    ErroDeInstrumentacao(
                        "não consegui ler fonte ou pyproject.toml", str(erro)
                    ),
                )
            )
        return relatorio
    for celula, wheel in alvos:
        try:
            relatorio.registrar(
                conferir_site_errors(celula, wheel, raiz, fonte, versao, dependencias)
            )
        except ErroDeInstrumentacao as erro:
            relatorio.registrar(Resultado.de_erro(f"{celula}/{wheel.name}", erro))
    return relatorio


def reconstruir_site_errors(raiz: Path) -> int:
    raiz = raiz_declarada(raiz)
    pacote = raiz / PACOTE_SITE_ERRORS
    dados = tomllib.loads((pacote / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    versao = str(dados["version"])
    modulo = pacote / "src" / MODULO_SITE_ERRORS
    dist_info = f"site_errors-{versao}.dist-info"
    nome_wheel = f"site_errors-{versao}-py3-none-any.whl"
    alvos = _consumidores_site_errors(raiz)
    with tempfile.TemporaryDirectory() as pasta:
        wheel = Path(pasta) / nome_wheel
        metadata = [
            "Metadata-Version: 2.1",
            f"Name: {dados['name']}",
            f"Version: {versao}",
            f"Summary: {dados.get('description', '')}",
            f"Requires-Python: {dados['requires-python']}",
            *[f"Requires-Dist: {item}" for item in dados.get("dependencies", [])],
            "",
            "",
        ]
        arquivos = {
            f"{MODULO_SITE_ERRORS}/{arquivo.relative_to(modulo).as_posix()}": _normalizar_linhas_site_errors(
                arquivo.read_bytes()
            )
            for arquivo in sorted(modulo.rglob("*"))
            if arquivo.is_file() and "__pycache__" not in arquivo.parts
        }
        arquivos[f"{dist_info}/METADATA"] = "\n".join(metadata).encode("utf-8")
        arquivos[f"{dist_info}/WHEEL"] = (
            "Wheel-Version: 1.0\nGenerator: ci.portao_do_pacote_compartilhado\n"
            "Root-Is-Purelib: true\nTag: py3-none-any\n"
        ).encode("utf-8")
        arquivos[f"{dist_info}/top_level.txt"] = f"{MODULO_SITE_ERRORS}\n".encode()
        linhas = []
        for caminho, conteudo in sorted(arquivos.items()):
            digest = (
                base64.urlsafe_b64encode(hashlib.sha256(conteudo).digest())
                .decode()
                .rstrip("=")
            )
            linhas.append((caminho, f"sha256={digest}", str(len(conteudo))))
        record = f"{dist_info}/RECORD"
        with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as pacote_zip:
            for caminho, conteudo in arquivos.items():
                pacote_zip.writestr(caminho, conteudo)
            from io import StringIO

            saida_csv = StringIO(newline="")
            csv.writer(saida_csv, lineterminator="\n").writerows(
                [*linhas, (record, "", "")]
            )
            pacote_zip.writestr(record, saida_csv.getvalue())
        for celula, antiga in alvos:
            destino = antiga.parent / nome_wheel
            if antiga.name != nome_wheel:
                antiga.unlink()
            shutil.copy2(wheel, destino)
            print(f"  {celula}: {destino.relative_to(raiz).as_posix()}")
    relatorio = rodar_site_errors(raiz)
    print(relatorio.render())
    return relatorio.exit_code


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Prova que as wheels vendorizadas são as wheels deste fonte."
    )
    parser.add_argument("--raiz", type=Path, default=None, help="raiz do repositório")
    parser.add_argument(
        "--reconstruir",
        action="store_true",
        help="constrói a wheel outbox-relay do fonte e a copia para os consumidores",
    )
    parser.add_argument(
        "--reconstruir-site-errors",
        action="store_true",
        help="constrói a wheel site_errors sem ferramentas externas e a copia aos consumidores",
    )
    args = parser.parse_args(argv)

    if args.reconstruir_site_errors:
        try:
            raiz = raiz_declarada(args.raiz) if args.raiz else raiz_do_repo()
            return reconstruir_site_errors(raiz)
        except ErroDeInstrumentacao as erro:
            print(f"ERROR {erro.resumo}")
            print(erro.detalhe)
            return 2
    if args.reconstruir:
        try:
            raiz = raiz_declarada(args.raiz) if args.raiz else raiz_do_repo()
            return reconstruir(raiz)
        except ErroDeInstrumentacao as erro:
            print(f"ERROR {erro.resumo}")
            print(erro.detalhe)
            return 2

    relatorio = rodar(args.raiz)
    print(relatorio.render())
    if relatorio.estado is Estado.FAIL:
        print("")
        print(f"CONSERTO: {CONSERTO}")
        print("Reconstruir a wheel faz o PR tocar services/**, e é assim que as")
        print("suítes das duas células rodam e o deploy da correção dispara.")
    return relatorio.exit_code


def _blindar(rotulo: str, funcao):
    """Exceção não prevista dentro do portão vira ERROR, nunca FAIL. [INV-CI01]"""

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
                "A medição NÃO foi concluída. Este resultado NÃO é um PASS "
                "nem um FAIL: nada foi provado sobre as wheels."
            )
            return 2

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar("portao-do-pacote-compartilhado", main)())
