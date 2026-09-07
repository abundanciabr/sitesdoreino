"""`/admin/perpetuo/` — a área do lançamento perpétuo (02/09/2026).

Pedido do mantenedor, na frase dele: *"no painel do admin crie uma parte assim
`/admin/perpetuo` onde iremos criar várias coisas sobre o lançamento perpétuo,
teremos várias páginas, vários painéis"*. Este arquivo é a PORTA dessa área e a
primeira peça dela: **o mapa da máquina, com o estado de cada engrenagem**.

## O que é um lançamento perpétuo, para quem lê esta pasta

Um lançamento comum abre as matrículas por alguns dias e fecha. O perpétuo não
fecha: cada pessoa que chega começa o próprio caminho, no relógio dela. Quem
entrou hoje encontra o mesmo convite que alguém encontrou semana passada, na
mesma ordem, porque quem conduz é a máquina e não o calendário.

Uma máquina dessas tem seis peças, e é isso que a tela desenha. As peças são
CONCEITO (o que cada etapa faz), e conceito não envelhece em silêncio.

## O que mudou em 07/09/2026, e por quê

Até aqui a tela era uma PLANTA: seis caixas, cada uma com os endereços que a
servem. Ela respondia *"de que a máquina é feita"* e deixava sem resposta a
única pergunta que o dono faz ao abrir uma tela chamada lançamento perpétuo:
**ela está girando?**

Agora cada peça traz um veredito, lido AO VIVO de quem tem o dado. Quatro
peças conseguem responder hoje; duas dizem, com o motivo, que a casa ainda não
sabe medir. Nenhuma inventa: a peça que não tem fonte não ganha número
estimado, porque um número inventado numa tela de decisão é pior que a
ausência dele.

## De onde vêm os endereços — e por que esta tela NÃO os escreve

Aqui embaixo, cada etapa lista só o **endereço** das portas que já a servem
hoje. O nome de cada porta, a explicação e o link clicável saem de
`painel/mapa-do-site.json`, que é a única fonte de endereços do projeto — o
`ci/mapa_do_site.py` a confere em todo PR, nos dois sentidos (rota sem entrada
no mapa reprova, entrada sem rota também).

É a lei anti-duplicação do `CLAUDE.md` aplicada: se o nome de uma tela mudasse,
uma cópia dele aqui continuaria mostrando o nome velho, e ninguém saberia qual
das duas está certa. Aqui só mora o que o mapa não sabe: **a qual peça da
máquina cada porta pertence**, que é uma decisão de negócio e não um fato
medível.

**Endereço escrito aqui que não existe no mapa é BURACO, e a tela grita.** A
linha vira um aviso à vista em vez de um link para lugar nenhum, e
`tests/test_perpetuo.py::test_toda_porta_existe_no_mapa_do_site` reprova o PR
antes disso chegar à tela do mantenedor. Um link que devolve 404 é pior que
link nenhum: ele faz o dono concluir que o site quebrou.

## De onde vem o VEREDITO, e por que ele também não mora aqui

Mesma lei, aplicada ao número. Nenhuma contagem nasce neste arquivo: cada peça
pergunta à célula dona, pelo contrato congelado dela (Lei 3), e traduz a
resposta em uma das quatro palavras do vocabulário fechado abaixo. Uma segunda
contagem montada aqui divergiria da tela dona no primeiro estado novo, e o
mantenedor leria a que abrisse primeiro sem saber que a outra discorda.

## O que esta área NÃO faz

Não guarda lista própria de "o que já está pronto" nem de "o que falta". Isso é
superfície paralela de acompanhamento, e o `CLAUDE.md` a proíbe: o que está
pronto se lê no livro de ocorrências, calculado, em `/admin/painel/`.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from django.shortcuts import render
from django.views.decorators.http import require_GET

from .clients import AlunosClient, GamificacaoClient, MensageriaClient

# `_preparar` é REUSADA, e não copiada, de propósito: é ela que decide quando
# um endereço vira link clicável (endereço concreto, público, que não é gesto
# de botão) e quando não vira. Uma segunda cópia dessa regra aqui ofereceria
# link para um molde como `/quiz/quiz/<slug:slug>/`, que devolve 404.
from .mapa_do_site import _preparar, arquivo_do_mapa

# `site_de` é a MESMA leitura de host que a tela do placar usa para saber de
# qual site perguntar. Copiada aqui, esta tela e aquela discordariam sobre qual
# escola estão mostrando no dia em que a plataforma servisse um segundo domínio.
from .placar import site_de

# Reusada de `restricao.py`, e não redefinida: é o mesmo "esperar demais" que o
# placar já usa para chamar a fila de gargalo. Dois números diferentes para a
# mesma ideia fariam esta tela dizer "girando" enquanto a outra diz "entupida".
from .restricao import DIAS_DE_ESPERA_QUE_VIRAM_GARGALO
from .restricao import ETAPAS as PASSAGENS_DO_FUNIL


# ---------------------------------------------------------------------------
# O VEREDITO DE CADA PEÇA (07/09/2026)
# ---------------------------------------------------------------------------
# Vocabulário fechado de propósito: quatro palavras, e não uma frase livre por
# caso. Frase livre vira adjetivo, e adjetivo não se compara entre peças.
#
# A diferença entre `SEM_FONTE` e `NAO_RESPONDEU` é a que mais importa, e é a
# mesma que `restricao.py` já faz: um é **a casa nunca soube medir isto** (falta
# construir a fonte), o outro é **a célula não respondeu agora** (a fonte
# existe, a rede falhou). Achatar os dois num "não sei" mandaria o mantenedor
# procurar defeito onde não há, ou esperar por um número que nunca vai chegar.
GIRANDO = "girando"
PARADA = "parada"
SEM_FONTE = "sem-fonte"
NAO_RESPONDEU = "nao-respondeu"

# As seis peças da máquina, na ordem em que uma pessoa as atravessa: de quem
# nunca ouviu falar da escola até quem já está dentro dela.
#
# `portas` são os endereços EXATOS do `painel/mapa-do-site.json`. Escrever o
# endereço e nada mais é o que mantém esta lista pequena e verdadeira: tudo o
# que se pode medir, o mapa mede.
#
# `sem_fonte_porque` só existe nas peças que a casa AINDA NÃO SABE MEDIR, e o
# texto diz o que falta construir. É o molde de `restricao.py::ETAPAS`, e serve
# à mesma disciplina: a ausência de um número é um fato, e fato se declara. Uma
# peça com fonte não traz este campo, e o veredito dela nasce da leitura.
ETAPAS = (
    {
        "chave": "atrair",
        "nome": "Atrair",
        "pergunta": "Como alguém que nunca ouviu falar da escola chega até aqui?",
        "resumo": (
            "A primeira peça é a mais barata de errar e a mais cara de deixar "
            "parada: sem gente nova entrando, todo o resto da máquina funciona "
            "no vazio. É a vitrine do site e o que aparece no alto de cada "
            "página."
        ),
        "portas": ("/", "/admin/menu/"),
        "sem_fonte_porque": (
            "ninguém conta quantas pessoas visitam o site. Nenhuma parte da "
            "plataforma guarda visita, e é por isso que esta peça não tem "
            "número: a fonte precisa nascer antes da tela."
        ),
    },
    {
        "chave": "capturar",
        "nome": "Capturar o contato",
        "pergunta": "O que a pessoa ganha em troca de deixar o contato dela?",
        "resumo": (
            "Visitante que vai embora sem deixar nada não volta, e a máquina "
            "fica sem como falar com ele de novo. Aqui a troca acontece: a "
            "pessoa recebe algo de valor e deixa nome, e-mail ou WhatsApp."
        ),
        "portas": ("/cadastro", "/quiz/quiz/<slug:slug>/"),
        "sem_fonte_porque": (
            "a parte que recebe os contatos guarda cada um, mas ainda não tem "
            "porta para dizer quantos são. É a mesma falta que a tela do "
            "placar já declara na passagem de quem se cadastrou."
        ),
    },
    {
        "chave": "aquecer",
        "nome": "Aquecer",
        "pergunta": "O que chega até a pessoa depois, sem você precisar mandar?",
        "resumo": (
            "É esta peça que faz o lançamento ser perpétuo: as mensagens saem "
            "sozinhas, na ordem certa, contadas a partir do dia em que aquela "
            "pessoa chegou. Os textos que convencem também moram aqui."
        ),
        # 07/09/2026: a tela das sequências entrou aqui, e a falta dela era o
        # buraco mais grave desta página. A peça se descreve como "as mensagens
        # saem sozinhas" e não oferecia a porta onde essas mensagens se ligam e
        # se desligam: o dono lia a promessa e não tinha como agir sobre ela.
        # Guarda: `test_a_peca_que_faz_o_perpetuo_oferece_o_interruptor_dela`.
        "portas": (
            "/admin/escola/jornadas/",
            "/avisos/ligar",
            "/docs/",
            "/admin/documentos/",
        ),
    },
    {
        "chave": "decidir",
        "nome": "Decidir a entrada",
        "pergunta": "Quem pediu para entrar, e o que você respondeu?",
        "resumo": (
            "O ponto em que a máquina para e espera por você. Toda pessoa que "
            "pede entrada fica numa fila, e cada dia parado nela é um dia de "
            "alguém animado esfriando."
        ),
        "portas": ("/login", "/admin/escola/alunos/", "/admin/escola/turmas/"),
    },
    {
        "chave": "entregar",
        "nome": "Entregar",
        "pergunta": "O que a pessoa encontra quando finalmente entra?",
        "resumo": (
            "A peça que decide se ela fica. Num perpétuo isso importa duas "
            "vezes: aluno satisfeito vira o boca a boca que alimenta a "
            "primeira peça, de graça."
        ),
        "portas": (
            "/forum/",
            "/conquistas/",
            "/forms/sugestoes/",
            "/admin/economia/",
            # 04/09/2026: o quadro de pontos nasceu depois desta área, e
            # entrega é onde ele responde ("quem está jogando, e quem parou").
            "/admin/escola/pontos/",
        ),
    },
    {
        "chave": "medir",
        "nome": "Medir",
        "pergunta": (
            "De cada cem pessoas que chegam, quantas passam para a etapa seguinte?"
        ),
        # O texto NÃO nomeia a tela para onde aponta, e o guarda
        # `test_o_codigo_nao_guarda_copia_do_nome_das_telas` reprovou a primeira
        # versão que nomeava — com razão. Nome de tela citado em prosa envelhece
        # no dia em que alguém a renomeia; o nome vivo vem do mapa, na porta
        # logo abaixo. Isto é a lei desta área funcionando contra quem a
        # escreveu, que é quando dá para confiar nela.
        "resumo": (
            "A peça que transforma melhorar a máquina em decisão, e não em "
            "palpite: quantas pessoas passam de uma etapa para a seguinte, e "
            "em quais delas a casa ainda não sabe medir."
        ),
        # `/admin/placar/` entra aqui em 04/09/2026, e a ordem importa: ele é
        # a tela do funil desta casa (a barra do mês, a meta e a restrição da
        # semana, com pedidos, liberações e tempo típico ao vivo da `alunos`).
        # A área do perpétuo NÃO monta um funil próprio — seria a segunda
        # definição do mesmo fato, e o `CLAUDE.md` a proíbe. Ela aponta.
        "portas": ("/admin/placar/", "/admin/escola/jornada/"),
    },
)


# ---------------------------------------------------------------------------
# AS LEITURAS — uma função por peça, e nenhuma delas toca a rede
# ---------------------------------------------------------------------------
# Cada função recebe o que a célula dona respondeu e devolve o veredito. Elas
# são separadas da rede de propósito: assim o teste prova a REGRA (fila vazia é
# girando, sequência desligada é parada) sem depender de rede nenhuma, e a
# view fica com um trabalho só, que é perguntar.
#
# `None` na entrada é sempre "a célula não respondeu", nunca "o valor é zero".
# Essa distinção é a espinha desta tela: zero pessoas na fila é uma máquina
# saudável, e não conseguir perguntar é uma tela que não sabe de nada.


def _veredito(estado: str, frase: str) -> dict:
    return {"estado": estado, "frase": frase}


def _aquecer(corpo: "dict | None") -> dict:
    """Peça 3: as mensagens saem sozinhas, ou não saem?

    É a peça que define o perpétuo, e por isso o veredito dela é o mais
    valioso da tela: uma sequência desligada não avisa ninguém de que está
    desligada, e o silêncio se parece com "está tudo bem".
    """
    if corpo is None:
        return _veredito(
            NAO_RESPONDEU,
            "A parte que manda as mensagens não respondeu agora. O número volta "
            "sozinho quando ela responder.",
        )
    jornadas = corpo.get("jornadas") or []
    if not jornadas:
        return _veredito(
            PARADA,
            "Nenhuma sequência de mensagens existe ainda. Enquanto não houver "
            "uma, quem se cadastra não recebe nada depois.",
        )
    ligadas = sum(1 for j in jornadas if j.get("ativa"))
    if ligadas == 0:
        return _veredito(
            PARADA,
            f"As {len(jornadas)} sequências existem e estão todas DESLIGADAS. "
            "Ninguém que se cadastrar hoje vai receber mensagem nenhuma.",
        )
    return _veredito(
        GIRANDO,
        f"{ligadas} de {len(jornadas)} sequências ligadas: quem se cadastra "
        "hoje entra nelas sozinho.",
    )


def _decidir(fila: "list | None") -> dict:
    """Peça 4: tem gente esperando resposta sua, e há quanto tempo?

    A única peça da máquina que para e espera por uma pessoa. O veredito olha
    a espera, e não o tamanho da fila: dez pedidos de ontem é uma máquina
    movimentada, e um pedido de cinco dias atrás é alguém desistindo.
    """
    if fila is None:
        return _veredito(
            NAO_RESPONDEU,
            "A parte que guarda os pedidos de entrada não respondeu agora. O "
            "número volta sozinho quando ela responder.",
        )
    if not fila:
        return _veredito(
            GIRANDO, "Ninguém esperando resposta: a fila de entrada está vazia."
        )
    demorando = sum(
        1
        for p in fila
        if isinstance(p.get("esperando_ha_dias"), int)
        and p["esperando_ha_dias"] >= DIAS_DE_ESPERA_QUE_VIRAM_GARGALO
    )
    if demorando:
        return _veredito(
            PARADA,
            f"{len(fila)} pessoas esperando, e {demorando} delas há mais de "
            f"{DIAS_DE_ESPERA_QUE_VIRAM_GARGALO} dias. A máquina parou aqui, "
            "esperando por você.",
        )
    return _veredito(
        GIRANDO,
        f"{len(fila)} pessoas esperando, nenhuma há mais de "
        f"{DIAS_DE_ESPERA_QUE_VIRAM_GARGALO} dias.",
    )


def _entregar(quadro: "list | None") -> dict:
    """Peça 5: quem entrou está fazendo alguma coisa lá dentro?

    Mede pela atividade que a escola registra, e não pela matrícula: gente
    matriculada que nunca voltou é exatamente o que esta peça existe para
    tornar visível.
    """
    if quadro is None:
        return _veredito(
            NAO_RESPONDEU,
            "A parte que guarda os pontos dos alunos não respondeu agora. O "
            "número volta sozinho quando ela responder.",
        )
    if not quadro:
        return _veredito(
            PARADA,
            "Nenhum aluno tem ponto ainda. Ou a escola não está premiando o "
            "que eles fazem, ou eles não estão fazendo.",
        )
    return _veredito(
        GIRANDO,
        f"{len(quadro)} pessoas já pontuaram: o que elas fazem lá dentro está "
        "sendo registrado.",
    )


def _medir() -> dict:
    """Peça 6: de quantas passagens do funil a casa sabe o número?

    ESTA É A ÚNICA PEÇA QUE NÃO PERGUNTA NADA A NINGUÉM, e é de propósito. O
    que ela mede não é um estado que muda de minuto a minuto: é quantas
    passagens do funil TÊM FONTE, um fato que só muda quando alguém constrói a
    fonte que falta. Quem já declara isso, uma por uma e com o motivo, é o
    `ETAPAS` de `restricao.py`, que a tela do placar usa. Ler de lá é o que
    impede as duas telas de discordarem sobre o que a casa sabe medir.
    """
    com_fonte = sum(1 for p in PASSAGENS_DO_FUNIL if p.get("fonte"))
    total = len(PASSAGENS_DO_FUNIL)
    if com_fonte == total:
        return _veredito(
            GIRANDO,
            f"As {total} passagens do funil têm de onde tirar número.",
        )
    if com_fonte == 0:
        return _veredito(
            PARADA,
            f"Nenhuma das {total} passagens do funil tem de onde tirar número.",
        )
    return _veredito(
        PARADA,
        f"De {total} passagens do funil, a casa sabe medir {com_fonte}. As "
        f"outras {total - com_fonte} esperam a parte que guarda a história dos "
        "números, e ela não está ligada.",
    )


# ---------------------------------------------------------------------------
# A REDE — três perguntas, feitas ao mesmo tempo
# ---------------------------------------------------------------------------
# As três células são independentes, e perguntadas em fila indiana a tela do
# dono esperaria a soma dos três tempos limite quando alguma delas estivesse
# fora do ar: doze segundos olhando para o nada. Perguntadas juntas, ela espera
# a mais lenta. É o mesmo `ThreadPoolExecutor` que `views.py` já usa para as
# liberações em lote, pelo mesmo motivo.


def _perguntar_a_todas(site_id: "str | None") -> dict:
    """O que cada célula respondeu, ou `None` para quem não respondeu.

    Sem `site_id` a `mensageria` não tem o que perguntar (as sequências são por
    site), e a resposta dela nasce `None` sem gastar uma viagem de rede. As
    outras duas não dependem do site e continuam valendo.
    """

    def sequencias():
        if site_id is None:
            return None
        return MensageriaClient().jornadas(site_id)

    with ThreadPoolExecutor(max_workers=3) as equipe:
        jornadas = equipe.submit(sequencias)
        fila = equipe.submit(AlunosClient().fila, "aguardando")
        quadro = equipe.submit(GamificacaoClient().quadro)
        return {
            "aquecer": jornadas.result(),
            "decidir": fila.result(),
            "entregar": quadro.result(),
        }


def vereditos(site_id: "str | None") -> dict:
    """O veredito de cada peça, pela chave dela em `ETAPAS`.

    As peças com `sem_fonte_porque` não aparecem aqui: o que elas mostram é o
    motivo escrito na própria peça, e não uma leitura. Inventar um veredito
    para elas seria dar ao mantenedor a impressão de que a casa mediu algo.
    """
    respostas = _perguntar_a_todas(site_id)
    return {
        "aquecer": _aquecer(respostas["aquecer"]),
        "decidir": _decidir(respostas["decidir"]),
        "entregar": _entregar(respostas["entregar"]),
        "medir": _medir(),
    }


# ---------------------------------------------------------------------------
# O MAPA DO SITE — de onde sai o nome e o link de cada porta
# ---------------------------------------------------------------------------


def _mapa_por_endereco() -> "dict | None":
    """O `painel/mapa-do-site.json` indexado pelo endereço, ou `None`.

    `None` é *"não consegui ler o mapa"*, e nunca um dicionário vazio: um vazio
    faria toda porta desta tela virar buraco, e o mantenedor leria "a máquina
    não tem nada" quando a verdade é que o arquivo não veio na imagem.
    """
    caminho = arquivo_do_mapa()
    if caminho is None:
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        entradas = dados["enderecos"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None
    if not isinstance(entradas, list):
        return None
    return {str(e.get("endereco", "")): e for e in entradas if isinstance(e, dict)}


def etapas_com_portas(mapa: "dict | None", estados: "dict | None" = None) -> list[dict]:
    """As seis peças, cada uma com as portas que o mapa do site descreve e o
    veredito de quem tem um.

    Porta que o mapa não conhece NÃO some: ela vira `faltando`, com o endereço
    à vista. Sumir em silêncio é a pior forma de perder um fato, e um endereço
    que mudou de nome sem ninguém avisar é exatamente o caso que esta linha
    existe para tornar visível.

    `estados` ausente devolve as peças sem veredito nenhum, e é assim que os
    guardas do mapa medem as portas sem subir rede.
    """
    estados = estados or {}
    montadas = []
    for etapa in ETAPAS:
        portas = []
        for endereco in etapa["portas"]:
            entrada = None if mapa is None else mapa.get(endereco)
            if entrada is None:
                portas.append({"endereco": endereco, "faltando": True})
                continue
            porta = _preparar(entrada)
            porta["faltando"] = False
            portas.append(porta)
        veredito = estados.get(etapa["chave"])
        if veredito is None and etapa.get("sem_fonte_porque"):
            veredito = _veredito(SEM_FONTE, etapa["sem_fonte_porque"])
        montadas.append({**etapa, "portas": portas, "veredito": veredito})
    return montadas


@require_GET
def perpetuo(request):
    """A porta da área: o mapa da máquina, com o estado de cada peça.

    **Abre com 200 mesmo sem o mapa do site, e a diferença para
    `mapa_do_site.py` (que devolve 500) é deliberada.** Lá, o arquivo É a
    página: sem ele não sobra nada, e uma tela vazia diria "este site não tem
    endereço nenhum". Aqui o arquivo é só a metade dos links: as seis peças da
    máquina continuam verdadeiras sem ele, e a tela diz em voz alta que os
    endereços não puderam ser lidos. Esconder o aviso, esse sim, seria mentira.

    **Célula fora do ar também abre a página**, pelo mesmo princípio: a peça
    que não pôde ser perguntada diz isso, e as outras cinco continuam
    respondendo. Uma tela de operação que não abre é inútil justamente no dia
    em que você precisa dela.
    """
    mapa = _mapa_por_endereco()
    return render(
        request,
        "admin/perpetuo.html",
        {
            "admin": request.admin,
            "etapas": etapas_com_portas(mapa, vereditos(site_de(request))),
            "mapa_ausente": mapa is None,
        },
    )
