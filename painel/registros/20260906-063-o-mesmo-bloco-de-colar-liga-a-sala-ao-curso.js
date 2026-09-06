(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-063-o-mesmo-bloco-de-colar-liga-a-sala-ao-curso",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "O mesmo bloco de colar tambem liga a sala ao curso do livro",
  detalhe: "A sala de aula passou a servir SO o curso em que a pessoa esta matriculada (PR 1201), e para isso ela precisa saber qual produto e qual curso. Sem essa ligacao a sala fecha para todo mundo, de proposito: nao conseguir conferir nunca pode virar 'pode entrar'.\n\nEM VEZ DE TE DAR UM SEGUNDO COMANDO, pus esse passo dentro do mesmo bloco que voce ja ia rodar. Continua sendo UMA LINHA so, agora com 5 passos em vez de 4.\n\nA ORDEM IMPORTA e foi escolhida: ligar a sala vem ANTES de mexer nas matriculas, porque e o ultimo passo que ainda pode falhar por configuracao. Se ele falhar, os cursos ficam criados e NENHUMA matricula e tocada, entao voce roda de novo sem susto.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1204 (PR #1204), toca infra (caminho CODEOWNERS), par obrigatorio do #1201. bash -n: sintaxe OK. python ci/ci.py --apenas muralhas: RESULTADO PASS nos 13 portoes. Roteiro rodado contra um docker falso nos SETE cenarios: caminho feliz completo com --site, --curso e --produto chegando inteiros nos dois comandos, e 6 recusas conferidas uma a uma. A recusa 'sala-recusa' prova a ordem: cursos criados, ligacao falhou, matriculas intactas. NAO RODEI na VPS: o robo nao tem SSH.",
  verificado_em: "2026-09-06",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
