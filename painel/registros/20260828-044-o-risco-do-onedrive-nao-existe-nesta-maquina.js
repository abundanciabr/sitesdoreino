(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-044-o-risco-do-onedrive-nao-existe-nesta-maquina",
  tipo: "nota",
  quando: "2026-08-28",
  titulo: "O risco do OneDrive não existe nesta máquina — você me disse, eu conferi, e está encerrado",
  detalhe: "Duas das cinco IAs consultadas apontaram, sem uma saber da outra, que guardar o projeto dentro do OneDrive estraga o histórico em silêncio quando vários robôs trabalham juntos. Eu levei isso a sério e te perguntei se dava para mover a pasta.\n\nVocê respondeu que o OneDrive está apenas instalado, sem conta de usuário, e que você não usa para nada. Conferi antes de arquivar, e confirmei por três caminhos independentes: o programa do OneDrive não está em execução; não há nenhuma conta configurada nesta máquina; e a pasta do projeto não tem nenhuma marca de sincronização com a nuvem — para o Windows ela é uma pasta local comum, que por acaso tem 'OneDrive' no nome.\n\nEntão não há o que mover. O conselho das duas IAs estava certo em geral e não se aplica aqui: elas não tinham como saber que a pasta era só um nome. Fica encerrado, com a medição registrada para ninguém precisar redescobrir.\n\nÉ a terceira vez hoje que medir venceu supor — e as três a favor: a proteção que eu achava que não existia já estava ligada; o comando que dizia ter ligado a trava não tinha ligado; e agora um risco que parecia real não é. Nas três, o que decidiu foi conferir em vez de acreditar.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/383. Conferido em 28/08/2026 nesta maquina, por tres sinais independentes: (1) Get-Process OneDrive => nao esta em execucao; (2) HKCU:\\Software\\Microsoft\\OneDrive\\Accounts\\Personal => nenhuma conta pessoal configurada; (3) atributos da pasta C:\\Users\\davia\\OneDrive\\Documentos\\sitesdoreino => 'Directory' apenas, SEM ReparsePoint, ou seja, sem ponto de sincronizacao com a nuvem. Declaracao do mantenedor na mesma sessao: 'o OneDrive esta apenas instalado no PC mas eu nao uso, nao tem conta de usuario'.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: "20260828-032-voce-decidiu-projeto-aberto-e-a-mudanca-da-pasta",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
