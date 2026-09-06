(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-061-as-tres-celulas-subiram-a-tela-esta-no-ar",
  tipo: "medicao",
  quando: "2026-09-06",
  titulo: "As tres celulas subiram: a tela de liberar com os cursos esta no ar",
  detalhe: "Veredito dos deploys que os merges de hoje dispararam. As tres celulas que a lei de cursos tocou recarregaram com sucesso, e agora o que voce pediu esta de pe no servidor, nao so no codigo.\n\nUM SUSTO QUE NAO ERA SUSTO: tres deploys apareceram como reprovados no meio do caminho. Nao eram: o GitHub CANCELOU os runs porque outro merge chegou por cima, e cancelado quer dizer que a celula nao foi reconstruida, nao que algo quebrou. Repeti os dois que faltavam e os dois subiram.\n\nO QUE ISSO LIBERA PARA VOCE: a linha para colar na VPS que cria os dois cursos e matricula no primeiro todo mundo que ja esta no site. Ela esta no registro do roteiro, e agora ela roda de verdade.",
  autoridade: "github",
  evidencia: "Lido por gh run view --json status,conclusion,jobs, nunca por pipe. deploy (admin): completed/success no run 34043720508, e git merge-base --is-ancestor f6fc537a 2e2e15a9 confirma que o commit da tela (PR #1199) esta dentro dele. deploy (alunos): completed/success no run 34043277202 (segunda tentativa), sobre 7ce84f12, que e o merge do #1178. deploy (catalogo): completed/success no run 34043608110, sobre 5a787561, que e o merge do #1198 e contem o #1194. Prova de fora depois de tudo: curl devolveu 200 em /, /cadastro e /cursos/profissional/, e 301 em /forum.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
