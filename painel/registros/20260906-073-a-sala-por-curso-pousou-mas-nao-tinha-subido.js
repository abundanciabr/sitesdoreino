(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-073-a-sala-por-curso-pousou-mas-nao-tinha-subido",
  tipo: "incidente",
  quando: "2026-09-06",
  titulo: "A sala por curso tinha sido aprovada mas nunca subiu, e a ferramenta me disse que sim",
  detalhe: "Peguei isto a tempo, e vale contar porque e o tipo de erro que passa despercebido. A mudanca que faz a sala servir SO o curso da pessoa foi aprovada e entrou no projeto, mas o servidor NUNCA a recebeu: o envio dela foi cancelado no meio (outro trabalho chegou por cima) e nenhum envio seguinte tocou aquela parte do site.\n\nO PIOR: a ferramenta que existe justamente para conferir isso me respondeu 'ja esta no ar, nada a fazer'. Ela olha se o projeto inteiro foi publicado depois, e nao se AQUELA PARTE foi reconstruida. Conferi na mao e nao estava.\n\nO QUE EU FIZ: como o sistema nao aceita empurrar um envio a mao (de proposito, para ninguem publicar codigo que ninguem revisou), abri uma mudanca de verdade naquela parte do site, que carrega as licoes da equipe e leva o codigo parado junto.\n\nA ferramenta vai ser consertada: virou tarefa, com a medicao inteira e o aviso do conserto errado.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1210 (PR #1210), com a TAR-228 a bordo. Medido: dos 8 runs mais recentes de deploy-celula, todos tem o job deploy (admin) e NENHUM tem deploy (cursos); o run do PR #1201 (f98ee3ca) foi cancelado antes de criar job. A saida errada do ci/rerun_de_deploy.py esta no corpo do PR. .github/workflows/deploy-celula.yml nao tem workflow_dispatch, e o proprio arquivo diz por que.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
