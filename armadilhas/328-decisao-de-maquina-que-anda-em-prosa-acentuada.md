---
schema_version: 2
armadilha: 328
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  detector: ci/tests/test_utf8_na_fronteira.py
  motivo: são quatro guardas para quatro modos de morte distintos - a porta parar de pôr UTF-8 no ambiente, a ferramenta nova não passar pela porta, a marca ganhar acento, e as duas pontas divergirem; e um job windows-latest em muralhas.yml como rede para o que ninguém pensou em reproduzir
sinal:
  - "[a-zA-Z]\\ufffd[a-zA-Z]"
---

# Decisão de máquina que anda em prosa acentuada morre na travessia, e morre calada

**Sintoma.** Não há sintoma. É esse o problema.

Uma funcionalidade inteira simplesmente não acontece, sem erro, sem aviso, sem
uma linha vermelha em lugar nenhum. Neste caso foi a remedição do ERROR do
portão de pouso: `ci/esperar.py --e-pousar` deveria tentar de novo quando o
GitHub responde "ainda estou calculando se há conflito", e nunca tentava. O robô
desistia na primeira, exatamente como antes de a cura existir.

O que aparece, se alguém rodar a suíte na mão numa máquina Windows:

```
FAILED ci/tests/test_espera.py::test_o_portao_que_nao_conseguiu_medir_e_remedido_e_o_pouso_sai
FAILED ci/tests/test_espera.py::test_o_ERROR_que_nao_para_de_vir_desiste_e_conta_a_recusa_inteira
2 failed, 1676 passed
```

E os mesmos dois testes ficam **verdes na CI**, em todo PR, o tempo todo.

**Causa.** No Windows, um `python` filho escreve no cano pela codepage do
console (cp1252), enquanto todo leitor desta casa decodifica utf-8. Medido nesta
máquina em 04/09/2026:

```
o filho escreveu ... b'calcula isso de forma ass\xedncrona\r\n'
o pai leu .......... 'calcula isso de forma ass�ncrona\n'
a marca casa? ...... False
```

O `errors="replace"` do pai (que está certo, e evita uma exceção) transforma o
byte inválido em `�` e a leitura segue adiante como se nada tivesse
acontecido. Nada explode. O que muda é o resultado de um `in`.

E aí está o veneno: **o `esperar.py` decidia se remedia procurando a frase
`"calcula isso de forma assíncrona"` na saída do portão.** Uma decisão de
máquina viajando dentro de uma frase escrita para um humano ler. Bastou um `í`
para a decisão virar `False` para sempre.

A frase tinha ainda uma segunda forma de morrer, independente da primeira: ela
existia copiada em três arquivos (`mergear.py`, `esperar.py` e o teste).
Reescrever a mensagem para uma pessoa entender melhor mataria a remedição em
silêncio, com a suíte inteira verde — porque o teste carregava a mesma cópia
velha.

**Por que ninguém viu.** Os 33 jobs deste repositório rodavam em
`ubuntu-latest`, e nenhum outro. Os robôs desta casa trabalham na máquina
Windows do mantenedor. Toda diferença entre os dois sistemas era, por
construção, invisível para a CI — e diferença de codepage não grita.

A remedição foi construída em 03/09/2026 porque dois PRs do mesmo lote, #954 e
#956, morreram sem ela. **Ela nasceu inerte na única máquina onde roda**, e
ficou assim por um dia, verde em todo PR.

**E não foi surpresa.** Esta é a terceira vez da mesma classe:

| quando | onde | o que ficou |
|---|---|---|
| PR #15 | `armadilhas/003` — acento em cp1252 vira lixo | só a nota |
| 27/08/2026 | `armadilhas/138` — a mesma classe, no stdin | só a nota |
| 04/09/2026 | esta — a mesma classe, agora numa DECISÃO | a cura abaixo |

A `138` chegou a escrever a previsão exata do que aconteceria, com todas as
letras: *"o required check `muralhas` roda em `ubuntu-latest`, não Windows"*.
Estava certa, estava escrita, e nada foi construído. Catálogo cura o caso; só
mecanismo cura a classe (`docs/decisoes/RETROSPECTIVA-FASE-D.md` §2, garantia
sem mecanismo).

**Solução.** Três coisas, e cada uma fecha uma porta diferente.

1. **UTF-8 no ambiente de todo filho, numa linha só.**
   `_nucleo.configurar_saida()` passou a fazer
   `os.environ.setdefault("PYTHONUTF8", "1")` além de reconfigurar a própria
   saída. Filho herda `os.environ`, então a porta por onde as 33 ferramentas de
   `ci/` já passam cobre as **90 fronteiras que decodificam texto** — 89 delas
   não declaravam ambiente nenhum. A mesma linha em `ci/tests/conftest.py`,
   porque o pytest não passa por aquela porta. Remendar chamada a chamada seria
   a esteira infinita: quem escrevesse a de número 91 recomeçaria a doença.
   (Não cobre filho que não é Python — `git`, `gh`, `docker`. `PYTHONUTF8` é
   chave do interpretador, e dizer o contrário seria garantia sem mecanismo.)

2. **A decisão saiu da prosa.** `mergear.py` declara
   `MOTIVO_GITHUB_AINDA_CALCULANDO = "MOTIVO  github-ainda-calculando"`, em
   ASCII puro, e o `esperar.py` **importa** essa constante em vez de copiar a
   frase. A mensagem em português continua lá, inteira, e agora pode ser
   reescrita à vontade sem quebrar nada.

3. **A cegueira acabou.** Um job `windows-latest` no `muralhas.yml` roda a
   mesma suíte no sistema onde os robôs de fato trabalham. Custo zero
   (repositório público), em paralelo com os outros: não muda o relógio do PR.
   Ele bloqueia o pouso do mesmo jeito, porque `ci/mergear.py` avalia todos os
   checks do rollup, não uma lista fixa.

**Prova.** `ci/tests/test_utf8_na_fronteira.py` (5 guardas) e
`test_a_remedicao_sobrevive_ao_portao_que_escreve_em_cp1252` em
`ci/tests/test_espera.py`. Mutação deliberada, uma linha: devolvendo a marca à
prosa acentuada, os dois caem —

```
FAILED test_a_remedicao_sobrevive_ao_portao_que_escreve_em_cp1252
FAILED test_a_decisao_de_remedir_anda_em_marca_ascii_e_numa_fonte_so
E  AssertionError: a marca ganhou um caractere não-ASCII
```

O guarda do cp1252 **manda o dublê escrever cp1252**, então roda no Linux da CI
em 9 segundos. Foi de propósito: o perigo era de plataforma, e virou uma linha
de fita.

**A régua que fica, e é maior que este caso:** *prosa é para gente ler; decisão
de máquina anda em marca de máquina.* Se um `if` compara uma frase que
atravessou um cano entre dois processos, ele não está medindo o que você acha —
está medindo a codepage da máquina e o humor de quem revisar a mensagem depois.

**E a régua de baixo:** quando um teste reprova só na sua máquina e passa na CI,
isso não é "flaky", nem "coisa do meu ambiente". É a CI sendo cega para um
sistema onde o código roda de verdade. A pergunta certa não é como fazer o teste
passar aqui: é o que mais essa cegueira está escondendo.
