# Consultoria — a gamificação da escola

**Rodada fechada em 30/08/2026.** Esta pasta arquiva a consultoria externa que
desenhou o sistema de gamificação da Meshcraft Academy (o "Sistema de Formação
de Criadores"), no padrão da casa: prompt → pareceres → auditorias → VEREDITO.

## O que tem aqui

| Arquivo | O que é |
|---|---|
| `PROMPT-CONSULTORIA.md` | O prompt colado pelo mantenedor nas outras IAs (as duas versões: a primeira, com a premissa errada sobre a escola, e a corrigida) |
| `resposta-consultor-1.txt` … `-6.txt` | Os 6 pareceres, VERBATIM, como chegaram (fontes nomeadas quando o mantenedor as nomeou) |
| `auditoria-1.txt` … `-5.txt` | As 5 auditorias independentes do veredito consolidado, VERBATIM |
| `VEREDITO.md` | A consolidação auditável: matriz de rastreabilidade, consensos com argumento, recusas com motivo, correções das auditorias e as 4 decisões do mantenedor |

## Como esta rodada funcionou

1. O mantenedor colou o prompt em 6 IAs diferentes e trouxe os pareceres um a um.
2. Cada parecer foi analisado na hora (aceita / aceita com mudança / recusada,
   com motivo) e as divergências viraram placar.
3. As decisões que só o dono podia tomar foram consolidadas em UMA pergunta
   estruturada (ligas, ritmo, nomes, validação) — nunca uma caixa por consultor.
4. O veredito preliminar foi então submetido a 5 auditorias independentes
   (inclusive de IAs que tinham dado parecer), que produziram ~35 correções
   reais absorvidas no desenho final.

## Onde a história continua

- O desenho de engenharia (célula `gamificacao`, eventos, contratos, escada de
  PRs): `docs/decisoes/PLANO-CELULA-GAMIFICACAO.md`.
- O playbook de produto (o manual do jogo, para leitura): publicado como
  artefato privado do mantenedor em 30/08/2026.
- O que aconteceu depois: o livro (`painel/registros/`), como sempre.

Regra desta pasta (a mesma do fórum): pareceres e auditorias são material
bruto e **não se editam**. Correção ou releitura vira registro novo no
VEREDITO, nunca reescrita do arquivo original.
