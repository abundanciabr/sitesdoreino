(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-105-abri-o-caminho-para-corrigir-o-nome-de-uma-sugestao",
  tipo: "decisao",
  quando: "2026-08-31",
  titulo: "Voce vai poder corrigir o nome e o texto de uma sugestao: este e o primeiro dos tres degraus",
  detalhe: "Voce me trouxe hoje um caso concreto: um aluno criou uma sugestao chamada 'turorial de cabelo avancado masculino', repetiu o mesmo erro numa segunda, e voce procurou no site onde corrigir esse nome e nao achou. Nao achou porque nao existia. Na tela da ideia dava para mover de fase, avaliar, assinar, arquivar e apagar — corrigir o texto era exatamente o que faltava.\n\nESTE DEGRAU NAO TEM TELA AINDA. Ele e o acordo escrito entre as duas partes do sistema: a parte que guarda as sugestoes precisa passar a aceitar 'corrija este texto', e por lei desta casa esse acordo muda sozinho, num pedido de mudanca separado do codigo, com voce tendo decidido antes. Foi o que este PR fez. Os dois degraus seguintes sao o miolo (a parte que guarda as ideias aprende a corrigir e a guardar o texto antigo) e a tela em si, em /admin/caixa/.\n\nAS DUAS COISAS QUE VOCE DECIDIU HOJE, e que eu perguntei antes de escrever qualquer linha:\n\nPRIMEIRA: da para corrigir o nome E o texto que o aluno escreveu, nao so o nome. Quem digita 'turorial' no titulo costuma repetir o erro no meio do texto, e uma ferramenta que consertasse so a primeira linha deixaria o outro erro vivo, sem nenhum caminho ate ele.\n\nSEGUNDA: a correcao e CALADA. O aluno nao ve marca nenhuma na pagina dele — nem 'editado', nem 'corrigido pela escola', nem data. Voce escolheu isso entre tres opcoes.\n\nE AQUI ESTA A PARTE QUE EU ACRESCENTEI, porque calada sozinha seria perigosa: o que estava escrito antes fica guardado inteiro, do lado de dentro, onde so quem administra alcanca. Cada campo corrigido vira uma linha com o texto velho, o texto novo, quem corrigiu e quando — e essa linha nao pode ser editada nem apagada por ninguem, nem por mim, porque o proprio banco de dados se recusa. Sem isso, 'correcao calada' viraria 'a escola pode reescrever a fala de um aluno e ninguem consegue provar o que ele disse'. O dia em que alguem reclamar do texto trocado e exatamente o dia em que essa prova faz falta.\n\nUMA TRAVA QUE VALE VOCE SABER: sugestao que voce ja apagou de vez nao volta por aqui. Corrigir o texto dela seria trazer de volta, por uma porta lateral, o conteudo que o apagar prometeu destruir — entao o pedido e recusado com essa frase.",
  autoridade: "rito",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/779 (Rito de Contrato, RITOS.md §3, etiqueta 'contrato'). Adicao pura: 120 linhas inseridas, nada removido nem renomeado. ci/contrato_aditivo.py PASS ('mudanca aditiva — nada removido'); ci/cerca-de-celula.sh PASS com 0 celulas tocadas (contrato nao viaja junto com codigo); ci/ci.py --apenas muralhas PASS nas 13 muralhas. O contrato congelado deste PR foi GERADO pelo exportador da celula rodando contra o codigo do degrau 2, e nao escrito a mao: ci/contract_freeze.py sugestoes deu PASS ('identico ao congelado', 1062 linhas comparadas, 10 operacoes com autenticacao conferida na fonte). Lei em docs/decisoes/DECISAO-corrigir-o-texto-de-uma-ideia.md. Balcao: TAR-085.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
