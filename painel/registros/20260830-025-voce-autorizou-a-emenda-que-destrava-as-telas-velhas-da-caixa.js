(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-025-voce-autorizou-a-emenda-que-destrava-as-telas-velhas-da-caixa",
  tipo: "decisao",
  quando: "2026-08-30",
  titulo: "Voce autorizou ensinar o Admin a mostrar o documento que liberou cada ideia — e isso destrava as telas velhas da Caixa",
  detalhe: "UM ROBO PAROU DE PROPOSITO HOJE, E ELE ESTAVA CERTO. A tarefa dele era aposentar as telas antigas de moderacao da Caixa — as que ja foram substituidas pelo Admin. Antes de aposentar, ele conferiu as CINCO telas velhas uma a uma, em vez de confiar na promessa escrita.\n\nQUATRO TINHAM SUBSTITUTA IDENTICA. A quinta nao tinha nenhuma: a que mostra COM BASE EM QUAL DOCUMENTO ASSINADO cada ideia foi liberada para virar obra — qual documento, quem aprovou, quando, quem registrou. O Admin de hoje so sabe dizer duas coisas: 'assinada' ou 'nao assinada'. Ele deixa ASSINAR, mas nao deixa CONFERIR DEPOIS o que foi assinado.\n\nPOR QUE ISSO IMPORTA: essa assinatura e a trava mais dura da Caixa — e ela que autoriza uma ideia a virar obra de verdade, e so quem esta na lista de aprovadores atravessa. Aposentar as telas velhas hoje deixaria inalcancavel, para sempre, a resposta de 'com base em que isto foi liberado'.\n\nVOCE ESCOLHEU A OPCAO COMPLETA: ensinar o Admin a mostrar a ficha inteira, e so DEPOIS aposentar as telas velhas. Voce escolheu isso contra a alternativa de aposentar so as quatro que ja tem substituta, sabendo que custa um passo a mais e que passa pelo portao mais rigoroso do projeto (o que guarda os contratos entre as pecas).\n\nISSO VIROU A TAREFA TAR-023 na fila, com a escada de quatro passos escrita dentro: primeiro o contrato, depois a peca da Caixa responder a ficha, depois o Admin mostrar, e so entao as cinco telas velhas serem aposentadas — redirecionando atras do cracha, nunca apagando endereco. O ultimo passo fecha a TAR-014, que ficou bloqueada esperando exatamente esta sua palavra.\n\nO robo que parou nao perdeu tempo: ele deixou a auditoria pronta, rota por rota, e o proximo robo comeca de onde ele parou.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/578 — este PR, que traz a TAR-023 e este registro. A autorizacao foi dada por ele em caixa de pergunta estruturada, em 30/08/2026, escolhendo 'Ensinar o Admin a mostrar' contra 'Aposentar as 4 que tem substituta' e 'Deixar tudo como esta'. O vazio foi MEDIDO pelo robo da TAR-014 e esta no registro 20260830-019 (PR 572): GET /forms/sugestoes/moderacao/<id>/changespec expoe change_id, documento, aprovado_por, aprovado_em, registrado_por e registrado_em, enquanto services/admin/apps/core/templates/admin/caixa_ideia.html conhece so o booleano tem_changespec, e contracts/sugestoes.openapi.yaml nao carrega nenhum dos campos da ficha.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: "20260830-019-parei-antes-de-aposentar-a-moderacao",
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
