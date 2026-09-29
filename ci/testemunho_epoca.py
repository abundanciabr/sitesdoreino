"""Testemunho de época fora do PostgreSQL; nenhuma falha autoriza retomada."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

REPO = "abundanciabr/sitesdoreino"
IDENTIDADE = (
    f"https://github.com/{REPO}/.github/workflows/coordenacao-epoca.yml"
    "@refs/heads/main"
)
PREFIXO = "coordenacao-epoca"
SHA = re.compile(r"[0-9a-f]{64}\Z")
OID = re.compile(r"[0-9a-f]{40}\Z")
COORTE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}\Z")
TRANSICAO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
CAMPOS = {
    "versao",
    "coorte",
    "epoca",
    "transicao",
    "estado",
    "anterior",
    "watermark_sha256",
    "autoridade_sha256",
}


class ErroTestemunho(RuntimeError):
    """ERROR: a autoridade não pôde ser comprovada; mantenha a coorte pausada."""


def canonico(valor: object) -> bytes:
    return json.dumps(
        valor,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(valor: object) -> str:
    return hashlib.sha256(canonico(valor)).hexdigest()


def exigir(condicao: bool, motivo: str) -> None:
    if not condicao:
        raise ErroTestemunho(
            f"ERROR: {motivo}. Mantenha a coorte pausada e reconcilie a fonte oficial."
        )


def nome_tag(coorte: str, epoca: int, estado: str) -> str:
    exigir(bool(COORTE.fullmatch(coorte)), "coorte inválida")
    exigir(type(epoca) is int and epoca > 0, "época inválida")
    exigir(estado in {"preparada", "ativa"}, "fase inválida")
    return f"{PREFIXO}/{coorte}/{epoca:020d}/{estado}"


def validar_registro(registro: dict) -> None:
    exigir(
        isinstance(registro, dict) and set(registro) == CAMPOS,
        "campos do registro inválidos",
    )
    exigir(
        registro["versao"] == 1 and type(registro["versao"]) is int, "versão inválida"
    )
    nome_tag(registro["coorte"], registro["epoca"], registro["estado"])
    exigir(
        isinstance(registro["transicao"], str)
        and bool(TRANSICAO.fullmatch(registro["transicao"])),
        "transição inválida",
    )
    for campo in ("watermark_sha256", "autoridade_sha256"):
        exigir(
            isinstance(registro[campo], str) and bool(SHA.fullmatch(registro[campo])),
            f"{campo} inválido",
        )
    anterior = registro["anterior"]
    if anterior is not None:
        exigir(
            isinstance(anterior, dict)
            and set(anterior) == {"epoca", "registro_sha256"}
            and type(anterior["epoca"]) is int
            and 0 < anterior["epoca"] <= registro["epoca"]
            and isinstance(anterior["registro_sha256"], str)
            and bool(SHA.fullmatch(anterior["registro_sha256"])),
            "elo anterior inválido",
        )


def validar_assinado(assinado: dict) -> dict:
    exigir(
        isinstance(assinado, dict) and set(assinado) == {"registro", "bundle"},
        "registro assinado incompleto",
    )
    exigir(isinstance(assinado["bundle"], dict), "bundle Sigstore ausente")
    validar_registro(assinado["registro"])
    return assinado["registro"]


class FonteGitHub:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)

    def _executar(self, args: list[str]) -> bytes:
        try:
            proc = subprocess.run(
                args, cwd=self.raiz, capture_output=True, timeout=90, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as erro:
            raise ErroTestemunho(
                "ERROR: instrumento GitHub indisponível. Mantenha a coorte pausada e confira acesso."
            ) from erro
        if proc.returncode:
            raise ErroTestemunho(
                f"ERROR: {args[0]} não confirmou a operação. Mantenha a coorte pausada e consulte o remoto."
            )
        return proc.stdout

    def _api(self, caminho: str) -> object:
        try:
            return json.loads(self._executar(["gh", "api", caminho]))
        except (ValueError, UnicodeError) as erro:
            raise ErroTestemunho(
                "ERROR: GitHub devolveu JSON inválido. Mantenha a coorte pausada e repita a consulta."
            ) from erro

    def protecao_ativa(self, coorte: str) -> bool:
        regras = self._api(f"repos/{REPO}/rulesets?includes_parents=true")
        exigir(isinstance(regras, list), "lista de regras nativas inválida")
        padrao = f"refs/tags/{PREFIXO}/*/*/*"
        for resumo in regras:
            if not isinstance(resumo, dict) or resumo.get("target") != "tag":
                continue
            regra = self._api(f"repos/{REPO}/rulesets/{resumo['id']}")
            if not isinstance(regra, dict):
                continue
            condicao = regra.get("conditions", {}).get("ref_name", {})
            incluir = condicao.get("include", [])
            excluir = condicao.get("exclude", [])
            tipos = {
                item.get("type")
                for item in regra.get("rules", [])
                if isinstance(item, dict)
            }
            if (
                regra.get("enforcement") == "active"
                and regra.get("target") == "tag"
                and regra.get("bypass_actors") == []
                and {"update", "deletion"} <= tipos
                and isinstance(incluir, list)
                and excluir == []
                and padrao in incluir
            ):
                return True
        return False

    def listar(self, coorte: str) -> dict[str, str]:
        prefixo = f"refs/tags/{PREFIXO}/{coorte}/"
        resposta = self._api(f"repos/{REPO}/git/matching-refs/tags/{PREFIXO}/{coorte}/")
        exigir(isinstance(resposta, list), "listagem oficial de tags inválida")
        saida = {}
        for item in resposta:
            exigir(
                isinstance(item, dict)
                and isinstance(item.get("ref"), str)
                and item["ref"].startswith(prefixo)
                and isinstance(item.get("object"), dict)
                and item["object"].get("type") == "tag"
                and isinstance(item["object"].get("sha"), str)
                and bool(OID.fullmatch(item["object"]["sha"])),
                "referência remota inválida",
            )
            nome = item["ref"][len("refs/tags/") :]
            exigir(nome not in saida, "referência remota duplicada")
            saida[nome] = item["object"]["sha"]
        return saida

    def ler(self, oid: str) -> tuple[dict, str]:
        exigir(bool(OID.fullmatch(oid)), "objeto de tag inválido")
        tag = self._api(f"repos/{REPO}/git/tags/{oid}")
        exigir(
            isinstance(tag, dict)
            and tag.get("sha") == oid
            and tag.get("object", {}).get("type") == "commit"
            and bool(OID.fullmatch(tag.get("object", {}).get("sha", ""))),
            "tag anotada ou fonte ausente",
        )
        mensagem = tag.get("message")
        exigir(isinstance(mensagem, str), "conteúdo da tag ausente")
        try:
            assinado = json.loads(mensagem)
        except ValueError as erro:
            raise ErroTestemunho(
                "ERROR: conteúdo da tag inválido. Mantenha a coorte pausada e reconcilie."
            ) from erro
        exigir(
            mensagem.encode("utf-8") == canonico(assinado).strip(),
            "conteúdo da tag não canônico",
        )
        validar_assinado(assinado)
        return assinado, tag["object"]["sha"]

    def verificar_assinatura(self, assinado: dict, revisao: str | None = None) -> str:
        registro = validar_assinado(assinado)
        with tempfile.TemporaryDirectory(prefix="testemunho-epoca-") as pasta:
            arquivo = Path(pasta) / "registro.json"
            bundle = Path(pasta) / "bundle.json"
            arquivo.write_bytes(canonico(registro))
            bundle.write_bytes(canonico(assinado["bundle"]))
            comando = [
                "gh",
                "attestation",
                "verify",
                str(arquivo),
                "--bundle",
                str(bundle),
                "--repo",
                REPO,
                "--cert-identity",
                IDENTIDADE,
                "--source-ref",
                "refs/heads/main",
                "--deny-self-hosted-runners",
                "--format",
                "json",
            ]
            if revisao is not None:
                comando.extend(["--source-digest", revisao, "--signer-digest", revisao])
            try:
                provas = json.loads(self._executar(comando))
            except (ValueError, UnicodeError) as erro:
                raise ErroTestemunho(
                    "ERROR: prova Sigstore inválida. Mantenha a coorte pausada e verifique a execução oficial."
                ) from erro
        exigir(isinstance(provas, list) and bool(provas), "assinatura oficial ausente")
        for prova in provas:
            resultado = (
                prova.get("verificationResult", {}) if isinstance(prova, dict) else {}
            )
            certificado = resultado.get("signature", {}).get("certificate", {})
            subjects = resultado.get("statement", {}).get("subject", [])
            origem = certificado.get("sourceRepositoryDigest")
            uri = certificado.get("runInvocationURI", "")
            partes = re.fullmatch(
                rf"https://github.com/{REPO}/actions/runs/([1-9][0-9]*)/attempts/([1-9][0-9]*)",
                uri,
            )
            if (
                partes
                and certificado.get("buildTrigger") == "workflow_dispatch"
                and isinstance(origem, str)
                and bool(OID.fullmatch(origem))
                and (revisao is None or origem == revisao)
                and resultado.get("verifiedTimestamps")
                and any(
                    isinstance(s, dict)
                    and s.get("digest", {}).get("sha256") == digest(registro)
                    for s in subjects
                )
            ):
                run = self._api(
                    f"repos/{REPO}/actions/runs/{partes[1]}/attempts/{partes[2]}"
                )
                exigir(
                    isinstance(run, dict)
                    and run.get("status") == "completed"
                    and run.get("conclusion") == "success"
                    and run.get("head_sha") == origem
                    and run.get("head_branch") == "main"
                    and run.get("event") == "workflow_dispatch"
                    and run.get("path") == ".github/workflows/coordenacao-epoca.yml",
                    "execução oficial ainda não concluída ou divergente",
                )
                return origem
        raise ErroTestemunho(
            "ERROR: assinatura não vincula registro e execução oficial main. Mantenha a coorte pausada."
        )

    def criar(self, nome: str, assinado: dict, revisao: str) -> None:
        resposta = self._executar(
            [
                "gh",
                "api",
                "-X",
                "POST",
                f"repos/{REPO}/git/tags",
                "-f",
                f"tag={nome}",
                "-f",
                f"message={canonico(assinado).decode('utf-8')}",
                "-f",
                f"object={revisao}",
                "-f",
                "type=commit",
            ]
        )
        try:
            oid = json.loads(resposta)["sha"]
        except (ValueError, KeyError, TypeError) as erro:
            raise ErroTestemunho(
                "ERROR: criação da tag não confirmou objeto. Releia o remoto antes de agir."
            ) from erro
        exigir(
            isinstance(oid, str) and bool(OID.fullmatch(oid)), "objeto criado inválido"
        )
        self._executar(
            [
                "gh",
                "api",
                "-X",
                "POST",
                f"repos/{REPO}/git/refs",
                "-f",
                f"ref=refs/tags/{nome}",
                "-f",
                f"sha={oid}",
            ]
        )

    def cas_ponteiro(self, coorte: str, nome: str, oid: str) -> None:
        referencia = f"refs/tags/{PREFIXO}-ponteiro/{coorte}"
        resposta = self._executar(["git", "ls-remote", "--refs", "origin", referencia])
        linhas = resposta.decode("utf-8").splitlines()
        exigir(len(linhas) <= 1, "ponteiro remoto ambíguo")
        antigo = linhas[0].split("\t")[0] if linhas else ""
        exigir(not antigo or bool(OID.fullmatch(antigo)), "ponteiro remoto inválido")
        if antigo == oid:
            return
        self._executar(["git", "fetch", "--no-tags", "origin", f"refs/tags/{nome}"])
        try:
            self._executar(
                [
                    "git",
                    "push",
                    f"--force-with-lease={referencia}:{antigo}",
                    "origin",
                    f"{oid}:{referencia}",
                ]
            )
        except ErroTestemunho:
            depois = self._executar(
                ["git", "ls-remote", "--refs", "origin", referencia]
            )
            exigir(
                depois.decode("utf-8").startswith(oid + "\t"),
                "CAS do ponteiro não confirmado",
            )


class TestemunhoEpoca:
    def __init__(self, raiz: Path, verificar_prova_pg, fonte=None):
        self.fonte = fonte if fonte is not None else FonteGitHub(raiz)
        self.verificar_prova_pg = verificar_prova_pg

    def consultar(self, coorte: str) -> dict:
        nome_tag(coorte, 1, "preparada")
        exigir(
            self.fonte.protecao_ativa(coorte),
            "tags sem proteção nativa ativa e sem bypass",
        )
        referencias = self.fonte.listar(coorte)
        por_epoca = {}
        for nome, oid in referencias.items():
            partes = nome.split("/")
            exigir(
                len(partes) == 4
                and partes[0] == PREFIXO
                and partes[1] == coorte
                and re.fullmatch(r"[0-9]{20}", partes[2]) is not None
                and partes[3] in {"preparada", "ativa"}
                and int(partes[2]) > 0,
                "referência de época malformada",
            )
            epoca = int(partes[2])
            exigir(
                nome == nome_tag(coorte, epoca, partes[3]), "nome de época não canônico"
            )
            assinado, revisao = self.fonte.ler(oid)
            registro = validar_assinado(assinado)
            exigir(
                registro["coorte"] == coorte
                and registro["epoca"] == epoca
                and registro["estado"] == partes[3],
                "tag não corresponde ao registro assinado",
            )
            self.fonte.verificar_assinatura(assinado, revisao)
            por_epoca.setdefault(epoca, {})[partes[3]] = (registro, digest(assinado))
        if not por_epoca:
            return {
                "max_epoca": 0,
                "estado": "vazia",
                "transicao": None,
                "registro_sha256": None,
                "watermark_sha256": None,
            }
        maior = max(por_epoca)
        exigir(set(por_epoca) == set(range(1, maior + 1)), "lacuna na cadeia de épocas")
        anterior = None
        ultimo = None
        for epoca in range(1, maior + 1):
            fases = por_epoca[epoca]
            exigir("preparada" in fases, "tag preparada ausente")
            exigir(epoca == maior or "ativa" in fases, "época anterior não foi ativada")
            preparada, preparada_sha = fases["preparada"]
            exigir(preparada["anterior"] == anterior, "elo da preparada divergente")
            ultimo = (preparada, preparada_sha)
            if "ativa" in fases:
                ativa, ativa_sha = fases["ativa"]
                exigir(
                    ativa["anterior"]
                    == {"epoca": epoca, "registro_sha256": preparada_sha}
                    and ativa["transicao"] == preparada["transicao"]
                    and ativa["watermark_sha256"] == preparada["watermark_sha256"],
                    "ativa não vincula a preparação da mesma transição",
                )
                ultimo = (ativa, ativa_sha)
            anterior = {"epoca": epoca, "registro_sha256": ultimo[1]}
        registro, sha = ultimo
        return {
            "max_epoca": maior,
            "estado": registro["estado"],
            "transicao": registro["transicao"],
            "registro_sha256": sha,
            "watermark_sha256": registro["watermark_sha256"],
        }

    def _publicar(self, assinado: dict, esperado: dict, fase: str) -> dict:
        registro = validar_assinado(assinado)
        exigir(registro["estado"] == fase, "fase da publicação divergente")
        atual = self.consultar(registro["coorte"])
        desejado = {
            "max_epoca": registro["epoca"],
            "estado": fase,
            "transicao": registro["transicao"],
            "registro_sha256": digest(assinado),
            "watermark_sha256": registro["watermark_sha256"],
        }
        if atual == desejado:
            return atual
        exigir(atual == esperado, "estado remoto mudou durante a transição")
        if fase == "preparada":
            exigir(
                atual["estado"] in {"vazia", "ativa"}
                and registro["epoca"] == atual["max_epoca"] + 1
                and registro["anterior"]
                == (
                    None
                    if atual["max_epoca"] == 0
                    else {
                        "epoca": atual["max_epoca"],
                        "registro_sha256": atual["registro_sha256"],
                    }
                ),
                "preparada não sucede a maior época",
            )
        else:
            exigir(
                atual["estado"] == "preparada"
                and registro["epoca"] == atual["max_epoca"]
                and registro["transicao"] == atual["transicao"]
                and registro["watermark_sha256"] == atual["watermark_sha256"]
                and registro["anterior"]
                == {
                    "epoca": atual["max_epoca"],
                    "registro_sha256": atual["registro_sha256"],
                },
                "ativa não sucede sua preparação",
            )
        revisao = self.fonte.verificar_assinatura(assinado)
        nome = nome_tag(registro["coorte"], registro["epoca"], fase)
        try:
            self.fonte.criar(nome, assinado, revisao)
        except ErroTestemunho:
            confirmado = self.consultar(registro["coorte"])
            exigir(
                confirmado == desejado, "escrita incerta não confirmou o mesmo conteúdo"
            )
        referencias = self.fonte.listar(registro["coorte"])
        exigir(nome in referencias, "tag criada não apareceu no remoto")
        confirmado, fonte = self.fonte.ler(referencias[nome])
        exigir(
            canonico(confirmado) == canonico(assinado),
            "tag concorrente possui outro conteúdo",
        )
        self.fonte.verificar_assinatura(confirmado, fonte)
        self.fonte.cas_ponteiro(registro["coorte"], nome, referencias[nome])
        final = self.consultar(registro["coorte"])
        exigir(final == desejado, "confirmação final encontrou época diferente")
        return final

    def preparar(self, registro_assinado: dict, esperado: dict) -> dict:
        return self._publicar(registro_assinado, esperado, "preparada")

    def ativar(self, registro_assinado: dict, esperado: dict, prova_pg: dict) -> dict:
        registro = validar_assinado(registro_assinado)
        exigir(
            isinstance(prova_pg, dict)
            and self.verificar_prova_pg(prova_pg) is True
            and prova_pg.get("coorte") == registro["coorte"]
            and prova_pg.get("epoca") == registro["epoca"]
            and prova_pg.get("transicao") == registro["transicao"]
            and prova_pg.get("pausada") is True
            and prova_pg.get("concessoes_invalidas") is True
            and prova_pg.get("watermark_sha256") == registro["watermark_sha256"]
            and prova_pg.get("autoridade_sha256") == registro["autoridade_sha256"],
            "prova PG autenticada e pausada não corresponde à ativação",
        )
        return self._publicar(registro_assinado, esperado, "ativa")

    def referencia_confirmada(self, coorte: str, esperado: dict) -> str:
        atual = self.consultar(coorte)
        exigir(
            atual == esperado and atual["estado"] in {"preparada", "ativa"},
            "tag aprovada não corresponde ao remoto",
        )
        nome = nome_tag(coorte, atual["max_epoca"], atual["estado"])
        referencias = self.fonte.listar(coorte)
        exigir(
            nome in referencias and bool(OID.fullmatch(referencias[nome])),
            "OID da tag ausente",
        )
        return referencias[nome]


CAMPOS_RESPOSTA_PG = {
    "coorte",
    "epoca_atual",
    "epoca",
    "transicao",
    "pausada",
    "concessoes_invalidas",
    "watermark_sha256",
    "autoridade_sha256",
    "fase",
    "nonce",
}


def registro_da_consulta_pg(
    resposta: dict, esperado: dict, coorte: str, transicao: str, fase: str, nonce: str
) -> dict:
    exigir(
        isinstance(resposta, dict) and set(resposta) == CAMPOS_RESPOSTA_PG,
        "resposta PG incompleta ou inesperada",
    )
    dados = resposta
    exigir(
        isinstance(nonce, str)
        and re.fullmatch(r"[0-9a-f]{32}", nonce) is not None
        and dados["nonce"] == nonce
        and dados["coorte"] == coorte
        and dados["transicao"] == transicao
        and dados["fase"] == fase
        and dados["pausada"] is True
        and dados["concessoes_invalidas"] is True,
        "consulta PG não vincula nonce, contexto e pausa",
    )
    exigir(
        type(dados["epoca_atual"]) is int
        and dados["epoca_atual"] >= 0
        and type(dados["epoca"]) is int
        and dados["epoca"] > 0
        and isinstance(dados["watermark_sha256"], str)
        and bool(SHA.fullmatch(dados["watermark_sha256"]))
        and isinstance(dados["autoridade_sha256"], str)
        and bool(SHA.fullmatch(dados["autoridade_sha256"])),
        "época ou digest PG inválido",
    )
    if fase == "preparada":
        exigir(
            esperado["estado"] in {"vazia", "ativa"}
            and dados["epoca_atual"] == esperado["max_epoca"]
            and dados["epoca"] == esperado["max_epoca"] + 1,
            "preparação PG diverge da maior época externa",
        )
    else:
        exigir(
            fase == "ativa"
            and esperado["estado"] == "preparada"
            and esperado["transicao"] == transicao
            and esperado["watermark_sha256"] == dados["watermark_sha256"]
            and dados["epoca_atual"] == esperado["max_epoca"]
            and dados["epoca"] == esperado["max_epoca"],
            "ativação PG diverge da preparação externa",
        )
    anterior = (
        None
        if esperado["max_epoca"] == 0
        else {
            "epoca": esperado["max_epoca"],
            "registro_sha256": esperado["registro_sha256"],
        }
    )
    registro = {
        "versao": 1,
        "coorte": coorte,
        "epoca": dados["epoca"],
        "transicao": transicao,
        "estado": fase,
        "anterior": anterior,
        "watermark_sha256": dados["watermark_sha256"],
        "autoridade_sha256": dados["autoridade_sha256"],
    }
    validar_registro(registro)
    return registro


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os
    import secrets

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operacao", choices=("preparar-consulta", "construir-registro"))
    args = parser.parse_args(argv)
    try:
        coorte = os.environ["COORTE"]
        transicao = os.environ["TRANSICAO"]
        fase = os.environ["FASE"]
        exigir(bool(COORTE.fullmatch(coorte)), "coorte inválida")
        exigir(bool(TRANSICAO.fullmatch(transicao)), "transição inválida")
        exigir(fase in {"preparada", "ativa"}, "fase inválida")
        pasta = Path(os.environ["RUNNER_TEMP"])
        if args.operacao == "preparar-consulta":
            nonce = secrets.token_hex(16)
            with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as saida:
                saida.write(f"nonce={nonce}\n")
        else:
            nonce = os.environ["NONCE"]
            resposta = json.loads(os.environ["SAIDA_PG"])
            esperado = TestemunhoEpoca(Path.cwd(), None).consultar(coorte)
            registro = registro_da_consulta_pg(
                resposta, esperado, coorte, transicao, fase, nonce
            )
            (pasta / "registro.json").write_bytes(canonico(registro))
        return 0
    except (ErroTestemunho, OSError, KeyError, ValueError, TypeError) as erro:
        print(
            f"ERROR: consulta de época não concluída: {erro}. "
            "Mantenha a coorte pausada; confira o receptor, a proteção e a origem."
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
