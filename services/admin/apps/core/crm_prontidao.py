"""O bloco "Pronto para vender?" de `/admin/crm/agentes/`.

A prova do CRM com agentes mostrou que um lead real pode terminar em "passou
para uma pessoa" por causas que não aparecem em tela nenhuma: quiz sem oferta,
nenhuma condição liberada, checkout em modo de teste, modelo sem chave ou sem
saldo, WhatsApp sem modelo aprovado, respostas por e-mail que não chegam. Aqui
cada uma vira uma linha: `pronto`, `falta` ou `não consegui conferir`, com o que
fazer e o link da tela certa.

Regras da tela:

* cada fonte é consultada pela porta da célula dona (quiz, checkout,
  mensageria, contatos), nunca pelo banco dela; só o que mora no próprio admin
  (chave e autorização do modelo) é lido direto;
* fonte fora do ar, sem configuração ou fora do contrato vira "não consegui
  conferir" naquela linha, e a página continua de pé; nunca erro 500;
* nenhuma linha mostra chave, endereço ou segredo: só se existe.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.urls import reverse

logger = logging.getLogger(__name__)

PRONTO = "pronto"
FALTA = "falta"
NAO_CONFERI = "nao_conferi"

ROTULOS = {PRONTO: "Pronto", FALTA: "Falta", NAO_CONFERI: "Não consegui conferir"}


def _item(chave, titulo, estado, detalhe, fazer="", link="", link_texto=""):
    return {
        "chave": chave,
        "titulo": titulo,
        "estado": estado,
        "rotulo": ROTULOS[estado],
        "detalhe": detalhe,
        "fazer": fazer,
        "link": link,
        "link_texto": link_texto,
    }


def _nao_conferi(chave, titulo, o_que, link="", link_texto=""):
    return _item(
        chave, titulo, NAO_CONFERI, o_que,
        "Tente de novo em instantes. Se continuar, a conexão com essa parte ainda não está ligada neste ambiente.",
        link, link_texto,
    )


class _Fontes:
    """As consultas a outras células, feitas no máximo uma vez por abertura da
    tela e compartilhadas entre as linhas que precisam da mesma resposta."""

    def __init__(self, request, escopo):
        self.request = request
        self.escopo = list(escopo or [])
        self._guardado = {}

    def _uma_vez(self, nome, fazer):
        if nome not in self._guardado:
            try:
                self._guardado[nome] = (True, fazer())
            except Exception:  # fonte fora do ar vira "não consegui conferir"; nunca derruba a tela
                logger.exception("prontidão comercial: falha ao consultar %s", nome)
                self._guardado[nome] = (False, None)
        ok, valor = self._guardado[nome]
        return valor if ok else None

    def host(self):
        from .conteudos import host_da_requisicao

        return host_da_requisicao(self.request)

    def quizzes(self):
        """Os quizzes publicados que a equipe atende (o escopo, se houver), já
        com a oferta de cada resultado. `None` = não consegui consultar."""

        def ler():
            from .ofertas_dos_quizzes import _contexto

            contexto, status = _contexto(self.request)
            if status != 200 or contexto.get("indisponivel"):
                return None
            return contexto["quizzes"]

        return self._uma_vez("quizzes", ler)

    def condicoes(self):
        def ler():
            from .crm_condicoes import CondicoesClient

            estado, dados = CondicoesClient(self.host()).ofertas()
            return dados if estado == CondicoesClient.OK else None

        return self._uma_vez("condicoes", ler)

    def ambiente(self):
        def ler():
            from .crm_condicoes import CondicoesClient

            estado, dados = CondicoesClient(self.host()).ambiente()
            return dados if estado == CondicoesClient.OK else None

        return self._uma_vez("ambiente", ler)

    def mensageria(self):
        def ler():
            from .clients import CatalogoClient, MensageriaClient

            site = CatalogoClient().site_por_host(self.host()) or {}
            if not site.get("id"):
                return None
            dados = MensageriaClient().prontidao_comercial(str(site["id"]))
            if not isinstance(dados, dict) or not isinstance(dados.get("whatsapp"), dict) or not isinstance(
                dados.get("email"), dict
            ):
                return None
            return dados

        return self._uma_vez("mensageria", ler)

    def contatos(self):
        def ler():
            from .clients import LeadsClient

            cliente = LeadsClient()
            estado, reais = cliente.listar(por_pagina=1, testes="ocultar")
            if estado != cliente.OK:
                return None
            estado, todos = cliente.listar(por_pagina=1, testes="mostrar")
            if estado != cliente.OK:
                return None
            return reais["total"], max(todos["total"] - reais["total"], 0)

        return self._uma_vez("contatos", ler)


def _quizzes_do_escopo(fontes):
    quizzes = fontes.quizzes()
    if quizzes is None:
        return None
    publicados = [q for q in quizzes if q.get("published")]
    if fontes.escopo:
        publicados = [q for q in publicados if q.get("slug") in fontes.escopo]
    return publicados


def _linha_quizzes(fontes):
    titulo = "Quizzes publicados com oferta ligada"
    link, texto = reverse("crm_ofertas_dos_quizzes"), "Ligar ofertas aos quizzes"
    publicados = _quizzes_do_escopo(fontes)
    if publicados is None:
        return _nao_conferi("quizzes", titulo, "Não consegui consultar os quizzes agora.", link, texto)
    do_escopo = " (só os quizzes escolhidos em “Em quais quizzes a equipe atua”)" if fontes.escopo else ""
    if not publicados:
        return _item(
            "quizzes", titulo, FALTA, f"Nenhum quiz publicado{do_escopo}.",
            "Publique um quiz e ligue uma oferta ao botão de cada resultado.", link, texto,
        )
    ligados = [q for q in publicados if not q.get("precisa_de_atencao")]
    if len(ligados) == len(publicados):
        return _item(
            "quizzes", titulo, PRONTO,
            f"{len(ligados)} de {len(publicados)} quiz{'zes' if len(publicados) != 1 else ''} publicado{'s' if len(publicados) != 1 else ''}"
            f"{do_escopo} com oferta ligada em todos os resultados.", "", link, "Ver as ofertas",
        )
    sem = ", ".join(q.get("title") or q.get("slug") or "?" for q in publicados if q.get("precisa_de_atencao"))
    return _item(
        "quizzes", titulo, FALTA,
        f"{len(ligados)} de {len(publicados)} quiz{'zes' if len(publicados) != 1 else ''} publicado{'s' if len(publicados) != 1 else ''}"
        f"{do_escopo} com oferta em todos os resultados. Sem oferta ou com problema: {sem}.",
        "Sem oferta ligada, o agente não prepara link de compra e passa o lead para uma pessoa. "
        "Ligue a oferta, ou escolha abaixo só os quizzes prontos para a equipe começar por eles.",
        link, texto,
    )


def _ofertas_ligadas(publicados):
    apelidos = []
    for quiz in publicados:
        for faixa in quiz.get("faixas", []):
            oferta = faixa.get("oferta") or {}
            if oferta.get("tipo") == "oferta" and oferta.get("apelido") not in apelidos:
                apelidos.append(oferta["apelido"])
    return apelidos


def _linha_condicoes(fontes):
    titulo = "Ao menos uma condição liberada em cada oferta ligada"
    link, texto = reverse("crm_condicoes"), "Liberar condições"
    publicados = _quizzes_do_escopo(fontes)
    if publicados is None:
        return _nao_conferi("condicoes", titulo, "Não consegui saber quais ofertas estão ligadas aos quizzes.", link, texto)
    ofertas = _ofertas_ligadas(publicados)
    if not ofertas:
        return _item(
            "condicoes", titulo, FALTA, "Ainda não há oferta ligada a um quiz publicado.",
            "Ligue uma oferta ao quiz primeiro; depois libere o Pix e o cartão que o agente pode oferecer.", link, texto,
        )
    dados = fontes.condicoes()
    if dados is None:
        return _nao_conferi("condicoes", titulo, "Não consegui consultar o checkout agora.", link, texto)
    linhas = {l.get("oferta_ref"): l for l in dados.get("ofertas", []) if isinstance(l, dict)}
    sem, duvida = [], []
    for apelido in ofertas:
        linha = linhas.get(apelido)
        if linha is None:
            sem.append(apelido)  # nunca marcada: o checkout só lista as que ele já viu ou que têm marca
        elif linha.get("disponivel") is False:
            duvida.append(apelido)
        elif not linha.get("liberadas_total"):
            sem.append(apelido)
    if sem:
        return _item(
            "condicoes", titulo, FALTA, "Nenhuma condição liberada em: " + ", ".join(sem) + ".",
            "Sem condição liberada o agente só pode falar do preço da oferta, sem Pix nem parcelas. "
            "Marque na tela de condições o que ele pode oferecer.", link, texto,
        )
    if duvida:
        return _nao_conferi(
            "condicoes", titulo, "O checkout não conseguiu conferir: " + ", ".join(duvida) + ".", link, texto
        )
    return _item(
        "condicoes", titulo, PRONTO,
        f"{len(ofertas)} oferta{'s' if len(ofertas) != 1 else ''} ligada{'s' if len(ofertas) != 1 else ''}, todas com condição liberada.",
        "", link, "Ver as condições",
    )


def _linha_checkout(fontes):
    titulo = "Checkout: pedidos de teste ou de verdade"
    dados = fontes.ambiente()
    if dados is None:
        return _nao_conferi("checkout", titulo, "Não consegui perguntar ao checkout em que modo ele está.")
    partes = f"Cartão: {'produção' if dados.get('cartao') == 'producao' else 'teste'}; Pix: {'produção' if dados.get('pix') == 'producao' else 'teste'}."
    if dados.get("modo") == "producao":
        return _item("checkout", titulo, PRONTO, "Os pedidos nascem em produção: o dinheiro é real. " + partes)
    return _item(
        "checkout", titulo, FALTA, "Hoje os pedidos nascem em modo de teste. " + partes,
        "Pedido de teste usa o sandbox do provedor: nenhum dinheiro real entra e a compra não conta como venda. "
        "Para vender de verdade, o provedor de pagamento precisa estar em produção no servidor "
        "(isso só o mantenedor muda).",
    )


def _linha_modelo():
    titulo = "Modelo de IA conectado"
    link, texto = reverse("robos_admin"), "Robôs e conexão"
    from apps.agentes import modelo
    from apps.agentes.models import Conexao

    if not modelo.tem_chave():
        return _item(
            "modelo", titulo, FALTA, "Nenhuma chave do modelo guardada.",
            "Cole a chave na tela de robôs e conexão (ela nunca aparece de novo, só os quatro últimos caracteres).",
            link, texto,
        )
    conexao = modelo.conexao()
    S = Conexao.Situacao
    if conexao.situacao == S.CONFERIDA:
        return _item("modelo", titulo, PRONTO, conexao.detalhe or "Chave aceita pela conta.", "", link, texto)
    if conexao.situacao == S.RECUSADA:
        return _item(
            "modelo", titulo, FALTA, "A conta recusou a chave.", "Guarde uma chave válida e confira de novo.", link, texto
        )
    if conexao.situacao == S.FALHOU:
        return _item(
            "modelo", titulo, FALTA, conexao.detalhe or "A última conferência da chave falhou.",
            "Confira de novo na tela de robôs e conexão.", link, texto,
        )
    return _item(
        "modelo", titulo, NAO_CONFERI, "A chave está guardada, mas ainda não foi conferida na conta.",
        "Use “Conferir” na tela de robôs e conexão.", link, texto,
    )


def _linha_gasto(gasto_comercial):
    titulo = "Autorização de gasto com saldo"
    link, texto = reverse("robos_admin"), "Robôs e conexão"
    from apps.agentes import modelo

    autorizacao = modelo.autorizacao_ativa()
    if autorizacao is None:
        return _item(
            "gasto", titulo, FALTA, "Nenhum limite de gasto autorizado: os agentes não fazem chamadas pagas.",
            "Autorize um limite mensal na tela de robôs e conexão.", link, texto,
        )
    teto = autorizacao.teto_mensal_usd or Decimal("0")
    usado = max(modelo.gasto_do_mes(autorizacao.pk), gasto_comercial or Decimal("0"))
    disponivel = max(teto - usado, Decimal("0"))
    if teto <= 0 or disponivel <= 0:
        return _item(
            "gasto", titulo, FALTA, f"Limite de US$ {teto:.2f} no mês já usado (US$ {usado:.2f}).",
            "Os agentes esperam o mês virar ou um limite novo.", link, texto,
        )
    return _item(
        "gasto", titulo, PRONTO, f"Limite de US$ {teto:.2f} no mês; ainda disponível US$ {disponivel:.2f}.", "", link, texto
    )


def _linha_whatsapp(fontes):
    titulo = "WhatsApp conectado"
    link, texto = reverse("whatsapp"), "Conexão do WhatsApp"
    dados = fontes.mensageria()
    if dados is None:
        return _nao_conferi("whatsapp", titulo, "Não consegui perguntar à mensageria agora.", link, texto)
    conexao = dados["whatsapp"].get("conexao")
    if conexao == "open":
        return _item("whatsapp", titulo, PRONTO, "O número do WhatsApp está conectado.", "", link, texto)
    if conexao == "indisponivel":
        return _nao_conferi("whatsapp", titulo, "O serviço do WhatsApp não respondeu agora.", link, texto)
    if conexao == "nao_configurado":
        return _item(
            "whatsapp", titulo, FALTA, "Nenhum número de WhatsApp configurado para este site.",
            "Configure e conecte o número na tela do WhatsApp.", link, texto,
        )
    return _item(
        "whatsapp", titulo, FALTA, f"O WhatsApp está configurado, mas não conectado (estado: {conexao}).",
        "Leia o QR de novo na tela do WhatsApp.", link, texto,
    )


def _linha_modelo_whatsapp(fontes):
    titulo = "WhatsApp: modelo aprovado para o primeiro contato"
    link, texto = reverse("crm_modelos"), "Modelos do WhatsApp"
    dados = fontes.mensageria()
    if dados is None:
        return _nao_conferi("modelo_whatsapp", titulo, "Não consegui perguntar à mensageria agora.", link, texto)
    zap = dados["whatsapp"]
    if zap.get("canal_oficial") != "ligado":
        return _item(
            "modelo_whatsapp", titulo, FALTA, "O canal oficial do WhatsApp ainda não está ligado.",
            "Fora da janela de 24 horas o WhatsApp só aceita modelo aprovado. Sem ele, o agente cai para o e-mail.",
            link, texto,
        )
    if not zap.get("modelo_primeiro_contato"):
        motivo = str(zap.get("motivo") or "").strip()
        return _item(
            "modelo_whatsapp", titulo, FALTA,
            "Nenhum modelo aprovado serve ao primeiro contato" + (f" ({motivo})." if motivo else "."),
            "Aprove na Meta um modelo cujo nome comece por primeiro_contato e sem botão com link; "
            "depois sincronize na tela de modelos.", link, texto,
        )
    return _item(
        "modelo_whatsapp", titulo, PRONTO, "Há modelo aprovado para o primeiro contato.", "", link, texto
    )


def _linha_email(fontes):
    titulo = "E-mail: respostas dos leads chegam"
    dados = fontes.mensageria()
    if dados is None:
        return _nao_conferi("email", titulo, "Não consegui perguntar à mensageria agora.")
    if dados["email"].get("respostas_recebidas"):
        return _item("email", titulo, PRONTO, "O endereço de entrada das respostas por e-mail está protegido por token e ativo.")
    return _item(
        "email", titulo, FALTA, "O token de entrada das respostas por e-mail não está configurado na mensageria.",
        "Sem ele, a resposta que o lead manda por e-mail é recusada e o agente não a vê. "
        "Só o mantenedor configura isso no servidor.",
    )


def _linha_contatos(fontes):
    titulo = "Contatos reais e de teste"
    link, texto = reverse("contatos"), "Ver contatos"
    contagem = fontes.contatos()
    if contagem is None:
        return _nao_conferi("contatos", titulo, "Não consegui perguntar ao serviço de contatos agora.", link, texto)
    reais, testes = contagem
    detalhe = f"{reais} contato{'s' if reais != 1 else ''} {'reais' if reais != 1 else 'real'} e {testes} de teste (os de teste ficam fora dos totais)."
    if reais == 0:
        return _item(
            "contatos", titulo, FALTA, detalhe, "A equipe comercial trabalha com quem respondeu um quiz de verdade.", link, texto
        )
    return _item("contatos", titulo, PRONTO, detalhe, "", link, texto)


def verificar(request, escopo=(), gasto_comercial=None) -> dict:
    """As linhas do bloco e o resumo. Cada linha falha sozinha: uma fonte fora
    do ar nunca derruba a página nem as outras linhas."""
    fontes = _Fontes(request, escopo)
    linhas = (
        ("quizzes", "Quizzes publicados com oferta ligada", lambda: _linha_quizzes(fontes)),
        ("condicoes", "Ao menos uma condição liberada em cada oferta ligada", lambda: _linha_condicoes(fontes)),
        ("checkout", "Checkout: pedidos de teste ou de verdade", lambda: _linha_checkout(fontes)),
        ("modelo", "Modelo de IA conectado", _linha_modelo),
        ("gasto", "Autorização de gasto com saldo", lambda: _linha_gasto(gasto_comercial)),
        ("whatsapp", "WhatsApp conectado", lambda: _linha_whatsapp(fontes)),
        ("modelo_whatsapp", "WhatsApp: modelo aprovado para o primeiro contato", lambda: _linha_modelo_whatsapp(fontes)),
        ("email", "E-mail: respostas dos leads chegam", lambda: _linha_email(fontes)),
        ("contatos", "Contatos reais e de teste", lambda: _linha_contatos(fontes)),
    )
    itens = []
    for chave, titulo, fazer in linhas:
        try:
            itens.append(fazer())
        except Exception:  # a linha some em "não consegui conferir"; a página e as outras linhas seguem
            logger.exception("prontidão comercial: falha na linha %s", chave)
            itens.append(_nao_conferi(chave, titulo, "Não consegui conferir esta parte agora."))
    prontos = sum(1 for i in itens if i["estado"] == PRONTO)
    faltam = sum(1 for i in itens if i["estado"] == FALTA)
    duvida = sum(1 for i in itens if i["estado"] == NAO_CONFERI)
    todos = fontes.quizzes()
    return {
        "itens": itens,
        # Para escolher o escopo: todos os quizzes publicados (não só os do escopo atual).
        "quizzes": None
        if todos is None
        else [{"slug": q["slug"], "titulo": q.get("title") or q["slug"]} for q in todos if q.get("published")],
        "prontos": prontos,
        "faltam": faltam,
        "duvida": duvida,
        "total": len(itens),
        "tudo_pronto": prontos == len(itens),
    }
