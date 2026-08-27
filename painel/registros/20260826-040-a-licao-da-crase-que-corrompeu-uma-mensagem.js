(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-040-a-licao-da-crase-que-corrompeu-uma-mensagem",
  tipo: "nota",
  quando: "2026-08-26",
  titulo: "Um erro meu, registrado: o terminal executou parte de um texto que eu estava escrevendo",
  detalhe: "Isto é pequeno e não afetou nada do que você usa — mas é do tipo que volta se ninguém escrever, então fica registrado.\n\nAo gravar a explicação de um dos trabalhos de hoje, usei um sinal de pontuação que o terminal do Windows entende como 'execute isto'. Resultado: pedaços do meu texto viraram comandos, a explicação foi gravada com buracos, e três arquivos vazios de nome absurdo apareceram na pasta do projeto.\n\nPor que isso importa mesmo sendo pequeno: o comando não falhou. Ficou tudo verde, com o texto estragado por dentro. E é nesse texto que o projeto guarda o PORQUÊ de cada decisão — alguém iria ler daqui a meses para entender uma escolha e encontraria lixo no lugar do argumento.\n\nCorrigido na hora: reescrevi a explicação, apaguei os três arquivos um a um (não com o comando de limpeza geral, que levaria junto o trabalho das outras sessões que estão na mesma pasta), e a lição virou entrada nova na memória de campo do projeto, com o jeito certo de fazer.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/259 — armadilhas/136; o commit corrompido foi corrigido com --amend antes do PR #257, e a árvore ficou limpa (git status vazio, conferido)",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
