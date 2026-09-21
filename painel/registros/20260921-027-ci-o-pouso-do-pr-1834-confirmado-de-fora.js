(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260921-027-ci-o-pouso-do-pr-1834-confirmado-de-fora",
  tipo: "entrega",
  quando: "2026-09-21",
  titulo: "O comando que resume a fábrica voltou a rodar no Windows, e um guarda impede a próxima",
  detalhe: "O PR 1834 pousou na main. Confirmado de fora, com gh pr view: state=MERGED, mergedBy=abundanciabr, commit de merge eba6585c. O conserto está na main: ci/resumo_maestro.py já traz encoding declarado, configurar_saida() e sys.executable.\n\nO defeito: o comando morria no Windows lendo em cp1252 um texto escrito em utf-8. A casa guardava só metade da fronteira, a do programa filho; faltava a do programa que lê. Eram 14 leituras assim em 10 arquivos, contra 34 já corretas.\n\nFicaram de fora, declarado: 4 leituras em ci/registrar_tarefa_fase4.py, que é instrumento de medição congelado (registro 011), e 4 em services/, que a cerca de célula impede num PR de ferramenta (TAR-578).",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1834",
  verificado_em: "2026-09-21",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null
}); })();
