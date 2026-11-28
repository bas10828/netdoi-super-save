# Netdoi super Save - uninstall
# Stops the app, removes the Startup shortcut and the firewall rule.
# Asks before removing the Python packages and the local settings/history.
# Never touches the shared folder (your files) or Python itself.
# Run by double-clicking uninstall.bat.

param(
    [switch]$NoFirewall,  # skip the firewall step (no admin prompt)
    [switch]$NoPrompt     # answer "no" to every question (keep packages + settings)
)

$ErrorActionPreference = 'Stop'
$AppDir = $PSScriptRoot
$ShortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Netdoi super Save.lnk'
$RuleName = 'Netdoi super Save'

function Step($text) { Write-Host ''; Write-Host "==> $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "    OK  $text" -ForegroundColor Green }
function Warn($text) { Write-Host "    !!  $text" -ForegroundColor Yellow }
function Ask($question) {
    if ($NoPrompt) { return $false }
    $answer = Read-Host "    $question [y/N]"
    return $answer -match '^(y|yes)$'
}

try {
    Write-Host 'Netdoi super Save - uninstall' -ForegroundColor White

    # Read the share folder before anything is deleted, to show it at the end
    $shareDir = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Netdoi Share'
    $cfg = Join-Path $AppDir 'config.json'
    if (Test-Path $cfg) {
        try {
            $value = (Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json).share_dir
            if ($value) { $shareDir = $value }
        } catch {}
    }

    # 1. Stop the app (remember which Python runs it, for step 4)
    Step 'Stop Netdoi super Save'
    $pythonw = $null
    $procs = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -like '*netdoi_super_save*' }
    foreach ($proc in $procs) {
        $pythonw = $proc.ExecutablePath
        Stop-Process -Id $proc.ProcessId -Force
    }
    if ($procs) { Ok 'stopped' } else { Ok 'was not running' }

    # 2. Startup shortcut
    Step 'Start with Windows'
    if (Test-Path $ShortcutPath) {
        if (-not $pythonw) {
            try { $pythonw = (New-Object -ComObject WScript.Shell).CreateShortcut($ShortcutPath).TargetPath } catch {}
        }
        Remove-Item $ShortcutPath -Force
        Ok 'shortcut removed'
    } else {
        Ok 'no shortcut'
    }

    # 3. Firewall rule
    Step 'Windows Firewall'
    $hasRule = $false
    try { $hasRule = [bool](Get-NetFirewallRule -DisplayName $RuleName -ErrorAction Stop) } catch {}
    if ($NoFirewall) {
        Warn 'skipped (-NoFirewall)'
    } elseif (-not $hasRule) {
        Ok 'no rule'
    } else {
        Write-Host '    removing the rule (Windows will ask for admin permission)...'
        try {
            $p = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -WindowStyle Hidden `
                -ArgumentList '-NoProfile', '-Command', "Remove-NetFirewallRule -DisplayName '$RuleName'"
            if ($p.ExitCode -eq 0) { Ok 'rule removed' }
            else { Warn "could not remove the rule; remove '$RuleName' in Windows Defender Firewall" }
        } catch {
            Warn "admin permission declined; rule '$RuleName' is still there"
        }
    }

    # 4. Python packages (other programs may use them, so only on request)
    Step 'Python packages (Pillow, pystray, segno, PyMuPDF)'
    $python = $null
    if ($pythonw) { $python = Join-Path (Split-Path $pythonw) 'python.exe' }
    if (-not ($python -and (Test-Path $python))) {
        $python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    }
    if (-not (Test-Path $python)) {
        Ok 'Python 3.12 not found, nothing to remove'
    } elseif (Ask 'Remove the packages? (say no if other programs use them)') {
        & $python -m pip uninstall -y --disable-pip-version-check Pillow pystray segno PyMuPDF | Out-Host
        Ok 'packages removed'
    } else {
        Ok 'kept'
    }

    # 5. Local settings and history in the app folder
    Step 'Settings and history (PIN, text messages, log)'
    $local = @('config.json', 'clips.json', 'qr.png', 'netdoi_super_save.log') |
        ForEach-Object { Join-Path $AppDir $_ } |
        Where-Object { Test-Path $_ }
    $local += Get-ChildItem $AppDir -Filter 'netdoi_super_save.log.*' -File | ForEach-Object FullName
    $local += Get-ChildItem $AppDir -Filter '*.tmp' -File | ForEach-Object FullName
    if (-not $local) {
        Ok 'nothing to remove'
    } elseif (Ask 'Delete config.json (PIN), text history and log?') {
        $local | ForEach-Object { Remove-Item $_ -Force }
        Ok 'deleted'
    } else {
        Ok 'kept'
    }

    Write-Host ''
    Write-Host 'Uninstall finished.' -ForegroundColor Green
    Write-Host "Not touched: your shared folder ($shareDir), Python, and this program folder."
    Write-Host 'Delete them by hand if you no longer need them. Run setup.bat to install again.'
    $exitCode = 0
} catch {
    Write-Host ''
    Write-Host "Uninstall failed: $($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
}
exit $exitCode
