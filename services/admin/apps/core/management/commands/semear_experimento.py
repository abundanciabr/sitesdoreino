"""`manage.py semear_experimento --host <site> --acao iniciar-aa|encerrar`.

Liga e desliga o A/A técnico da página de oferta sem navegador e sem login: é
o que o robô usa para rodar o ensaio do sistema de experimentos sem o
mantenedor (decisão dele em 27/09/2026). Quem chama é
`infra/semear-experimento.sh`, disparado por `.github/workflows/semear-experimento.yml`.

## A mesma porta da tela, e não um atalho

O comando chama as funções que a tela `/admin/paginas/experimentos/` e a tela
de decisão chamam (`criar_rascunho`, `iniciar`, `decidir`), com as mesmas
recusas, o mesmo catálogo e a mesma auditoria. A única diferença é quem assina
a linha de auditoria: `ATOR`, o semeador pelo pipeline, sem dado de pessoa.

## O que é o A/A, e como ele é reconhecido

Um experimento no espaço `cubo.headline` com a hipótese exata `HIPOTESE` e as
duas variantes com o mesmo texto, que é o texto publicado. Mede o sorteio, a
exposição e a contagem, e não a conversão. Um experimento que não tem essa
assinatura inteira nunca é iniciado nem encerrado por aqui.

## Idempotente, e com a prova relida por fora

A/A já no ar é PRONTO sem escrita. A/A em rascunho é iniciado em vez de
nascer outro. Encerrar sem A/A no ar sai verde sem mudar nada. A linha
`PRONTO:` só sai depois de reler o experimento no catálogo, numa chamada
separada da que o mudou.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError

from apps.core.clients import CatalogoClient
from apps.core.decisao_do_experimento import decidir
from apps.core.experimentos import (
    CAMPOS,
    ESPACO_PADRAO,
    METRICAS,
    _recusas,
    _texto_no_ar,
    criar_rascunho,
    iniciar,
)
from apps.core.paginas import SLUG_DA_PAGINA

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

TELA = "/admin/paginas/experimentos/"

SEM_HOST = (
    "Falta o host do site. Nada foi alterado. O QUE FAZER: rode de novo com "
    "--host, por exemplo --host meshcraft.top."
)

HOST_DESCONHECIDO = (
    "O catálogo não devolveu o site {host}: o host não está cadastrado ou o "
    "catálogo não respondeu. Nada foi alterado. O QUE FAZER: confira a grafia "
    "(sem https:// e sem barra no fim) e rode de novo; se a grafia estiver "
    "certa, rode de novo em alguns minutos."
)


def e_o_aa(experimento: dict) -> bool:
    """A assinatura inteira: hipótese exata, um texto só nas variantes, o espaço."""
    if experimento.get("hipotese") != HIPOTESE:
        return False
    variantes = experimento.get("variantes") or []
    if len({v.get("valor") for v in variantes}) != 1:
        return False
    espaco = f"{experimento.get('secao')}.{experimento.get('slot')}"
    return len(variantes) >= 2 and espaco == ESPACO_PADRAO


def _outro_no_ar(outro: dict, host: str) -> str:
    return (
        "PAROU POR SEGURANÇA: a página já tem outro experimento ativo, "
        f"{outro.get('id')} no espaço {outro.get('secao')}.{outro.get('slot')}, "
        f"com a hipótese \"{outro.get('hipotese')}\". Só um experimento fica no "
        "ar por página, e este comando nunca mexe num experimento que não é o "
        "A/A. Nada foi alterado. O QUE FAZER: decida esse experimento em "
        f"https://{host}{TELA} (Encerrar, na tela de decisão) e rode de novo."
    )


def _texto(experimento: dict) -> str:
    return (experimento.get("variantes") or [{}])[0].get("valor") or ""


class Command(BaseCommand):
    help = (
        "Liga (iniciar-aa) ou desliga (encerrar) o A/A técnico da página de "
        "oferta de um site, pelas mesmas regras e com a mesma auditoria da tela."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--host", default="", help="host do site, por exemplo meshcraft.top"
        )
        parser.add_argument("--acao", required=True, choices=("iniciar-aa", "encerrar"))

    def handle(self, *args, host: str, acao: str, **options):
        host = host.strip().lower()
        if not host:
            raise CommandError(SEM_HOST)
        site = CatalogoClient().site_por_host(host)
        if site is None:
            raise CommandError(HOST_DESCONHECIDO.format(host=host))
        self.host, self.site = host, site
        situacao, lista = CatalogoClient().experimentos_da_pagina(
            site["id"], SLUG_DA_PAGINA
        )
        if situacao != CatalogoClient.OK:
            raise CommandError(
                f"Não consegui ler os experimentos da página {SLUG_DA_PAGINA} "
                f"({lista}). Nada foi alterado. O QUE FAZER: rode de novo em "
                "alguns minutos."
            )
        if acao == "iniciar-aa":
            self._iniciar(lista)
        else:
            self._encerrar(lista)

    # ------------------------------------------------------------------ ligar
    def _iniciar(self, lista: list[dict]) -> None:
        ativos = [e for e in lista if e.get("estado") == "ativo"]
        no_ar = next((e for e in ativos if e_o_aa(e)), None)
        if no_ar is not None:
            return self._pronto(str(no_ar["id"]), "ativo")
        if ativos:
            raise CommandError(_outro_no_ar(ativos[0], self.host))

        situacao, publicado = _texto_no_ar(self.site, ESPACO_PADRAO)
        if situacao != CatalogoClient.OK:
            raise CommandError(
                f"Não consegui ler o texto no ar de {ESPACO_PADRAO} ({publicado}). "
                "Nada foi alterado. O QUE FAZER: confira que a página "
                f"{SLUG_DA_PAGINA} foi publicada e rode de novo."
            )
        if not publicado.strip():
            raise CommandError(
                f"O espaço {ESPACO_PADRAO} está vazio na página no ar, e o A/A "
                "compara esse texto com ele mesmo. Nada foi alterado. O QUE FAZER: "
                f"publique o título em https://{self.host}/admin/paginas/ e rode "
                "de novo."
            )

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

        situacao, resposta = iniciar(ATOR, self.site, alvo)
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
        erros = _recusas(escrito)
        if erros:
            raise CommandError(
                "A tela recusaria este plano: "
                + " ".join(erros.values())
                + " Nada foi alterado. O QUE FAZER: corrija o PLANO em "
                "apps/core/management/commands/semear_experimento.py por PR."
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
        alvo = next(
            (str(e["id"]) for e in lista if e.get("estado") == "ativo" and e_o_aa(e)),
            None,
        )
        if alvo is None:
            self.stdout.write(
                f"PRONTO: nada a encerrar em {self.host}, nenhum A/A ativo na "
                f"página {SLUG_DA_PAGINA}. Nada foi alterado."
            )
            return
        self._decidir_encerrar(alvo)
        self._pronto(alvo, "encerrado")

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
        variantes = relido.get("variantes") or []
        decisao = "encerrar" if estado == "encerrado" else None
        if (
            relido.get("estado") != estado
            or relido.get("decisao") != decisao
            or not e_o_aa(relido)
        ):
            raise CommandError(
                f"Pedi o estado {estado} ao A/A {alvo} e o catálogo diz estado "
                f"{relido.get('estado')}, com {len(variantes)} variantes e "
                f"{len({v.get('valor') for v in variantes})} texto(s). Não é o "
                f"que foi pedido. O QUE FAZER: confira a lista em "
                f"https://{self.host}{TELA} antes de rodar de novo."
            )
        if estado == "encerrado":
            self.stdout.write(
                f"PRONTO: A/A encerrado em {self.host}, experimento {alvo}, "
                f"estado encerrado, decisão {decisao}."
            )
        else:
            self.stdout.write(
                f"PRONTO: A/A ativo em {self.host}, experimento {alvo}, estado "
                f"ativo, {len(variantes)} variantes com o mesmo texto."
            )
