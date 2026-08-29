(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-103-o-cadeado-agora-tem-quem-o-vigie-todo-dia",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "O cadeado do site agora tem quem o vigie todo dia — e te avise antes de estourar",
  detalhe: "Você perguntou se dava para fazer a renovação do cadeado ser automática. Fui conferir no código, e a resposta tem duas metades.\n\nA PRIMEIRA METADE, boa: a renovação JÁ é automática. O porteiro do site pede um cadeado novo sozinho, cerca de 30 dias antes de vencer. E o detalhe que costuma quebrar isso em outros projetos está certo aqui: o cadeado é guardado num cofre que sobrevive a cada publicação. Se ele morasse junto com os arquivos que a publicação substitui, seria apagado toda vez, e o site pediria cadeado novo sem parar até ser bloqueado por excesso de pedidos. Não é o caso.\n\nA SEGUNDA METADE, ruim, e é ela que eu consertei: NINGUÉM conferia se a renovação tinha acontecido. Procurei no projeto inteiro — não havia nenhuma rotina que rodasse no relógio. Zero. E isso importa porque o projeto já tinha medido o modo de falha: se a renovação falhar, o porteiro volta a servir o crachá genérico e não avisa ninguém. O site cai naquela tela vermelha, e a primeira pessoa a descobrir é um visitante — ou você, por acaso, como aconteceu hoje.\n\n\"Renova sozinho\" sem ninguém medindo é promessa, não mecanismo.\n\nO QUE PASSOU A EXISTIR: uma rotina que acorda sozinha todo dia de manhã, vai até os seus sites PELA INTERNET — como um visitante faria, não por dentro do servidor — e mede o cadeado de verdade. Ela grita se achar qualquer uma de três coisas: o crachá genérico voltou, o cadeado vence em menos de 3 semanas, ou o site não responde. Gritar significa abrir um chamado no GitHub, do mesmo jeito que o alarme que já existia.\n\nELA SE MANTÉM SOZINHA: lê a lista de sites do próprio projeto, então cada site novo que você criar já nasce vigiado, sem ninguém precisar lembrar de acrescentá-lo. E ela imprime, na tela, quais endereços ela decidiu NÃO vigiar e por quê — porque omissão silenciosa é como um vigia vira enfeite.\n\nPOR QUE 3 SEMANAS: o cadeado vale 90 dias e a renovação começa aos 30. Se ainda faltam menos de 21, a renovação teve mais de uma semana e não aconteceu — isso não é \"ainda dá tempo\", é defeito. E sobram 3 semanas para consertar com calma.\n\nUM PERIGO QUE EU EVITEI DE PROPÓSITO: existe um portão que barra publicações se enxergar qualquer alarme vermelho. Se eu tivesse deixado o vigia entrar ali, um cadeado vermelho travaria TODAS as suas entregas — inclusive a entrega que conserta o cadeado, porque o conserto dele é justamente uma publicação. Seria trancar a porta por dentro. Declarei a exceção por escrito, com testes que provam que a exceção é estreita: um alarme desconhecido continua travando, como deve.\n\nPROVA DE QUE O VIGIA FUNCIONA: rodei contra endereços públicos que existem justamente para testar isso — um com cadeado vencido e um com crachá autoassinado. Ele ficou vermelho nos dois, com a mensagem certa. E contra os seus sites, verde nos dois, com 90 dias de folga.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/510",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
