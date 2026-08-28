"""[INVARIANTE] A Mesa é um ESPELHO: ela calcula, não guarda e não escreve.

Dois guardas, e cada um fecha uma porta diferente:

1. **A plateia que a mesa promete é a que o sininho entrega.** A tela diz
   "N pessoas atrás desta ideia"; quando a ideia andar, `avisos.interessados_em()`
   é quem decide quem recebe o aviso. São duas implementações da mesma definição
   — uma em duas consultas por sugestão, outra em duas para a lista inteira —, e
   duas implementações divergem no primeiro ajuste que só uma delas receber. Este
   guarda compara as duas na mesma ideia.

2. **Abrir a mesa não muda nada.** Ela não decide: assinar continua sendo do
   `changespecs.py`, mudar status continua sendo do `moderacao.py`. Uma tela de
   leitura que escreve é como se descobre, tarde, que um relatório estava
   alterando o que relatava.

O motivo de o primeiro existir é a lei anti-duplicação do projeto: nenhum fato
mora em dois lugares. Quando um número precisa aparecer em dois lugares, o que
não pode existir em dois é a REGRA que o produz — e quando ela precisa mesmo
existir duas vezes por custo, o que segura as duas juntas é um guarda como este.
"""

from apps.core.avisos import interessados_em
from apps.core.gestao import plateia_de
from apps.sugestoes.models import (
    Aviso,
    AvaliacaoInterna,
    ChangeSpecAprovado,
    Comentario,
    HistoricoStatus,
    Sugestao,
    Voto,
)


def test_a_plateia_da_mesa_e_a_mesma_do_sininho(sugestao, plateia):
    """Autor, quem comentou e quem votou — cada pessoa contada uma vez só.

    A plateia é montada com sobreposição de propósito: quem comenta E vota tem
    de contar UMA vez, e é justamente aí que duas implementações se separam.
    """
    montada = plateia(sugestao, votantes=7, comentaristas=4, marca="mesa")
    # A mesma pessoa acumulando dois papéis: ela já votou, agora comenta.
    Comentario.objects.create(
        sugestao=sugestao,
        autor=montada["votaram"][0],
        texto="Também sinto isso.",
    )
    # E o próprio autor votando na ideia dele.
    Voto.objects.create(sugestao=sugestao, autor=sugestao.autor)

    pela_mesa = plateia_de([sugestao])[sugestao.id]
    pelo_sininho = len(interessados_em(sugestao))

    assert pela_mesa == pelo_sininho, (
        "a mesa promete uma plateia e o sininho entrega outra — as duas contas "
        "precisam da MESMA definição de 'quem está atrás desta ideia'"
    )


def test_a_plateia_conta_o_autor_mesmo_sem_ninguem_mais(sugestao):
    """Ideia sem voto nenhum tem UMA pessoa atrás dela: quem a escreveu.

    Zero apareceria como "ninguém está esperando", que é falso e é exatamente a
    frase que faria a ideia ser despriorizada para sempre.
    """
    assert plateia_de([sugestao])[sugestao.id] == 1
    assert len(interessados_em(sugestao)) == 1


def test_a_plateia_de_uma_lista_vazia_e_um_mapa_vazio():
    """Sem esta saída o `filter(id__in=[])` viraria uma consulta inútil por página."""
    assert plateia_de([]) == {}


def _retrato():
    """O estado do banco em números — tudo que a mesa poderia tocar sem querer."""
    return {
        "sugestoes": Sugestao.objects.count(),
        "status": sorted(Sugestao.objects.values_list("id", "status")),
        "historico": HistoricoStatus.objects.count(),
        "avaliacoes": AvaliacaoInterna.objects.count(),
        "changespecs": ChangeSpecAprovado.objects.count(),
        "avisos": Aviso.objects.count(),
        "votos": Voto.objects.count(),
        "comentarios": Comentario.objects.count(),
    }


def test_a_leitura_do_contrato_nao_muda_nada_no_banco(
    caixa, equipe, sugestao, plateia, settings, client
):
    """Ela CONTA; não decide, não marca, não arruma.

    Até 28/08/2026 este guarda media a tela da Mesa, que morava nesta célula.
    A tela mudou de casa (DECISAO-a-gestao-da-caixa-mora-no-admin), e a
    propriedade seguiu o dado: quem lê agora é a superfície de máquina, e é ela
    que não pode escrever.

    O cenário é montado cheio de propósito: uma ideia com plateia, outra parada
    esperando assinatura. Uma leitura que "arrumasse" algo — marcar como vista,
    criar a avaliação vazia, gravar um histórico — mudaria um destes números.
    """
    settings.TOKENS_ACEITOS = {"token-do-par-admin-sugestoes"}
    outra = caixa.publicar("Outra ideia qualquer")
    plateia(sugestao, votantes=5, comentaristas=2, marca="retrato")
    caixa.mudar_status(outra, Sugestao.Status.PLANEJADO, nota="Vai entrar.")

    antes = _retrato()
    for _ in range(2):
        resposta = client.get(
            "/interno/gestao/ideias",
            headers={"authorization": "Bearer token-do-par-admin-sugestoes"},
        )
        assert resposta.status_code == 200, resposta.content
    depois = _retrato()

    assert antes == depois
