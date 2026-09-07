"""O Revisor de coerencia: codigo, nao IA. Ele APONTA, e nunca corrige.

Degrau 3.1 da escada (`docs/decisoes/PLANO-CELULA-CURSOS.md` §10), e o primeiro
verificador desta celula. A linha "Revisor de coerencia" do §7 lista as seis
conferencias, e elas sao exatamente as seis funcoes deste arquivo:

1. toda remissao "E[NN]" aponta para aula existente do mesmo curso;
2. instrumentos e defeitos citados pelo nome canonico;
3. nomes de arquivo identicos entre as pecas da mesma aula;
4. numeros repetidos iguais entre pecas;
5. o "Aceito quando" da peca "Voce faz" igual a lista do checkpoint;
6. nenhum numero de plataforma no corpo.

Nao ha modelo de linguagem aqui, e a ausencia e o desenho: o §7 poe este agente
no degrau A ("sem modelo: codigo"). Nada aqui sai para a rede, nada aqui grava,
e `conferir` e uma leitura sobre uma `Aula` que o chamador ja carregou.

O MODO DE FALHAR DESTE VERIFICADOR E O FALSO POSITIVO
-----------------------------------------------------
O §7 mede este agente por "zero falso positivo em amostra da professora", e a
razao e humana: um revisor que grita onde nao ha defeito e desligado na terceira
vez, e a partir dai o defeito de verdade passa sozinho. Por isso toda regra
daqui so dispara quando a divergencia e MECANICAMENTE CERTA, e o empate e
sempre a favor do silencio:

- a remissao so e quebrada quando o numero nao existe no curso;
- o nome fora do canonico exige que o texto tenha escrito O MESMO nome de outro
  jeito; a forma exata nunca dispara, e a primeira letra em caixa diferente
  tambem nao, porque comeco de frase e maiuscula em portugues;
- a lista do checkpoint so se compara quando a peca declara "Aceito quando";
- a contagem que a plataforma calcula so dispara quando a peca CRAVA o numero.

Quem quiser acrescentar uma setima conferencia comeca por esta pergunta: existe
texto legitimo que ela reprovaria? Se existe, ela nao entra.

O QUE O REVISOR LE, E O QUE ELE NAO LE
---------------------------------------
Ele le AS PECAS da aula, que e onde o texto mora, e os campos que a plataforma
calcula (`aceito_quando`) como termo de comparacao, nunca como texto a
vasculhar.

A conferencia 6 e a unica que olha um subconjunto: ela roda so no que O ALUNO
LE (as 16 da anatomia e a video-aula em texto), e deixa em paz o `roteiro` e o
`guia_do_mentor`. Os dois sao a mesa de trabalho da professora, e "hoje o limite
e 20 mil triangulos" e uma anotacao legitima para ela; a lei que proibe o numero
("botoes envelhecem, principios nao", §0 do plano) fala do texto do capitulo,
que e o que envelhece na mao do aluno.

Guardas: `tests/test_coerencia.py` (as seis, mais a aula limpa) e
`tests/test_inv_c1_remissao_quebrada_nao_publica.py` ([INV-CUR-C1]).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from apps.cursos.models import Aula, Instrumento, Peca

REMISSAO_QUEBRADA = "remissao_quebrada"
NOME_FORA_DO_CANONICO = "nome_fora_do_canonico"
NOME_DE_ARQUIVO_DIVERGENTE = "nome_de_arquivo_divergente"
NUMERO_DIVERGENTE = "numero_divergente"
ACEITO_QUANDO_DIVERGENTE = "aceito_quando_divergente"
NUMERO_DE_PLATAFORMA = "numero_de_plataforma"


@dataclass(frozen=True)
class Defeito:
    """Um defeito apontado, com endereco e conserto.

    `peca` e o tipo da peca onde ele esta (o vocabulario de `Peca.Tipo`), ou
    texto vazio quando o defeito e da aula inteira e nao de uma peca so.

    `alvo` e o pedaco de texto em falta: a remissao, a grafia errada, o nome do
    arquivo, o numero. Ele existe porque quem le o defeito precisa poder
    PROCURAR a coisa, e porque a recusa de publicar cita os alvos sem ter de
    despedacar a frase para achar o numero de volta.

    `impede_publicar` e verdadeiro em UM codigo, e so nele: a remissao quebrada,
    que e o [INV-CUR-C1]. Os outros cinco sao aviso, e a aula publica com eles.
    Apontar nao e vetar, e o §7 so pos o veto na remissao.
    """

    codigo: str
    peca: str
    alvo: str
    frase: str
    o_que_fazer: str

    @property
    def impede_publicar(self) -> bool:
        return self.codigo == REMISSAO_QUEBRADA


# ---------------------------------------------------------------------------
# AS FERRAMENTAS DE COMPARACAO
# ---------------------------------------------------------------------------
# Comparar texto de livro exige decidir o que conta como "a mesma palavra".
# A regua e uma so e vale para as seis conferencias: sem acento, em caixa
# baixa, com os espacos colapsados. Ela serve para ACHAR o candidato; quem
# decide se ha defeito e sempre a comparacao com a forma EXATA.

_VOGAIS_COM_ACENTO = {
    "a": "aáàâãä",
    "e": "eéèêë",
    "i": "iíìîï",
    "o": "oóòôõö",
    "u": "uúùûü",
    "c": "cç",
    "n": "nñ",
}

# "letra" para efeito de fronteira de palavra inclui as acentuadas: o `\b` do
# `re` corta antes do acento e faria "topologia" casar dentro de "topologias".
_LETRA = r"[^\W\d_]"
_ANTES = r"(?<!" + _LETRA + r")(?<![\d_])"
_DEPOIS = r"(?!" + _LETRA + r")(?![\d_])"


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(letra for letra in decomposto if not unicodedata.combining(letra))


def _chave(texto: str) -> str:
    return " ".join(_sem_acento(texto).lower().split())


def _padrao_frouxo(nome: str) -> re.Pattern[str]:
    """O nome como expressao que ignora acento, caixa e quantidade de espaco.

    E com ela que se ACHA no texto o lugar onde alguem escreveu este nome de
    outro jeito. Achar nao e acusar: quem acusa e `_e_o_mesmo_nome`.
    """
    partes = []
    for letra in _sem_acento(nome).lower():
        if letra in _VOGAIS_COM_ACENTO:
            partes.append("[" + _VOGAIS_COM_ACENTO[letra] + "]")
        elif letra.isspace():
            partes.append(r"\s+")
        else:
            partes.append(re.escape(letra))
    return re.compile(_ANTES + "".join(partes) + _DEPOIS, re.IGNORECASE)


def _e_o_mesmo_nome(achado: str, canonico: str) -> bool:
    """Duas grafias que a casa considera A MESMA, e por isso nao viram defeito.

    A forma exata, claro. E a que difere SO na caixa da primeira letra, porque
    em portugues comeco de frase e maiuscula: cobrar "n-gon" de quem escreveu
    "N-gon" no comeco de uma frase seria o falso positivo mais barato de
    produzir e o mais caro em confianca. Acento na primeira letra ja e
    diferenca de verdade, e por isso a comparacao o mantem.
    """
    if achado == canonico:
        return True
    return achado[:1].lower() == canonico[:1].lower() and achado[1:] == canonico[1:]


def _textos_das_pecas(aula: Aula) -> list[tuple[str, str]]:
    """As pecas da aula como pares (tipo, texto), sem as vazias."""
    return [
        (peca.tipo, peca.texto)
        for peca in aula.pecas.all()
        if (peca.texto or "").strip()
    ]


# ---------------------------------------------------------------------------
# 1. A REMISSAO QUEBRADA, a unica que impede publicar ([INV-CUR-C1])
# ---------------------------------------------------------------------------
# `\d{2,}` e nao `\d{2}`: "E100" e uma remissao quebrada tao real quanto "E99",
# e um `\d{2}` cravado a deixaria passar calada por nao fechar a borda.
_REMISSAO = re.compile(_ANTES + r"E(\d{2,})" + _DEPOIS)


def remissoes_quebradas(aula: Aula) -> list[Defeito]:
    """Toda "E[NN]" citada nas pecas aponta para aula existente do mesmo curso.

    O universo e o CURSO da aula, lido do banco, e nao a tupla `NUMEROS_DE_AULA`
    do modelo: um curso pode ter sido instalado com menos encomendas, e o que
    importa a quem clica e se a aula existe naquele curso, nao se o numero e
    legal no vocabulario.
    """
    existentes = set(
        Aula.objects.filter(curso_id=aula.curso_id).values_list("numero", flat=True)
    )
    defeitos = []
    for tipo, texto in _textos_das_pecas(aula):
        vistas: set[str] = set()
        for achado in _REMISSAO.finditer(texto):
            numero = "E" + achado.group(1)
            if numero in existentes or numero in vistas:
                continue
            vistas.add(numero)
            defeitos.append(
                Defeito(
                    codigo=REMISSAO_QUEBRADA,
                    peca=tipo,
                    alvo=numero,
                    frase=(
                        f"esta peca manda o aluno para a encomenda {numero}, "
                        f"e {numero} nao existe neste curso"
                    ),
                    o_que_fazer=(
                        "troque pelo numero da encomenda certa, ou tire a "
                        "remissao. Enquanto ela estiver aqui, esta aula nao "
                        "publica."
                    ),
                )
            )
    return defeitos


# ---------------------------------------------------------------------------
# 2. O NOME FORA DO CANONICO: instrumentos e defeitos
# ---------------------------------------------------------------------------
# Os nomes canonicos dos INSTRUMENTOS sao DADO: os 13 estao no banco desde o
# semeador, com `nome_canonico`. Os nomes canonicos dos DEFEITOS tambem sao
# dado, e a fonte deles e a propria aula: a peca "Erros classicos" e onde o
# livro batiza cada defeito, e o nome e o que ela poe em negrito no comeco do
# item. Nao ha lista de defeitos escrita neste arquivo, e nao pode haver: seria
# a mesma frase em dois lugares, e no dia em que a professora renomeasse um
# defeito o codigo continuaria cobrando o nome velho.
_DEFEITO_BATIZADO = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s*\*\*(.+?)\*\*", re.MULTILINE)


def _defeitos_batizados(aula: Aula) -> list[str]:
    """Os nomes que a peca "Erros classicos" desta aula da aos defeitos.

    Sem a peca, ou sem negrito nela, a lista e vazia e a conferencia fica
    calada: e o empate a favor do silencio. Adivinhar o nome de um defeito a
    partir de prosa corrida seria o falso positivo que o §7 proibe.
    """
    for tipo, texto in _textos_das_pecas(aula):
        if tipo == Peca.Tipo.ERROS_CLASSICOS:
            return [
                achado.group(1).strip() for achado in _DEFEITO_BATIZADO.finditer(texto)
            ]
    return []


def nomes_fora_do_canonico(aula: Aula) -> list[Defeito]:
    """Instrumento e defeito escritos de um jeito diferente do nome canonico."""
    canonicos = [
        (nome.strip(), "instrumento")
        for nome in Instrumento.objects.values_list("nome_canonico", flat=True)
        if nome and nome.strip()
    ]
    canonicos += [(nome, "defeito") for nome in _defeitos_batizados(aula) if nome]

    defeitos = []
    for tipo, texto in _textos_das_pecas(aula):
        for canonico, especie in canonicos:
            vistas: set[str] = set()
            for achado in _padrao_frouxo(canonico).finditer(texto):
                grafia = achado.group(0)
                if _e_o_mesmo_nome(grafia, canonico) or grafia in vistas:
                    continue
                vistas.add(grafia)
                defeitos.append(
                    Defeito(
                        codigo=NOME_FORA_DO_CANONICO,
                        peca=tipo,
                        alvo=grafia,
                        frase=(
                            f"esta peca escreve '{grafia}', e o nome canonico "
                            f"deste {especie} e '{canonico}'"
                        ),
                        o_que_fazer=(
                            f"escreva '{canonico}'. O aluno procura pelo nome "
                            "que o livro deu, e duas grafias viram duas coisas "
                            "na cabeca dele."
                        ),
                    )
                )
    return defeitos


# ---------------------------------------------------------------------------
# 3. O NOME DE ARQUIVO QUE MUDA DE UMA PECA PARA A OUTRA
# ---------------------------------------------------------------------------
# As extensoes sao as do oficio (modelagem 3D e Roblox) mais as de imagem que
# uma encomenda entrega. A lista e fechada de proposito: reconhecer "qualquer
# palavra com ponto no meio" acharia "versao 2.0" e encheria a tela de defeito
# que nao existe.
#
# O nome nao pode conter espaco, e isso nao e descuido: com espaco dentro, o
# casamento mais a esquerda de "o arquivo cubo.blend" e a frase inteira, e o
# revisor passaria a comparar prosa em vez de nome de arquivo.
_ARQUIVO = re.compile(
    r"(?<![\w./-])([^\W\d_][\w.-]{0,60}?)"
    r"\.(blend|fbx|obj|rbxm|rbxl|png|jpg|jpeg|psd|tga|zip|mp4)" + _DEPOIS,
    re.IGNORECASE,
)


def nomes_de_arquivo_divergentes(aula: Aula) -> list[Defeito]:
    """O mesmo arquivo citado com grafias diferentes entre as pecas da aula.

    "Mesmo arquivo" e o nome sem acento, em caixa baixa, com `-` e `_` valendo
    a mesma coisa: e exatamente por esses tres caminhos que um nome de arquivo
    se deforma ao ser recopiado de uma peca para outra, e e o aluno quem paga,
    procurando no disco um arquivo que nao esta com aquele nome.
    """
    achados: dict[str, list[str]] = {}
    for _tipo, texto in _textos_das_pecas(aula):
        for achado in _ARQUIVO.finditer(texto):
            inteiro = achado.group(0).strip()
            chave = _chave(inteiro).replace("_", "-").replace(" ", "")
            grafias = achados.setdefault(chave, [])
            if inteiro not in grafias:
                grafias.append(inteiro)

    defeitos = []
    for chave in sorted(achados):
        grafias = achados[chave]
        if len(grafias) < 2:
            continue
        defeitos.append(
            Defeito(
                codigo=NOME_DE_ARQUIVO_DIVERGENTE,
                peca="",
                alvo=sorted(grafias)[0],
                frase=(
                    "o mesmo arquivo aparece com nomes diferentes nesta aula: "
                    + ", ".join(f"'{nome}'" for nome in sorted(grafias))
                ),
                o_que_fazer=(
                    "escolha uma grafia e use a mesma em todas as pecas. O "
                    "aluno vai procurar este arquivo no computador dele pelo "
                    "nome que voce escreveu."
                ),
            )
        )
    return defeitos


# ---------------------------------------------------------------------------
# 4. O NUMERO QUE MUDA DE UMA PECA PARA A OUTRA
# ---------------------------------------------------------------------------
# O vocabulario e fechado e curto, e cada palavra dele conta uma coisa que UMA
# encomenda so pode ter em UMA quantidade. "3 minutos" e "5 minutos" na mesma
# aula sao legitimos (o recall dura um tempo, o drill outro), e e por isso que
# tempo NAO entra aqui: entraria so para produzir falso positivo.
#
# "movimento" e "expressao" tambem ficaram de fora, e por um motivo medido: dois
# dos treze instrumentos tem numero no proprio nome ("Prova dos 3 Movimentos",
# "Prova das 5 Expressoes"). Citar o instrumento passaria a contar como contagem
# da aula, e a aula que citasse os dois seria acusada de se contradizer.
_CONTAVEIS = frozenset({"passo", "drill", "etapa"})
_CONTAGEM = re.compile(_ANTES + r"(\d{1,3})\s+([^\W\d_]+)")


def _singular(palavra: str) -> str:
    chave = _chave(palavra)
    return chave[:-1] if chave.endswith("s") else chave


def numeros_divergentes(aula: Aula) -> list[Defeito]:
    """A mesma contagem dita com dois numeros diferentes na mesma aula."""
    contagens: dict[str, set[str]] = {}
    for _tipo, texto in _textos_das_pecas(aula):
        for achado in _CONTAGEM.finditer(texto):
            coisa = _singular(achado.group(2))
            if coisa in _CONTAVEIS:
                contagens.setdefault(coisa, set()).add(achado.group(1))

    defeitos = []
    for coisa in sorted(contagens):
        numeros = contagens[coisa]
        if len(numeros) < 2:
            continue
        ditos = ", ".join(sorted(numeros, key=int))
        defeitos.append(
            Defeito(
                codigo=NUMERO_DIVERGENTE,
                peca="",
                alvo=coisa,
                frase=(
                    f"esta aula diz de mais de um jeito quantos '{coisa}' sao: "
                    f"{ditos}"
                ),
                o_que_fazer=(
                    "confira qual e o numero certo e deixe o mesmo em todas as "
                    "pecas. O aluno conta, e para quando o numero bate."
                ),
            )
        )
    return defeitos


# ---------------------------------------------------------------------------
# 5. O "ACEITO QUANDO" DA PECA "VOCE FAZ" CONTRA A LISTA DO CHECKPOINT
# ---------------------------------------------------------------------------
# A peca 9 da anatomia e "Voce faz (com 'Aceito quando')", e a lista que ela
# escreve e a MESMA que vira o formulario do checkpoint (`aula.aceito_quando`).
# Duas listas que deviam ser uma e o defeito mais caro desta aula: o aluno
# entrega pelo que leu e e conferido por outra coisa.
_ACEITO_QUANDO = re.compile(r"^[#\s>*_]*aceito\s+quando\b.*$", re.IGNORECASE)
_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+?)\s*$")


def _lista_da_peca(texto: str) -> list[str] | None:
    """Os itens listados logo abaixo do "Aceito quando" da peca.

    `None` quando a peca nao declara "Aceito quando": ai nao ha o que comparar,
    e o revisor fica calado. Lista vazia quando declara e nao lista nada, e
    isso e defeito, apontado por quem chama.
    """
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if not _ACEITO_QUANDO.match(linha):
            continue
        itens = []
        for seguinte in linhas[i + 1 :]:
            item = _ITEM.match(seguinte)
            if item:
                itens.append(re.sub(r"[*_`]", "", item.group(1)).strip())
                continue
            if not seguinte.strip():
                continue
            # Prosa ou um cabecalho novo fecham a lista: o que vem depois e
            # outro assunto, e engolir isso encheria a comparacao de linhas
            # que ninguem escreveu como criterio.
            break
        return itens
    return None


def aceito_quando_divergente(aula: Aula) -> list[Defeito]:
    """A lista da peca "Voce faz" e a mesma do formulario do checkpoint."""
    for tipo, texto in _textos_das_pecas(aula):
        if tipo != Peca.Tipo.VOCE_FAZ:
            continue
        na_peca = _lista_da_peca(texto)
        if na_peca is None:
            return []
        no_formulario = [str(item).strip() for item in (aula.aceito_quando or [])]
        if [_chave(item) for item in na_peca] == [
            _chave(item) for item in no_formulario
        ]:
            return []
        return [
            Defeito(
                codigo=ACEITO_QUANDO_DIVERGENTE,
                peca=tipo,
                alvo="Aceito quando",
                frase=(
                    f"o 'Aceito quando' desta peca lista {len(na_peca)} "
                    f"criterio(s) e o formulario do checkpoint tem "
                    f"{len(no_formulario)}, e eles nao sao os mesmos"
                ),
                o_que_fazer=(
                    "deixe as duas listas iguais, no campo 'Aceito quando' "
                    "desta tela e no texto da peca. O aluno entrega pelo que "
                    "leu na peca, e e conferido pelo formulario."
                ),
            )
        ]
    return []


# ---------------------------------------------------------------------------
# 6. O NUMERO DE PLATAFORMA NO CORPO
# ---------------------------------------------------------------------------
# "Botoes envelhecem, principios nao" (§0 do plano): nenhum numero de
# plataforma em texto de capitulo, porque o capitulo fica e o numero muda. Sao
# duas familias, e as duas sao de plataforma pelo mesmo motivo:
#
# - o que o Roblox decide e muda sozinho: limite de triangulos, taxa, prazo de
#   moderacao;
# - o que ESTA plataforma calcula para esta aula: quantas pausas o video tem,
#   quantas perguntas o quiz faz, quantos criterios o checkpoint confere. Aqui
#   o numero esta errado mesmo quando esta certo hoje, porque quem o conta e a
#   tela, e a peca que o crava passa a mentir no dia seguinte a uma edicao.
_DE_FORA = (
    "triangulo",
    "tris",
    "poligono",
    "robux",
    "taxa",
    "comissao",
    "moderacao",
    "prazo",
)
_CALCULADAS = re.compile(
    _ANTES + r"(\d{1,4})\s+(pausas?|perguntas?|crit[eé]rios?)" + _DEPOIS,
    re.IGNORECASE,
)
_FRASE = re.compile(r"[^.!?\n]+")
_TEM_NUMERO = re.compile(r"\d")


def numeros_de_plataforma(aula: Aula) -> list[Defeito]:
    """Numero de plataforma cravado no que o aluno le."""
    do_aluno = set(Peca.ORDEM_CANONICA) | set(Peca.TIPOS_SOB_DEMANDA)
    defeitos = []
    for tipo, texto in _textos_das_pecas(aula):
        if tipo not in do_aluno:
            continue
        for frase in _FRASE.finditer(texto):
            trecho = frase.group(0).strip()
            if not _TEM_NUMERO.search(trecho):
                continue
            chave = _chave(trecho)
            citados = [termo for termo in _DE_FORA if termo in chave]
            if citados:
                defeitos.append(
                    Defeito(
                        codigo=NUMERO_DE_PLATAFORMA,
                        peca=tipo,
                        alvo=trecho,
                        frase=(
                            f"esta frase crava um numero que quem decide e o "
                            f"Roblox ({citados[0]}): '{trecho}'"
                        ),
                        o_que_fazer=(
                            "tire o numero do capitulo e aponte para o "
                            "apendice vivo. O capitulo fica; este numero muda "
                            "sem avisar, e o aluno le o antigo."
                        ),
                    )
                )
        for achado in _CALCULADAS.finditer(texto):
            defeitos.append(
                Defeito(
                    codigo=NUMERO_DE_PLATAFORMA,
                    peca=tipo,
                    alvo=achado.group(0),
                    frase=(
                        f"esta peca crava '{achado.group(0)}', e quem conta "
                        "isso e a tela"
                    ),
                    o_que_fazer=(
                        "escreva sem o numero. No dia em que voce acrescentar "
                        "ou tirar uma linha nesta tela, a peca passa a mentir "
                        "e ninguem vai lembrar de vir corrigi-la."
                    ),
                )
            )
    return defeitos


# ---------------------------------------------------------------------------
# A CONFERENCIA INTEIRA
# ---------------------------------------------------------------------------
AS_SEIS = (
    remissoes_quebradas,
    nomes_fora_do_canonico,
    nomes_de_arquivo_divergentes,
    numeros_divergentes,
    aceito_quando_divergente,
    numeros_de_plataforma,
)


def conferir(aula: Aula) -> list[Defeito]:
    """As seis conferencias, na ordem do §7. Aula limpa devolve lista vazia."""
    defeitos: list[Defeito] = []
    for conferencia in AS_SEIS:
        defeitos.extend(conferencia(aula))
    return defeitos


def impedem_publicar(aula: Aula) -> list[Defeito]:
    """So os defeitos que o [INV-CUR-C1] transforma em recusa de publicar."""
    return [defeito for defeito in conferir(aula) if defeito.impede_publicar]
