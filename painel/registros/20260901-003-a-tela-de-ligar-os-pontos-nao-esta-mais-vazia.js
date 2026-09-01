(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-003-a-tela-de-ligar-os-pontos-nao-esta-mais-vazia",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A sua tela de ligar os pontos nao esta mais vazia",
  detalhe: "Voce abriu https://meshcraft.top/admin/economia/ ontem e ela estava vazia. O motivo ja tinha sido achado (as regras nunca tinham sido criadas no servidor, so no banco de teste) e o conserto ja estava pronto: um botao de publicacao. Faltava alguem apertar esse botao, e ninguem tinha apertado.\n\nApertei agora. As regras existem na producao:\n\n- 6 regras de pontuacao\n- 10 niveis\n- 5 missoes\n- 7 conquistas\n- 4 ligas\n- 5 itens de decoracao\n\nTODAS DESLIGADAS, e o proprio comando conferiu isso e disse em voz alta: 'nenhuma linha ativa neste site'. Ligar continua sendo decisao sua, uma regra de cada vez, na tela.\n\nO QUE VOCE PODE FAZER AGORA, se quiser ver o numero mexer: abra a tela, ligue a regra 'Ter a propria sugestao feita' (a que voce escolheu, 40 pontos, a unica sem espera de 24h), escreva uma sugestao na Caixa e marque ela como pronta. Os 40 pontos aparecem no seu perfil na hora. Os 5 Cristais que a regra promete NAO vao sair, e a tela avisa isso antes do clique: a lista de origens que podem criar Cristal e fechada de proposito, e mexer nela e outra decisao sua, noutro dia.\n\nPOR QUE A PROVA NAO E 'O COMANDO RODOU SEM ERRO': o script conta as linhas no banco DEPOIS de criar, pelo mesmo numero de escola que a sua tela consulta, e so entao imprime a linha de conclusao. Comando que termina sem erro nao prova que criou nada, e essa confusao ja custou caro aqui.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/33458525884 — o workflow `semear-economia` (criado no PR #796) rodado em 01/09/2026, conclusao `success` conferida por `gh run view --json status,conclusion`, nunca pelo exit de um pipe. A saida crua do log traz a contagem feita do lado de fora do comando: 'regras de pontuacao no banco ...... 6', 'dessas, ligadas ................... 0', e a linha 'PRONTO: a economia da escola existe', que so e impressa no caminho feliz.",
  verificado_em: "2026-09-01",
  precisa_do_dono: false,
  responde_a: "20260831-122-a-tela-abriu-vazia-e-o-motivo-era-outro",
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
