(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-091-a-linha-que-nao-desligava-era-de-uma-celula-so",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "A linha telefônica que não desligava era de UMA parte só do sistema — achei, e ela está consertada",
  detalhe: "Fui conferir no código real do Django instalado, em vez de confiar no diagnóstico anterior. Ele estava certo no MECANISMO e largo demais no ALCANCE.\n\nO QUE EU ENCONTREI: das 13 partes do sistema, DOZE já desligavam a linha ao fim de cada visita — isso sempre foi o comportamento padrão delas. Só o LOGIN tinha um ajuste diferente, posto em 25/08 por um bom motivo: manter a linha aberta por 60 segundos deixava cada consulta cem vezes mais rápida (0,2 milésimo de segundo contra 24). O que ninguém tinha visto é que, do jeito que o servidor atende, cada visita ganha um atendente novo e descartável — e a linha aberta ficava presa com o atendente que já foi embora. Ninguém mais tinha como desligá-la.\n\nPOR QUE FOI JUSTAMENTE O PAINEL QUE ESTOUROU: todo pedido do painel passa pelo login. Os 86 pedidos de uma vez, em 27/08, viraram 86 linhas presas — e só existem 100 no total para o sistema inteiro.\n\nO CONSERTO, QUE NÃO ABRE MÃO DE NADA: em vez de voltar a desligar sempre (o que devolveria a lentidão), o login passou a usar uma central de linhas compartilhada, que é do prédio e não do atendente. Atendente que vai embora DEVOLVE a linha em vez de abandoná-la. E agora existe um teto: o login nunca passa de 8 linhas, aconteça o que acontecer do lado de fora.\n\nO QUE AINDA NÃO ESTÁ RESOLVIDO, E EU NÃO DECIDO SOZINHO: as outras 12 partes não vazam, mas também não têm teto — uma página muito movimentada pode abrir muitas linhas de uma vez. Pôr teto em todas é obra maior, uma entrega separada por parte. Levei isso a você como pergunta nesta mesma sessão.",
  autoridade: "sessao",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/422. Diagnostico conferido no codigo instalado (Django 5.1.4, asgiref 3.12.1): ASGIHandler.__call__ abre um ThreadSensitiveContext por requisicao; close_old_connections so fecha conexao OBSOLETA, e com conn_max_age=60 ela nao esta. O comando grep -rn conn_max_age services/ devolve UMA ocorrencia (identidade) — as outras 12 celulas usam o default 0 do dj_database_url. Guarda: services/identidade/tests/test_pool_de_conexoes.py, 4 testes. Vermelho-verde REAL: primeira execucao 2 failed (faltava psycopg[pool]), depois 4 passed; mutacao renomeando OPTIONS = 2 failed, restaurado = 4 passed.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: "20260827-036-o-servidor-abre-uma-linha-nova-a-cada-visita",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
