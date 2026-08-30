(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-050-o-remedio-do-deploy-cancelado-existe-e-ninguem-o-toma",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "Tres vezes em dois dias um trabalho pronto ficou fora do ar em silencio — e o remedio ja existe, so nao tem quem o tome",
  detalhe: "TEM UM JEITO DE UM TRABALHO SEU FICAR FORA DO AR SEM NINGUEM PERCEBER, e ele aconteceu tres vezes em dois dias.\n\nCOMO ACONTECE: existem duas esteiras de publicacao — uma leva as pecas do site, a outra leva a base onde elas rodam. As duas dividem UMA VAGA so. Quando as duas querem publicar quase ao mesmo tempo, uma EXPULSA a outra, e a expulsa termina 'cancelada'.\n\nO PROBLEMA NAO E O CANCELAMENTO. E o SILENCIO dele. Cancelado nao e vermelho: nao acende alarme, nao abre aviso, nao aparece em lugar nenhum. O trabalho fica pronto no projeto e ausente do site, e a unica forma de descobrir e alguem estar olhando o historico e reparar num cinza no meio de verdes.\n\nE ISSO PIOROU JUSTAMENTE PORQUE O PROJETO FICOU MAIS DISCIPLINADO. Toda tarefa deste projeto e obrigada a deixar um registro no livro — e o livro fica dentro da mesma pasta que aciona a esteira das pecas. Entao QUALQUER trabalho de base aciona as duas esteiras ao mesmo tempo, e elas brigam pela vaga. Quanto mais robos trabalhando juntos, mais isso acontece: hoje foram duas vezes, uma atras da outra.\n\nA PARTE QUE MAIS INCOMODA: O REMEDIO JA EXISTE. Foi construido hoje mesmo. Ele sabe olhar um deploy cancelado e decidir com seguranca se repetir faz o site AVANCAR (repete) ou se repetir jogaria o site para tras (para e explica). Esta escrito, testado, e provado.\n\nSo que ele e um comando que ALGUEM PRECISA RODAR. Ninguem o chama sozinho. Ou seja: a cura existe e nao tem gatilho. Este projeto tem nome para isso — 'garantia sem mecanismo': a regra esta escrita, e o que a faz acontecer nao existe.\n\nHOJE QUEM PERCEBEU FORAM OS ROBOS, um a um, porque a lei da casa manda conferir o deploy depois de todo merge. Isso funcionou — mas depende de alguem estar prestando atencao, e depender de atencao e exatamente o que este projeto tenta nao fazer.\n\nVIROU A TAREFA TAR-029, com tres ordens: fazer o cancelamento deixar SINAL (hoje ele e cinza e mudo); ligar o remedio ao gatilho, para ele se tomar sozinho, sem afrouxar nenhuma das travas que impedem o site de voltar para tras; e olhar a CAUSA — se as duas esteiras podem ter vagas separadas, a briga acaba na raiz e as outras duas viram rede de seguranca em vez de conserto diario.\n\nNENHUM SITE CAIU por causa disso. O que se perde e entrega: trabalho pronto que nao chega, sem ninguem ser avisado.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/608 — este PR, com a TAR-029 e este registro. MEDIDO por robos diferentes, sempre por 'gh run view --json' e nunca por cano: o robo da TAR-024 contou 2 cancelados contra 20 sucessos no deploy-infra, os dois nos merges dos PRs 602 e 605, ambos em 30/08/2026, e esperou vaga livre em vez de expulsar o deploy de outro robo. Os outros dois casos estao em armadilhas/188 (PR 558, 30/08, deploy-celula) e armadilhas/183 (PR 527, 29/08, deploy-celula). A causa da briga: os dois workflows compartilham o grupo de concorrencia 'deploy', e todo PR carrega registro em painel/registros/, que casa 'painel/**' e dispara o deploy-celula. O remedio que existe e nao tem gatilho e o ci/rerun_de_deploy.py, ensinado a tratar o cancelado por push hoje pela TAR-017 (PR 573).",
  verificado_em: "2026-08-30",
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
