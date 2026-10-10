"""Vocabulário público do canal. Texto de exceção nunca atravessa a fronteira."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import re
import tempfile

ETAPAS = frozenset(("recebimento", "integracao", "dependencia", "espelhamento",
    "preparacao", "ensaio", "prova", "promocao", "preservacao", "ativacao",
    "recuperacao", "verificacao", "publicador", "backup", "imagem", "mercadopago"))
# categoria, causa pública, próxima ação. Nunca interpolar saídas de processos.
CATALOGO = {
    "autoridade_indisponivel": ("infra", "O canal do publicador está indisponível.", "Aguardar a retomada do canal; a entrega permanece registrada."),
    "resposta_perdida": ("infra", "A confirmação da operação não chegou; o resultado é desconhecido.", "Consultar a mesma entrega; a retomada confere o resultado antes de repetir."),
    "registro_indisponivel": ("infra", "O registro necessário ainda não está disponível.", "Aguardar a próxima consulta; ausência de registro não confirma ativação."),
    "registro_ilegivel": ("infra", "O registro da operação está incompleto ou ilegível.", "O mantenedor deve conferir o registro preservado; não reenviar como nova entrega."),
    "espelho_identidade_divergente": ("recusa", "O espelho contém outra identidade para esta entrega.", "Conferir ramo, commit, base e origem no registro preservado."),
    "espelho_candidata_divergente": ("recusa", "A candidata pedida não corresponde ao registro atual da entrega.", "Consultar a mesma entrega e retomar sua candidata atual."),
    "espelho_promocao_protegida": ("recusa", "O espelho contém uma intenção ou promoção que não pode ser substituída.", "Conferir a promoção da mesma entrega antes de retomar o espelho."),
    "prova_ausente": ("espera", "A prova isolada desta candidata ainda não existe.", "Conferir o resultado do ensaio antes de iniciar a primeira preparação."),
    "resultado_ensaio_ausente": ("espera", "O resultado do ensaio desta candidata ainda não existe.", "Preparar o ensaio desta candidata pelo fluxo existente."),
    "main_indisponivel": ("infra", "Não foi possível conferir a main remota.", "Aguardar a reconciliação da mesma entrega quando o remoto voltar."),
    "dependencia_pendente": ("espera", "Uma dependência ainda não tem ativação comprovada.", "Acompanhar as dependências indicadas; a retomada é automática."),
    "ensaio_reprovado": ("ensaio", "O ensaio da candidata não foi aprovado.", "Corrigir a contribuição indicada e enviar a revisão."),
    "ensaio_indisponivel": ("infra", "A infraestrutura do ensaio está indisponível.", "Aguardar a retomada; indisponibilidade não comprova reprovação da candidata."),
    "tentativas_esgotadas": ("recusa", "As tentativas de ensaio disponíveis foram usadas.", "Consultar a última falha e corrigir sua causa antes de nova revisão."),
    "ativacao_nao_confirmada": ("infra", "A ativação ainda não tem confirmação suficiente.", "Aguardar a conferência da mesma operação; integrada na main não significa no ar."),
    "falha_operacional": ("infra", "Uma etapa operacional falhou sem diagnóstico público reconhecido.", "O mantenedor deve conferir o registro privado dessa operação."),
    "mercadopago_rotas_divergentes": ("recusa", "As rotas protegidas divergem da referência do Mercado Pago no controlador.", "Conferir as referências com o mantenedor; nenhuma sincronização automática é permitida."),
    "mercadopago_destino_funil_invalido": ("recusa", "O destino do funil está fora do formato aceito pelo verificador congelado.", "Conferir a rota com o mantenedor preservando a referência aprovada."),
    "mercadopago_integridade": ("recusa", "A conferência do Mercado Pago congelado recusou a candidata ou o ambiente.", "Conferir a divergência com o mantenedor e preservar a versão aprovada."),
    "docs_protegidos": ("recusa", "A conferência dos documentos protegidos recusou o código.", "Corrigir o código preservando a publicação manual pelo administrador."),
    "prova_divergente": ("recusa", "A prova está ausente ou não corresponde à candidata e ao pacote.", "Reconferir ou repetir o ensaio da mesma candidata pelo fluxo existente."),
    "versao_real_divergente": ("recusa", "A versão em execução difere da versão aprovada no registro.", "Conferir a operação e sua recuperação antes de ativar outra versão."),
    "preservacao_nao_comprovada": ("recusa", "Uma versão posterior alterou arquivos da entrega; sua preservação não foi comprovada.", "Conferir as alterações na tarefa de origem; não reativar automaticamente a versão antiga."),
    "versao_posterior_pendente": ("espera", "A versão posterior ainda não tem aprovação comprovada.", "Aguardar sua conferência; a entrega anterior não será reativada."),
    "backup_falhou": ("infra", "O backup anterior à ativação não foi concluído.", "Corrigir o armazenamento ou o backup e retomar a mesma entrega."),
    "espaco_insuficiente": ("infra", "Não há espaço suficiente para concluir a operação.", "O mantenedor deve disponibilizar espaço; nenhum dado será apagado pelo canal."),
}


def agora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def horario(valor):
    if not isinstance(valor, str) or len(valor) > 40:
        return None
    try:
        instante = datetime.datetime.fromisoformat(valor.replace("Z", "+00:00"))
        return valor if instante.tzinfo else None
    except ValueError:
        return None


def criar_diagnostico(codigo, etapa="publicador", celula=None, em=None):
    codigo = codigo if isinstance(codigo, str) and codigo in CATALOGO else "falha_operacional"
    categoria, motivo, acao = CATALOGO[codigo]
    dado = {"codigo": codigo, "categoria": categoria, "motivo": motivo, "acao": acao,
            "etapa": etapa if isinstance(etapa, str) and etapa in ETAPAS else "publicador", "em": horario(em) or agora()}
    if celula in ("aplicacao", "funil"):
        dado["celula"] = celula
    return dado


def diagnostico_publico(dado):
    if not isinstance(dado, dict) or not isinstance(dado.get("codigo"), str) or dado["codigo"] not in CATALOGO:
        return None
    # Reconstrói os textos: nem um motivo antigo/manipulado vira saída pública.
    em = horario(dado.get("em"))
    publico = criar_diagnostico(dado["codigo"], dado.get("etapa"), dado.get("celula"), em)
    if em is None:
        publico.pop("em")  # consulta histórica não inventa quando ocorreu a falha
    return publico


def classificar_erro(erro, etapa="publicador", celula=None):
    pronto = diagnostico_publico(getattr(erro, "diagnostico", None))
    if pronto:
        return pronto
    texto = str(erro).casefold()
    tipo = type(erro).__name__
    codigo = "falha_operacional"
    if "rotas protegidas alteradas:" in texto:
        codigo = "mercadopago_rotas_divergentes"
    elif "destino funil inválido" in texto or "destino funil invalido" in texto:
        codigo = "mercadopago_destino_funil_invalido"
    elif tipo == "IntegridadeMercadoPagoErro":
        codigo = "mercadopago_integridade"
    elif etapa == "mercadopago":
        codigo = "mercadopago_integridade"
    elif tipo == "IntegridadeDocumentosErro":
        codigo = "docs_protegidos"
    elif isinstance(erro, OSError) and getattr(erro, "errno", None) == 28:
        codigo = "espaco_insuficiente"
    elif "resposta perdida" in texto or "resposta remota perdida" in texto or "resposta ausente" in texto:
        codigo = "resposta_perdida"
    elif "autoridade indisponivel" in texto:
        codigo = "autoridade_indisponivel"
    elif "registro ilegivel" in texto or isinstance(erro, json.JSONDecodeError):
        codigo = "registro_ilegivel"
    elif "identidade do espelho diverge" in texto:
        codigo = "espelho_identidade_divergente"
    elif etapa == "espelhamento" and "candidata difere do registro" in texto:
        codigo = "espelho_candidata_divergente"
    elif "registro antigo nao substitui promocao confirmada" in texto or "promocao pendente pertence a outra candidata" in texto:
        codigo = "espelho_promocao_protegida"
    elif texto in ("prova ausente", "candidata sem prova isolada"):
        codigo = "prova_ausente"
    elif texto in ("resultado ausente", "resultado do ensaio ausente"):
        codigo = "resultado_ensaio_ausente"
    elif "registro indisponivel" in texto:
        codigo = "registro_indisponivel"
    elif "main remota" in texto or "promoção remota" in texto or "promocao remota" in texto:
        codigo = "main_indisponivel"
    elif "versao posterior alterou" in texto:
        codigo = "preservacao_nao_comprovada"
    elif "posterior ainda nao aprovada" in texto or "aprovada nao esta no ar" in texto:
        codigo = "versao_posterior_pendente"
    elif "difere da aprovada" in texto or "diverge do registro" in texto or "real difere" in texto:
        codigo = "versao_real_divergente"
    elif "prova" in texto and ("diverg" in texto or "ausente" in texto or "corresponde" in texto or "mudou" in texto or "outra prova" in texto):
        codigo = "prova_divergente"
    elif "ativacao ainda nao confirmada" in texto or "ativação" in texto and "confirmada" in texto:
        codigo = "ativacao_nao_confirmada"
    elif getattr(erro, "categoria", None) == "ensaio":
        codigo = "ensaio_reprovado"
    elif etapa in ("preparacao", "ensaio") and getattr(erro, "categoria", None) == "infra":
        codigo = "ensaio_indisponivel"
    elif etapa == "backup":
        codigo = "backup_falhou"
    return criar_diagnostico(codigo, etapa, celula)


def gravar_json(arquivo, dado):
    arquivo = Path(arquivo)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=".diagnostico-", dir=arquivo.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as aberto:
            json.dump(dado, aberto, ensure_ascii=False, sort_keys=True)
            aberto.flush()
            os.fsync(aberto.fileno())
        os.replace(temporario, arquivo)
        if os.name == "posix":
            dfd = os.open(arquivo.parent, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


class RegistroPublicador:
    """Fotografia durável anterior à intenção de ativação; não altera a intenção."""
    def __init__(self, pasta, id_, candidata, celula):
        if not re.fullmatch(r"[0-9a-f]{12}", id_) or not re.fullmatch(r"[0-9a-f]{40}", candidata) or celula not in ("aplicacao", "funil"):
            raise ValueError("identidade inválida")
        self.arquivo = Path(pasta) / (id_ + "-" + celula + ".json")
        anterior = {}
        if self.arquivo.is_file() and not self.arquivo.is_symlink():
            try:
                anterior = json.loads(self.arquivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        self.dado = {"id": id_, "candidata": candidata, "celula": celula,
                     "tentativa_em": agora(), "estado": "em andamento", "etapa": "publicador"}
        if isinstance(anterior, dict) and anterior.get("candidata") == candidata:
            self.dado["ultima_falha"] = diagnostico_publico(anterior.get("ultima_falha"))
        self.etapa("publicador")

    def etapa(self, etapa):
        self.dado.update(etapa=etapa if isinstance(etapa, str) and etapa in ETAPAS else "publicador", observado_em=agora())
        gravar_json(self.arquivo, self.dado)

    def falhar(self, erro):
        diag = classificar_erro(erro, self.dado["etapa"], self.dado["celula"])
        self.dado.update(estado="falhou", diagnostico=diag, ultima_falha=diag, observado_em=agora())
        gravar_json(self.arquivo, self.dado)
        return diag

    def concluir(self):
        self.dado.update(estado="concluida", diagnostico=None, observado_em=agora())
        gravar_json(self.arquivo, self.dado)
