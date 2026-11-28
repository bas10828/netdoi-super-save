# Netdoi super Save - setup
# Installs Python 3.12 (if missing) and the Python packages, opens the port in
# Windows Firewall (private networks), adds the Startup shortcut and starts the app.
# Run by double-clicking setup.bat. Safe to run again (it skips what is already done).

param([switch]$NoFirewall)  # -NoFirewall: skip the firewall step (no admin prompt)

$ErrorActionPreference = 'Stop'
$AppDir = $PSScriptRoot
$Script = Join-Path $AppDir 'netdoi_super_save.pyw'
$PyVersion = '3.12.10'
$PyUrl = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-amd64.exe"
$ShortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Netdoi super Save.lnk'
$RuleName = 'Netdoi super Save'

function Step($text) { Write-Host ''; Write-Host "==> $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "    OK  $text" -ForegroundColor Green }
function Warn($text) { Write-Host "    !!  $text" -ForegroundColor Yellow }

function Find-Python {
    $candidates = @()
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $exe = & $py.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { $candidates += $exe.Trim() }
        } catch {}
    }
    $candidates += "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    $candidates += "$env:ProgramFiles\Python312\python.exe"
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
}

function Install-Python {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host '    installing Python 3.12 with winget...'
        & $winget.Source install --id Python.Python.3.12 -e --scope user --silent `
            --accept-package-agreements --accept-source-agreements | Out-Host
        $found = Find-Python
        if ($found) { return $found }
        Warn 'winget did not finish the install, downloading from python.org instead'
    }
    $installer = Join-Path $env:TEMP "python-$PyVersion-amd64.exe"
    Write-Host "    downloading $PyUrl"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $PyUrl -OutFile $installer -UseBasicParsing
    Write-Host '    running the Python installer (per user, quiet)...'
    $p = Start-Process -FilePath $installer -Wait -PassThru -ArgumentList `
        '/quiet', 'InstallAllUsers=0', 'PrependPath=0', 'Include_launcher=1', 'Include_test=0'
    Remove-Item $installer -ErrorAction SilentlyContinue
    if ($p.ExitCode -ne 0) { throw "Python installer failed (exit code $($p.ExitCode))" }
    $found = Find-Python
    if (-not $found) { throw 'Python 3.12 was installed but python.exe was not found' }
    return $found
}

try {
    Write-Host 'Netdoi super Save - setup' -ForegroundColor White
    if (-not (Test-Path $Script)) { throw "netdoi_super_save.pyw not found in $AppDir" }

    # 1. Python
    Step 'Python 3.12'
    $python = Find-Python
    if (-not $python) { $python = Install-Python }
    $pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
    if (-not (Test-Path $pythonw)) { throw "pythonw.exe not found next to $python" }
    Ok $python

    # 2. Packages
    Step 'Python packages (Pillow, pystray, segno, PyMuPDF)'
    & $python -m pip install --disable-pip-version-check -r (Join-Path $AppDir 'requirements.txt') | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'pip install failed (check the internet connection)' }
    & $python -c 'import PIL, pystray, segno, pymupdf' 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'packages installed but cannot be imported' }
    Ok 'all packages import'

    # 3. Firewall: let the phone reach the app on private (home/office) networks only
    Step 'Windows Firewall'
    $hasRule = $false
    try { $hasRule = [bool](Get-NetFirewallRule -DisplayName $RuleName -ErrorAction Stop) } catch {}
    if ($NoFirewall) {
        Warn 'skipped (-NoFirewall)'
    } elseif ($hasRule) {
        Ok 'rule already exists'
    } else {
        Write-Host '    adding an inbound rule (Windows will ask for admin permission)...'
        $cmd = "New-NetFirewallRule -DisplayName '$RuleName' -Direction Inbound -Action Allow " +
               "-Program '$pythonw' -Protocol TCP -Profile Private,Domain | Out-Null"
        try {
            $p = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -WindowStyle Hidden `
                -ArgumentList '-NoProfile', '-Command', $cmd
            if ($p.ExitCode -eq 0) { Ok 'rule added (private networks only)' }
            else { Warn 'could not add the rule; allow Python when Windows asks on first start' }
        } catch {
            Warn 'admin permission declined; allow Python when Windows asks on first start'
        }
    }
    try {
        $public = Get-NetConnectionProfile -ErrorAction Stop | Where-Object NetworkCategory -eq 'Public'
        if ($public) {
            Warn "network '$($public[0].Name)' is set to Public: the phone cannot connect until it is"
            Warn 'set to Private (Settings > Network > Wi-Fi > the network > Private).'
        }
    } catch {}

    # 4. Startup shortcut
    Step 'Start with Windows'
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($ShortcutPath)
    $lnk.TargetPath = $pythonw
    $lnk.Arguments = "`"$Script`""
    $lnk.WorkingDirectory = $AppDir
    $lnk.Description = 'Netdoi super Save'
    $lnk.Save()
    Ok $ShortcutPath

    # 5. (Re)start the app so it runs with the packages just installed
    Step 'Start Netdoi super Save'
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -like '*netdoi_super_save*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host '    stopped the running copy' }
    Start-Sleep -Seconds 1
    Start-Process -FilePath $ShortcutPath
    $port = 8765
    $cfg = Join-Path $AppDir 'config.json'
    $listening = $false
    for ($i = 0; $i -lt 20 -and -not $listening; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $cfg) {
            try { $port = [int]((Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json).port) } catch {}
        }
        $listening = [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    }
    if ($listening) {
        Ok "running on port $port - look for the tray icon, then use 'QR code' to connect the phone"
    } else {
        Warn "app did not start listening on port $port; see netdoi_super_save.log"
    }

    Write-Host ''
    Write-Host 'Setup finished.' -ForegroundColor Green
    $exitCode = 0
} catch {
    Write-Host ''
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
}
exit $exitCode
