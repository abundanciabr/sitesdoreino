(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-083-o-conserto-do-alarme-esta-no-ar",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O conserto do alarme que tocava à toa entrou e a publicação saiu verde",
  detalhe: "O trabalho descrito no registro 080 pousou e está no ar.\n\nO que muda na prática: os robôs pararam de ser interrompidos por um alerta vermelho em dia normal. O alarme continua tocando quando a anotação realmente falta, que é o único momento em que ele deveria falar.\n\nA publicação da área de administração foi junto, porque todo registro novo no livro entra na imagem dessa parte do site. Ela saiu verde, conferida pelo veredito real do serviço e não pelo resultado de um comando encadeado.\n\nNada ficou pendente com você nesta entrega.",
  autoridade: "github",
  evidencia: "Pouso do https://github.com/abundanciabr/sitesdoreino/pull/642 confirmado por gh pr view --json state,mergedBy,mergeCommit,mergedAt: state MERGED, mergeCommit c97e2ebfe6bcdd6bfba36b39e521a94d67f77a20, mergedAt 2026-08-30T21:59:02Z. A pista levou 1min32s do pedido ao merge, com os 7 checks verdes antes (medidos por ci/esperar.py --checks 642, 16s). DEPLOY conferido por gh run view 33337876103 --json status,conclusion: workflowName deploy-celula, status completed, conclusion success (https://github.com/abundanciabr/sitesdoreino/actions/runs/33337876103) — nunca pelo exit de um pipe (ARMADILHAS §5.10). No mesmo commit: ci-celula run 33337876119 completed/success e alarme-main run 33337876106 completed/success. Livro conferido depois do merge com divida_do_livro.divida(): 0 devedores, porque o registro 080 citou o número do PR na evidencia — que é a lição da armadilhas/185 aplicada a ela mesma. PROVA DE FORA do conserto, no comando de verdade contra o PR 642: a linha 'dívida do livro   PASS   livro em dia' apareceu em três execuções de ci/mergear.py 642 --conferir e o sino não tocou em nenhuma; antes do conserto essa mesma linha tocava o sino toda vez.",
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
