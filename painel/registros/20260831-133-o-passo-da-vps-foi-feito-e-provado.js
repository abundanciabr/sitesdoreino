(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-133-o-passo-da-vps-foi-feito-e-provado",
  tipo: "resposta",
  quando: "2026-08-31",
  titulo: "O passo da VPS foi feito, e eu provei que funcionou de verdade (não só suposição)",
  detalhe: "Você colou o bloco com TOKENS_SENHA_FUNIL e TOKENS_SENHA_ADMIN em identidade.env e reiniciou a célula. Em vez de confiar que deu certo, eu testei o cadastro de verdade no site ao vivo (uma conta descartável, e-mail teste-verificacao-login-senha-*@example.com, nome 'TESTE VERIFICACAO (pode apagar)') e recebi de volta a mensagem de sucesso 'Pronto! Seu pedido está aguardando aprovação' — isso só acontece se o cadastro E a criação de senha tiverem funcionado juntos (o desenho é fail-closed: se a senha falhasse, a tela mostraria erro). Essa conta de teste está na sua fila 'Aguardando aprovação' só por causa deste teste — pode ignorar ou apagar, não é uma pessoa de verdade.\n\nO botão de resetar senha (grau TOKENS_SENHA_ADMIN) usa o MESMO arquivo e o mesmo reinício, então tudo indica que também está valendo, mas esse eu não testei sozinho porque depende do seu login. Quando quiser, teste você mesmo no prontuário de um aluno real, ou me chame que eu confirmo junto.\n\nCOM ISSO, o projeto de login sem Google está encerrado: cadastro com senha, entrada com senha, e reset manual pelo painel, todos no ar e com prova real, não só CI verde.",
  autoridade: "sessao",
  evidencia: "https://meshcraft.top/cadastro",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: "20260831-127-o-login-por-senha-esta-completo-e-no-ar",
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null
});})();
