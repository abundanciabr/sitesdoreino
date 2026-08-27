(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-002-o-aviso-de-painel-quebrado-nao-se-repete-agora",
  tipo: "nota",
  quando: "2026-08-27",
  titulo: "Você colou um aviso de painel quebrado — não consegui reproduzir agora, e preciso que você reabra para confirmar",
  detalhe: "Você colou no chat a tela vermelha do painel dizendo 'o manifesto lista 58 registros, mas só 2 carregaram'. Fui investigar antes de acreditar em qualquer conserto.\n\nO QUE CONFERI: rodei o mesmo validador que a página usa (node painel/gerar_manifesto.js) tanto na versão mais nova do livro (60 registros) quanto numa cópia mais antiga (56 registros) — as duas vieram limpas, sem nenhum registro quebrado e com o manifesto em dia. Também li o código que serve o painel na área administrativa: ele é fail-closed por desenho (a mesma trava que pintou a tela vermelha que você viu), lê os arquivos direto da pasta-fonte, e o próprio CI recusa PR com o livro fora de sincronia — então um manifesto que promete 58 e entrega só 2 não deveria conseguir nem ser mergeado.\n\nNÃO CONSEGUI ABRIR O PAINEL NUM NAVEGADOR DE VERDADE para reproduzir ao vivo (a ponte do Chrome desta sessão estava fora do ar). Por isso não estou fechando isto como resolvido — estou fechando como 'não reproduzido'.\n\nO PALPITE MAIS PROVÁVEL: uma leitura no meio de uma mudança — por exemplo abrir o arquivo local bem no instante em que outra sessão de robô estava mexendo na mesma pasta (isto já aconteceu antes neste projeto: armadilhas/135 e 137), ou uma sincronização do OneDrive ainda trazendo os arquivos. Nenhuma das duas é defeito no painel — são o painel fazendo exatamente o que devia: gritar em vez de mentir.\n\nO QUE EU PRECISO DE VOCÊ: feche e reabra o painel agora (o arquivo local, com F5, ou o site) e me diga se o aviso vermelho sumiu ou continua. Se continuar, me diga TAMBÉM se foi o arquivo no seu PC ou o site (meshcraft.top/admin/painel/) — isso muda onde eu procuro.",
  autoridade: "sessao",
  evidencia: "medição em 27/08/2026: 'node painel/gerar_manifesto.js --conferir' limpo no HEAD atual (60 registros) e num checkout 6 commits mais antigo (56 registros); nenhum dos dois reproduziu a divergência de contagem",
  verificado_em: "2026-08-27",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
