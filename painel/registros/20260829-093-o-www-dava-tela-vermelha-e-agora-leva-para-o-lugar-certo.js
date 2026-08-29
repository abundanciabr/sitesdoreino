(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-093-o-www-dava-tela-vermelha-e-agora-leva-para-o-lugar-certo",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "O endereço do site com \"www.\" dava tela vermelha de site perigoso — agora leva para o lugar certo",
  detalhe: "Você perguntou hoje se o site estava com problema no cadeado, e mandou a foto do aviso. Medi tudo: o endereço principal (meshcraft.top) está impecável — cadeado válido até 21 de novembro, e o próprio Windows do seu PC confirma que confia nele.\n\nO problema estava no endereço IRMÃO, o que tem \"www.\" na frente. Quem digitasse www.meshcraft.top levava a tela vermelha grande de \"sua conexão não é particular\" — aquela que faz qualquer visitante fechar a aba na hora. E, se insistisse, caía numa página de erro.\n\nPOR QUE ISSO ACONTECIA: o endereço com \"www.\" existe no registro de domínios (veio de fábrica com o domínio, ninguém escolheu ter), e ele chegava até o servidor — mas o servidor nunca tinha pedido um cadeado para ele. Sem cadeado próprio, o servidor entrega um crachá genérico, sem assinatura de cartório, que navegador nenhum aceita.\n\nO CONSERTO tem duas peças, e uma sozinha não resolveria. Primeira: o cadeado do site passa a cobrir os dois endereços. Segunda: quem digitar com \"www.\" é levado automaticamente para o endereço certo. A ordem importa — só dá para levar alguém a outro endereço DEPOIS que o cadeado fecha; sem a primeira peça, a pessoa nunca chegaria a ser levada.\n\nUM DEFEITO MEU QUE O CI PEGOU ANTES DE IR PARA O AR: no primeiro desenho, eu mandei o desvio valer para tudo no \"www.\" — inclusive para o caminho por onde passa uma compra. Um guarda automático reprovou na hora, e com razão: desviar um pedido de compra no meio do caminho o transforma em outra coisa e o pedido se perde. Ajustei a faixa de alcance do desvio para deixar o caminho da compra intocado. Ninguém afrouxou o guarda — o erro era meu e foi corrigido no meu lado.\n\nAINDA NÃO ESTÁ NO AR: falta este PR ser aprovado, mergeado e publicado. Quando publicar, eu confiro o cadeado do \"www.\" de fora e registro a prova.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/502",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
