# Integração automática sem o rito de pouso

Decisão expressa do mantenedor em 13/09/2026, no pedido de fazer o resultado
aparecer em dois pedaços. O primeiro liga o painel local antes desta mudança.

A proteção nativa da main fica: PR obrigatório, sem bypass, com muralhas e
ci-celula-gate obrigatórios. Saem o revisor obrigatório, o atestado de revisão,
a etiqueta de pouso e a maestro no caminho da integração. Esta decisão substitui
as disposições anteriores sobre esses quatro requisitos, inclusive fichas de
agentes e decisões históricas. Não altera o contrato congelado nem CODEOWNERS.

O workflow lê a main e lista PRs prontos da própria origem. Os dois checks
verdes no SHA atual permitem o merge. Base atrasada é atualizada e volta a ser
medida; conflito, rascunho ou ausência de sucesso não vira aprovação.

Mandato nos caminhos CODEOWNERS é uma autorização do dono, e vale onde ele a
deu: dita na sessão vale tanto quanto digitada no site (emenda dele em
19/09/2026). Quem a recebeu transcreve na descrição do PR, que sai da conta
dele, `Mandato-do-mantenedor:` seguido do pedido, dos caminhos autorizados
separados por espaços e da origem. A declaração registra uma autorização já
recebida; o executor não pode inventá-la nem parar a tarefa para mandar o dono
repetir no site o que já pediu. Sem autorização nenhuma, pergunte a ele na
própria sessão. Terceiros não concedem esse mandato. Contratos mantêm seu rito.

Transição: o executor pode integrar o PR desta decisão pelo portão atualizado
após os checks verdes. A primeira integração instala o workflow; a prova seguinte
usa um PR de trabalho real e ocorre sem chamada manual de merge.

Prova local inicial: test_merge_automatico.py passou de 12 falhas antes da
mudança para 12 aprovações depois, incluindo recusa de checks sem sucesso,
mandato ausente e autorização de terceiro. Evidência remota e tempo do push ao
merge serão registrados no livro após serem medidos.

**Quem faz valer:** ci/mergear.py, .github/workflows/pouso.yml e o ruleset da main.
