(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-114-o-aviso-de-liberacao-esta-construido-de-ponta-a-ponta",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "O aviso de liberacao esta construido de ponta a ponta — cinco pecas, e a parte que guarda os alunos ganhou VOZ",
  detalhe: "VOCE ESCOLHEU, e foi construido. Quando voce liberar alguem da fila, essa pessoa passa a receber um recado no sininho do site.\n\nAS CINCO PECAS:\n\n1. O portao do CI aprendeu a medir contrato de evento — sem isso, editar um era impossivel (PR #523, e a licao 179 sobre numero de registro veio junto no PR #509).\n2. Os contratos: a pergunta nova na entrada com o Google, e o tipo de aviso novo (PR #524).\n3. A tela da Caixa aprendeu a desenhar o aviso novo — ANTES de alguem publicar um, porque a tela antiga daria erro 500 na primeira carta que nao fosse de sugestao (PR #527).\n4. A entrada com o Google ganhou a porta que traduz e-mail em numero de plataforma (PR #528).\n5. A parte que guarda os alunos ganhou VOZ: ate hoje ela so escutava, e agora ela afirma um fato ao resto da plataforma (PR #530).\n\nO CUIDADO QUE CARREGA A ENTREGA: a carta NUNCA impede a liberacao. Se a peca da entrada estiver fora do ar, se a senha nao estiver posta, se a pessoa nunca tiver entrado com o Google — a liberacao acontece igual, e a carta simplesmente nao existe. Voce clicar em 'Liberar' e nada acontecer, por causa de uma peca de notificacao, seria muito pior que um aviso a menos.\n\nE A CARTA NASCE DENTRO DA MESMA TRANSACAO DO FATO. Se a liberacao der errado no meio, a carta vai junto — nunca existe aviso para algo que nao aconteceu.\n\nSO QUEM GANHA ACESSO E AVISADO. Recusar nao avisa, pausar nao avisa, encerrar nao avisa. Nao e esquecimento: quem PERDE o acesso nao consegue abrir a pagina de avisos, porque ela mora dentro da Caixa e a Caixa so abre para aluno. A carta seria escrita e nunca lida. A bifurcacao esta no registro 108.\n\nFALTA UM COMANDO SEU para o aviso sair de verdade — esta no registro 113, com a linha pronta para colar.",
  autoridade: "github",
  evidencia: "PRs #509, #523, #524, #527, #528 e #530, todos mergeados em 29/08/2026. Vermelho->verde em cada um: #523 (33 passed em ci/tests/test_contrato_aditivo.py, 1037 em ci/tests inteiro), #527 (490 passed na celula sugestoes; o guarda novo test_uma_carta_de_assunto_desconhecido_NAO_derruba_a_pagina reprovava com NoReverseMatch/500 na main de antes), #528 (95 passed na celula identidade, freeze do contrato PASS em 219 linhas), #530 (137 passed na celula alunos com postgres 17 e redis 7 locais, freeze PASS em 934 linhas, e o envelope validado contra o ARQUIVO do contrato e nao contra uma copia dentro do teste). ci/ci.py --apenas muralhas PASS em todos.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: "20260829-108-o-sino-da-matricula-voce-decidiu-e-falta-construir",
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null
});})();
