(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-016-o-botao-de-teste-precisa-de-um-passo-seu-na-vps",
  tipo: "pendencia",
  quando: "2026-09-03",
  titulo: "O botão de testar o aviso precisa de um passo seu na VPS",
  detalhe: "Você testou o botão 'Testar o aviso no celular' e ele respondeu 'Não deu para saber'. A tela não mentiu: eu esqueci de ligar a credencial que faz o seu painel conseguir falar com a parte que guarda os aparelhos. Erro meu, achado por você usando a própria tela, exatamente como o instrumento deveria funcionar.\n\nO QUE É: toda vez que uma parte do sistema passa a falar com outra pela primeira vez, as duas precisam combinar uma senha entre si. Essa senha nunca pode vir por mim, de propósito: ela é gerada e guardada só dentro do seu servidor. Eu escrevi o código que usa essa senha, mas esqueci de criar o passo que gera ela.\n\nO QUE NÃO QUEBROU: nenhum aviso de verdade (sugestão respondida, matrícula liberada, medalha da escola) depende disso. Só esse botão de teste, especificamente, fica mudo até você rodar o comando abaixo.\n\nO QUE VOCÊ PRECISA FAZER: entrar na VPS (o prompt começa com deploy@srv... ou root@srv...) e colar este bloco único:\n\ncurl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-do-teste-de-aviso.sh -o /tmp/p.sh && bash /tmp/p.sh\n\nEle não pergunta nada, gera a senha sozinho, e no final reinicia as três partes que precisam saber da senha nova. Vai aparecer 'PRONTO' no final. Depois disso, volte em /admin/avisos/ e clique no botão de novo.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/913. 13 muralhas do repositório em PASS. Script no mesmo molde dos outros pares do admin (infra/provisionar-par-da-economia.sh), sintaxe conferida com bash -n.",
  verificado_em: "2026-09-03",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: "O botão de teste continua respondendo 'Não deu para saber' para sempre. Nada mais no site é afetado.",
  recomendacao: "Colar o bloco de um comando só dentro da VPS, e depois testar o botão de novo.",
  reversivel: true,
  impacto: "baixo"
});})();
