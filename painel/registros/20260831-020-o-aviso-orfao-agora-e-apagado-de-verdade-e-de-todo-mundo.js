(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-020-o-aviso-orfao-agora-e-apagado-de-verdade-e-de-todo-mundo",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "O aviso que sobrou de uma ideia apagada agora é APAGADO de verdade, e de todo mundo, não só de quem reclamou",
  detalhe: "Você mandou a foto do cartão e fez a pergunta certa: e os outros usuários? Esta entrega responde as duas coisas.\n\nO QUE JÁ TINHA SIDO FEITO antes desta: o conserto que faz a tela PARAR DE MOSTRAR o recado de uma ideia apagada. Isso resolve o que você vê, mas é meia solução: a linha continuava guardada, e o numerinho do sino continuava contando um recado invisível.\n\nO QUE ENTROU AGORA: a caixa central de avisos aprendeu a RETIRAR. Ela nunca soube fazer isso — sabia contar, listar e marcar como lido, e mais nada. Agora existe um passo de pipeline que pergunta à Caixa de Sugestões quais ideias foram apagadas, leva essa lista até a caixa de avisos, e apaga os recados sobre elas. De todas as pessoas de uma vez, que era a sua pergunta.\n\nELE RESPONDE ANTES DE AGIR: o passo roda primeiro em modo de simulação e imprime quantos recados existem e quantas PESSOAS têm algum, sem tocar em nada. Só depois apaga. Se a simulação achar zero, ele termina ali e diz que não havia nada.\n\nO NUMERINHO DO SINO DESCE JUNTO. Isso não é detalhe: aquele número é guardado numa conta separada, para o sino não ficar lento. Apagar o recado sem descontar deixaria você com um número que nenhuma lista explica — exatamente a doença que este trabalho veio curar, só que do outro lado. O desconto acontece na mesma operação, e só pelos recados ainda não lidos.\n\nO CUIDADO QUE TOMEI, e metade dos testes existe para isso: um comando que apaga em lote é justamente o tipo de ferramenta que leva vizinho junto quando o filtro erra. Recado de outro assunto, de outra ideia, de outra pessoa: todos continuam de pé, cada um com teste próprio. Também há teste para uma falha que teria sido SILENCIOSA — se o comando tratasse o número da ideia como número em vez de texto, ele não acharia nada e terminaria dizendo que deu certo.\n\nO PASSO SEGUINTE é meu: com isto no ar, eu rodo a limpeza e te digo quantos recados sumiram e de quantas pessoas.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/684 — suíte da célula notificacoes 112/112 verdes (eram 100 mais 12 novos), Postgres 17 local. Prova vermelho para verde: quebrando de propósito o desconto no contador, 3 testes REPROVARAM; restaurado, 12/12. O conserto irmão, que esconde na leitura, é https://github.com/abundanciabr/sitesdoreino/pull/678. black PASS em 43 arquivos; bash -n, parse de YAML e ci/travessao.py PASS.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
