from django.db import migrations
from django.db.models import Max

ALTERACOES = {'compras-no-ciclo': {'criterio': 'pessoas-unicas-2027',
                      'pergunta': 'Quantas pessoas únicas fizeram uma compra '
                                  'elegível desde 12/10/2026?',
                      'definicao': 'Pessoas únicas por e-mail normalizado, de '
                                   '12/10/2026 a 31/12/2027, horário de São '
                                   'Paulo, com compra confirmada no checkout '
                                   'ou liberação administrativa marcada como '
                                   'nova venda paga. A base anterior, testes, '
                                   'pedidos sem pagamento, reembolsos e '
                                   'liberações comuns ficam fora. Recompras '
                                   'não multiplicam pessoas.',
                      'formula': 'cadastros distintos deste site pela primeira '
                                 'compra elegível na janela; status ativa, '
                                 'suspensa ou encerrada; origem comprou inclui '
                                 'nova venda paga manual na API de matrículas',
                      'acao': 'Conferir anúncio → quiz → low ticket → mid '
                              'ticket → plataforma; comparar vendas por '
                              'produto com o calendário e ajustar o gargalo '
                              'observado. Confirmar acesso antigo não cria '
                              'nova venda.',
                      'alvo': 10000,
                      'ate': '2027-12-31',
                      'partida': 0,
                      'partida_em': '2026-10-12',
                      '_por_que': 'Decisão de 12/10 e correção expressa em '
                                  '14/10/2026. Pessoas únicas não são a soma '
                                  'das vendas low e mid. Não há curva de '
                                  'pessoas aprovada. Referência: '
                                  'https://meshcraft.top/admin/documentos/principio-central-lancamentos-perpetuos-20261012'},
 'compras-no-mes': {'pergunta': 'Quantas novas pessoas únicas entraram na meta '
                                'de 2027 neste mês?',
                    'definicao': 'Cadastros cuja primeira compra elegível na '
                                 'janela de 12/10/2026 a 31/12/2027 ocorreu '
                                 'neste mês, horário de São Paulo. Recompras '
                                 'em outro mês não contam como novas pessoas.',
                    'formula': 'e-mails normalizados distintos deste site por '
                               'mês da primeira compra elegível na janela',
                    'acao': 'Comparar grupos de entrada, campanhas e ofertas. '
                            'Metas de vendas low e mid seguem o calendário; '
                            'não há meta mensal de pessoas aprovada.',
                    'alvo_do_mes': None,
                    '_por_que': 'Mesma população da meta de pessoas de 2027, '
                                'recortada pela primeira compra elegível.'},
 'pedidos-de-entrada-por-semana': {'definicao': 'Chegadas à sala de espera nos '
                                                'últimos 7 dias. Indicador de '
                                                'atendimento a compras '
                                                'externas, separado das metas '
                                                'comerciais; não deriva alvo '
                                                'de pessoas ou vendas low e '
                                                'mid.',
                                   'acao': 'Conferir atendimento e entrega de '
                                           'acesso. Liberação comum não cria '
                                           'venda nem soma pessoa à meta.',
                                   'meta_semanal': None,
                                   '_por_que': 'Atendimento sem transformar a '
                                               'curva comercial em meta de '
                                               'chegadas à fila.'},
 'alunos-ativos-30d': {'definicao': 'Atividade dos alunos nos últimos 30 dias, '
                                    'separada de novas pessoas e vendas. '
                                    'Acesso e liberação comum não provam nova '
                                    'venda paga.'}}


def atualizar(apps, schema_editor):
    Cartao = apps.get_model("core", "CartaoDoPlacar")
    Versao = apps.get_model("core", "VersaoDoCartaoDoPlacar")
    db = schema_editor.connection.alias
    for nome, alteracoes in ALTERACOES.items():
        cartao = Cartao.objects.using(db).filter(nome=nome).first()
        if cartao is None:
            continue
        revisao = (Versao.objects.using(db).filter(cartao=cartao).aggregate(n=Max("revisao"))["n"] or 0)
        if not Versao.objects.using(db).filter(cartao=cartao, dados=cartao.dados).exists():
            revisao += 1
            Versao.objects.using(db).create(cartao=cartao, revisao=revisao,
                dados=cartao.dados, responsavel="preservacao-anterior-placar-20261014")
        dados = {**cartao.dados, **alteracoes}
        if nome == "compras-no-ciclo":
            dados.pop("semanas", None)
        dados.update(versao=int(cartao.dados.get("versao") or 0) + 1, desde="2026-10-14")
        cartao.dados = dados
        cartao.save(using=db, update_fields=["dados", "atualizado_em"])
        Versao.objects.using(db).create(cartao=cartao, revisao=revisao + 1,
            dados=dados, responsavel="correcao-autorizada-placar-20261014")


class Migration(migrations.Migration):
    dependencies = [("core", "0049_perfil_da_comunidade")]
    operations = [migrations.RunPython(atualizar, migrations.RunPython.noop)]
