(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-029-ponte-do-fundador",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A medalha de Fundador já pode ser entregue a quem pediu entrada na escola",
  detalhe: "Você decidiu dar a medalha de Fundador a todo mundo que já pediu entrada. O comando que entrega a medalha existia e funcionava, mas ele pedia o número interno de cada pessoa, e a parte da plataforma que guarda os pedidos de entrada conhece as pessoas pelo e-mail. Faltava a ponte entre as duas coisas. Ela está pronta.\n\nO que passou a existir: a parte dos alunos aprendeu a dizer quem pediu entrada, agrupado por situação e contado; o comando das conquistas aprendeu a receber uma lista de e-mails e traduzir cada um no número interno; e um script de uma linha junta os dois dentro do servidor.\n\nO padrão é OLHAR: rodar o script sem nenhuma palavra a mais mostra a lista completa na tela, agrupada, e não entrega medalha nenhuma. Só com a palavra --confirmo no fim ele concede de verdade. Rodar de novo é seguro: ninguém ganha a medalha duas vezes, e os 25 Cristais são creditados uma vez só.\n\nQuem entra, por padrão: todo mundo com pedido de entrada em qualquer situação, menos quem só teve o pedido negado. O ensaio mostra esse grupo contado em separado, com nome e e-mail, e existe a opção --incluir-recusados se você decidir o contrário. A escolha é sua.\n\nFALTA UM PASSO SEU, de uma linha, e o script o explica: a parte das conquistas precisa de autorização para perguntar 'quem tem este e-mail?' à parte que guarda as identidades. Ela nunca precisou disso antes, então a autorização não existe no servidor. O script confere isso ANTES de qualquer coisa e, se faltar, para e entrega a linha pronta para colar, com o aviso sobre o sinal de maior duplo. Enquanto ninguém colar essa linha, nada quebra e nada muda no site: a medalha simplesmente continua sem dono.\n\nA regra mais importante que ficou trancada por teste: quando a parte das identidades não responde, o comando PARA e não entrega medalha a ninguém naquela rodada. 'Não consegui perguntar' nunca vira 'esta pessoa não existe', porque as duas frases sairiam iguais num relatório mal escrito e uma delas é uma afirmação sobre gente de verdade.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/833",
  verificado_em: "2026-09-01",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,

  se_eu_nao_decidir: "Nada quebra e nada muda no site. A medalha de Fundador continua existindo sem dono, e ninguém recebe os 25 Cristais nem a carta de celebração. O resto da plataforma segue igual.",
  recomendacao: "Rodar o script em modo ensaio primeiro (é uma linha, e ele não muda nada), ler a lista de nomes que aparece, e só então rodar de novo com --confirmo. Se ele parar pedindo a autorização de uma linha, cole a linha que ele mesmo entrega e rode outra vez.",
  reversivel: false,
  impacto: "medio"
});})();
