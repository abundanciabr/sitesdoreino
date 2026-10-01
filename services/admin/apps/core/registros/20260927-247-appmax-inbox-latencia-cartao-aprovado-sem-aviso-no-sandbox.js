(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260927-247-appmax-inbox-latencia-cartao-aprovado-sem-aviso-no-sandbox",
  tipo: "medicao",
  quando: "2026-09-27",
  titulo: "Latência do aviso Appmax de cartão: não chegou no sandbox em 3 pedidos",
  detalhe: "Descoberta na main (run 36326508157) achou 47 candidatas de cartão dos últimos 7 dias; medi 3 aprovadas (runs 36326584933, 36326621783, 36326661927), todas do run 36298068269 (matriz appmax-sandbox-tela, cartão final 0010). As 3: PASS, zero avisos na inbox, um efeito (pagamento.aprovado) cada. A aprovação chega por outro caminho (resposta síncrona da tokenização), não pelo webhook; o aviso de cartão não chegou à inbox em nenhuma das 3 janelas lidas. Latência ainda não medida para cartão; reentregas (TAR-821) não se aplicam sem aviso.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/36326584933",
  verificado_em: "2026-09-27",
  precisa_do_dono: false,
  responde_a: null,
  tarefa: "TAR-872",
  gravidade: "ambar",
  frente: "fabrica",
  area: "ci"
}); })();
