"""A caixa central de avisos — uma linha por carta recebida.

Lei da gênese: `docs/decisoes/DECISAO-notificacoes.md` (Fase 0) e
`docs/decisoes/DECISAO-fase-2-do-sininho.md` (as três escolhas do mantenedor no
Rito de Contrato de 26/08/2026). Mapa: `docs/notificacoes/PLANO-MESTRE.md` §6.

**Esta célula é BURRA de propósito, e é isso que a mantém barata.** Ela não faz
leque: cada carta que chega no fio (`notificacao.devida.v1`) já vem endereçada a
UMA pessoa, porque quem publica é que faz o fan-out, em lote, na transação do
fato. Aqui uma carta é uma linha. Quando dez células estiverem publicando, o
custo por carta continua o mesmo.
"""

from django.db import models


class Notificacao(models.Model):
    """Um aviso de uma pessoa. DADO, nunca frase pronta.

    **A irreversibilidade que este model existe para respeitar**
    (`DECISAO-notificacoes` §5.1): guardamos `assunto` + `parametros`, e a frase
    nasce na LEITURA, no idioma de quem está lendo. O site serve três idiomas —
    gravar *"Sua ideia mudou para Em desenvolvimento"* congela o idioma de quem
    gravou, e quem lê em espanhol recebe português para sempre. Texto já gravado
    não se traduz depois: por isso é lei, e não recomendação.

    `destinatario_id` e `ator_id` são ids da PLATAFORMA — os únicos que
    atravessam as células. NUNCA e-mail (`DECISAO-EVO-01` §3).
    """

    site_id = models.CharField(max_length=64)
    destinatario_id = models.CharField(max_length=64)
    # Nulável porque nem todo fato tem gente por trás: um pagamento aprovado
    # pelo provedor não tem ator. A carta declara isso no contrato, e a coluna
    # diz a mesma coisa. Decisão do mantenedor: GUARDAR quem mexeu, MOSTRAR "a
    # equipe" — mostrar o nome depois é reversível, não ter guardado não é.
    ator_id = models.CharField(max_length=64, null=True, blank=True)
    assunto = models.CharField(max_length=64)
    parametros = models.JSONField()
    # O event_id do FATO que gerou esta carta. As N cartas de uma mesma mudança
    # compartilham este valor — é o que permite reconstruir o leque inteiro e é
    # a parte "rastreável" da promessa nova (`DECISAO-notificacoes` §2).
    origem_event_id = models.UUIDField()
    criado_em = models.DateTimeField(auto_now_add=True)
    lido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            # O caminho quente é sempre o mesmo: "os avisos DESTA pessoa, os
            # mais novos primeiro" — e o `-criado_em` faz a página 1 sair sem
            # ordenar nada em memória.
            #
            # **`destinatario_id` lidera, e `site_id` nem aparece** — mudou de
            # forma na Fase 4 (`contracts/notificacoes.openapi.yaml`, Rito de
            # 27/08/2026). O índice original da gênese (PR #247) liderava com
            # `site_id`, apostando em como a Fase 4 ainda não escrita iria
            # consultar. Saiu diferente: as três rotas da porta de consulta só
            # recebem `destinatario_id` — "Id da PLATAFORMA da pessoa", nunca
            # site. Um índice liderado por `site_id` obrigaria o Postgres a
            # varrer entradas de todo site para achar as de uma pessoa — hoje
            # inofensivo (um site só em produção), mas o tipo de custo que some
            # do query plan e só aparece quando o segundo site nascer. Dívida
            # anotada, não bug: `LICOES.md` desta célula, seção "site_id no
            # contrato de leitura" (a Lei 9 da CONSTITUICAO continua cumprida
            # do lado da ESCRITA — `site_id` continua gravado em toda linha).
            models.Index(
                fields=["destinatario_id", "-criado_em"],
                name="notif_caixa_da_pessoa",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.assunto}→{self.destinatario_id}"


class ContadorDeNaoLidos(models.Model):
    """Quantos avisos não lidos uma pessoa tem — em UMA linha, lida em O(1).

    **Por que uma tabela e não `COUNT(*)`** (`DECISAO-notificacoes` §5.2): o sino
    aparece em TODA página do site. Um `COUNT(*)` numa tabela que cresce para
    sempre fica lento exatamente quando o produto der certo — e o custo apareceria
    na página inicial de todo mundo, não numa tela escondida.

    O contador é mantido na MESMA transação que escreve a notificação. Um
    contador atualizado depois, "quando der", é um contador que diverge no
    primeiro erro de rede e nunca mais volta ao lugar sozinho. O guarda que prova
    a igualdade é `tests/test_inv_contador_bate_com_a_tabela.py`.
    """

    site_id = models.CharField(max_length=64)
    destinatario_id = models.CharField(max_length=64)
    nao_lidos = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "destinatario_id"], name="contador_um_por_pessoa"
            )
        ]
        indexes = [
            # `GET /resumo` (Fase 4) soma `nao_lidos` por `destinatario_id`
            # SEM `site_id` — mesmo motivo do índice de `Notificacao` acima.
            # Índice à parte, e não reordenar o UniqueConstraint: a restrição
            # de unicidade não muda de significado com a ordem das colunas,
            # mas o índice que o Postgres usa para RESPONDER "quanto essa
            # pessoa tem, em qualquer site" precisa liderar por
            # `destinatario_id` para não virar varredura.
            models.Index(fields=["destinatario_id"], name="contador_por_pessoa"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.destinatario_id}={self.nao_lidos}"


class NotificacaoArquivada(models.Model):
    """Aviso lido e velho — fora do caminho quente, mas não apagado.

    **Tabela separada, e não uma coluna `arquivada`** (`DECISAO-notificacoes`
    §5.2: *"arquivamento desde o começo — notificação lida e velha sai do caminho
    quente"*). Uma coluna deixaria as linhas velhas no mesmo lugar, engordando o
    índice que a página do sino percorre em toda visita; o ganho seria só de
    filtro, e o custo continuaria crescendo. Mudar de tabela é o que faz a caixa
    quente parar de crescer de verdade.

    Nada se perde: o histórico continua consultável, só não está no caminho que
    toda página percorre.
    """

    site_id = models.CharField(max_length=64)
    destinatario_id = models.CharField(max_length=64)
    ator_id = models.CharField(max_length=64, null=True, blank=True)
    assunto = models.CharField(max_length=64)
    parametros = models.JSONField()
    origem_event_id = models.UUIDField()
    criado_em = models.DateTimeField()
    lido_em = models.DateTimeField()
    arquivada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # Mesma correção e mesmo motivo do índice de `Notificacao`: a
            # porta de consulta da Fase 4 nunca filtra por `site_id`.
            models.Index(
                fields=["destinatario_id", "-criado_em"],
                name="notif_arquivo_da_pessoa",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"[arquivada] {self.assunto}→{self.destinatario_id}"
