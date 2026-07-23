$ErrorActionPreference = 'Stop'

# Capture the hook payload once so it can be forwarded to the selected runtime.
$hookPayload = [Console]::In.ReadToEnd()
$loggerScript = Join-Path $PSScriptRoot 'save_conversation_log.py'
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = $utf8WithoutBom
[Console]::OutputEncoding = $utf8WithoutBom

$pyLauncher = Get-Command 'py' -ErrorAction SilentlyContinue
if ($null -ne $pyLauncher) {
    try {
        $hookPayload | & $pyLauncher.Source -3 $loggerScript --tool codex 2>$null
        if ($LASTEXITCODE -eq 0) {
            exit 0
        }
    }
    catch {
        # Continue with executable-path candidates below.
    }
}

$pythonCandidates = @()
foreach ($commandName in @('python3', 'python')) {
    $command = Get-Command $commandName -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        $pythonCandidates += $command.Source
    }
}

if ($env:USERPROFILE) {
    $pythonCandidates += Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
}

foreach ($pythonPath in $pythonCandidates | Select-Object -Unique) {
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        continue
    }
    try {
        $hookPayload | & $pythonPath $loggerScript --tool codex
        if ($LASTEXITCODE -eq 0) {
            exit 0
        }
    }
    catch {
        continue
    }
}

# Conversation logging must never block the Codex task.
exit 0
