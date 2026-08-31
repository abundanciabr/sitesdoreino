(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-072-a-fila-de-merge-estava-emperrada-e-agora-nao-esta",
  tipo: "incidente",
  quando: "2026-08-31",
  titulo: "A fila que junta o trabalho pronto ao site estava emperrada, e agora nao esta",
  detalhe: "Voce notou que o trabalho nao avancava e mandou consertar. Estava certo: era defeito, nao lentidao.\n\nO que acontecia. Existe uma fila automatica que pega cada trabalho pronto e junta ao projeto. A regra dela e que o trabalho precisa estar atualizado com a versao mais recente do projeto no exato momento de entrar. Quando ela encontrava um trabalho desatualizado, ela o atualizava e o mandava para o fim da fila. So que atualizar faz as conferencias comecarem do zero, e elas levam de 2 a 3 minutos. Hoje o projeto recebeu 108 juncoes em uma hora, uma a cada 33 segundos: nesses 2 ou 3 minutos o projeto andava mais 4 ou 5 vezes, e o trabalho ficava desatualizado de novo antes de terminar as conferencias.\n\nOu seja: uma corrida impossivel de vencer. E pior, a fila comeca pelos mais antigos, entao ela reiniciava justamente quem esperava ha mais tempo, enquanto os recem-chegados passavam na frente. Nada ficava vermelho, porque a fila parecia andar. Um dos trabalhos levou nove reinicios sem entrar nenhuma vez, e outro estava preso ha mais de uma hora.\n\nO conserto, com a sua ordem: a fila agora NAO larga a vez de quem ela mesma acabou de atualizar. Ela espera as conferencias daquele trabalho terminarem, com hora marcada para desistir, e so entao decide. Isso vale para todos os trabalhos, os meus e os das outras sessoes que estavam presos junto.\n\nA licao ficou guardada na memoria de campo do projeto (armadilha 251), e a prova esta no teste: ele reprova com a fila antiga e passa com a nova.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/750",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
