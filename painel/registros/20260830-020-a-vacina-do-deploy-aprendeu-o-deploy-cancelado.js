(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-020-a-vacina-do-deploy-aprendeu-o-deploy-cancelado",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O robô que conserta publicação agora enxerga o caso em que ela é cancelada — antes ele dizia que não havia nada a fazer",
  detalhe: "Quando uma entrega é aprovada, o site é republicado automaticamente. Essa republicação às vezes é CANCELADA no meio da fila: chega uma entrega nova, ela toma o lugar da que estava esperando, e a anterior simplesmente some. Nada fica vermelho, nenhum aviso aparece — mas a mudança aprovada continua fora do ar, servindo a versão velha.\n\nO robô que cuida de republicação já sabia consertar o caso em que ela FALHA. No caso em que ela é CANCELADA, ele respondia \"não há nada a fazer\" e a sessão fechava a tarefa achando que estava tudo certo. Foi o que aconteceu em 30/08/2026: duas entregas ficaram na versão oficial sem chegar ao site.\n\nAgora ele distingue os dois cancelamentos. Se foi um disparo manual, a resposta continua sendo a de antes (repetir não adianta, o conserto é outro). Se foi uma entrega aprovada, ele confere sozinho — pelo histórico do próprio GitHub, sem precisar entrar no servidor — se repetir a publicação só AVANÇA ou se faria o site voltar para uma versão mais velha. Só repete no primeiro caso; no segundo ele PARA e escreve o que aconteceu. E quando não consegue conferir, ele diz que não conseguiu em vez de tentar na esperança.\n\nEle também passou a avisar uma coisa que ninguém veria sozinho: se as entregas seguintes forem todas de pastas que não disparam publicação, nenhuma publicação nova vai nascer para carregar a sua — repetir é a única saída.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/573",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
