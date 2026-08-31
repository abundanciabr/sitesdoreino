(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-103-o-passo-para-ligar-a-tela-da-economia",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "O passo de uma linha para ligar a tela da economia, e um alarme falso a menos",
  detalhe: "Este degrau prepara a colada que voce vai dar na VPS quando a tela ficar pronta. E uma linha so, sem argumento nenhum, e ela nao pergunta nada: o segredo e criado la dentro do servidor, nao aparece na tela e nao passa por mim. Se rodar duas vezes, nao estraga nada: ele reusa o que ja existe em vez de trocar.\n\nPor que isso precisa de voce: a senha que faz uma parte do sistema confiar na outra nao pode viajar pela esteira de publicacao, por lei do projeto. E o unico tipo de coisa que so voce pode fazer.\n\nACHEI UM ALARME FALSO NO CAMINHO, e ele valia mais que o proprio degrau. O script que faz esse tipo de ligacao terminava reiniciando as pecas do sistema e dizendo PRONTO. So que a maneira como ele perguntava 'deu certo?' estava errada: ele perguntava para o comando errado, um que responde 'sim' quase sempre. Resultado: se o reinicio FALHASSE, o script diria PRONTO do mesmo jeito, e voce abriria uma tela morta sem nada na tela dizendo por que. O aviso de erro que existia ali embaixo nunca ia aparecer.\n\nE o mesmo tipo de engano que ja enganou este projeto antes, em agosto, quando publicacoes apareciam verdes sem terem funcionado. Corrigi nos DOIS arquivos onde ele estava: no meu e no do menu do topo, que foi escrito ontem e tem o mesmo defeito. Nao mexi em mais nada do arquivo do menu.\n\nCOMO EU SEI QUE ESTA CONSERTADO: o teste que escrevi RODA o script de verdade, com o docker fora de alcance de proposito, e exige que ele NAO diga PRONTO. Com o defeito de volta, o teste acusa na hora. Ele confere tambem que a senha nunca aparece na tela, que rodar de novo nao troca a senha, que os dois lados ficam com o mesmo valor, e que rodar na pasta errada para sem escrever nada.\n\nSE VOCE NAO RODAR NADA: nada quebra e nada muda no site. A tela vai abrir dizendo, em portugues, que ainda nao consegue falar com a parte das conquistas. A economia continua inteira desligada, como nasceu.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/777. PROVA VERMELHO->VERDE POR ASSERCAO (armadilhas/195), com o guarda que EXECUTA o script em vez de le-lo: com o 'if docker compose ... | tail -5' de volta e o docker fora de alcance, 'AssertionError: o script anunciou PRONTO com o reinicio FALHANDO — e o ramo de erro virou codigo morto (ARMADILHAS §5.10)'; com o conserto, 10 passed. Somando o guarda antigo, 30 passed. bash -n limpo nos dois scripts. O defeito e o ARMADILHAS §5.10, o mesmo que fez os greens do deploy-celula mentirem ate 21/08/2026 (H13); varredura em infra/*.sh achou exatamente DOIS arquivos com ele, e os dois estao corrigidos neste PR. Toca ci/ (CODEOWNERS) apenas para acrescentar o guarda novo.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
