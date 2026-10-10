#!/usr/bin/env python3
"""Worker recuperavel das entregas. A autoridade de producao fica na ponte."""
from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from types import SimpleNamespace

import entregas
from ponte_entregas import ClientePonte, ErroPonte

try:
    import fcntl
except ImportError:
    fcntl = None
    import msvcrt

ID = re.compile(r"[0-9a-f]{12}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
FINAL = {"ativa", "preservada em versão posterior", "falha no ensaio",
         "precisa de correção", "incompatibilidade"}
TENTATIVAS = 3


def agora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class Estados:
    def __init__(self, pasta: Path):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)

    def ler(self, id_):
        if not ID.fullmatch(id_):
            raise ValueError("id invalido")
        arquivo = self.pasta / (id_ + ".json")
        if not arquivo.exists():
            return None
        return json.loads(arquivo.read_text(encoding="utf-8"))

    def salvar(self, estado):
        id_ = estado["id"]
        if not ID.fullmatch(id_):
            raise ValueError("id invalido")
        estado["atualizada_em"] = agora()
        fd, nome = tempfile.mkstemp(prefix=".tmp-", dir=self.pasta)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as aberto:
                json.dump(estado, aberto, ensure_ascii=False, sort_keys=True)
                aberto.flush()
                os.fsync(aberto.fileno())
            os.replace(nome, self.pasta / (id_ + ".json"))
            if os.name == "posix":
                dfd = os.open(self.pasta, os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(nome)

    @contextlib.contextmanager
    def exclusao(self):
        with (self.pasta / ".worker.lock").open("a+b") as aberto:
            if fcntl:
                fcntl.flock(aberto, fcntl.LOCK_EX)
            else:
                aberto.seek(0)
                msvcrt.locking(aberto.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                if fcntl:
                    fcntl.flock(aberto, fcntl.LOCK_UN)
                else:
                    aberto.seek(0)
                    msvcrt.locking(aberto.fileno(), msvcrt.LK_UNLCK, 1)


class Servico:
    def __init__(self, integrador=entregas, ponte=None, estados=None, remoto=None):
        self.integrador = integrador
        self.ponte = ponte or ClientePonte()
        self.estados = estados or Estados(integrador.pasta() / "fases")
        self.remoto_leitura = os.environ.get("ENTREGAS_REMOTO_LEITURA", "origin")
        self.remoto_promocao = remoto or os.environ.get("ENTREGAS_REMOTO_PROMOCAO", "integrador")

    def _estado(self, reg):
        id_ = reg["id"]
        cand = (reg.get("promocao") or {}).get("candidata") or reg.get("promovida_candidata") or reg.get("candidata")
        anterior = self.estados.ler(id_)
        if anterior and anterior.get("candidata") == cand:
            return anterior
        if not cand or not SHA.fullmatch(cand):
            raise ValueError("candidata ausente")
        atual = {"id": id_, "candidata": cand, "fase": "recebida", "tentativas": 0}
        self.estados.salvar(atual)
        return atual

    def _fase(self, estado, fase, motivo=None, **dados):
        estado.update(dados)
        estado["fase"] = fase
        estado["motivo"] = motivo
        self.estados.salvar(estado)

    def _celulas(self, reg, estado):
        if estado.get("celulas"):
            return estado["celulas"]
        base = (reg.get("promocao") or {}).get("main_esperada") or reg.get("base_da_candidata")
        cand = estado["candidata"]
        if not SHA.fullmatch(base or ""):
            raise ValueError("base da candidata ausente")
        diff = self.integrador.git("diff", "--name-only", base, cand, check=True)
        caminhos = diff.stdout.splitlines()
        if not caminhos:
            raise ValueError("candidata sem alteracoes")
        celulas = []
        if any(not p.startswith("services/funil/") for p in caminhos):
            celulas.append("aplicacao")
        if any(p.startswith("services/funil/") for p in caminhos):
            celulas.append("funil")
        estado["celulas"] = celulas
        self.estados.salvar(estado)
        return celulas

    def _dependencias_ativas(self, reg):
        for dep in reg.get("depende_de") or []:
            fase = self.estados.ler(dep)
            if not fase:
                return False
            if fase.get("fase") == "ativa":
                continue
            provas = fase.get("preservacao") or {}
            celulas = fase.get("celulas") or []
            if (fase.get("fase") != "preservada em versão posterior" or not celulas
                    or set(provas) != set(celulas)
                    or any(not SHA.fullmatch((provas[c].get("sha_aprovada") or ""))
                           or not re.fullmatch(r"[0-9a-f]{64}", provas[c].get("prova_identidade") or "")
                           for c in celulas)):
                return False
        return True

    def _conciliar_promovida(self, reg, estado, celulas):
        """Nunca tenta publicar uma candidata que ja saiu da main remota."""
        cand = estado["candidata"]
        consultas = {celula: self.ponte.conferir_preservacao(reg["id"], cand, celula)
                     for celula in celulas}
        situacoes = {r["situacao"] for r in consultas.values()}
        if situacoes == {"publicavel"}:
            if estado["fase"] == "ativa":
                return {"id": reg["id"], "fase": "ativa"}
            return None
        if "publicavel" in situacoes or not situacoes <= {"preservada", "aguardando", "conflito"}:
            raise ErroPonte("conferencia da promocao inconsistente", "recusa")
        if "conflito" in situacoes:
            motivo = next(r.get("motivo") for r in consultas.values() if r["situacao"] == "conflito")
            self._fase(estado, "preservação não comprovada", motivo, preservacao={})
            return {"id": reg["id"], "fase": estado["fase"], "motivo": motivo}
        if "aguardando" in situacoes:
            motivo = next(r.get("motivo") for r in consultas.values() if r["situacao"] == "aguardando")
            self._fase(estado, "aguardando versão posterior", motivo, preservacao={})
            return {"id": reg["id"], "fase": estado["fase"], "motivo": motivo}
        provas = {celula: {"sha_aprovada": r["sha_aprovada"],
                           "prova_identidade": r["prova_identidade"],
                           "arquivos_conferidos": r["arquivos_conferidos"]}
                  for celula, r in consultas.items()}
        fase = ("ativa" if all(r["sha_aprovada"] == cand for r in consultas.values())
                else "preservada em versão posterior")
        self._fase(estado, fase, preservacao=provas)
        return {"id": reg["id"], "fase": fase,
                "versoes_aprovadas": {c: p["sha_aprovada"] for c, p in provas.items()}}

    def processar(self, reg):
        id_ = reg["id"]
        promocao = reg.get("promocao") or {}
        if reg.get("estado") not in ("pronta", entregas.NA_MAIN) and promocao.get("estado") != "intencao":
            return None
        if reg.get("estado") == entregas.NA_MAIN and not self.estados.ler(id_):
            return None  # nao assume entregas historicas como ativacoes suas
        anterior = self.estados.ler(id_)
        cand_reg = ((reg.get("promocao") or {}).get("candidata")
                    or reg.get("promovida_candidata") or reg.get("candidata"))
        if anterior and anterior.get("candidata") == cand_reg and anterior.get("fase") in FINAL:
            return {"id": id_, "fase": anterior["fase"]}
        if not self._dependencias_ativas(reg):
            return {"id": id_, "fase": "aguardando dependência"}
        try:
            estado = self._estado(reg)
            if estado["fase"] in FINAL:
                return {"id": id_, "fase": estado["fase"]}
            cand = estado["candidata"]
            celulas = self._celulas(reg, estado)
            if reg.get("estado") == entregas.NA_MAIN:
                conciliada = self._conciliar_promovida(reg, estado, celulas)
                if conciliada is not None:
                    return conciliada
            self.ponte.espelhar(id_, cand)
            if reg.get("estado") != entregas.NA_MAIN:
                comprovadas = estado.setdefault("comprovadas", {})
                tentativas = estado.setdefault("tentativas_celula", {})
                for celula in celulas:
                    if celula in comprovadas:
                        prova = self.ponte.verificar_prova(id_, cand, celula)
                        if prova["identidade"] != comprovadas[celula]:
                            raise ErroPonte("prova da candidata mudou", "recusa")
                        continue
                    # Consulta antes de executar cobre perda de resposta do ensaio/registro.
                    try:
                        prova = self.ponte.verificar_prova(id_, cand, celula)
                    except ErroPonte:
                        try:
                            self.ponte.registrar(id_, cand, celula)
                            prova = self.ponte.verificar_prova(id_, cand, celula)
                        except ErroPonte:
                            tentativas[celula] = tentativas.get(celula, 0) + 1
                            if tentativas[celula] > TENTATIVAS:
                                self._fase(estado, "falha no ensaio", "tentativas esgotadas")
                                return {"id": id_, "fase": estado["fase"]}
                            self._fase(estado, "ensaiando")
                            self.ponte.preparar(id_, cand, celula)
                            self.ponte.registrar(id_, cand, celula)
                            prova = self.ponte.verificar_prova(id_, cand, celula)
                    comprovadas[celula] = prova["identidade"]
                    self._fase(estado, "ensaio aprovado")
                self._fase(estado, "promoção pendente")
                # Registra intencao antes do push e reconcilia resposta remota perdida.
                self.integrador.cmd_promover(SimpleNamespace(id=id_, remoto=self.remoto_promocao))
                reg = self.integrador.ler(id_)
                if reg.get("estado") != entregas.NA_MAIN:
                    raise ErroPonte("promoção remota ainda não confirmada")
                conciliada = self._conciliar_promovida(reg, estado, celulas)
                if conciliada is not None:
                    return conciliada
            self.ponte.espelhar(id_, cand)
            ativadas = estado.setdefault("ativadas", [])
            self._fase(estado, "ativação pendente")
            for celula in celulas:  # aplicacao antes de funil; nunca declara parcial como ativa
                if celula not in ativadas:
                    self.ponte.publicar(id_, cand, celula)
                    ativadas.append(celula)
                    self._fase(estado, "ativação pendente")
            self._fase(estado, "ativa")
            return {"id": id_, "fase": "ativa"}
        except ErroPonte as erro:
            if "estado" not in locals():
                return {"id": id_, "fase": "infraestrutura indisponível", "motivo": str(erro)[:180]}
            if estado["fase"] in ("ativa", "preservada em versão posterior"):
                self._fase(estado, "conciliação pendente", str(erro)[:180], preservacao={})
            elif erro.categoria == "ensaio" and estado["fase"] == "ensaiando":
                self._fase(estado, "falha no ensaio", str(erro)[:180])
            elif estado["fase"] != "ativação pendente":
                self._fase(estado, estado["fase"], str(erro)[:180])
            return {"id": id_, "fase": estado["fase"], "motivo": str(erro)[:180]}
        except (entregas.Recusa, OSError, ValueError, KeyError) as erro:
            if "estado" not in locals():
                return {"id": id_, "fase": "precisa de correção", "motivo": str(erro)[:180]}
            fase = ("precisa de correção" if isinstance(erro, ValueError) else
                    "conciliação pendente" if estado["fase"] in ("ativa", "preservada em versão posterior")
                    else estado["fase"])
            self._fase(estado, fase, str(erro)[:180],
                       **({"preservacao": {}} if fase == "conciliação pendente" else {}))
            return {"id": id_, "fase": estado["fase"], "motivo": estado.get("motivo")}

    def _sincronizar_main(self):
        self.integrador.git("fetch", "--no-tags", self.remoto_leitura,
                            "main:refs/heads/main", check=True)

    @staticmethod
    def _ordem_dependencias(registros):
        """Reconfere cada dependencia antes de processar quem depende dela."""
        pendentes = {reg["id"]: reg for reg in registros}
        ordem = []
        while pendentes:
            prontos = [id_ for id_, reg in pendentes.items()
                       if not any(dep in pendentes for dep in reg.get("depende_de") or [])]
            if not prontos:
                ordem.extend(pendentes.values())  # ciclo continua aguardando dependencia
                break
            for id_ in prontos:
                ordem.append(pendentes.pop(id_))
        return ordem

    def rodada(self):
        resultados = []
        with self.estados.exclusao():
            try:
                self._sincronizar_main()
                self.integrador.cmd_integrar(SimpleNamespace())
            except (entregas.Recusa, OSError) as erro:
                return [{"fase": "infraestrutura indisponível",
                         "motivo": "main remota indisponível; nenhuma candidata promovida"}]
            for original in self._ordem_dependencias(self.integrador.todos()):
                reg = self.integrador.ler(original["id"])
                if reg is None:
                    continue
                resultado = self.processar(reg)
                if resultado:
                    resultados.append(resultado)
                    if resultado["fase"] == "ativa":
                        # Promocao muda a base das proximas candidatas.
                        try:
                            self._sincronizar_main()
                            self.integrador.cmd_integrar(SimpleNamespace())
                        except (entregas.Recusa, OSError):
                            # Proxima rodada retomara a sincronizacao; entregas anteriores ficam registradas.
                            break
        return resultados


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("acao", choices=("uma-vez", "continuo", "consultar"))
    parser.add_argument("id", nargs="?")
    parser.add_argument("--intervalo", type=int, default=30)
    args = parser.parse_args(argv)
    servico = Servico()
    if args.acao == "consultar":
        if args.id:
            saida = servico.estados.ler(args.id)
        else:
            saida = [servico.estados.ler(p.stem) for p in sorted(servico.estados.pasta.glob("[0-9a-f]*.json"))]
        print(json.dumps(saida, ensure_ascii=False))
        return 0
    while True:
        print(json.dumps(servico.rodada(), ensure_ascii=False), flush=True)
        if args.acao == "uma-vez":
            return 0
        time.sleep(max(5, args.intervalo))


if __name__ == "__main__":
    sys.exit(main())

