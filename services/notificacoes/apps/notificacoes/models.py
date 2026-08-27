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
            # O caminho quente é sempre o mesmo: "os avisos DESTA pessoa NESTE
            # site, os mais novos primeiro" — e o `-criado_em` faz a página 1
            # sair sem ordenar nada em memória.
            #
            # **`site_id` E `destinatario_id` lideram JUNTOS.** Decisão do
            # mantenedor de 27/08/2026 (mesmo dia da Fase 4, CONSTITUICAO.md
            # Lei 9): "cada site mostra só os avisos que vieram dele" — as três
            # rotas da porta de consulta passaram a exigir os dois. Medido com
            # `EXPLAIN ANALYZE` (não suposto — 500 pessoas de ruído + 1 pessoa
            # com 1.500 linhas em 5 sites, 300 no site pedido): o índice
            # anterior, liderado só por `destinatario_id`, lia as 1.500 linhas
            # da pessoa em TODO site e só depois descartava 1.200 com um
            # `Filter` pós-índice ("Rows Removed by Filter: 1200") — o índice
            # não ajudava em nada a encontrar as 300 do site certo. Com as
            # duas colunas liderando, o Postgres usa `Index Cond` para as duas
            # e não descarta nenhuma linha depois. A prova mora em
            # `services/notificacoes/tests/test_indices_da_porta_de_consulta.py`.
            models.Index(
                fields=["site_id", "destinatario_id", "-criado_em"],
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
        # SEM índice extra de propósito. `GET /resumo` (Fase 4) lê por
        # `(site_id, destinatario_id)` — exatamente a chave do
        # `UniqueConstraint` acima, que JÁ é um índice único nessas duas
        # colunas, nessa ordem. Um índice às-pressas liderado só por
        # `destinatario_id` chegou a existir aqui (entre a Fase 4 sem site_id
        # e a emenda que passou a exigi-lo) — `EXPLAIN ANALYZE` mostrou o
        # Postgres preferindo `contador_um_por_pessoa` (`Index Cond` nas DUAS
        # colunas, zero linha descartada) no instante em que a query passou a
        # filtrar as duas, tornando o índice extra dead weight: nunca mais
        # escolhido para leitura, e ainda assim custando em todo `INSERT`.
        # Removido na migração que trouxe este comentário. Prova em
        # `tests/test_indices_da_porta_de_consulta.py`.

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
            # Mesma correção e mesmo motivo do índice de `Notificacao`: as
            # três rotas da porta de consulta filtram por `site_id` E
            # `destinatario_id` juntos (decisão do mantenedor, 27/08/2026,
            # CONSTITUICAO.md Lei 9) — os dois lideram o índice.
            models.Index(
                fields=["site_id", "destinatario_id", "-criado_em"],
                name="notif_arquivo_da_pessoa",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"[arquivada] {self.assunto}→{self.destinatario_id}"
