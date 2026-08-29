(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-009-a-primeira-vez-que-a-volta-automatica-foi-usada-de-verdade",
  tipo: "incidente",
  quando: "2026-08-29",
  titulo: "A volta automática foi usada de verdade pela primeira vez — e mostrou um defeito dela mesma",
  detalhe: "Uma entrega falhou por um motivo velho e conhecido: o servidor recusou a conexão do robô três vezes seguidas (é intermitente, já aconteceu outras vezes). Nada foi publicado, e o site continuou no ar com a versão anterior — quem estava usando não sentiu nada. Pedi para tentar de novo e entrou na primeira.\n\nO que interessa é o que aconteceu no meio: foi a estreia da volta automática que subiu hoje. Ela entrou em cena e disse \"não há versão anterior desta parte para voltar\" — sobre uma parte do site com dezenas de versões publicadas. A frase estava errada.\n\nO motivo: o robô baixa só o último pedaço do histórico do projeto, para ser rápido. Quem procura versões antigas ali não acha nenhuma — não porque não existam, mas porque não vieram junto.\n\nO erro não foi o número: foi a categoria. Ela disse \"procurei e não achei\" quando a verdade era \"não consegui procurar\" — e as duas frases mandam a gente investigar lugares diferentes. Consertei os dois lados: o robô passa a baixar o histórico inteiro nessa hora, e a peça passa a se recusar a responder quando o histórico não veio. Cada metade tem seu teste.\n\nÉ o tipo de defeito que nenhum teste pega e só a realidade mostra — e ele apareceu no primeiro dia, na melhor hora possível: com o site intacto.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/PRNUM. Run 33226662838 do deploy-celula (falha por 'dial tcp :22 i/o timeout' nas tres tentativas; rerun --failed verde na sequencia, producao em dia). Armadilha 159 escrita com o diagnostico.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
