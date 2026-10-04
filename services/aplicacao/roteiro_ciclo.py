"""O ciclo comercial no site no ar, com dados de teste, sem mensagem de verdade e sem pagar.

Roda dentro do container da aplicação (mesmos arquivos de ambiente do site):

    python roteiro_ciclo.py --host meshcraft.top --quiz-a <slug> --quiz-b <slug> --oferta <slug>

O que ele faz, na ordem: captura parcial e quiz completo de uma pessoa de teste,
contato e oportunidade no CRM, perfil, mensagem recebida, envio com chave
repetida, link de compra, pedido, Pix aguardando, aprovação pelo provedor
(simulado), oportunidade certa ganha, pedido de PARAR e envio barrado.

O que ele NÃO faz, por construção (tudo dentro do processo do roteiro):

* mensagem de verdade: o gateway do WhatsApp é um servidor local de mentira;
* pagamento de verdade: o Mercado Pago é simulado; a OpenAI também;
* qualquer outra conexão para fora: barrada ao nível do socket (só vale
  rede local, banco e Redis do próprio site);
* mexer no barramento do site: os avisos entre células trafegam num Redis de
  ensaio (banco separado, que precisa estar vazio) e a caixa de saída deixa a
  linha já publicada, então os trabalhadores do site não a veem;
* tarefas em segundo plano do site (Huey): ficam descartadas dentro do roteiro.

Os dados criados são de teste (e-mail @example.com, nome com "Sandbox"): ficam
fora dos totais do CRM e nada é apagado. O relatório diz o contato criado.

Falta de configuração aparece como "indisponível" com o motivo, nunca como erro.
Saída: 0 tudo certo, 1 algum passo falhou, 2 ambiente não permite rodar.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from ciclo_comercial import (  # noqa: E402
    Ambiente, Cena, Ciclo, FalhaDoCiclo, GatewayFalso, Pessoa, ProvedoresFalsos, Rotas,
    esperar, iniciar_consumidores,
)

BANCO_DE_ENSAIO = 15


class Indisponivel(Exception):
    """O site não tem o que este passo precisa (mostrado como tal, nunca como erro)."""


# ---------------------------------------------------------------------------
# Isolamento do processo
# ---------------------------------------------------------------------------


def _com_banco(url: str, numero: int) -> str:
    return urlunsplit(urlsplit(url)._replace(path=f"/{numero}"))


def _ips(nome_ou_url: str) -> set[str]:
    destino = urlsplit(nome_ou_url).hostname or nome_ou_url
    try:
        return {info[4][0] for info in socket.getaddrinfo(destino, None)}
    except OSError:
        return set()


class Isolamento:
    """Tudo o que impede o roteiro de tocar no mundo de fora do site de ensaio."""

    def __init__(self, redis_ensaio: str, gateway: GatewayFalso) -> None:
        self.redis_ensaio, self.gateway = redis_ensaio, gateway
        self.tarefas_descartadas = 0
        self.conexoes_barradas: list[str] = []
        self._desfazer: list = []
        self._cliente = None

    # -- ligar / desligar -----------------------------------------------------

    def ligar(self) -> "Isolamento":
        import redis as redis_lib
        from django.conf import settings

        self._cliente = redis_lib.from_url(self.redis_ensaio)
        try:
            ocupadas = self._cliente.dbsize()
        except Exception as erro:  # noqa: BLE001
            raise Indisponivel(f"o Redis de ensaio não responde ({type(erro).__name__})") from erro
        if ocupadas:
            raise Indisponivel(
                "o banco de ensaio do Redis não está vazio; o roteiro só usa um banco que ele mesmo criou"
            )
        permitidos = _ips(self.redis_ensaio)
        for configuracao in settings.DATABASES.values():
            permitidos |= _ips(str(configuracao.get("HOST") or ""))
        self._redirecionar_ambientes()
        self._publicar_ao_gravar()
        self._calar_relays()
        self._descartar_tarefas()
        self._barrar_rede(permitidos)
        return self

    def desligar(self) -> None:
        for passo in reversed(self._desfazer):
            try:
                passo()
            except Exception:  # noqa: BLE001 - desfazer o resto mesmo assim
                traceback.print_exc()
        self._desfazer.clear()
        if self._cliente is not None:
            try:
                self._cliente.flushdb()  # só existe o que este roteiro criou: o banco começou vazio
            except Exception:  # noqa: BLE001
                pass

    # -- peças ------------------------------------------------------------------

    def _redirecionar_ambientes(self) -> None:
        from config import runtime

        def trocar(dicionario: dict, chave: str, valor: str) -> None:
            tinha, antigo = chave in dicionario, dicionario.get(chave)
            dicionario[chave] = valor
            self._desfazer.append(
                lambda d=dicionario, k=chave, t=tinha, a=antigo: d.__setitem__(k, a) if t else d.pop(k, None)
            )

        for servico, valores in runtime._service_environments.items():
            trocar(valores, "REDIS_STREAMS_URL", self.redis_ensaio)
            if "REDIS_STREAMS_URL" in runtime._service_settings.get(servico, {}):
                trocar(runtime._service_settings[servico], "REDIS_STREAMS_URL", self.redis_ensaio)
        mensageria = runtime._service_environments["mensageria"]
        configurado = runtime._service_settings["mensageria"]
        for chave, valor in (("WHATSAPP_GATEWAY_URL", self.gateway.url), ("WHATSAPP_GATEWAY_TOKEN", "ensaio")):
            trocar(mensageria, chave, valor)
            trocar(configurado, chave, valor)

    def _publicar_ao_gravar(self) -> None:
        """Cada linha da caixa de saída vai direto ao barramento de ensaio, já marcada publicada.

        Como o `published_at` entra na mesma transação da linha, o relé do site
        (que só lê linhas sem `published_at`) nunca enxerga o que o roteiro cria.
        """
        from django.apps import apps
        from django.db.models.signals import post_save
        from django.utils import timezone as fuso

        cliente = self._cliente

        def publicar(sender, instance, created, using=None, **kwargs):
            if not created or instance.published_at:
                return
            envelope = {
                "event": instance.event, "version": instance.version,
                "event_id": str(instance.event_id),
                "occurred_at": instance.occurred_at.isoformat(), "data": instance.payload,
            }
            cliente.xadd(f"eventos.{instance.event}", {"json": json.dumps(envelope, ensure_ascii=False)})
            sender.objects.using(using).filter(pk=instance.pk).update(published_at=fuso.now())
            instance.published_at = fuso.now()

        for modelo in apps.get_models():
            if modelo.__name__ == "OutboxEvent" and modelo.__module__.startswith("modules."):
                post_save.connect(publicar, sender=modelo, weak=False, dispatch_uid=f"roteiro-{modelo.__module__}")
                self._desfazer.append(
                    lambda m=modelo: post_save.disconnect(sender=m, dispatch_uid=f"roteiro-{m.__module__}")
                )
        self._publicar = publicar  # mantém a função viva

    def _calar_relays(self) -> None:
        """O relé do site some dentro do roteiro: ele publicaria linhas pendentes de visitantes de verdade."""
        from django.apps import apps

        modulos = set()
        for modelo in apps.get_models():
            if modelo.__name__ != "OutboxEvent" or not modelo.__module__.startswith("modules."):
                continue
            modulos.add(modelo.__module__)
            pacote = apps.get_app_config(modelo._meta.app_label).name
            try:
                modulos.add(import_module(f"{pacote}.tasks").__name__)
            except ImportError:
                pass
        for nome in modulos:
            modulo = import_module(nome)
            original = getattr(modulo, "relay_outbox", None)
            if original is None:
                continue
            modulo.relay_outbox = lambda *a, **k: 0
            self._desfazer.append(lambda m=modulo, o=original: setattr(m, "relay_outbox", o))

    def _descartar_tarefas(self) -> None:
        """Tarefas Huey de dentro do roteiro não vão para a fila do site."""
        from config.registry import SERVICES

        for servico in SERVICES:
            try:
                instancia = import_module(f"modules.{servico}.config.huey").huey
            except (ImportError, AttributeError):
                continue
            original = instancia.enqueue

            def descartar(tarefa, _isolamento=self):
                _isolamento.tarefas_descartadas += 1
                return None

            instancia.enqueue = descartar
            self._desfazer.append(lambda i=instancia, o=original: setattr(i, "enqueue", o))

    def _barrar_rede(self, permitidos: set[str]) -> None:
        """Só rede local, banco e Redis do site. O resto é recusado na hora."""
        original = socket.socket.connect
        barradas = self.conexoes_barradas

        def conectar(self_socket, endereco):
            if self_socket.family in (socket.AF_INET, socket.AF_INET6) and isinstance(endereco, tuple):
                destino = str(endereco[0])
                if not (destino.startswith("127.") or destino in ("::1", "localhost") or destino in permitidos):
                    barradas.append(destino)
                    raise OSError(f"saída bloqueada pelo roteiro do ciclo: {destino}")
            return original(self_socket, endereco)

        socket.socket.connect = conectar
        self._desfazer.append(lambda: setattr(socket.socket, "connect", original))


# ---------------------------------------------------------------------------
# O ambiente do site (tokens saem dos arquivos de ambiente e nunca são impressos)
# ---------------------------------------------------------------------------


def _env(servico: str, chave: str) -> str:
    from django.conf import settings

    return (settings.SERVICE_ENV.get(servico, {}).get(chave) or "").strip()


def _primeiro_com_prefixo(servico: str, prefixo: str) -> str:
    from django.conf import settings

    for chave, valor in settings.SERVICE_ENV.get(servico, {}).items():
        if chave.startswith(prefixo) and valor.strip():
            return valor.strip()
    return ""


def montar_ambiente(gateway: GatewayFalso, provedores: ProvedoresFalsos) -> Ambiente:
    faltam = []
    leads_admin = _env("leads", "TOKENS_ACEITOS_ADMIN")
    mensageria = _primeiro_com_prefixo("mensageria", "TOKENS_PUBLICACAO_")
    pagina = _env("checkout", "TOKENS_ACEITOS_PAGINAS")
    checkout = _env("checkout", "TOKENS_ACEITOS_ADMIN")
    webhook = _env("mensageria", "WHATSAPP_WEBHOOK_TOKEN")
    segredo_mp = _env("pagamentos", "MP_WEBHOOK_SECRET")
    for nome, valor in (("leads: TOKENS_ACEITOS_ADMIN", leads_admin), ("mensageria: TOKENS_PUBLICACAO_*", mensageria),
                        ("checkout: TOKENS_ACEITOS_ADMIN", checkout), ("checkout: TOKENS_ACEITOS_PAGINAS", pagina),
                        ("mensageria: WHATSAPP_WEBHOOK_TOKEN", webhook), ("pagamentos: MP_WEBHOOK_SECRET", segredo_mp)):
        if not valor:
            faltam.append(nome)
    if faltam:
        raise Indisponivel("faltam no ambiente do site: " + "; ".join(faltam))
    return Ambiente(
        rotas=Rotas.de(leads=leads_admin, leads_admin=leads_admin, mensageria=mensageria,
                       checkout=checkout, quiz=""),
        gateway=gateway, provedores=provedores, token_pagina=pagina, webhook_whatsapp=webhook,
        mp_segredo=segredo_mp, instancia="",  # preenchida da configuração do site, abaixo
        drenar=lambda: 0,  # a caixa de saída publica ao gravar (ver Isolamento)
        publicar_paradas=_publicar_so_desta_pessoa,
    )


def _publicar_so_desta_pessoa(email: str) -> int:
    from ciclo_comercial import publicar_capturas_paradas

    if not email:
        raise FalhaDoCiclo("sem e-mail, o roteiro não publica captura nenhuma")
    return publicar_capturas_paradas(email=email)


def montar_cena(host: str, quiz_a: str, quiz_b: str, oferta: str) -> tuple[Cena, str]:
    from config.runtime import serving

    from modules.catalogo.apps.ofertas.models import Offer
    from modules.catalogo.apps.sites.models import Site
    from modules.mensageria.apps.whatsapp.models import ConfiguracaoWhatsApp

    with serving("catalogo"):
        site = Site.objects.filter(host=host.lower(), active=True).first()
        if site is None:
            raise Indisponivel(f"o site {host} não está cadastrado e ativo no catálogo")
        publicada = Offer.objects.filter(site=site, slug=oferta).first()
        if publicada is None:
            raise Indisponivel(f"a oferta {oferta} não existe no site {host}")
        preco = publicada.price_cents
    instancia = ""
    with serving("mensageria"):
        config = ConfiguracaoWhatsApp.objects.filter(site_id=str(site.id), ativo=True).first()
        if config is not None:
            instancia = config.instancia
    cena = Cena(host=host.lower(), site_id=str(site.id), quiz_a=quiz_a, quiz_b=quiz_b or "",
                oferta=oferta, preco_cents=preco)
    return cena, instancia


# ---------------------------------------------------------------------------
# Os passos
# ---------------------------------------------------------------------------


@dataclass
class Passo:
    nome: str
    estado: str = "ok"  # ok | falhou | indisponivel | pulado
    detalhe: str = ""
    segundos: float = 0.0


@dataclass
class Relatorio:
    passos: list[Passo] = field(default_factory=list)
    pessoa: Pessoa | None = None
    avisos: list[str] = field(default_factory=list)

    @property
    def falhou(self) -> bool:
        return any(p.estado == "falhou" for p in self.passos)

    def texto(self) -> str:
        sinal = {"ok": "ok", "falhou": "FALHOU", "indisponivel": "indisponível", "pulado": "pulado"}
        linhas = ["Ciclo comercial no site, com dados de teste", ""]
        for passo in self.passos:
            extra = f" - {passo.detalhe}" if passo.detalhe else ""
            linhas.append(f"[{sinal[passo.estado]}] {passo.nome}{extra}")
        if self.pessoa is not None:
            linhas += ["", f"Contato de teste criado: {self.pessoa.email} (id {self.pessoa.lead_id or 'não criado'})",
                       "Ele fica marcado como teste e fora dos totais; nada foi apagado."]
        linhas += [""] + self.avisos
        return "\n".join(linhas)


def _rodar(relatorio: Relatorio, nome: str, funcao) -> bool:
    passo = Passo(nome)
    relatorio.passos.append(passo)
    inicio = time.monotonic()
    try:
        resultado = funcao()
        passo.detalhe = resultado if isinstance(resultado, str) else ""
    except Indisponivel as motivo:
        passo.estado, passo.detalhe = "indisponivel", str(motivo)
    except (FalhaDoCiclo, AssertionError) as erro:
        passo.estado, passo.detalhe = "falhou", str(erro)[:400]
    except Exception as erro:  # noqa: BLE001 - um passo nunca derruba o relatório
        passo.estado, passo.detalhe = "falhou", f"{type(erro).__name__}: {str(erro)[:300]}"
    passo.segundos = time.monotonic() - inicio
    return passo.estado == "ok"


def _pix_so_pelo_mercado_pago(cena: Cena) -> None:
    """Se o site cobra Pix pela Appmax, o roteiro não cria pedido: a Appmax não é simulada."""
    from config.runtime import serving
    from django.conf import settings

    with serving("checkout"):
        appmax = set(getattr(settings, "APPMAX_PIX_ENABLED_SITES", ())) | set(
            getattr(settings, "APPMAX_PIX_FALLBACK_SITES", ()))
    if cena.site_id in appmax:
        raise Indisponivel("este site cobra Pix pela Appmax; o roteiro só simula o Mercado Pago, então não cria pedido")


def executar_ciclo(cena: Cena, amb: Ambiente, *, pessoa: Pessoa | None = None) -> Relatorio:
    """Roda os passos. O ambiente já está isolado (ver `Isolamento`) e os consumidores ligados."""
    ciclo = Ciclo(cena, amb)
    sufixo = uuid.uuid4().hex[:8]
    pessoa = pessoa or Pessoa(
        nome=f"Ciclo Sandbox {sufixo[:4].upper()}", email=f"ciclo-{sufixo}@example.com",
        telefone="11900" + str(int(sufixo, 16) % 1_000_000).zfill(6), de_teste=True, aceita_whatsapp=True)
    relatorio = Relatorio(pessoa=pessoa)
    estado: dict = {}
    chave = f"roteiro-{sufixo}"

    def parcial():
        estado["aberto"] = ciclo.captura_parcial(pessoa, cena.quiz_a)
        ciclo.contato(pessoa)
        ciclo.oportunidade_do_quiz(pessoa, cena.quiz_a)
        return "contato e oportunidade criados pela captura parcial"

    def completo():
        ciclo.concluir_quiz(pessoa, cena.quiz_a, estado.get("aberto"))
        esperar(lambda: any(q.get("situacao") == "completo" for q in ciclo.ficha(pessoa)["quizzes"]), 40,
                "quiz completo na ficha")
        iguais = [o for o in ciclo.oportunidades(pessoa)
                  if o["fonte"]["referencia_id"] == f"oferta:{cena.quiz_a}"]
        if len(iguais) != 1:
            raise FalhaDoCiclo(f"esperava 1 oportunidade do quiz, achei {len(iguais)}")

    def perfil():
        lido = ciclo.gravar_perfil(pessoa)
        return f"perfil versão {lido['versao']}"

    def fora_dos_totais():
        quadro = ciclo.crm()
        if any(i["contato"]["email"] == pessoa.email for i in quadro["itens"]):
            raise FalhaDoCiclo("a pessoa de teste apareceu no quadro normal do CRM")
        if not any(i["registro_de_teste"] for i in ciclo.crm(testes="somente")["itens"]
                   if i["contato"]["email"] == pessoa.email):
            raise FalhaDoCiclo("a pessoa de teste não está marcada como teste")

    def exigir_whatsapp():
        if not amb.instancia:
            raise Indisponivel("o site não tem WhatsApp ativo na mensageria")

    def conversa():
        exigir_whatsapp()
        ciclo.abrir_conversa(pessoa)
        ciclo.receber_mensagem(pessoa, "Oi! Quero saber como funciona.", f"WA-{sufixo}")
        dados = ciclo.mensagens(pessoa)
        if [m["direcao"] for m in dados["mensagens"]] != ["entrada"]:
            raise FalhaDoCiclo("a mensagem recebida não entrou uma vez só na conversa")
        if not dados["conversa"]["janela_aberta"]:
            raise FalhaDoCiclo("a janela de 24h não abriu")
        return "mensagem recebida entrou na conversa ligada ao contato"

    def envio():
        exigir_whatsapp()
        primeira = ciclo.enviar(pessoa, "Oi! Aqui é a equipe. Já te explico.", chave)
        if primeira["resultado"] != "enviada":
            raise FalhaDoCiclo(f"primeiro envio deu {primeira['resultado']}: {primeira.get('detalhe')}")
        repetida = ciclo.enviar(pessoa, "Oi! Aqui é a equipe. Já te explico.", chave)
        if repetida["resultado"] != "repetida":
            raise FalhaDoCiclo(f"a chave repetida deu {repetida['resultado']}")
        if len(amb.gateway.para(pessoa.whatsapp)) != 1:
            raise FalhaDoCiclo("o gateway de mentira deveria ter 1 mensagem")
        return "1 envio simulado; a repetição foi reconhecida"

    def compra():
        _pix_so_pelo_mercado_pago(cena)
        if "pix" not in ciclo.condicoes_liberadas():
            raise Indisponivel(f"o mantenedor ainda não liberou o Pix da oferta {cena.oferta} para o agente; "
                               "o roteiro não libera condição por conta própria")
        link = ciclo.link_de_compra(pessoa, cena.quiz_a, chave + "-link")
        if ciclo.link_de_compra(pessoa, cena.quiz_a, chave + "-link")["link_id"] != link["link_id"]:
            raise FalhaDoCiclo("o mesmo pedido de link criou dois links")
        estado["link"] = link
        pedido = ciclo.fechar_pedido_na_pagina(pessoa, link)
        estado["pedido"] = pedido
        situacao = ciclo.estado_do_pedido(pedido["id"])
        if situacao["confirmado"] or situacao["valor_cents"] != cena.preco_cents:
            raise FalhaDoCiclo(f"pedido criado em estado inesperado: {situacao}")
        return f"pedido de R$ {cena.preco_cents / 100:.2f} aguardando o Pix simulado"

    def pagamento():
        pedido = estado.get("pedido")
        if not pedido:
            raise Indisponivel("não houve pedido")
        pix = ciclo.pix_do_pedido[pedido["id"]]
        antes = ciclo.crm(testes="mostrar")["resumo"]["ganhas"]
        amb.provedores.mp.aprovar(pix)
        if ciclo.aviso_do_provedor(pix).status_code not in (200, 202):
            raise FalhaDoCiclo("o aviso do provedor foi recusado")
        esperar(lambda: ciclo.estado_do_pedido(pedido["id"])["confirmado"], 40, "pedido confirmado")
        esperar(lambda: ciclo.oportunidade(pessoa, cena.quiz_a)["etapa"] == "ganha", 40, "oportunidade ganha")
        depois = ciclo.crm(testes="mostrar")["resumo"]["ganhas"]
        if depois != antes + 1:
            raise FalhaDoCiclo(f"o total de ganhas devia subir 1 (era {antes}, agora {depois})")

    def so_a_certa():
        if not cena.quiz_b:
            raise Indisponivel("sem --quiz-b, não há segunda oportunidade para provar que só a certa fecha")
        ciclo.concluir_quiz(pessoa, cena.quiz_b)
        ciclo.oportunidade_do_quiz(pessoa, cena.quiz_b)
        outra = ciclo.oportunidade(pessoa, cena.quiz_b)
        if outra["etapa"] == "ganha" or outra["situacao"] != "aberta":
            raise FalhaDoCiclo("a oportunidade do outro quiz foi fechada pelo pagamento")
        if ciclo.pedidos_da_oportunidade(outra["id"])["pedidos"]:
            raise FalhaDoCiclo("o outro quiz ficou com pedido de outra compra")

    def parar():
        exigir_whatsapp()
        antes = len(amb.gateway.para(pessoa.whatsapp))
        ciclo.pedir_para_parar(pessoa, f"WA-parar-{sufixo}")
        esperar(lambda: ciclo.mensagens(pessoa)["conversa"]["descadastrado"], 20, "conversa descadastrada")
        depois = ciclo.enviar(pessoa, "Última chance!", chave + "-depois")
        if depois["resultado"] != "descadastrado":
            raise FalhaDoCiclo(f"depois do PARAR o envio deu {depois['resultado']}")
        if len(amb.gateway.para(pessoa.whatsapp)) != antes:
            raise FalhaDoCiclo("saiu mensagem depois do PARAR")

    def fora():
        if amb.provedores.openai:
            raise FalhaDoCiclo(f"a OpenAI foi chamada: {amb.provedores.openai}")
        if amb.provedores.barradas:
            raise FalhaDoCiclo(f"saídas para fora barradas: {amb.provedores.barradas}")

    if _rodar(relatorio, "Captura parcial vira contato e oportunidade", parcial):
        _rodar(relatorio, "Quiz completo da mesma pessoa não duplica", completo)
        _rodar(relatorio, "Perfil do contato", perfil)
        _rodar(relatorio, "Pessoa de teste fica fora dos totais do CRM", fora_dos_totais)
        if _rodar(relatorio, "Mensagem recebida entra na conversa do contato", conversa):
            _rodar(relatorio, "Envio com a mesma chave sai uma vez só", envio)
        _rodar(relatorio, "Link de compra, pedido e Pix aguardando", compra)
        _rodar(relatorio, "Pagamento aprovado pelo provedor fecha a oportunidade", pagamento)
        _rodar(relatorio, "Só a oportunidade da compra fecha", so_a_certa)
        _rodar(relatorio, "Pedido de PARAR interrompe o envio", parar)
    _rodar(relatorio, "Nada saiu para fora (OpenAI e outras conexões)", fora)
    return relatorio


# ---------------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------------


def subir_aplicacao() -> None:
    """O começo do entrypoint, sem migrar (o site já está migrado) e sem servidor."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    from config.migracoes import preparar_migracoes
    from config.runtime import install_contextual_settings, load_original_settings

    django.setup()
    load_original_settings()
    install_contextual_settings()
    preparar_migracoes()
    from internal import instalar

    instalar()
    import config.asgi  # noqa: F401


def rodar(host: str, quiz_a: str, quiz_b: str, oferta: str, redis_ensaio: str) -> Relatorio:
    """Roda o ciclo no processo já iniciado. Sempre desfaz o isolamento no fim."""
    gateway = GatewayFalso()
    provedores = ProvedoresFalsos().instalar()
    isolamento = Isolamento(redis_ensaio, gateway)
    relatorio = Relatorio()
    trabalhadores = None
    try:
        isolamento.ligar()
        ambiente = montar_ambiente(gateway, provedores)
        cena, instancia = montar_cena(host, quiz_a, quiz_b, oferta)
        ambiente.instancia = instancia
        trabalhadores = iniciar_consumidores(("leads", "checkout"))
        time.sleep(1)
        relatorio = executar_ciclo(cena, ambiente)
        if isolamento.tarefas_descartadas:
            relatorio.avisos.append(
                f"{isolamento.tarefas_descartadas} tarefa(s) em segundo plano do site ficaram de fora (por segurança).")
        if isolamento.conexoes_barradas:
            relatorio.avisos.append(f"conexões para fora barradas: {sorted(set(isolamento.conexoes_barradas))}")
            relatorio.passos.append(Passo("Nenhuma conexão para fora foi tentada", "falhou",
                                          ", ".join(sorted(set(isolamento.conexoes_barradas)))))
    finally:
        if trabalhadores is not None:
            trabalhadores.parar.set()
        isolamento.desligar()
        provedores.remover()
        gateway.parar()
    return relatorio


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Roda o ciclo comercial no site, com dados de teste.")
    parser.add_argument("--host", required=True, help="o site (ex.: meshcraft.top)")
    parser.add_argument("--quiz-a", required=True, help="slug do quiz cuja oferta será comprada")
    parser.add_argument("--quiz-b", default="", help="slug de um segundo quiz, para provar que só a oportunidade certa fecha")
    parser.add_argument("--oferta", required=True, help="slug da oferta vendida")
    parser.add_argument("--redis-ensaio", default=os.environ.get("ROTEIRO_REDIS_ENSAIO", ""),
                        help=f"URL do Redis de ensaio (banco vazio); padrão: o Redis do site, banco {BANCO_DE_ENSAIO}")
    opcoes = parser.parse_args(argv)
    subir_aplicacao()
    from config import runtime

    redis_ensaio = opcoes.redis_ensaio or _com_banco(
        runtime._service_environments["leads"].get("REDIS_STREAMS_URL", "redis://redis:6379/0"), BANCO_DE_ENSAIO)
    try:
        relatorio = rodar(opcoes.host, opcoes.quiz_a, opcoes.quiz_b, opcoes.oferta, redis_ensaio)
    except Indisponivel as motivo:
        print(f"O roteiro não pôde rodar: {motivo}")
        return 2
    print(relatorio.texto())
    return 1 if relatorio.falhou else 0


if __name__ == "__main__":
    sys.exit(principal())
