# Traz para este PC as cópias de segurança da VPS: o cofre fora da VPS.
#
# Copia só o que é novo ou mudou. Traz também as senhas (env/ e .env) para a pasta senhas.
# Dos backups do banco guarda só os últimos 7 dias, como a VPS (escolha do mantenedor em 02/10/2026).
# Cópia preparada para chave SSH nova com comando forçado; não foi instalada na tarefa agendada.
# Uso futuro: powershell -NoProfile -ExecutionPolicy Bypass -File puxar-cofre-restrito.ps1
# Guia: infra/COMO-RESTAURAR.md.
param(
  [string]$Cofre = "$env:USERPROFILE\Cofre-sitesdoreino",
  [string]$Vps = "sitesdoreino-cofre",
  [switch]$PreservarCopias
)
$ErrorActionPreference = "Stop"
if ($Vps -notmatch '^[A-Za-z0-9_-]+$') { throw "alias SSH inválido" }
# Uma copia por vez: a de logon e a diaria podem se encontrar.
$umaPorVez = New-Object System.Threading.Mutex($false, "Local\CofreSitesdoreino")
if (-not $umaPorVez.WaitOne(0)) { Write-Output "Outra copia ja esta rodando."; exit 0 }
$ssh = "$env:WINDIR\System32\OpenSSH\ssh.exe"
$tar = "$env:WINDIR\System32\tar.exe"
$utf8 = New-Object System.Text.UTF8Encoding $false
$cofreAbsoluto = [System.IO.Path]::GetFullPath($Cofre)
New-Item -ItemType Directory -Force $cofreAbsoluto | Out-Null
$Cofre = $cofreAbsoluto
$relatorio = @("Ultima copia: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') (hora deste PC)", "")
$tudoIgual = $true
# Backup com carimbo de antes deste dia (UTC) nao vem e sai daqui: ficam os ultimos 7 dias.
$limite = [DateTime]::UtcNow.AddDays(-7).ToString("yyyyMMdd")
function Velho($nome) {
  $m = [regex]::Match([System.IO.Path]::GetFileName($nome), '^(?:.*-)?(\d{8})-\d{6}Z')
  return $m.Success -and ($m.Groups[1].Value -lt $limite)
}

function Entrada($linha) {
  $campos = $linha -split "`t", 2
  if ($campos.Count -ne 2 -or $campos[1] -notmatch '^[0-9]+$') { throw "lista da VPS inválida" }
  try {
    $utf8Estrito = New-Object System.Text.UTF8Encoding($false, $true)
    $rel = $utf8Estrito.GetString([Convert]::FromBase64String($campos[0]))
  } catch { throw "nome da VPS inválido" }
  if (-not $rel -or $rel.StartsWith('/') -or $rel -match '[<>:"\\|?*]' -or
      ($rel -split '/' | Where-Object { $_ -eq '' -or $_ -eq '.' -or $_ -eq '..' }).Count -gt 0 -or
      ($rel.ToCharArray() | Where-Object { [char]::IsControl($_) }).Count -gt 0) {
    throw "nome da VPS inseguro"
  }
  return [pscustomobject]@{ Rel = $rel; Cod = $campos[0]; Tamanho = [int64]$campos[1] }
}

# Fluxo binário sem PowerShell/cmd no meio. A entrada do fetch é enviada em
# paralelo à leitura para não bloquear quando ambas as filas do SSH enchem.
function Baixar-Cofre([string]$Acao, [string]$Recurso, [string]$Destino, [string[]]$Codigos = @()) {
  $comando = "cofre $Acao"
  if ($Recurso) { $comando += " $Recurso" }
  $inicio = New-Object System.Diagnostics.ProcessStartInfo
  $inicio.FileName = $ssh
  $inicio.Arguments = "-o BatchMode=yes $Vps $comando"
  $inicio.UseShellExecute = $false
  $inicio.CreateNoWindow = $true
  $inicio.RedirectStandardInput = $true
  $inicio.RedirectStandardOutput = $true
  $processo = New-Object System.Diagnostics.Process
  $processo.StartInfo = $inicio
  $arquivo = $null
  $iniciado = $false
  try {
    $arquivo = [System.IO.FileStream]::new($Destino, [System.IO.FileMode]::CreateNew,
      [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    if (-not $processo.Start()) { throw "SSH não iniciou" }
    $iniciado = $true
    [byte[]]$entrada = @()
    if ($Codigos.Count) { $entrada = $utf8.GetBytes(($Codigos -join "`n") + "`n") }
    $envio = $null
    if ($entrada.Length -gt 0) { $envio = $processo.StandardInput.BaseStream.WriteAsync($entrada, 0, $entrada.Length) }
    $recebimento = $processo.StandardOutput.BaseStream.CopyToAsync($arquivo)
    if ($envio) { [void]$envio.GetAwaiter().GetResult() }
    $processo.StandardInput.Close()
    [void]$recebimento.GetAwaiter().GetResult()
    $processo.WaitForExit()
    if ($processo.ExitCode -ne 0) { throw "leitura SSH falhou: $Acao $Recurso" }
  } finally {
    if ($arquivo) { $arquivo.Dispose() }
    if ($iniciado -and -not $processo.HasExited) { $processo.Kill(); $processo.WaitForExit() }
    $processo.Dispose()
  }
}

function Novo-Temporario([string]$Pasta, [string]$Sufixo) {
  return Join-Path $Pasta (".cofre-{0}.{1}" -f [guid]::NewGuid().ToString('N'), $Sufixo)
}

# Pastas que mudam: traz arquivo novo ou de tamanho diferente.
foreach ($pasta in @("backups-de-banco", "admin-midia", "backups-coordenacao")) {
  $local = Join-Path $Cofre $pasta
  New-Item -ItemType Directory -Force $local | Out-Null
  $linhasRemotas = & $ssh -o BatchMode=yes $Vps "cofre list $pasta"
  if ($LASTEXITCODE -ne 0) { throw "a VPS nao respondeu ao listar $pasta" }
  $remota = @($linhasRemotas | Where-Object { $_ } | ForEach-Object { Entrada $_ })
  if ($pasta -eq "backups-de-banco") { $remota = @($remota | Where-Object { -not (Velho $_.Rel) }) }
  $faltam = @()
  $bytes = [int64]0
  foreach ($item in $remota) {
    $bytes += $item.Tamanho
    $arquivo = Join-Path $local ($item.Rel -replace '/', '\')
    if (-not (Test-Path -LiteralPath $arquivo) -or (Get-Item -LiteralPath $arquivo).Length -ne $item.Tamanho) {
      $faltam += $item.Cod
    }
  }
  if ($faltam.Count -gt 0) {
    $temporario = Novo-Temporario $local 'tar'
    try {
      Baixar-Cofre 'fetch' $pasta $temporario $faltam
      & $tar -xf $temporario -C $local
      if ($LASTEXITCODE -ne 0) { throw "a extração de $pasta falhou" }
    } finally { Remove-Item -LiteralPath $temporario -Force -ErrorAction SilentlyContinue }
  }
  # Conferencia: todo arquivo da VPS existe aqui com o mesmo tamanho.
  $iguais = 0
  foreach ($item in $remota) {
    $arquivo = Join-Path $local ($item.Rel -replace '/', '\')
    if ((Test-Path -LiteralPath $arquivo) -and (Get-Item -LiteralPath $arquivo).Length -eq $item.Tamanho) { $iguais++ }
  }
  $total = $remota.Count
  if ($iguais -ne $total) { $tudoIgual = $false }
  $relatorio += "{0}: VPS {1} arquivos / {2:N0} bytes; aqui {3} iguais; trazidos agora {4}" -f $pasta, $total, $bytes, $iguais, $faltam.Count
  if ($pasta -eq "backups-de-banco") {
    $velhos = @(Get-ChildItem -LiteralPath $local -File | Where-Object { Velho $_.Name })
    if (-not $PreservarCopias) {
      $velhos | Remove-Item -Force
      if ($velhos.Count -gt 0) { $relatorio += "backups-de-banco: sairam daqui {0} arquivos com carimbo de antes de {1}" -f $velhos.Count, $limite }
    } elseif ($velhos.Count -gt 0) {
      $relatorio += "backups-de-banco: preservados {0} arquivos antigos neste piloto" -f $velhos.Count
    }
  }
}

# As senhas (env/ e .env da VPS): com elas uma VPS nova volta com as mesmas chaves.
$senhas = Join-Path $Cofre "senhas"
New-Item -ItemType Directory -Force $senhas | Out-Null
$temporario = Novo-Temporario $senhas 'tar'
try {
  Baixar-Cofre 'secrets' '' $temporario
  & $tar -xf $temporario -C $senhas
  if ($LASTEXITCODE -ne 0) { throw "a extração das senhas falhou" }
} finally { Remove-Item -LiteralPath $temporario -Force -ErrorAction SilentlyContinue }
$relatorio += "senhas: {0} arquivos (env/ e .env da VPS)" -f @(Get-ChildItem -LiteralPath $senhas -File -Recurse -Force).Count

# admin-dados e admin-dados.new: fotos da fila antiga, que nao mudam mais. Vem uma vez, compactada.
foreach ($pasta in @("admin-dados", "admin-dados.new")) {
  $dados = Join-Path $Cofre $pasta
  New-Item -ItemType Directory -Force $dados | Out-Null
  $pacote = Join-Path $dados "$pasta.tar.gz"
  if (-not (Test-Path $pacote)) {
    $temporario = Novo-Temporario $dados 'tar.gz'
    try {
      Baixar-Cofre 'archive' $pasta $temporario
      & $tar -tzf $temporario | Out-Null
      if ($LASTEXITCODE -ne 0) { throw "pacote de $pasta inválido" }
      Move-Item -LiteralPath $temporario -Destination $pacote
    } finally { Remove-Item -LiteralPath $temporario -Force -ErrorAction SilentlyContinue }
  }
  $relatorio += "{0}: pacote unico de {1:N0} bytes" -f $pasta, (Get-Item $pacote).Length
}

# O guia mais novo, da main que a VPS recebeu.
$guia = Join-Path $Cofre "COMO-RESTAURAR.md"
$temporario = Novo-Temporario $Cofre 'md'
try {
  Baixar-Cofre 'guide' '' $temporario
  if ((Get-Item -LiteralPath $temporario).Length -gt 0) {
    Move-Item -LiteralPath $temporario -Destination $guia -Force
  }
} finally { Remove-Item -LiteralPath $temporario -Force -ErrorAction SilentlyContinue }

# O backup mais novo e as contagens dele.
$ultimo = Get-ChildItem (Join-Path $Cofre "backups-de-banco") -Filter "*.contagens.tsv" |
  Sort-Object Name | Select-Object -Last 1
if ($ultimo) {
  $linhas = Get-Content $ultimo.FullName | ForEach-Object { [int64](($_ -split "`t")[2]) } | Measure-Object -Sum
  $relatorio += ""
  $relatorio += "Backup mais novo: {0} ({1} tabelas, {2:N0} linhas no total)" -f ($ultimo.Name -replace '\.contagens\.tsv$', ''), $linhas.Count, $linhas.Sum
}
$relatorio += ""
$relatorio += $(if ($tudoIgual) { "Todos os arquivos atuais da VPS conferidos por tamanho neste PC." } else { "ATENCAO: algum arquivo da VPS nao bateu; rode de novo." })
[System.IO.File]::WriteAllLines((Join-Path $Cofre "ultima-copia.txt"), $relatorio, $utf8)
$relatorio | ForEach-Object { Write-Output $_ }
if (-not $tudoIgual) { exit 1 }
