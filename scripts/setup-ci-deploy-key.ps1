<#
.SYNOPSIS
    Richtet den lesenden Engine-Zugriff der Spiel-CI ein (Deploy-Key fuer grimoire).

.DESCRIPTION
    Erzeugt ein frisches ed25519-Schluesselpaar ohne Passphrase in einem temporaeren Verzeichnis,
    hinterlegt den oeffentlichen Teil als READ-ONLY-Deploy-Key im Engine-Repo und speichert den
    privaten Teil als Actions-Secret im Spiel-Repo. Die Schluesseldateien werden am Ende immer
    geloescht; der private Schluessel wird nie ausgegeben und nie als Kommandozeilenargument
    uebergeben (gh liest ihn von stdin).

    Voraussetzungen: GitHub CLI (gh) angemeldet mit Admin-Rechten auf beiden Repos, ssh-keygen
    (Windows-Feature "OpenSSH-Client" oder Git for Windows).

    Kompatibel mit Windows PowerShell 5.1 und PowerShell 7.

    Hinweis: Von gh angelegte Deploy-Keys haengen am Token der GitHub CLI. Wird diese Autorisierung
    widerrufen, entfernt GitHub den Key; dann dieses Skript erneut ausfuehren.

.PARAMETER ReplaceExisting
    Rotation: vorhandene Deploy-Keys mit demselben Titel werden nach erfolgreicher Einrichtung des
    neuen Keys entfernt. Ohne diesen Schalter bricht das Skript ab, wenn ein solcher Key existiert.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-ci-deploy-key.ps1

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-ci-deploy-key.ps1 -ReplaceExisting
#>
[CmdletBinding()]
param(
    [string]$Owner = 'LupusMalusDeviant',
    [string]$EngineRepo = 'grimoire',
    [string]$GameRepo = 'fiends-n-patrons',
    [string]$SecretName = 'GRIMOIRE_DEPLOY_KEY',
    [string]$KeyTitle = 'fiends-n-patrons CI (read-only)',
    [switch]$ReplaceExisting
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Write-Step([string]$Text) {
    Write-Host ''
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Write-Ok([string]$Text) {
    Write-Host "    [ok] $Text" -ForegroundColor Green
}

function Write-Hint([string]$Text) {
    Write-Host "    $Text" -ForegroundColor Yellow
}

# Quotes one argument for the Windows command line (CommandLineToArgvW rules).
# Needed because Windows PowerShell 5.1 drops empty arguments such as ssh-keygen -N "".
function ConvertTo-NativeArgument([string]$Value) {
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') {
        return $Value
    }
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($ch in $Value.ToCharArray()) {
        if ($ch -eq [char]'\') {
            $backslashes++
            continue
        }
        if ($ch -eq [char]'"') {
            [void]$builder.Append('\' * (2 * $backslashes + 1))
        }
        elseif ($backslashes -gt 0) {
            [void]$builder.Append('\' * $backslashes)
        }
        [void]$builder.Append($ch)
        $backslashes = 0
    }
    if ($backslashes -gt 0) {
        [void]$builder.Append('\' * (2 * $backslashes))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

# Runs a native program without a console prompt and returns exit code, stdout and stderr.
# stdin is always redirected (and closed), so gh never waits for interactive input.
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$StandardInput = ''
    )
    $quoted = @()
    foreach ($argument in $Arguments) {
        $quoted += ConvertTo-NativeArgument $argument
    }
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = ($quoted -join ' ')
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.EnvironmentVariables['GH_PROMPT_DISABLED'] = '1'
    $startInfo.EnvironmentVariables['NO_COLOR'] = '1'

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    # Windows PowerShell 5.1 (.NET Framework) builds the stdin writer from Console.InputEncoding
    # and writes that encoding's preamble during Start(). On a UTF-8 console (code page 65001) that
    # is a BOM in front of the private key, which ssh-add rejects. Writing to BaseStream does not
    # help (the preamble is already out), so a BOM-free UTF-8 encoding is set just for Start().
    $previousInputEncoding = $null
    try {
        try {
            $previousInputEncoding = [Console]::InputEncoding
            [Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false
        }
        catch {
            $previousInputEncoding = $null
        }
        [void]$process.Start()
    }
    finally {
        if ($null -ne $previousInputEncoding) {
            try { [Console]::InputEncoding = $previousInputEncoding } catch { }
        }
    }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if ($StandardInput.Length -gt 0) {
        $process.StandardInput.Write($StandardInput)
    }
    $process.StandardInput.Close()
    $process.WaitForExit()

    return New-Object PSObject -Property @{
        ExitCode = $process.ExitCode
        StdOut   = $stdoutTask.Result
        StdErr   = $stderrTask.Result
    }
}

function Get-FirstLine([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) {
        return '(keine Ausgabe)'
    }
    return ($Text.Trim() -split "`r?`n")[0]
}

function Get-DeployKeys([string]$GhPath, [string]$Repository) {
    $result = Invoke-Native $GhPath @('repo', 'deploy-key', 'list', '--repo', $Repository, '--json', 'id,title,key,readOnly')
    if ($result.ExitCode -ne 0) {
        throw "Deploy-Keys von $Repository konnten nicht gelesen werden: $(Get-FirstLine $result.StdErr)"
    }
    $keys = @()
    if (-not [string]::IsNullOrWhiteSpace($result.StdOut)) {
        $parsed = $result.StdOut | ConvertFrom-Json
        foreach ($key in @($parsed)) {
            if ($null -ne $key) {
                $keys += $key
            }
        }
    }
    return , $keys
}

$engine = "$Owner/$EngineRepo"
$game = "$Owner/$GameRepo"
$tempDir = $null
$privateKey = $null
$exitCode = 0

try {
    Write-Host 'Einrichtung des Engine-Zugriffs fuer die Spiel-CI' -ForegroundColor White
    Write-Host "  Engine-Repo (Deploy-Key, nur lesen): $engine"
    Write-Host "  Spiel-Repo  (Secret $SecretName):   $game"

    # ------------------------------------------------------------------ Voraussetzungen
    Write-Step 'Pruefe Voraussetzungen'

    $ghCommand = Get-Command gh -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $ghCommand) {
        throw 'GitHub CLI (gh) wurde nicht gefunden. Installieren (https://cli.github.com/ oder "winget install GitHub.cli") und danach "gh auth login" ausfuehren.'
    }
    $gh = $ghCommand.Path
    Write-Ok "GitHub CLI gefunden: $gh"

    $auth = Invoke-Native $gh @('auth', 'status', '--hostname', 'github.com')
    if ($auth.ExitCode -ne 0) {
        throw "gh ist bei github.com nicht angemeldet. Bitte zuerst 'gh auth login' ausfuehren. ($(Get-FirstLine $auth.StdErr))"
    }
    Write-Ok 'gh ist bei github.com angemeldet.'

    $keygenCommand = Get-Command ssh-keygen -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $keygenCommand) {
        throw 'ssh-keygen wurde nicht gefunden. Windows: Einstellungen > System > Optionale Features > "OpenSSH-Client" hinzufuegen, oder Git for Windows installieren.'
    }
    $sshKeygen = $keygenCommand.Path
    Write-Ok "ssh-keygen gefunden: $sshKeygen"

    foreach ($repository in @($engine, $game)) {
        $view = Invoke-Native $gh @('repo', 'view', $repository, '--json', 'nameWithOwner,visibility,viewerPermission')
        if ($view.ExitCode -ne 0) {
            throw "Repository $repository existiert nicht oder ist fuer dieses gh-Konto nicht sichtbar. Erst anlegen, dann das Skript erneut starten. ($(Get-FirstLine $view.StdErr))"
        }
        $info = $view.StdOut | ConvertFrom-Json
        if ($info.viewerPermission -ne 'ADMIN') {
            throw "Fuer $repository fehlen Admin-Rechte (vorhanden: $($info.viewerPermission)). Deploy-Keys und Secrets verlangen Admin."
        }
        Write-Ok "$($info.nameWithOwner) gefunden ($($info.visibility), Rechte: $($info.viewerPermission))."
    }

    $existing = @()
    foreach ($key in (Get-DeployKeys $gh $engine)) {
        if ($key.title -eq $KeyTitle) {
            $existing += $key
        }
    }
    if ($existing.Count -gt 0) {
        if (-not $ReplaceExisting) {
            throw "Auf $engine existiert bereits ein Deploy-Key mit dem Titel '$KeyTitle' (Anzahl: $($existing.Count)). Zum Rotieren das Skript mit -ReplaceExisting starten."
        }
        Write-Hint "Vorhandene Keys mit Titel '$KeyTitle' werden nach erfolgreicher Einrichtung entfernt: $(($existing | ForEach-Object { $_.id }) -join ', ')"
    }

    # ------------------------------------------------------------------ Schluessel erzeugen
    Write-Step 'Erzeuge ein frisches ed25519-Schluesselpaar ohne Passphrase (temporaer)'
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ('fnp-deploy-key-' + [guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $tempDir)
    $keyFile = Join-Path $tempDir 'grimoire_deploy_key'
    $publicKeyFile = "$keyFile.pub"

    # Neutral comment on purpose: a GitHub URL in the comment would make webfactory/ssh-agent
    # install its own URL rewrite, which would compete with the rewrite in the CI action.
    $comment = "$GameRepo-ci-readonly"
    $generate = Invoke-Native $sshKeygen @('-q', '-t', 'ed25519', '-N', '', '-C', $comment, '-f', $keyFile)
    if ($generate.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $keyFile) -or -not (Test-Path -LiteralPath $publicKeyFile)) {
        throw "ssh-keygen ist fehlgeschlagen (Exit-Code $($generate.ExitCode)): $(Get-FirstLine $generate.StdErr)"
    }
    Write-Ok "Schluesselpaar erzeugt in $tempDir"

    # ------------------------------------------------------------------ Deploy-Key (read-only)
    Write-Step "Hinterlege den oeffentlichen Schluessel als READ-ONLY-Deploy-Key in $engine"
    # No --allow-write: gh creates deploy keys read-only unless that flag is given.
    $add = Invoke-Native $gh @('repo', 'deploy-key', 'add', $publicKeyFile, '--repo', $engine, '--title', $KeyTitle)
    if ($add.ExitCode -ne 0) {
        throw "Deploy-Key konnte nicht angelegt werden: $(Get-FirstLine $add.StdErr)"
    }

    $publicKeyParts = ([System.IO.File]::ReadAllText($publicKeyFile).Trim() -split '\s+')
    $publicKey = "$($publicKeyParts[0]) $($publicKeyParts[1])"
    $created = $null
    foreach ($key in (Get-DeployKeys $gh $engine)) {
        $keyParts = ([string]$key.key).Trim() -split '\s+'
        if ($keyParts.Count -ge 2 -and "$($keyParts[0]) $($keyParts[1])" -eq $publicKey) {
            $created = $key
        }
    }
    if ($null -eq $created) {
        throw "Der neue Deploy-Key ist in $engine nicht auffindbar. Bitte in den Repo-Einstellungen unter 'Deploy keys' pruefen."
    }
    if ($created.readOnly -ne $true) {
        throw "Der neue Deploy-Key (id $($created.id)) hat Schreibrechte. Bitte sofort in den Repo-Einstellungen von $engine entfernen."
    }
    Write-Ok "Deploy-Key angelegt (id $($created.id), nur lesen)."

    # ------------------------------------------------------------------ Secret
    Write-Step "Speichere den privaten Schluessel als Secret $SecretName in $game"
    $privateKey = [System.IO.File]::ReadAllText($keyFile)
    $set = Invoke-Native $gh @('secret', 'set', $SecretName, '--repo', $game, '--app', 'actions') -StandardInput $privateKey
    $privateKey = $null
    if ($set.ExitCode -ne 0) {
        throw "Secret konnte nicht gesetzt werden: $(Get-FirstLine $set.StdErr). Der neue Deploy-Key (id $($created.id)) existiert bereits; das Skript danach mit -ReplaceExisting erneut starten."
    }
    Write-Ok "Secret $SecretName gesetzt."

    # ------------------------------------------------------------------ Rotation
    if ($ReplaceExisting -and $existing.Count -gt 0) {
        Write-Step "Entferne alte Deploy-Keys mit Titel '$KeyTitle' aus $engine"
        foreach ($old in $existing) {
            $delete = Invoke-Native $gh @('repo', 'deploy-key', 'delete', [string]$old.id, '--repo', $engine)
            if ($delete.ExitCode -ne 0) {
                Write-Hint "Alter Key id $($old.id) konnte nicht entfernt werden: $(Get-FirstLine $delete.StdErr) - bitte von Hand in den Repo-Einstellungen loeschen."
            }
            else {
                Write-Ok "Alter Key id $($old.id) entfernt."
            }
        }
    }

    Write-Host ''
    Write-Host 'Fertig. Die Spiel-CI kann die Engine jetzt lesend ueber SSH laden.' -ForegroundColor Green
    Write-Host 'Naechster Schritt: einen CI-Lauf starten und bis zum Ende ueberwachen, z. B.'
    Write-Host "  gh workflow run ci.yml --repo $game"
    Write-Host "  gh run watch --repo $game --exit-status"
}
catch {
    Write-Host ''
    Write-Host "FEHLER: $($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
}
finally {
    $privateKey = $null
    if ($null -ne $tempDir -and (Test-Path -LiteralPath $tempDir)) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $tempDir) {
            Write-Host "WARNUNG: Das temporaere Verzeichnis $tempDir konnte nicht geloescht werden. Es enthaelt den privaten Schluessel - bitte sofort von Hand loeschen!" -ForegroundColor Red
            $exitCode = 1
        }
        else {
            Write-Host 'Temporaere Schluesseldateien geloescht.'
        }
    }
}

exit $exitCode
