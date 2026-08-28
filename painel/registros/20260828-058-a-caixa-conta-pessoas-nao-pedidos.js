(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-058-a-caixa-conta-pessoas-nao-pedidos",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "A Caixa passou a contar PESSOAS esperando, e não pedidos — antes o número ia aparecer maior do que a realidade",
  detalhe: "Isto é de outra frente de trabalho, entregue mais cedo hoje. Estou registrando porque ninguém tinha contado a você ainda, e a porta do merge me cobrou — do jeito que ela foi feita para cobrar.\n\nO QUE ESTAVA PARA DAR ERRADO: a tela de gestão da Caixa ia mostrar 'quantas pessoas estão esperando resposta'. O jeito antigo de calcular somava a plateia de cada ideia. Só que a mesma pessoa costuma estar atrás de duas ou três ideias — e somando, ela era contada duas ou três vezes. O número apareceria na tela maior do que a realidade, com toda a cara de certeza.\n\nFoi pego ANTES de a tela ser construída em cima dele, e não depois.\n\nO QUE MUDOU: agora quem faz a conta é a própria Caixa, que é o único lugar do sistema que sabe quem é quem — do lado de fora só existe 'quantos por ideia', e somar isso é justamente o erro. Passaram a existir três números honestos: quantas pessoas distintas esperam resposta, há quanto tempo em média elas esperam, e quantas já passaram de 30 dias sem ouvir nada.\n\nE tem um detalhe bonito: uma ideia RECUSADA com justificativa para de contar como gente esperando. Um 'não' explicado é uma resposta.\n\nA PROVA: o teste monta de propósito uma pessoa atrás de duas ideias e exige que a conta de pessoas seja MENOR que a soma das plateias. Se alguém reintroduzir a soma ingênua, esse teste fica vermelho na hora.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/394 (emenda de contrato) e https://github.com/abundanciabr/sitesdoreino/pull/395 (a celula que fornece os numeros). Ambos MERGED em 28/08/2026, conferidos por gh pr view. Prova declarada nos PRs: freeze de contrato PASS (532 linhas, 5 operacoes com auth na fonte); suite da celula sugestoes de 488 para 491 testes; black limpo. Registro escrito por uma sessao diferente da que entregou — a divida foi cobrada pela porta do merge (ci/mergear.py) a quem chegou depois, que e como ela foi desenhada para funcionar.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "site",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: true,
  impacto: null
});})();
