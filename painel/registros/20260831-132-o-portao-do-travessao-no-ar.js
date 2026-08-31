(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-132-o-portao-do-travessao-no-ar",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "As seis frases com travessão saíram do site, e o guarda que as achou está no ar",
  detalhe: "O trabalho que você autorizou entrou na main e o deploy ficou verde. O fórum e a Caixa responderam depois dele.\n\nO que mudou para quem lê o site: as três descrições de quem enxerga cada área do fórum e as três frases da Caixa foram reescritas. Duas delas são o que o aluno lê quando erra ao mandar uma sugestão, e agora estão em português correto.\n\nO que mudou para a fábrica: o guarda que confere travessão deixou de ter ponto cego no código. Antes ele só olhava os arquivos de tela, e uma parte do que o aluno lê não mora lá. Agora, qualquer lista de situações que apareça na tela entra na conferência sozinha, sem ninguém precisar lembrar, e um arquivo que escreve frases inteiras para o aluno pode se declarar com uma marca.\n\nA armadilha que eu tinha aberto de manhã como \"anotada, não consertada\" foi fechada no mesmo dia e mudou de estado: de lição escrita para muralha que roda em todo trabalho.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/803 MERGED, commit f4e6b84f. deploy-celula run 33450361801, sha f4e6b84fc: status completed, conclusion success, lido por 'gh run view --json status,conclusion' e nao pelo exit de um pipe. PROVA DE FORA, depois do deploy: https://meshcraft.top/forum/ responde 200 e https://meshcraft.top/forms/sugestoes/entrar responde 200. Antes do merge: 9 checks verdes no PR; suite do repositorio 1406 passed; celula forum 207 passed; celula sugestoes 574 passed com freeze de contrato PASS; muralhas 13/13 PASS; ci/travessao.py PASS com 81 arquivos inspecionados contra 75 antes.",
  verificado_em: "2026-08-31",
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
