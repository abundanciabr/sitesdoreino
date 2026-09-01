"""O perfil de quem está olhando a tela, e a escada de níveis dele.

**Nenhuma view calcula nível por conta própria.** A conta mora aqui, num lugar
só, pelo mesmo motivo que `dia_local_de()` mora num lugar só em `models.py`:
duas expressões da mesma regra divergem no primeiro dia em que alguém mexer numa
delas, e aqui divergir significa mostrar ao aluno um número diferente do que o
motor gravou.

**O perfil NASCE ao ser olhado, e isso é decisão.** A alternativa seria criá-lo
quando o primeiro XP chegar, e aí a Base precisaria de uma tela de "você ainda
não tem perfil" que ninguém quer manter. Perfil zerado é um estado legítimo:
significa "entrou hoje, ainda não fez nada", que é a verdade sobre quase todo
aluno no primeiro dia.

O QUE ESTE ARQUIVO NÃO FAZ
--------------------------
Não concede XP, não lê evento, não decide se alguém PODE ver a tela. O motor é
o degrau seguinte da escada (`PLANO-CELULA-GAMIFICACAO.md` §6, passo 8), e quem
responde "pode?" é a `identidade` que já respondeu antes de chegarmos aqui.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.gamificacao.models import NivelDefinicao, Pessoa, PerfilJogador


@dataclass(frozen=True)
class Escada:
    """Onde a pessoa está entre um degrau e o próximo.

    `falta` e `fracao` existem para a barra de progresso não precisar de conta
    nenhuma no template. Template que calcula é template que erra em silêncio,
    e ninguém escreve teste para uma divisão dentro de um `{{ }}`.
    """

    nivel: int
    titulo: str
    xp: int
    xp_do_nivel: int
    xp_do_proximo: int | None
    falta: int | None
    fracao: int  # 0 a 100, já em inteiro, pronto para o `style="width:…%"`
    degraus: int  # quantos degraus ATIVOS a escola ligou. 0 é o estado normal.

    @property
    def montada(self) -> bool:
        """A escola já ligou algum degrau.

        Enquanto for `False`, não existe escada para esta pessoa subir, e a tela
        não pode falar de degrau nenhum — nem do primeiro, nem do último.
        """
        return self.degraus > 0

    @property
    def tem_proximo(self) -> bool:
        """Há um degrau acima deste, e por isso há barra de progresso."""
        return self.xp_do_proximo is not None

    @property
    def no_topo(self) -> bool:
        """Subiu a escada inteira, de verdade.

        **Exige `degraus >= 2`, e essa é a correção de 01/09/2026.** Até aqui
        `no_topo` era só `xp_do_proximo is None`, que é verdade em três
        situações que não têm nada a ver uma com a outra: a pessoa chegou ao
        fim de uma escada de verdade; a escola ligou UM degrau só e não há para
        onde subir; a economia inteira está desligada e não há degrau nenhum.
        Com a economia desligada — o estado de TODO aluno hoje — a Base dizia
        "Nível 1" e, na linha seguinte, "você chegou ao último degrau desta
        escada", com "0 de experiência até aqui" embaixo. O mantenedor leu isso
        na tela dele e as três frases se contradiziam: é a ausência de dado
        sendo lida como conclusão, a mesma doença de `armadilhas/240`.

        Ausência não é conquista. Sem degrau nenhum não há topo; com um degrau
        só, o que existe é uma escada que ainda não abriu o resto.
        """
        return self.degraus >= 2 and self.xp_do_proximo is None

    @property
    def sem_xp(self) -> bool:
        """Ainda não somou experiência nenhuma.

        Existe para a tela poder dizer isso com uma frase em vez de mostrar um
        `0` solto: "0 de experiência até aqui" ao lado de um degrau parece
        placar quebrado, e placar quebrado é o que faz o aluno desconfiar do
        resto da página.
        """
        return self.xp <= 0


def perfil_de(pessoa_id: str, site_id: str) -> PerfilJogador:
    """O perfil desta pessoa neste site, criando-o se for a primeira visita.

    `get_or_create` DENTRO de transação, pelo par `(pessoa, site_id)`, que é o
    `Unique` do modelo. Dois cliques simultâneos na mesma tela não criam dois
    perfis: o banco recusa o segundo, e é o banco que decide isso, nunca uma
    conferência em Python que perde a corrida.

    O espelho `Pessoa` nasce junto, e com o mínimo: o id opaco. E-mail e nome
    ficam para quem os tiver de fato — esta porta não os recebe, e inventar
    string vazia como se fosse dado é pior que a ausência.
    """
    with transaction.atomic():
        pessoa, _ = Pessoa.objects.get_or_create(
            id_da_plataforma=pessoa_id,
            defaults={"email": f"{pessoa_id}@desconhecido.invalid"},
        )
        perfil, _ = PerfilJogador.objects.get_or_create(pessoa=pessoa, site_id=site_id)
    return perfil


def escada_de(perfil: PerfilJogador) -> Escada:
    """A escada vista do degrau em que a pessoa está.

    Lê só `NivelDefinicao` ATIVA: a economia inteira nasce desligada
    (`semear_economia`), e mostrar um degrau que o mantenedor ainda não ligou
    seria a tela prometendo o que a regra não paga.

    **Sem nível nenhum ativo, a resposta é honesta e não quebra:** nível 1, sem
    título, barra vazia, `degraus=0`. É o mesmo espírito da falha ABERTA da
    porta de máquina (`contracts/gamificacao.openapi.yaml`): página sem selo,
    nunca página quebrada.

    **`degraus` viaja junto de propósito, e não é enfeite.** É ele que deixa a
    tela distinguir "não há escada" de "acabou a escada" — duas coisas que o
    `xp_do_proximo is None` sozinho confundia, e que a Base mostrava ao aluno
    como se fossem a mesma (ver `Escada.no_topo`). Quem sabe quantos degraus a
    escola ligou é esta função, que já os contou; devolver o número é mais
    barato e mais honesto do que a tela adivinhar por dedução.
    """
    ativos = list(
        NivelDefinicao.objects.filter(site_id=perfil.site_id, ativa=True).order_by(
            "nivel"
        )
    )
    if not ativos:
        return Escada(
            nivel=perfil.nivel,
            titulo="",
            xp=perfil.xp_total,
            xp_do_nivel=0,
            xp_do_proximo=None,
            falta=None,
            fracao=0,
            degraus=0,
        )

    atual = ativos[0]
    proximo = None
    for degrau in ativos:
        if perfil.xp_total >= degrau.xp_necessario:
            atual = degrau
        else:
            proximo = degrau
            break

    if proximo is None:
        return Escada(
            nivel=atual.nivel,
            titulo=atual.titulo,
            xp=perfil.xp_total,
            xp_do_nivel=atual.xp_necessario,
            xp_do_proximo=None,
            falta=None,
            fracao=100,
            degraus=len(ativos),
        )

    vao = proximo.xp_necessario - atual.xp_necessario
    andado = perfil.xp_total - atual.xp_necessario
    # `vao` nunca é zero (o `Unique` é por número e a escada é crescente), mas
    # um degrau mal cadastrado não derruba a tela de ninguém.
    fracao = int(andado * 100 / vao) if vao > 0 else 0
    return Escada(
        nivel=atual.nivel,
        titulo=atual.titulo,
        xp=perfil.xp_total,
        xp_do_nivel=atual.xp_necessario,
        xp_do_proximo=proximo.xp_necessario,
        falta=proximo.xp_necessario - perfil.xp_total,
        fracao=max(0, min(100, fracao)),
        degraus=len(ativos),
    )
