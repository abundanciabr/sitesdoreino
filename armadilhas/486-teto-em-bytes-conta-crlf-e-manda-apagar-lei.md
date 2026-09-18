---
schema_version: 2
armadilha: 486
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/padrao_de_trabalho.py
  - ci/tests/test_padrao_de_trabalho.py
guarda:
  tipo: teste
  detector: ci/tests/test_padrao_de_trabalho.py
sinal:
  - "teto de CLAUDE.md FAIL na bancada e PASS na CI"
  - "Mova história para docs/decisoes com o arquivo dentro do teto"
licao: Portão que mede tamanho de arquivo tem de normalizar CRLF antes de contar. No Windows com core.autocrlf=true o checkout ganha 1 byte por linha, e um teto medido em bytes crus reprova só na bancada de quem trabalha. Pior que o falso vermelho é o conselho dele, que manda apagar texto de verdade para consertar um fim de linha.
---

# Teto em bytes que conta CRLF reprova na bancada e manda apagar lei

`ci/padrao_de_trabalho.py` limita `CLAUDE.md` a 12.000 bytes e lia o arquivo com
`read_bytes()` cru. O repositório guarda LF: 11.994 bytes, dentro do teto. O
checkout Windows guarda CRLF: 12.231 bytes, 231 acima. As outras quatro
checagens do MESMO arquivo já normalizavam com `.replace("\r\n", "\n")`; só a do
teto não.

O efeito não é um vermelho chato. É um vermelho que dá uma ordem errada:

    teto de CLAUDE.md          FAIL   12231 de 12000 bytes
    Mova história para docs/decisoes, preservando obrigações e referências.

Quem abre bancada no Windows lê isso, acredita, e corta lei de verdade para
recuperar bytes que não existem em lugar nenhum. O portão que existe para
impedir que a lei seja revogada em silêncio estava pedindo exatamente isso.

O teste que devia pegar também não pegava, pela mesma causa: `_cenario` gravava
o repositório de mentira com `write_text`, que traduz para CRLF no Windows. A
conta que enche o arquivo até passar do teto (`(teto - len(conteudo)) // 2 + 1`)
ficava negativa, nada era acrescentado, e o teste dava verde sem ter mutilado
nada. Dois defeitos que se escondiam um ao outro.

Conserto: normalizar antes de medir no portão, e gravar LF no cenário de teste
(`write_bytes(texto.encode("utf-8"))`). Vale para qualquer guarda futuro que
compare tamanho de arquivo versionado: meça o que o repositório guarda, nunca o
que o sistema de arquivos entregou.
