(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-088-a-busca-do-forum-esta-no-ar",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O fórum agora tem busca: o aluno acha a dúvida já respondida em vez de perguntar de novo",
  detalhe: "Tem um campo de busca no topo de todas as páginas do fórum. Quem escreve uma palavra ali recebe os trechos das mensagens que falam disso, com o termo grifado, e um clique leva direto para a mensagem dentro da conversa.\n\nIsso é o que faz as dez dúvidas já publicadas trabalharem: sem busca, o aluno teria de ler a lista inteira para achar a dele, e na prática perguntaria de novo. A parte cara já existia desde o começo do fórum (as mensagens são guardadas prontas para serem procuradas, em português); faltava a tela.\n\nCada pessoa só encontra o que ela já poderia ler. Um visitante acha apenas o que está nas áreas abertas; um aluno acha também as trancadas em que estuda. Isso não é um filtro novo escrito na busca: é a mesma regra das outras telas, perguntada no mesmo lugar. Medido na internet agora: sem login, procurar \"roblox\" devolve um resultado, o da área aberta.\n\nUM LIMITE QUE VALE VOCÊ SABER, e que a tela diz em português quando não acha nada: a busca leva o acento a sério. Quem procura \"chapeu\" não acha \"chapéu\". No Brasil quase ninguém acentua ao buscar, então isso erra boa parte das buscas reais. A cura existe e depende de um passo seu no servidor (instalar uma extensão do banco); ela já está no balcão como TAR-047, com o texto pronto.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/653 e o fecho em https://github.com/abundanciabr/sitesdoreino/pull/655 — 14 testes novos, suíte da célula 153 para 167 verdes; deploy-celula run 33340706830 completed/success nas duas células, lido por gh run view --json; prova de fora sem login: GET /forum/buscar 200, GET /forum/buscar?q=roblox 200 devolvendo '1 resultado para roblox', e a caixa de busca presente na capa",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
