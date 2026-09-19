"""O consentimento do aluno para a Galeria, e a regra que o traduz em candidata.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
O contrato congelado (`contracts/forum.openapi.yaml`) abre UMA exceção na porta
de máquina do fórum: `GET /galeria/candidatas/{pessoa_id}`. É a única operação
desta célula que fala de área TRANCADA, e o que a torna legítima não é o token
de quem chama, é o gesto de quem escreveu: o aluno marcou o próprio trabalho
para aparecer na Galeria.

Tudo o que decide essa exceção mora AQUI, e numa expressão só. A alternativa
seria a consulta na porta de máquina, o cadeado na tela do aluno e a validação
do endereço em três lugares diferentes, e duas expressões da mesma regra
divergem no primeiro dia em que alguém mexer numa delas. É o mesmo argumento
que já está escrito em `permissoes.py::areas_visiveis` e em `api.py`.

O QUE ESTE ARQUIVO NÃO FAZ
--------------------------
Ele não responde HTTP e não monta página. `apps/core/api.py` traduz o que
está aqui na resposta do contrato, e `apps/core/moderacao.py` recebe o POST do
botão. Assim a regra continua testável sem rede e sem template, e nenhum
`import` circular nasce entre a tela e a porta.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from django.utils import timezone

from apps.forum.models import ConsentimentoDaGaleria, Topico

from .menu import site_id_do_host

# ---------------------------------------------------------------------------
# O que o contrato fixou, e que por isso não é configuração
# ---------------------------------------------------------------------------
# A vitrine é a área `Mostre seu trabalho`, escrita com todas as letras na
# descrição da operação congelada. Consentir num tópico de qualquer outra área
# NÃO o torna candidato: a exceção do contrato é esta área, não "onde alguém
# marcou". É o que impede o gesto de virar uma chave que abre a área de turma.
AREA_DA_GALERIA = "mostre-seu-trabalho"

# O caminho público de uma conversa. Ele é CONTRATO, e não configuração: o
# `pattern` de `url_canonica` exige `^https://[^/]+/forum/t/[^/?#]+$`. Ler o
# prefixo do `FORCE_SCRIPT_NAME` deixaria a resposta fora da forma congelada
# no dia em que o env de um ambiente qualquer viesse diferente.
CAMINHO_PUBLICO_DO_TOPICO = "/forum/t/"

# ---------------------------------------------------------------------------
# A LISTA PERMITIDA — "links externos só de lista permitida"
# ---------------------------------------------------------------------------
# `docs/decisoes/DECISAO-gamificacao.md` §9, e lá está a razão com as palavras
# da lei: *"isto é segurança, não tutela"*. Sem lista, a Galeria da escola vira
# um lugar onde qualquer endereço da internet aparece com o selo da casa.
#
# **É uma constante e não uma variável de ambiente.** Uma variável seria uma
# segunda verdade que vive na VPS, que ninguém revisa e que, ausente, deixaria
# a funcionalidade morta no ar sem ninguém entender por quê. Aqui a lista é
# lida em revisão de código e cresce por PR, que é o degrau certo para uma
# decisão sobre onde a obra de um aluno pode estar hospedada.
#
# Subdomínio conta: `tr.rbxcdn.com` é do mesmo dono que `rbxcdn.com`. O
# endereço do próprio site da escola também entra, e esse não é lista fixa —
# é o host em que o aluno estava quando marcou.
DOMINIOS_PERMITIDOS = ("roblox.com", "rbxcdn.com")

# O que a Galeria pode desenhar como `<img>` sem adivinhar. Endereço sem uma
# destas terminações sai como `link`, que é o lado seguro: um link mostrado
# como link funciona; uma imagem que não é imagem vira um quadrado quebrado.
EXTENSOES_DE_IMAGEM = (".png", ".jpg", ".jpeg", ".gif", ".webp")

# ---------------------------------------------------------------------------
# Os recados da tela. Todo erro diz o que aconteceu E o que fazer.
# ---------------------------------------------------------------------------
ERRO_SEM_ENDERECO = "Ponha o endereço do seu trabalho para ele aparecer na Galeria."
ERRO_ENDERECO_INSEGURO = "O endereço precisa começar com https://."
ERRO_ENDERECO_DE_FORA = (
    "A Galeria aceita trabalho publicado no roblox.com ou aqui mesmo na "
    "escola. Ponha o endereço da sua criação no Roblox."
)
ERRO_SEM_ESCOLA = (
    "Não deu para identificar a escola deste endereço agora. Tente de novo em "
    "alguns instantes e, se continuar assim, avise a equipe."
)
ERRO_ACAO_DESCONHECIDA = "Ação desconhecida nesta caixa da Galeria."


def _host_limpo(host: str) -> str:
    """O domínio sem porta e em minúsculas, como `menu.py` já o trata."""
    return host.split(":")[0].lower()


def _permitido(host: str, host_publico: str) -> bool:
    if host and host == host_publico:
        return True
    return any(
        host == dominio or host.endswith(f".{dominio}")
        for dominio in DOMINIOS_PERMITIDOS
    )


def endereco_aceito(referencia: str, host_publico: str) -> tuple[str, str]:
    """O endereço conferido, ou o recado do porquê não. Nunca levanta.

    Devolve `(endereco, "")` quando passa e `("", recado)` quando não. As duas
    recusas são separadas de propósito: quem escreveu `http://` precisa ouvir
    outra coisa de quem escreveu um site que a escola não aceita.
    """
    endereco = (referencia or "").strip()
    if not endereco:
        return "", ERRO_SEM_ENDERECO
    if not endereco.startswith("https://"):
        return "", ERRO_ENDERECO_INSEGURO
    if not _permitido(_host_limpo(urlsplit(endereco).netloc), host_publico):
        return "", ERRO_ENDERECO_DE_FORA
    return endereco, ""


def tipo_de(endereco: str) -> str:
    """`imagem` só quando dá para afirmar; no resto, `link`."""
    caminho = urlsplit(endereco).path.lower()
    return "imagem" if caminho.endswith(EXTENSOES_DE_IMAGEM) else "link"


def origem_de(endereco: str, host_publico: str) -> str:
    """De onde vem a referência, no vocabulário fechado do contrato."""
    if _host_limpo(urlsplit(endereco).netloc) == host_publico:
        return "forum"
    return "lista_permitida"


def url_canonica(host_publico: str, topico_id: int) -> str:
    """O endereço público da conversa, que reaplica a permissão de leitura.

    Não é destino externo e não abre nada: quem chegar por ele passa pelo mesmo
    `pode_ler` de sempre. Ele existe para a Galeria ter para onde apontar sem
    copiar o conteúdo da conversa.
    """
    return f"https://{host_publico}{CAMINHO_PUBLICO_DO_TOPICO}{topico_id}"


# ---------------------------------------------------------------------------
# A CONSULTA da porta de máquina
# ---------------------------------------------------------------------------
def candidatas(pessoa_id: str, site_id: str) -> list[dict]:
    """As candidatas desta pessoa nesta escola, na forma do contrato.

    Os cinco filtros são a operação inteira, e cada um responde por um modo de
    vazamento: autoria (trabalho de outra pessoa), escola (Lei 9), área (a
    exceção é a vitrine, nunca a área de turma), estado (o que a moderação já
    tirou do ar) e consentimento em pé (o gesto do dono).

    Não trata erro de banco: quem traduz "a fonte não respondeu" em 503 é a
    porta de máquina, porque 503 é palavra de HTTP e não desta regra.
    """
    if not pessoa_id or not site_id:
        # Pedido sem pessoa ou sem escola é pedido que ninguém responde com
        # honestidade. Lista vazia, nunca um erro que conte o que existe.
        return []
    vigentes = (
        ConsentimentoDaGaleria.objects.filter(
            site_id=site_id,
            revogado_em__isnull=True,
            topico__autor_id=pessoa_id,
            topico__estado=Topico.Estado.PUBLICADO,
            topico__area__slug=AREA_DA_GALERIA,
            topico__area__ativa=True,
        )
        .select_related("topico")
        .order_by("-concedido_em")
    )
    return [
        {
            "site_id": marca.site_id,
            "topico_id": str(marca.topico_id),
            "titulo": marca.topico.titulo,
            "referencia": {
                "origem": origem_de(marca.referencia_url, marca.host_publico),
                "tipo": tipo_de(marca.referencia_url),
                "url": marca.referencia_url,
            },
            "url_canonica": url_canonica(marca.host_publico, marca.topico_id),
        }
        for marca in vigentes
    ]


# ---------------------------------------------------------------------------
# O GESTO do aluno
# ---------------------------------------------------------------------------
def pode_decidir(ator, topico) -> bool:
    """Só o dono do trabalho decide se ele aparece, e só na vitrine.

    Nem professor, nem administrador: consentimento dado por outra pessoa não é
    consentimento. Quem não pode decidir não vê a caixa E recebe 404 na rota
    (esconder o botão nunca foi a proteção).
    """
    return (
        ator is not None
        and ator.pessoa is not None
        and topico.autor_id == ator.pessoa.id_da_plataforma
        and topico.area.slug == AREA_DA_GALERIA
    )


def marca_de(topico):
    """O consentimento deste tópico, ou `None`. Uma linha por tópico."""
    return ConsentimentoDaGaleria.objects.filter(topico=topico).first()


def mostrar(request, ator, topico, referencia: str) -> str:
    """Grava o consentimento. Devolve o recado do erro, ou string vazia.

    A escola é resolvida AGORA porque agora é o único momento em que dá: a
    porta de máquina não tem host nem cookie. Catálogo mudo devolve escola
    vazia, e aí o gesto é RECUSADO com recado em vez de gravar uma linha órfã
    que a Galeria jamais conseguiria servir.
    """
    host_publico = _host_limpo(request.get_host())
    endereco, erro = endereco_aceito(referencia, host_publico)
    if erro:
        return erro
    site_id = site_id_do_host(request.get_host())
    if not site_id:
        return ERRO_SEM_ESCOLA

    ConsentimentoDaGaleria.objects.update_or_create(
        topico=topico,
        defaults={
            "site_id": site_id,
            "host_publico": host_publico,
            "referencia_url": endereco,
            "concedido_por": ator.pessoa,
            "concedido_em": timezone.now(),
            # Marcar de novo o que foi retirado é um consentimento NOVO: quem e
            # quando passam a ser os de agora, e a retirada antiga deixa de
            # valer. Guardar as duas datas ao mesmo tempo diria que a obra está
            # exposta e retirada ao mesmo tempo.
            "revogado_em": None,
        },
    )
    return ""


def tirar(topico) -> None:
    """Retira o consentimento sem apagar que ele existiu.

    A linha fica, com a data da retirada. É o que permite responder depois
    "esta obra esteve exposta, e até quando" — a pergunta que ninguém faz antes.
    """
    ConsentimentoDaGaleria.objects.filter(
        topico=topico, revogado_em__isnull=True
    ).update(revogado_em=timezone.now())


def caixa_da_galeria(ator, topico, erro: str = "") -> dict | None:
    """O que a página do tópico mostra ao dono do trabalho, ou `None`.

    `None` é o estado de quase todo mundo: visitante, colega, professor e o
    próprio aluno em conversa fora da vitrine. Para eles a caixa não existe.
    """
    if not pode_decidir(ator, topico):
        return None
    marca = marca_de(topico)
    return {
        "marca": marca if marca is not None and marca.em_pe else None,
        "erro": erro,
    }
