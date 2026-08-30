(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-037-main-vermelha-destravada",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "A linha principal ficou vermelha por 15 minutos e travou toda publicação — destravada",
  detalhe: "Enquanto eu entregava o mapa do site, a linha principal do projeto ficou vermelha e PAROU de publicar qualquer coisa no site. Isso é o desenho funcionando, não um defeito: quando algo está quebrado, o sistema se recusa a subir novidades por cima.\n\nO que causou: horas antes, outra tarefa fez uma mudança certa — três arquivos de índice das armadilhas deixaram de ser guardados no Git e passaram a ser MONTADOS na hora, para dois robôs pararem de brigar por eles. Faltou a outra metade da mudança: quem CONFERE esses arquivos precisa montá-los antes de olhar. Numa cópia limpa do projeto eles simplesmente não existiam, e dois testes passaram a ler um arquivo ausente.\n\nO efeito em cadeia: teste vermelho → alarme da linha principal vermelho → portão de publicação recusa subir qualquer célula. Três entregas já aprovadas ficaram paradas, inclusive a minha.\n\nO conserto foi de uma peça: os testes agora montam esses arquivos antes de medi-los, exatamente como a suíte da área administrativa já fazia com o painel. Também corrigi uma frase de documentação que ainda dizia que o arquivo era \"versionado\" — virou mentira no dia da mudança, e é dessa frase que a próxima pessoa tiraria a ideia errada.\n\nDepois disso a publicação voltou sozinha, e o mapa do site com busca e luz subiu junto.",
  autoridade: "github",
  evidencia: "PR #592 (https://github.com/abundanciabr/sitesdoreino/pull/592), fechando a issue #587 aberta pelo próprio alarme. Vermelho->verde simulando uma cópia limpa (apagando os três gerados): sem o conserto, 2 reprovações — exatamente os dois testes que a CI acusou (test_o_json_do_sino_aninha_additional_context e test_o_sinal_do_repositorio_real_e_lido_pelo_sino, com JSONDecodeError: Expecting value: line 1 column 1); com o conserto, 26 verdes, e 47 verdes somando os testes do índice. Depois do merge, o deploy c045725e terminou 'success' e o mapa (99 endereços, 8 com luz) subiu junto.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
