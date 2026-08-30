(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-059-um-so-preparo-antes-dos-testes-em-vez-de-dois",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "Dois robôs tinham montado o mesmo preparo antes dos testes; agora é um só",
  detalhe: "Antes de a bateria de testes rodar, ela precisa montar três arquivos que não ficam guardados no projeto (eles são construídos na hora, a partir das lições que os robôs escrevem). Esse preparo estava sendo feito DUAS vezes, por duas peças diferentes que faziam exatamente a mesma coisa.\n\nAconteceu no mesmo dia, e o motivo é quase bonito: a esteira ficou vermelha, dois robôs viram o problema ao mesmo tempo, e cada um consertou do seu jeito. Como os dois consertos foram acrescentados em pontos diferentes do arquivo, o sistema não reclamou de nada — juntou os dois e ficou verde. Ninguém viu.\n\nNão dava erro, e nada estava quebrado hoje: o preparo apenas era feito duas vezes seguidas. O risco era mais adiante — no dia em que alguém fosse mexer numa das duas peças e não soubesse da outra, as duas passariam a discordar, e isso só apareceria com a esteira vermelha de novo.\n\nAgora é uma peça só, que juntou o melhor das duas: o jeito mais rápido de fazer o trabalho, o nome que o resto da casa já usava, e as explicações que as duas guardavam (cada uma sabia uma coisa que a outra não sabia). Ela ganhou também um recado escrito para o próximo robô que vier consertar aqui: conserte ESTA, não acrescente outra ao lado.\n\nA prova foi feita do jeito difícil, que é o único que vale: os três arquivos foram APAGADOS antes de medir. Sem nenhuma peça de preparo, 2 testes falham e 24 passam; com a peça única, os 26 passam. A bateria inteira, também partindo do zero, fecha com 1284 testes passando.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/619 — a prova crua está no corpo do PR: apagados os três arquivos, sem a peça de preparo dá '2 failed, 24 passed' e com ela dá '26 passed'; a bateria inteira dá '1284 passed in 371.85s'",
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
