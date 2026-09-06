"""Os numeros desta celula que TEM DONO, num lugar so.

Lei: `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`, degrau 15 do §8, na parte que
diz *"tetos de contato como parametro com dono"*.

A DIFERENCA ENTRE UM PARAMETRO E UM LIMIAR DE REGRA
---------------------------------------------------
Nem todo numero deste app mora aqui, e a fronteira nao e de tamanho: e de QUEM
decide.

- **Parametro** e o numero que o MANTENEDOR pode querer diferente sem que a
  logica mude ("quantas mensagens uma pessoa aguenta por semana?"). Ele mora
  aqui, com o dono escrito ao lado, e trocar o valor e uma edicao de arquivo.
- **Limiar de regra** e o numero que faz PARTE da regra ("sumiu ha 7 dias").
  Ele mora na regra, em `proxima_acao.py`, porque troca-lo muda a regra, e
  regra que muda sobe de versao (o guarda de impressao digital cobra isso). Se
  esses limiares morassem aqui, mudariam sem passar pela versao, e a promessa
  do §6.4 do plano (*"regra versionada"*) viraria prosa.

O TETO DIARIO ESTAVA SOLTO NA REGUA, E FOI POR ISSO QUE ELE SE MUDOU PARA CA
----------------------------------------------------------------------------
`regua.TETO_POR_DIA = 1` existia desde 02/09/2026, com a lei citada e sem dono
nenhum. Copiar o numero para ca e deixar la seria dois lugares para o mesmo
fato, que e justamente o que esta casa mais combate: a regua passou a LER daqui.
Ha uma casa so, e ela tem o nome de quem decide.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Parametro:
    """Um numero com dono, unidade e motivo.

    O `dono` vazio LEVANTA, e nao e zelo: parametro sem dono e numero solto com
    uma classe em volta, e a unica coisa que a classe teria acrescentado seria a
    aparencia de governanca. Quem escrever um parametro novo e nao souber de
    quem ele e, descobre aqui, na hora de importar o modulo.
    """

    nome: str
    valor: int
    unidade: str
    dono: str
    porque: str

    def __post_init__(self) -> None:
        if not self.dono.strip():
            raise ValueError(
                f"o parametro {self.nome} nao tem dono declarado; "
                "diga de quem e a decisao antes de usar o numero"
            )


TETO_DE_CONTATO_POR_DIA = Parametro(
    nome="teto de contato por dia",
    valor=1,
    unidade="mensagens por pessoa, por dia",
    dono="o mantenedor",
    porque=(
        "Lei 4 do §3 do PLANO-SEQUENCIAS-DE-MENSAGENS.md: uma por dia, por "
        "pessoa. Quem faz valer e a regua, que le este valor."
    ),
)

TETO_DE_CONTATO_POR_SEMANA = Parametro(
    nome="teto de contato por semana",
    valor=3,
    unidade="mensagens por pessoa, nos ultimos 7 dias",
    dono="o mantenedor",
    porque=(
        "O teto diario sozinho permite 7 mensagens por semana, e 7 semanas "
        "seguidas assim e o que faz um aluno desligar tudo. O padrao nasce em 3 "
        "porque e o maior numero que ainda deixa uma semana com mais silencio "
        "do que fala. Quem faz valer e o roteador da fila de proxima acao, que "
        "e o unico ponto por onde passam tambem os gestos HUMANOS."
    ),
)

# A lista existe para o guarda poder varrer todos sem que ninguem mantenha uma
# copia a mao: parametro novo entra aqui no mesmo diff em que nasce.
PARAMETROS = (TETO_DE_CONTATO_POR_DIA, TETO_DE_CONTATO_POR_SEMANA)
