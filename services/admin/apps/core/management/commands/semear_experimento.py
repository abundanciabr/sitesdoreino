"""`manage.py semear_experimento --acao iniciar-aa|encerrar|medir`.

Liga, desliga e mede o A/A técnico da página de oferta de meshcraft.top sem
navegador e sem login: é o que o robô usa para rodar o ensaio do sistema de
experimentos sem o mantenedor (decisão dele em 27/09/2026). Quem chama é
`infra/semear-experimento.sh`, disparado por `.github/workflows/semear-experimento.yml`.

## Um site só, e não um parâmetro

A área administrativa só tem rota em `meshcraft.top` (router `admin` de
`infra/traefik/dynamic/plataforma.yml`) e `basileiatoutheou.org` está congelado
(`docs/decisoes/DECISAO-foco-em-meshcraft.md`). Um host escolhido na hora
apontaria para um site sem tela onde conferir ou encerrar o que foi ligado.

## A mesma porta das telas, e não um atalho

O comando chama as funções que a tela `/admin/paginas/experimentos/`, a tela de
decisão e a tela de resultado chamam (`criar_rascunho`, `iniciar_experimento`,
`decidir`, `contar`), com as mesmas recusas, o mesmo catálogo, a mesma medição
e a mesma auditoria. A única diferença é quem assina a linha de auditoria:
`ATOR`, o semeador pelo pipeline, sem dado de pessoa. Medir só lê.

## O que é o A/A, e como ele é reconhecido

Um experimento no espaço `cubo.headline` com a hipótese exata `HIPOTESE` e duas
variantes ou mais com o mesmo texto, que é o texto publicado. Mede o sorteio, a
exposição e a contagem, e não a conversão. Um experimento que não tem essa
assinatura inteira nunca é iniciado, encerrado nem medido por aqui.

## Idempotente, e com a prova relida por fora

A/A já no ar é PRONTO sem escrita. A/A em rascunho é iniciado em vez de
nascer outro. Encerrar sem A/A no ar sai verde sem mudar nada. A linha
`PRONTO:` de ligar e desligar só sai depois de reler o experimento no catálogo,
numa chamada separada da que o mudou, e a releitura precisa bater no estado, na
decisão e na assinatura inteira.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.clients import CatalogoClient
from apps.core.decisao_do_experimento import decidir
from apps.core.experimentos import (
    CAMPOS,
    ESPACO_PADRAO,
    METRICAS,
    criar_rascunho,
    iniciar_experimento,
    recusas_do_plano,
    texto_no_ar,
)
from apps.core.paginas import SLUG_DA_PAGINA
from apps.core.resultado_do_experimento import contar

HOST = "meshcraft.top"

HIPOTESE = "A/A técnico: mede sorteio, exposição e contagem, não conversão"

#: Quem assina a auditoria. `.invalid` é domínio reservado: nenhuma caixa real.
ATOR = SimpleNamespace(
    admin={
        "email": "semeador-de-experimento@pipeline.invalid",
        "id": "pipeline:semear-experimento",
    }
)

#: O plano, como a tela recebe do formulário: porcentagens, e não frações.
PLANO = {
    "espaco": ESPACO_PADRAO,
    "hipotese": HIPOTESE,
    "parte_b": "50",
    "metrica_principal": next(iter(METRICAS)),
    "taxa_base": "3",
    "mde": "1",
    "dias_planejados": "7",
}

#: As telas que as mensagens mandam abrir: rotas de `config/urls.py` sob o
#: prefixo `/admin` que o router da área administrativa entrega.
ADMIN = f"https://{HOST}/admin"
TELA_DA_PAGINA = f"{ADMIN}/paginas/"


def tela_de_decisao(experimento_id: str) -> str:
    return f"{ADMIN}/placar/experimentos/{experimento_id}/decisao/"


def tela_de_resultado(experimento_id: str) -> str:
    return f"{ADMIN}/placar/experimentos/{experimento_id}/resultado/"


SEM_SITE = (
    f"O catálogo não devolveu o site {HOST}, por uma de duas causas que a admin "
    "não separa: o catálogo não respondeu (ou a admin está sem a chave dele), "
    "ou o site não está cadastrado e ativo nele. Nada foi alterado. O QUE FAZER: "
    "rode de novo em alguns minutos, o que resolve a primeira causa. Se parar "
    f"de novo com esta frase, abra {TELA_DA_PAGINA}. Se ela disser que o "
    "catálogo não respondeu, a ligação entre a admin e o catálogo está fora do "
    "ar. Se ela abrir a página, o catálogo responde, e o site precisa ser "
    "cadastrado e ativado nele."
)

TITULO_VAZIO = (
    f"O espaço {ESPACO_PADRAO} está vazio na página no ar, e o A/A compara esse "
    "texto com ele mesmo. Nada foi alterado. O QUE FAZER: publique o título em "
    f"{TELA_DA_PAGINA} e rode de novo."
)

NO_AR_COM_TEXTOS_DIFERENTES = (
    "PAROU POR SEGURANÇA: o experimento {id} ESTÁ NO AR com textos diferentes "
    "nas variantes. A página foi publicada entre a leitura do título e o "
    "início, e o catálogo gravou o título novo na variante a, enquanto a b "
    "ficou com o antigo. Isso já não é um A/A, e este comando não o reconhece "
    "mais, nem para encerrar. O QUE FAZER: encerre-o agora em {tela}, com o "
    "gesto Encerrar, e rode iniciar-aa de novo."
)

MEDICAO_FORA = (
    "PAROU POR SEGURANÇA: a medição não respondeu à contagem do A/A {id} "
    "({desfecho}). Nada foi mudado. O QUE FAZER: rode medir de novo em alguns "
    "minutos. Se continuar, abra {tela}, que lê a mesma contagem e diz se a "
    "medição está fora do ar."
)

MEDICAO_INCOERENTE = (
    "PAROU POR SEGURANÇA: a medição respondeu à contagem do A/A {id} fora do "
    "combinado: {frase}. Nenhum número foi dado como certo, e nada foi mudado. "
    "O QUE FAZER: abra {tela}, que lê a mesma resposta, e corrija a contagem na "
    "célula metricas antes de confiar no ensaio."
)


def e_o_aa(experimento: dict) -> bool:
    """A assinatura inteira: hipótese exata, o espaço, duas variantes, um texto."""
    variantes = experimento.get("variantes") or []
    espaco = f"{experimento.get('secao')}.{experimento.get('slot')}"
    if experimento.get("hipotese") != HIPOTESE:
        return False
    if espaco != ESPACO_PADRAO:
        return False
    if len(variantes) < 2:
        return False
    if len(_textos(experimento)) != 1:
        return False
    return True


def _textos(experimento: dict) -> set:
    return {v.get("valor") for v in experimento.get("variantes") or []}


def _texto(experimento: dict) -> str:
    return (experimento.get("variantes") or [{}])[0].get("valor") or ""


def _aa_ativo(lista: list[dict]) -> "dict | None":
    return next((e for e in lista if e.get("estado") == "ativo" and e_o_aa(e)), None)


def _outro_no_ar(outro: dict) -> str:
    return (
        "PAROU POR SEGURANÇA: a página já tem outro experimento ativo, "
        f"{outro.get('id')} no espaço {outro.get('secao')}.{outro.get('slot')}, "
        f"com a hipótese \"{outro.get('hipotese')}\". Só um experimento fica no "
        "ar por página, e este comando nunca mexe num experimento que não é o "
        "A/A. Nada foi alterado. O QUE FAZER: decida esse experimento em "
        f"{tela_de_decisao(outro.get('id'))} (Encerrar) e rode de novo."
    )


def _releitura_errada(alvo: str, estado: str, lido: str) -> str:
    return (
        f"Pedi o estado {estado} ao A/A {alvo} e a releitura no catálogo diz "
        f"{lido}. Não é o que foi pedido, e nada foi dado como pronto. O QUE "
        f"FAZER: confira o experimento em {tela_de_decisao(alvo)} antes de rodar "
        "de novo."
    )


def _forma(relido: dict) -> str:
    return (
        f"{len(relido.get('variantes') or [])} variante(s), "
        f"{len(_textos(relido))} texto(s), espaço "
        f"{relido.get('secao')}.{relido.get('slot')} e hipótese "
        f"\"{relido.get('hipotese')}\""
    )


def divergencia_da_releitura(relido: dict, alvo: str, estado: str) -> str:
    """A frase da parada quando a releitura não é o pedido; vazio quando bate."""
    decisao = "encerrar" if estado == "encerrado" else None
    lido = f"estado {relido.get('estado')} e decisão {relido.get('decisao')}"
    no_ar = {"id": alvo, "tela": tela_de_decisao(alvo)}
    if relido.get("estado") != estado:
        return _releitura_errada(alvo, estado, lido)
    if relido.get("decisao") != decisao:
        return _releitura_errada(alvo, estado, lido)
    if estado == "ativo" and len(_textos(relido)) > 1:
        return NO_AR_COM_TEXTOS_DIFERENTES.format(**no_ar)
    if not e_o_aa(relido):
        return _releitura_errada(alvo, estado, _forma(relido))
    return ""


def _srm(srm) -> str:
    if srm.p is None:
        return "sem ninguém"
    return f"{'alarme' if srm.alarme else 'ok'} (p {srm.p:.4f})"


class Command(BaseCommand):
    help = (
        "Liga (iniciar-aa), desliga (encerrar) ou mede (medir) o A/A técnico da "
        f"página de oferta de {HOST}, pelas mesmas regras, medição e auditoria "
        "das telas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--acao", required=True, choices=("iniciar-aa", "encerrar", "medir")
        )

    def handle(self, *args, acao: str, **options):
        site = CatalogoClient().site_por_host(HOST)
        if site is None:
            raise CommandError(SEM_SITE)
        self.site = site
        situacao, lista = CatalogoClient().experimentos_da_pagina(
            site["id"], SLUG_DA_PAGINA
        )
        if situacao != CatalogoClient.OK:
            raise CommandError(
                f"Não consegui ler os experimentos da página {SLUG_DA_PAGINA} "
                f"({lista}). Nada foi alterado. O QUE FAZER: rode de novo em "
                "alguns minutos."
            )
        acoes = {
            "iniciar-aa": self._iniciar,
            "encerrar": self._encerrar,
            "medir": self._medir,
        }
        acoes[acao](lista)

    # ------------------------------------------------------------------ ligar
    def _iniciar(self, lista: list[dict]) -> None:
        no_ar = _aa_ativo(lista)
        if no_ar is not None:
            return self._pronto(str(no_ar["id"]), "ativo")
        ativos = [e for e in lista if e.get("estado") == "ativo"]
        if ativos:
            raise CommandError(_outro_no_ar(ativos[0]))

        situacao, publicado = texto_no_ar(self.site, ESPACO_PADRAO)
        if situacao != CatalogoClient.OK:
            raise CommandError(
                f"Não consegui ler o texto no ar de {ESPACO_PADRAO} ({publicado}). "
                f"Nada foi alterado. O QUE FAZER: confira em {TELA_DA_PAGINA} que "
                f"a página {SLUG_DA_PAGINA} foi publicada e rode de novo."
            )
        if not publicado.strip():
            raise CommandError(TITULO_VAZIO)

        rascunho = next(
            (e for e in lista if e.get("estado") == "rascunho" and e_o_aa(e)), None
        )
        alvo = None
        if rascunho is not None and _texto(rascunho) != publicado:
            # A página mudou desde o rascunho: iniciá-lo poria no ar `a` novo
            # contra `b` velho, que já não é A/A.
            self._decidir_encerrar(str(rascunho["id"]))
        elif rascunho is not None:
            alvo = str(rascunho["id"])
        alvo = alvo or self._criar(publicado)

        situacao, resposta = iniciar_experimento(ATOR, self.site, alvo)
        if situacao != CatalogoClient.OK:
            raise CommandError(
                f"O A/A {alvo} está em rascunho e o catálogo não o pôs no ar "
                f"({resposta}). O site não mudou. O QUE FAZER: rode de novo; o "
                "rascunho é reaproveitado e nenhum outro nasce."
            )
        self._pronto(alvo, "ativo")

    def _criar(self, publicado: str) -> str:
        escrito = dict.fromkeys(CAMPOS, "")
        escrito.update(PLANO, texto_b=publicado)
        erros = recusas_do_plano(escrito)
        if erros:
            raise CommandError(
                "A tela recusaria este plano: "
                + " ".join(erros.values())
                + " Nada foi alterado. O QUE FAZER: corrija o PLANO em "
                "apps/core/management/commands/semear_experimento.py."
            )
        situacao, resposta = criar_rascunho(ATOR, self.site, escrito)
        if situacao != CatalogoClient.OK:
            raise CommandError(
                f"O catálogo não criou o A/A ({resposta}). Nada foi ao ar. O QUE "
                "FAZER: rode de novo em alguns minutos."
            )
        return str(resposta["id"])

    def _decidir_encerrar(self, alvo: str) -> None:
        """Encerra pela decisão da tela, com a trava e a auditoria dela."""
        desfecho = decidir(ATOR, self.site["id"], alvo, "encerrar", None, False)
        if desfecho.estado not in ("feito", "repetido"):
            raise CommandError(
                f"O catálogo não encerrou o A/A {alvo}: {desfecho.frase} O QUE "
                "FAZER: rode de novo; encerrar duas vezes não repete nada."
            )

    # --------------------------------------------------------------- desligar
    def _encerrar(self, lista: list[dict]) -> None:
        aa = _aa_ativo(lista)
        if aa is None:
            self.stdout.write(
                f"PRONTO: nada a encerrar em {HOST}, nenhum A/A ativo na "
                f"página {SLUG_DA_PAGINA}. Nada foi alterado."
            )
            return
        self._decidir_encerrar(str(aa["id"]))
        self._pronto(str(aa["id"]), "encerrado")

    # ------------------------------------------------------------------ medir
    def _medir(self, lista: list[dict]) -> None:
        """A contagem por braço, pela conta da tela de resultado. Só lê."""
        aa = _aa_ativo(lista)
        if aa is None:
            self.stdout.write(
                f"PRONTO: nada a medir em {HOST}, nenhum A/A ativo na página "
                f"{SLUG_DA_PAGINA}. Nada foi lido da medição. O QUE FAZER: ligue "
                "o A/A com a ação iniciar-aa e meça de novo."
            )
            return
        alvo = str(aa["id"])
        contagem = contar(self.site["id"], aa, timezone.localdate())
        campos = {**contagem, "id": alvo, "tela": tela_de_resultado(alvo)}
        if contagem["estado"] == "medicao-nao-respondeu":
            raise CommandError(MEDICAO_FORA.format(**campos))
        if contagem["estado"] == "fora-do-contrato":
            raise CommandError(MEDICAO_INCOERENTE.format(**campos))
        janela = f"janela {contagem['desde']:%d/%m/%Y} a {contagem['ate']:%d/%m/%Y}"
        if contagem["estado"] == "sem-coleta":
            self.stdout.write("Nenhum evento do funil chegou na janela.")
            zeros = "atribuidos=0 expostos=0 convertidos=0"
            pesos = contagem["experimento"]["pesos"]
            bracos = "; ".join(f"{v} {zeros}" for v in pesos)
            return self._contagem(alvo, janela, f"{bracos}; trocados=0")

        r = contagem["resultado"]
        bracos = "; ".join(
            f"{b.variante_id} atribuidos={b.atribuidos} expostos={b.expostos} "
            f"convertidos={b.convertidos}"
            for b in (r.controle, r.tratamento)
        )
        self.stdout.write(
            "convertidos = quem, exposto ao título, clicou para o checkout "
            f"(métrica {aa.get('metrica_principal')}). Tela: {campos['tela']}"
        )
        numeros = (
            f"{bracos}; trocados={r.trocados}; srm atribuidos="
            f"{_srm(r.srm_atribuidos)}, expostos={_srm(r.srm_expostos)}; "
            f"veredito {r.veredito}"
        )
        self._contagem(alvo, janela, numeros)

    def _contagem(self, alvo: str, janela: str, numeros: str) -> None:
        linha = f"PRONTO: contagem do A/A {alvo} em {HOST}, {janela}: {numeros}"
        self.stdout.write(linha)

    # ------------------------------------------------------------------ prova
    def _pronto(self, alvo: str, estado: str) -> None:
        """Relê no catálogo, por fora da chamada que mudou, e só então diz PRONTO."""
        situacao, relido = CatalogoClient().experimento(
            self.site["id"], SLUG_DA_PAGINA, alvo
        )
        if situacao != CatalogoClient.OK:
            raise CommandError(
                f"Pedi o estado {estado} ao A/A {alvo} e não consegui relê-lo "
                f"({relido}). O QUE FAZER: rode de novo; o comando é idempotente."
            )
        divergencia = divergencia_da_releitura(relido, alvo, estado)
        if divergencia:
            raise CommandError(divergencia)
        if estado == "encerrado":
            self.stdout.write(
                f"PRONTO: A/A encerrado em {HOST}, experimento {alvo}, "
                "estado encerrado, decisão encerrar."
            )
        else:
            self.stdout.write(
                f"PRONTO: A/A ativo em {HOST}, experimento {alvo}, estado "
                f"ativo, {len(relido['variantes'])} variantes com o mesmo texto."
            )
