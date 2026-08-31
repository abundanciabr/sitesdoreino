(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-085-uma-ferramenta-para-saber-se-o-aviso-chega-mesmo",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "Uma ferramenta para saber se o aviso chega mesmo, e a resposta sobre o botao no painel",
  detalhe: "Voce pediu duas coisas: mandar um aviso de teste para o Lucas, e um botao no seu painel para mandar avisos daqui em diante. Sao duas respostas diferentes, e as duas estao aqui.\n\nSOBRE O AVISO PARA O LUCAS: um aviso no celular so chega a quem LIGOU os avisos naquele aparelho. Nao existe jeito de ligar por ele, nem eu nem voce: e o navegador dele que guarda essa permissao. Como o recurso subiu hoje, e bem provavel que ele ainda nao tenha ligado.\n\nEntao, em vez de prometer, construi a ferramenta que RESPONDE essa pergunta: um comando que primeiro CONTA quem ja ligou os avisos, sem enviar nada, e so envia se voce mandar explicitamente. Se aparecer 'nenhum', a resposta esta dada e nao ha o que testar ainda. Se aparecer alguem, voce dispara para aquela pessoa e a gente ve chegar.\n\nEle nao suja a caixa de avisos de ninguem (nao grava nada), e faz exatamente o ultimo passo que a entrega real faz: se chegar na tela, o caminho inteiro funciona.\n\nSOBRE O BOTAO NO PAINEL, e aqui e uma correcao de rota que eu prefiro dizer agora: ELE JA ESTA PLANEJADO, com um desenho aprovado hoje mesmo, noutra sessao. A decisao foi 'servico no contrato, incentivo na minha tela': a mensagem que VOCE escreve mora numa tela sua e pode ser reescrita depois sem estragar o sentido dos avisos ja enviados. A tarefa existe no balcao (TAR-078) e depende do motor de mensagens, que esta sendo construido.\n\nSe eu fizesse um botao separado agora, criaria uma SEGUNDA casa para 'mensagem escrita pelo dono' — que e exatamente o que a lei anti-duplicacao proibe, e o tipo de atalho que cobra caro depois. Preferi te contar em vez de construir dois caminhos para a mesma coisa.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/761. 8 testes novos, um por modo de falha do comando: so-de-olhar nao envia, sem chave ele avisa em vez de fingir, recusa do servidor aparece como nao-saiu, aparelho morto sai do banco, o teste nao grava carta, e o endereco do aparelho sai cortado na tela (armadilhas/090). 144 verdes na celula (as duas de indice exigem Postgres e rodam no CI).",
  verificado_em: "2026-08-31",
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
