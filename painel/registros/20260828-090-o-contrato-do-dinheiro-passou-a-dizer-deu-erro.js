(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-090-o-contrato-do-dinheiro-passou-a-dizer-deu-erro",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "O contrato da parte do dinheiro passou a dizer 'deu erro' — com você presente, como a regra exige",
  detalhe: "Você confirmou disponibilidade e o rito foi tocado na hora. Este era o pedido mais antigo da sua caixa: estava aberto desde 21/08.\n\nO QUE ESTAVA ERRADO: desde 21/08 o sistema já se comportava certo — quando o Mercado Pago falha, a parte do dinheiro responde 'deu erro' em vez de fingir que a cobrança foi criada (o defeito antigo devolvia um QR de Pix em branco, com um botão de copiar que copiava nada). Só que o CONTRATO da célula — o documento oficial que lista tudo que ela pode responder — nunca listou essa resposta. Nenhum papel dizia à parte da compra o que fazer ao recebê-la.\n\nO QUE MUDOU: o contrato agora descreve essa falha por escrito, com nome próprio, e com a instrução exata para quem a recebe — repetir o pedido com a MESMA chave, nunca gerar chave nova (é o que impede cobrar duas vezes). Vale para as quatro portas que atravessam o Mercado Pago; a quinta, que só lê o banco, ficou de fora porque nunca pode falhar assim.\n\nPOR QUE ISSO NÃO VAI APODRECER: quem tirar essa resposta do código deixa o portão da célula VERMELHO na hora. O portão compara o documento oficial com o que o código realmente publica — e eu vi ele reprovar de verdade nesta sessão, não supus.\n\nUMA MENTIRA DE COMENTÁRIO CORRIGIDA JUNTO: dentro do código havia um bilhete dizendo 'isto fica, por ora, sem documentação'. Deixou de ser verdade neste PR, e por isso foi reescrito — bilhete que descreve um mundo que não existe mais manda o próximo robô para a pedra errada.\n\nAVISO HONESTO: este item e o do cartão de teste são da era do pagamento, congelada por ordem sua ('pagamento por último'). Você pediu os 7, então tratei os dois como reabertos. Isto NÃO reabre a frente de vendas — nenhuma linha de comportamento mudou, só o documento.",
  autoridade: "rito",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/417 (o contrato, etiqueta contrato, MERGED commit 2980a6697322) e PR https://github.com/abundanciabr/sitesdoreino/pull/420 (o lado do codigo). Evidencia vermelho-verde medida com python ci/contract_freeze.py pagamentos: baseline PASS (404 linhas); so o contrato = FAIL, com o diff acusando exatamente os quatro 502 a menos no exportado; contrato + codigo = PASS (431 linhas). Portoes locais do PR do codigo: black 24.10.0 limpo em 25 arquivos, mypy 1.13.0 Success em 39 arquivos.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: "20260821-001-h7-rito-de-contrato-do-502",
  gravidade: "verde",
  frente: "vender",
  vence_em_dias: null
});})();
