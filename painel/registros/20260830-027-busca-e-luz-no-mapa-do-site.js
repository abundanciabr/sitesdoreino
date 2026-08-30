(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-027-busca-e-luz-no-mapa-do-site",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O mapa do site ganhou busca e uma luz de \"está no ar?\" nas portas principais",
  detalhe: "As duas coisas que você escolheu depois de abrir o mapa.\n\nA BUSCA: um campo em cima da lista. Você digita 'fórum', 'aluno' ou 'pagar' e a lista encolhe, dizendo quantos de quantos sobraram. Ignora acento e maiúscula, e procura no nome, na explicação, no endereço e nas notas de cada linha. O endereço da busca fica guardável nos favoritos — se você achar uma pesquisa útil, pode salvá-la.\n\nEla recarrega a página em vez de filtrar na hora, e isso é de propósito: funciona mesmo com script bloqueado, é o mesmo gesto da peneira que você já usa na lista de alunos, e não pede nada da segurança da página.\n\nA LUZ: oito portas principais — a entrada do site, a tela de entrar, o fórum, a Caixa, a compra, a área administrativa, a biblioteca pública e o mapa para IA — ganham uma etiqueta que diz \"no ar\" ou \"não respondeu\", conferida na hora em que você abre o mapa.\n\nQuem pergunta é o SEU navegador, não o servidor. Isso importa: um servidor conferindo a si mesmo por dentro responderia \"está tudo bem\" mesmo para uma porta que a internet não alcança. Do seu navegador, o caminho é o mesmo que um visitante faria — passando pelo roteador e pelo cadeado.\n\nE tem uma trava que vale a pena você saber que existe: o sistema RECUSA marcar com luz um endereço que seja um botão. Sem ela, o mapa abriria sozinho o endereço de \"sair\" toda vez que você o consultasse — e te deslogaria. Também recusa endereços internos (o navegador não os alcança, e a luz mentiria vermelho) e endereços que são molde (pedir o molde dá 404 e pintaria de vermelho uma porta aberta).",
  autoridade: "github",
  evidencia: "PR #583 (https://github.com/abundanciabr/sitesdoreino/pull/583). Busca medida: ?q=forum devolve 8 de 97 endereços. 21 testes no cartógrafo (4 novos, um por cerca da sonda, cada um sabotando o mapa e exigindo vermelho), 18 na tela (10 novos: a busca encolhe e conta, ignora acento, diz quando não acha; a luz só nas portas declaradas; nenhum gesto sondado; o hash do script e o do estilo no CSP; connect-src fechado), 363 na célula inteira.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
