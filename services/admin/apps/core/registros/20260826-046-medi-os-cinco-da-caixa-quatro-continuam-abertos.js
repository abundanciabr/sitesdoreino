(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-046-medi-os-cinco-da-caixa-quatro-continuam-abertos",
  tipo: "medicao",
  quando: "2026-08-26",
  titulo: "Medi os cinco pedidos da sua caixa: um estava feito, quatro continuam abertos — com a prova de cada um",
  detalhe: "Você disse que a caixa mostrava coisas já resolvidas. Em vez de fechar na sua palavra ou insistir na minha, fui medir os cinco. Resultado: um estava feito (o Docker, já fechado em registro próprio) e quatro NÃO estão. A prova de cada um:\n\n2) O 502 NO CONTRATO DA CÉLULA DO DINHEIRO — ABERTO. Procurei o código 502 nos dois contratos de dinheiro (pagamentos e checkout): não existe em nenhum dos dois. O que está escrito lá são outras respostas (201, 404, 409, 422). Este é o único dos cinco que exige uma sessão COM você de verdade — é mudança de contrato, e o rito da casa manda você presente.\n\n3) A CREDENCIAL DE TESTE DO MERCADO PAGO NO COFRE — ABERTO. O cofre do GitHub tem exatamente duas credenciais guardadas: a chave de publicação e o endereço do servidor. Nenhuma é do Mercado Pago. (Sem urgência: é da era do pagamento, pausada por sua ordem.)\n\n4) A PORTA LATERAL DO SERVIDOR — ABERTO, e é o único com peso de segurança. Bati direto no endereço numérico do servidor, de fora: ele respondeu. Também perguntei à porta de administração remota e ela se identificou normalmente para o meu PC. Um servidor protegido teria ficado em silêncio nas duas.\n\n5) A SEGUNDA CONFERÊNCIA DE TRADUÇÃO — ABERTO. Depende de uma credencial paga, e ela não está no cofre (mesma medição do item 3).\n\nPOR QUE A CAIXA NÃO SE ENGANOU: ela mostra pedido sem resposta, e quatro deles realmente não têm resposta. O que faltava era medir — e agora está medido, com data.",
  autoridade: "sonda",
  evidencia: "medições de 26/08/2026: 'gh secret list' devolve apenas DEPLOY_SSH_KEY e VPS_HOST; grep de '502' em contracts/pagamentos.openapi.yaml e contracts/checkout.openapi.yaml não encontra nada; http://217.196.62.220/ responde 301 e https:// responde 404 (servidor alcançável direto pelo IP); a porta 22 do mesmo IP devolveu o banner 'SSH-2.0-OpenSSH_9.6p1 Ubuntu-3' do PC do mantenedor",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
