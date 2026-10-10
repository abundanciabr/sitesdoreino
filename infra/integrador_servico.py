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
from diagnostico_entregas import criar_diagnostico, classificar_erro, diagnostico_publico
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


def identidade_processo():
    """Identidade Linux que muda ao reciclar PID; nada de cmdline ou ambiente."""
    if sys.platform != "linux":
        return None
    try:
        texto = Path("/proc/self/stat").read_text(encoding="ascii")
        campos = texto[texto.rfind(")") + 1:].split()
        inicio = int(campos[19])  # starttime: campo 22, após pid e comm
        return {"pid": os.getpid(), "inicio": inicio} if inicio > 0 else None
    except (OSError, ValueError, IndexError):
        return None


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
        estado = json.loads(arquivo.read_text(encoding="utf-8"))
        if not isinstance(estado, dict) or estado.get("id") != id_:
            raise ValueError("registro ilegivel")
        return estado

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

    def salvar_canal(self, estado):
        """Estado da rodada, separado dos registros de entregas."""
        arquivo = self.pasta / "canal.json"
        fd, nome = tempfile.mkstemp(prefix=".canal-", dir=self.pasta)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as aberto:
                json.dump(estado, aberto, ensure_ascii=False, sort_keys=True)
                aberto.flush()
                os.fsync(aberto.fileno())
            os.replace(nome, arquivo)
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
        atual = {"id": id_, "candidata": cand, "fase": "recebida", "tentativas": 0,
                 "em_andamento": False, "progresso_em": None, "tentativa_em": None}
        self.estados.salvar(atual)
        return atual

    def _fase(self, estado, fase, motivo=None, *, diagnostico=None, progresso=False, **dados):
        estado.update(dados)
        estado["fase"] = fase
        if diagnostico:
            publico = diagnostico_publico(diagnostico)
            estado["diagnostico"] = publico
            codigo = publico["codigo"] if publico else None
            if codigo != "tentativas_esgotadas" or not estado.get("ultima_falha"):
                estado["ultima_falha"] = publico
            estado["motivo"] = publico["motivo"] if publico else None
            anterior = estado.get("falha_repetida")
            quantidade = estado.get("falhas_consecutivas")
            quantidade = quantidade if isinstance(quantidade, int) and 0 <= quantidade <= 1000000 else 0
            estado["falhas_consecutivas"] = quantidade + 1 if anterior == codigo else 1
            estado["falha_repetida"] = codigo
            if (estado["falhas_consecutivas"] > 1
                    and codigo not in ("resposta_perdida", "dependencia_pendente")):
                espera = min(300, 30 * 2 ** min(4, estado["falhas_consecutivas"] - 2))
                estado["proxima_tentativa_em"] = (
                    datetime.datetime.now(datetime.timezone.utc)
                    + datetime.timedelta(seconds=espera)).isoformat(timespec="seconds")
            else:
                estado.pop("proxima_tentativa_em", None)
        else:
            estado["motivo"] = motivo
            estado["diagnostico"] = None
            estado.pop("proxima_tentativa_em", None)
            if progresso:
                estado["falhas_consecutivas"] = 0
                estado["falha_repetida"] = None
        if progresso:
            estado["progresso_em"] = agora()
        self.estados.salvar(estado)

    def _falha(self, estado, fase, erro, etapa, celula=None, **dados):
        diagnostico = (getattr(erro, "diagnostico", None)
                       or classificar_erro(erro, etapa=etapa, celula=celula))
        self._fase(estado, fase, diagnostico=diagnostico, **dados)
        return {"id": estado["id"], "fase": fase, "motivo": estado.get("motivo"),
                "diagnostico": estado.get("diagnostico")}

    def _tentativa(self, estado):
        estado["tentativas"] = estado.get("tentativas", 0) + 1
        estado["tentativa_em"] = agora()
        self.estados.salvar(estado)

    def _inicio_tentativa(self, estado):
        estado["tentativa_em"] = agora()
        self.estados.salvar(estado)

    @staticmethod
    def _espera_vigente(estado):
        limite = estado.get("proxima_tentativa_em")
        if not limite:
            return False
        try:
            return datetime.datetime.fromisoformat(limite) > datetime.datetime.now(datetime.timezone.utc)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _ausencia_esperada(erro):
        diagnostico = diagnostico_publico(getattr(erro, "diagnostico", None))
        if diagnostico is not None:
            return diagnostico["codigo"] in {"prova_ausente", "resultado_ensaio_ausente"}
        # Compatibilidade com as pontes falsas antigas; frases ambíguas como
        # "prova ausente ou divergente" nunca disparam novo ensaio.
        texto = str(erro).casefold()
        return ((texto in ("prova ausente", "candidata sem prova isolada")
                 and getattr(erro, "categoria", None) == "recusa")
                or (texto in ("resultado ausente", "resultado do ensaio ausente")
                    and getattr(erro, "categoria", None) == "infra"))

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
        bloqueadas = []
        registro_ilegivel = False
        for dep in reg.get("depende_de") or []:
            try:
                fase = self.estados.ler(dep)
            except (OSError, ValueError, TypeError):
                bloqueadas.append(dep)
                registro_ilegivel = True
                continue
            if not fase:
                bloqueadas.append(dep)
                continue
            if fase.get("fase") == "ativa":
                continue
            provas = fase.get("preservacao") or {}
            celulas = fase.get("celulas") or []
            if (fase.get("fase") != "preservada em versão posterior" or not celulas
                    or set(provas) != set(celulas)
                    or any(not isinstance(provas[c], dict)
                           or not SHA.fullmatch((provas[c].get("sha_aprovada") or ""))
                           or not re.fullmatch(r"[0-9a-f]{64}", provas[c].get("prova_identidade") or "")
                           for c in celulas)):
                bloqueadas.append(dep)
        return bloqueadas, registro_ilegivel

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
            diagnostico = criar_diagnostico("preservacao_nao_comprovada", etapa="preservacao")
            self._fase(estado, "preservação não comprovada", diagnostico=diagnostico, preservacao={})
            return {"id": reg["id"], "fase": estado["fase"], "motivo": estado["motivo"]}
        if "aguardando" in situacoes:
            diagnostico = criar_diagnostico("versao_posterior_pendente", etapa="preservacao")
            self._fase(estado, "aguardando versão posterior", diagnostico=diagnostico, preservacao={})
            return {"id": reg["id"], "fase": estado["fase"], "motivo": estado["motivo"]}
        provas = {celula: {"sha_aprovada": r["sha_aprovada"],
                           "prova_identidade": r["prova_identidade"],
                           "arquivos_conferidos": r["arquivos_conferidos"]}
                  for celula, r in consultas.items()}
        fase = ("ativa" if all(r["sha_aprovada"] == cand for r in consultas.values())
                else "preservada em versão posterior")
        self._fase(estado, fase, progresso=True, preservacao=provas)
        return {"id": reg["id"], "fase": fase,
                "versoes_aprovadas": {c: p["sha_aprovada"] for c, p in provas.items()}}

    def processar(self, reg):
        id_ = reg["id"]
        promocao = reg.get("promocao") or {}
        if reg.get("estado") not in ("pronta", entregas.NA_MAIN) and promocao.get("estado") != "intencao":
            return None
        estado = None
        etapa = "integracao"
        celula_atual = None
        try:
            if reg.get("estado") == entregas.NA_MAIN and not self.estados.ler(id_):
                return None  # nao assume entregas historicas como ativacoes suas
            anterior = self.estados.ler(id_)
            cand_reg = ((reg.get("promocao") or {}).get("candidata")
                        or reg.get("promovida_candidata") or reg.get("candidata"))
            if anterior and anterior.get("candidata") == cand_reg and anterior.get("fase") in FINAL:
                return {"id": id_, "fase": anterior["fase"]}
            estado = self._estado(reg)
            if estado["fase"] in FINAL:
                return {"id": id_, "fase": estado["fase"]}
            if self._espera_vigente(estado):
                return {"id": id_, "fase": estado["fase"], "motivo": estado.get("motivo")}
            etapa = "dependencia"
            bloqueadas, registro_ilegivel = self._dependencias_ativas(reg)
            if bloqueadas:
                codigo = "registro_ilegivel" if registro_ilegivel else "dependencia_pendente"
                diagnostico = criar_diagnostico(codigo, etapa="dependencia")
                self._fase(estado, "aguardando dependência", diagnostico=diagnostico,
                           dependencias_pendentes=bloqueadas)
                return {"id": id_, "fase": "aguardando dependência"}
            if estado.pop("dependencias_pendentes", None):
                self.estados.salvar(estado)
            estado["em_andamento"] = True
            identidade = identidade_processo()
            if identidade is not None:
                estado["execucao_processo"] = identidade
            else:
                estado.pop("execucao_processo", None)
            self.estados.salvar(estado)
            cand = estado["candidata"]
            etapa = "integracao"
            celulas = self._celulas(reg, estado)
            if reg.get("estado") == entregas.NA_MAIN:
                etapa = "preservacao"
                conciliada = self._conciliar_promovida(reg, estado, celulas)
                if conciliada is not None:
                    return conciliada
            etapa = "espelhamento"
            self.ponte.espelhar(id_, cand)
            if reg.get("estado") != entregas.NA_MAIN:
                comprovadas = estado.setdefault("comprovadas", {})
                tentativas = estado.setdefault("tentativas_celula", {})
                for celula in celulas:
                    celula_atual = celula
                    if celula in comprovadas:
                        etapa = "prova"
                        prova = self.ponte.verificar_prova(id_, cand, celula)
                        if prova["identidade"] != comprovadas[celula]:
                            raise ErroPonte("prova da candidata mudou", "recusa")
                        continue
                    # Consulta antes de executar cobre perda de resposta do ensaio/registro.
                    try:
                        etapa = "prova"
                        prova = self.ponte.verificar_prova(id_, cand, celula)
                    except ErroPonte as erro:
                        if not self._ausencia_esperada(erro):
                            raise
                        try:
                            etapa = "prova"
                            self.ponte.registrar(id_, cand, celula)
                            prova = self.ponte.verificar_prova(id_, cand, celula)
                        except ErroPonte as erro:
                            if not self._ausencia_esperada(erro):
                                raise
                            if tentativas.get(celula, 0) >= TENTATIVAS:
                                diagnostico = criar_diagnostico(
                                    "tentativas_esgotadas", etapa="ensaio", celula=celula)
                                self._fase(estado, "falha no ensaio", diagnostico=diagnostico)
                                return {"id": id_, "fase": estado["fase"],
                                        "motivo": estado["motivo"]}
                            etapa = "preparacao"
                            self._fase(estado, "ensaiando")
                            self._inicio_tentativa(estado)
                            try:
                                self.ponte.preparar(id_, cand, celula)
                            except ErroPonte as erro:
                                if erro.categoria == "ensaio":
                                    self._tentativa(estado)
                                    tentativas[celula] = tentativas.get(celula, 0) + 1
                                    self.estados.salvar(estado)
                                raise
                            self._tentativa(estado)
                            tentativas[celula] = tentativas.get(celula, 0) + 1
                            self.estados.salvar(estado)
                            etapa = "prova"
                            self.ponte.registrar(id_, cand, celula)
                            prova = self.ponte.verificar_prova(id_, cand, celula)
                    comprovadas[celula] = prova["identidade"]
                    self._fase(estado, "ensaio aprovado", progresso=True)
                celula_atual = None
                self._fase(estado, "promoção pendente")
                # Registra intencao antes do push e reconcilia resposta remota perdida.
                etapa = "promocao"
                self._tentativa(estado)
                self.integrador.cmd_promover(SimpleNamespace(id=id_, remoto=self.remoto_promocao))
                reg = self.integrador.ler(id_)
                if reg.get("estado") != entregas.NA_MAIN:
                    raise ErroPonte("promoção remota ainda não confirmada")
                self._fase(estado, "promoção pendente", progresso=True)
                etapa = "preservacao"
                conciliada = self._conciliar_promovida(reg, estado, celulas)
                if conciliada is not None:
                    return conciliada
            etapa = "espelhamento"
            self.ponte.espelhar(id_, cand)
            ativadas = estado.setdefault("ativadas", [])
            self._fase(estado, "ativação pendente")
            for celula in celulas:  # aplicacao antes de funil; nunca declara parcial como ativa
                if celula not in ativadas:
                    celula_atual = celula
                    etapa = "ativacao"
                    self._tentativa(estado)
                    self.ponte.publicar(id_, cand, celula)
                    ativadas.append(celula)
                    self._fase(estado, "ativação pendente", progresso=True)
            self._fase(estado, "ativa", progresso=True)
            return {"id": id_, "fase": "ativa"}
        except ErroPonte as erro:
            if estado is None:
                diagnostico = classificar_erro(erro, etapa=etapa, celula=celula_atual)
                return {"id": id_, "fase": "infraestrutura indisponível",
                        "motivo": diagnostico["motivo"], "diagnostico": diagnostico}
            if estado["fase"] in ("ativa", "preservada em versão posterior"):
                return self._falha(estado, "conciliação pendente", erro, etapa, celula_atual,
                                   preservacao={})
            elif erro.categoria == "ensaio" and estado["fase"] == "ensaiando":
                return self._falha(estado, "falha no ensaio", erro, etapa, celula_atual)
            return self._falha(estado, estado["fase"], erro, etapa, celula_atual)
        except (entregas.Recusa, OSError, ValueError, KeyError) as erro:
            if estado is None:
                diagnostico = classificar_erro(erro, etapa=etapa, celula=celula_atual)
                return {"id": id_, "fase": "precisa de correção",
                        "motivo": diagnostico["motivo"], "diagnostico": diagnostico}
            fase = ("precisa de correção" if isinstance(erro, ValueError)
                    and not isinstance(erro, json.JSONDecodeError) else
                    "conciliação pendente" if estado["fase"] in ("ativa", "preservada em versão posterior")
                    else estado["fase"])
            return self._falha(estado, fase, erro, etapa, celula_atual,
                               **({"preservacao": {}} if fase == "conciliação pendente" else {}))
        finally:
            if estado is not None and estado.get("em_andamento"):
                estado["em_andamento"] = False
                estado.pop("execucao_processo", None)
                self.estados.salvar(estado)

    def _sincronizar_main(self):
        self.integrador.git("fetch", "--no-tags", self.remoto_leitura,
                            "main:refs/heads/main", check=True)

    def _canal(self, estado, diagnostico=None):
        self.estados.salvar_canal({"estado": estado, "em": agora(), "execucao": os.getpid(),
                                   "diagnostico": diagnostico_publico(diagnostico)})

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
            self._canal("em andamento")
            try:
                self._sincronizar_main()
                self.integrador.cmd_integrar(SimpleNamespace())
                registros = self.integrador.todos()
            except (entregas.Recusa, OSError) as erro:
                diagnostico = criar_diagnostico("main_indisponivel", etapa="integracao")
                self._canal("infraestrutura indisponível", diagnostico)
                return [{"fase": "infraestrutura indisponível", "motivo": diagnostico["motivo"],
                         "diagnostico": diagnostico}]
            for original in self._ordem_dependencias(registros):
                id_ = original["id"]
                try:
                    reg = self.integrador.ler(id_)
                except (entregas.Recusa, OSError, ValueError, KeyError):
                    diagnostico = criar_diagnostico("registro_ilegivel", etapa="recebimento")
                    resultados.append({"id": id_, "fase": "registro ilegível",
                                       "motivo": diagnostico["motivo"], "diagnostico": diagnostico})
                    continue
                if reg is None:
                    diagnostico = criar_diagnostico("registro_indisponivel", etapa="recebimento")
                    resultados.append({"id": id_, "fase": "registro indisponível",
                                       "motivo": diagnostico["motivo"], "diagnostico": diagnostico})
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
                            self._canal("infraestrutura indisponível",
                                        criar_diagnostico("main_indisponivel", etapa="integracao"))
                            break
            else:
                self._canal("rodada concluída")
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

