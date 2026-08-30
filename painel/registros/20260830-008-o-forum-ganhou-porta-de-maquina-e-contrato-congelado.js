(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-008-o-forum-ganhou-porta-de-maquina-e-contrato-congelado",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O fórum ganhou a peça que permite trocar o motor dele um dia sem quebrar o site",
  detalhe: "Quando você decidiu construir o fórum na casa, os consultores deixaram uma condição junto: o resto do site NUNCA deve depender diretamente do motor do fórum, para que dê para trocar esse motor no futuro sem quebrar nada.\n\nAté hoje isso era só uma frase escrita num documento. Virou peça de verdade.\n\nO QUE ENTROU: uma \"porta de máquina\" — um jeito fixo e documentado de outra parte do site perguntar coisas ao fórum (quais são as áreas abertas, quais as conversas mais recentes, quantas existem). E o contrato dessa porta ficou CONGELADO: se alguém mudá-la sem passar pelo ritual, a esteira reprova o trabalho.\n\nA REGRA DURA DESSA PORTA: ela só fala de área PÚBLICA. Nem conteúdo, nem contagem, nem a existência de área trancada. O motivo é simples: nessa porta não chega pessoa nenhuma — ela sabe QUAL PARTE DO SITE está perguntando, nunca QUEM é o visitante. Sem visitante, a única resposta honesta é o que qualquer um já veria de graça. E não sai dado pessoal: nem e-mail, nem quem leu o quê.\n\nO teste que protege isso não é decorativo: ele monta áreas trancadas COM conteúdo dentro e exige que nada apareça. Removendo o filtro de propósito, 4 testes ficam vermelhos.\n\nPROVA DE FORA, medida na internet pública depois do deploy: as três operações da porta respondem 401 (senha exigida), inclusive com senha inventada, enquanto a página do fórum responde 200. E a muralha do contrato aprova na linha principal: idêntico ao congelado, 3 operações com autenticação conferida.\n\nUM ERRO MEU, achado e corrigido no mesmo dia: eu havia copiado de outra célula um comentário dizendo que essa porta não era alcançável pela internet. Aqui era — a diferença é uma linha de configuração que só o fórum tem. Nada estava inseguro (a porta já exigia senha própria), mas o comentário ensinava errado quem viesse depois. Corrigido, e a lição virou entrada permanente no catálogo de armadilhas (a de número 186), com a medição junto.\n\nESTE ERA O DEGRAU 1 DA ESCADA que você me deu, e ele estava travado por um pré-requisito que ninguém tinha visto: não dá para congelar o contrato de uma porta que não existe. Você decidiu, na caixa de pergunta, construir a porta. Foi o que fiz — e agora a escada inteira da lei do fórum está cumprida.\n\nEntregas deste bloco: #552 (a porta), #555 e #557 (a lição), #556 (o contrato congelado).",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/556",
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
