(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-014-o-quadro-da-caixa-respondia-nao-encontrado-em-producao",
  tipo: "incidente",
  quando: "2026-08-27",
  titulo: "Você clicou em 'Ver o quadro de sugestões' e a Caixa disse 'Não encontrado' — o script que conserta já está pronto",
  detalhe: "Achei este PR mergeado sem registro enquanto trabalhava em outra coisa hoje, e estou pagando a dívida do livro para poder seguir (a regra do CLAUDE.md: nenhum merge fica sem contar a você). Não fui eu quem construiu — foi outra sessão sua, na hora em que você reportou o problema.\n\nO SINTOMA: você entrou na Caixa em produção, o login funcionou, mas ao clicar em 'Ver o quadro de sugestões' veio 'Não encontrado'.\n\nA CAUSA: o quadro de sugestões nunca foi criado no banco de produção — a célula nasceu em duas entregas (Lotes 6 e 7) e esse passo específico ficou no meio, sem dono. O código está certo: ele se RECUSA a inventar um quadro quando não existe nenhum (é a mesma regra de segurança de sempre — melhor recusar do que adivinhar errado).\n\nO CONSERTO: um script que cria o quadro que falta, seguindo a mesma regra de segurança do resto do projeto — só age se houver exatamente UM site de verdade para amarrar o quadro; qualquer ambiguidade e ele para sozinho, sem arriscar.\n\nNÃO CONSIGO CONFIRMAR DAQUI se o script já foi rodado na VPS — isso é sempre um passo seu, e eu não tenho como ver de fora se já aconteceu. Se 'Ver o quadro de sugestões' já está funcionando para você, pode ignorar este registro; se ainda estiver dando 'Não encontrado', é só rodar o script.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/277 — MERGED; infra/semear-caixa.sh; travas testadas fora da VPS e com respostas variadas do catálogo (armadilhas/132)",
  verificado_em: "2026-08-27",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "comunidade",
  vence_em_dias: null
});})();
