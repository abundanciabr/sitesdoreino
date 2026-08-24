# Edição de UMA linha vira diff do arquivo inteiro (`449 +++---` num arquivo intocado)

**Sintoma:** você troca uma frase dentro de um arquivo por script Python, roda
`git diff --stat` e lê:

```
 ARMADILHAS-OPERACAO.md | 449 +++++++++++----------
```

449 linhas alteradas num arquivo onde você mexeu em **uma célula de tabela**. O
conteúdo está certo — abrir o arquivo mostra exatamente a mudança que você queria, e
mais nada. O git é que enxerga tudo diferente. Costuma vir acompanhado de:

```
warning: in the working copy of 'ARQUIVO.md', LF will be replaced by CRLF the next time Git touches it
```

**Causa: você reescreveu a quebra de linha do arquivo inteiro sem perceber.** O padrão
que faz isso é este, e ele *parece* correto:

```python
texto = io.open(caminho, encoding="utf-8").read()            # <- o erro mora AQUI
io.open(caminho, "w", encoding="utf-8", newline="").write(texto.replace(a, b))
```

A leitura **sem `newline=""`** liga o modo *universal newlines* do Python: todo `\r\n`
do disco vira `\n` em memória, em silêncio. A gravação com `newline=""` então escreve
literalmente o que está em memória — LF puro. Num arquivo que era CRLF (o normal para
quem edita no Windows), **todas as linhas mudaram**, e só uma delas era sua.

O perigo real não é o `--stat` feio. É que um diff que toca o arquivo inteiro **conflita
com qualquer outra sessão** que esteja mexendo naquele arquivo (RETROSPECTIVA §7), e
enterra a sua mudança de verdade no meio de centenas de linhas idênticas — ninguém
revisa isso, nem humano nem agente.

**Solução — leia e escreva em BINÁRIO, e confira a contagem antes e depois:**

```python
bruto = io.open(caminho, "rb").read()
crlf = bruto.count(b"\r\n")
lf   = bruto.count(b"\n") - crlf

novo = bruto.decode("utf-8").replace(velho, novo_texto).encode("utf-8")
io.open(caminho, "wb").write(novo)

depois = io.open(caminho, "rb").read()
assert (depois.count(b"\r\n"), depois.count(b"\n") - depois.count(b"\r\n")) == (crlf, lf)
```

Em binário não existe conversão em nenhum dos dois sentidos, e a asserção transforma
"eu acho que preservei" em **medição** — que é a Lei 6 aplicada a uma edição de texto.

**Se já aconteceu, o conserto é barato** (nada se perde, porque o conteúdo está certo):

```bash
git checkout HEAD -- ARQUIVO.md
```

…e refaça a edição pelo caminho binário acima. Foi assim que este caso fechou: `449`
voltou a ser `2`.

**Como conferir sem cair no falso-positivo:** não use `grep -c $'\r'` — nesta máquina
ele mente (`armadilhas/019` mediu `88` num arquivo com **zero** bytes CR). A contagem
confiável é a do Python em modo binário, acima; e `git diff --stat` é o alarme mais
barato de todos — **olhe o número antes de commitar**.

> Escrever o script num arquivo em vez de heredoc é a outra metade da higiene de edição
> por script nesta máquina: `armadilhas/093`.
