# xingchi-codex installer for Windows.
# Points the Codex CLI at the Xingchi upstream (OpenAI Responses API).
# Sol is required; Astra is optional and selected explicitly with --astra.
#
# NAME COLLISION WARNING: PowerShell variable names are case-INsensitive, so
# $Upstream and $upstream are the same variable. An earlier revision used that
# pair for the base URL and the API key; pasting the key silently overwrote the
# URL, which wrote base_url = "<api key>" into config.toml, pointed
# OPENAI_BASE_URL at the key, and made "verification" try to DNS-resolve the key
# as a hostname ("could not reach upstream /models"). Keep $BaseUrl and $ApiKey
# distinct, and never reintroduce the old pair. tests/test_install_windows.py
# enforces this.
#requires -version 5.1
param(
    [switch]$Yes,
    [switch]$NoPath,
    [switch]$Help
)
$ErrorActionPreference = 'Stop'

# A Python/cmd child of PowerShell 7 inherits PS7 module paths even when it
# starts Windows PowerShell 5.1. Prefer this host's bundled modules so Set-Acl
# and other shared commands cannot autoload an incompatible PS7 module.
$HostModules = [IO.Path]::Combine($PSHOME, 'Modules')
$env:PSModulePath = $HostModules + [IO.Path]::PathSeparator + $env:PSModulePath

# Windows PowerShell 5.1 negotiates SSL3/TLS1.0 by default on older builds, which
# fails against both codeload.github.com and the Xingchi API.
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }

$Repo = if ($env:XINGCHI_REPO) { $env:XINGCHI_REPO } else { 'kikiprojecto/xingchi-codex' }
$Branch = if ($env:XINGCHI_BRANCH) { $env:XINGCHI_BRANCH } else { 'main' }
$XDir = if ($env:XINGCHI_HOME) { $env:XINGCHI_HOME } else { Join-Path $env:USERPROFILE '.xingchi' }
$Bin = if ($env:XINGCHI_BIN) { $env:XINGCHI_BIN } else { Join-Path $env:LOCALAPPDATA 'xingchi\bin' }
$BaseUrl = if ($env:XINGCHI_UPSTREAM) { $env:XINGCHI_UPSTREAM } else { 'https://api.xingchiapi.com/v1' }
# A trailing slash would otherwise produce "//models" in the catalog URL.
$BaseUrl = "$BaseUrl".Trim().TrimEnd('/')
$Model = 'gpt-6.1-sol'
$KeyFile = Join-Path $XDir 'upstream.key'
$AstraKeyFile = Join-Path $XDir 'astra.key'
$CodexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$SharedSkills = Join-Path $env:USERPROFILE '.agents\skills'
$SkipPath = $NoPath -or ($env:XINGCHI_NO_PATH -eq '1')

if ($Help) {
    Write-Host "usage: install.ps1 [-Yes] [-NoPath]`n"
    Write-Host "Configures Codex for Xingchi (default: $Model)."
    Write-Host "Required GPT公益/Sol key: $KeyFile"
    Write-Host "Optional Astra-专属余额 key: $AstraKeyFile"
    Write-Host "Separate model catalogs are written under CODEX_HOME (default $CodexDir):"
    Write-Host "  xingchi-models.json (GPT公益/Sol)"
    Write-Host "  xingchi-models-astra.json (Astra)"
    Write-Host "Connects directly to $BaseUrl; the selected key is used for the whole session.`n"
    Write-Host "  -Yes     never prompt; requires XINGCHI_API_KEY; Astra is optional"
    Write-Host "  -NoPath  do not add the launcher directory to your user PATH"
    Write-Host 'Environment: XINGCHI_API_KEY (required), XINGCHI_ASTRA_API_KEY (optional).'
    Write-Host 'Interactive setup: press Enter at the Astra prompt for Sol-only; an existing astra.key is reused.'
    Write-Host 'Set XINGCHI_SKIP_INTEGRATIONS=1 to leave skills and MCP settings untouched.'
    Write-Host "Unified skills root: $SharedSkills (shared with local Codex/Claude skills)."
    Write-Host "Commands: xingchi-codex | xingchi-codex --astra | xingchi-codex -m gpt-6.1-sol | xingchi-codex --astra -m gpt-6-astra"
    Write-Host 'Inside Codex, use /model to select a model and its available reasoning effort.'
    Write-Host 'Inside xingchi-codex, /inherit opens a session picker and continues in a fresh chat.'
    Write-Host 'Type / to select /inherit from the command list.'
    Write-Host 'Continue saved work with /inherit (recommended for session limits):'
    Write-Host '  1. Launch xingchi-codex in the same project directory.'
    Write-Host '  2. Type /inherit and press Enter to open the session list.'
    Write-Host '  3. Use Up/Down or Page Up/Down; type a title or ID to filter. Esc cancels.'
    Write-Host '  4. Press Enter on a session; a fresh chat automatically reads saved history and continues the work.'
    Write-Host '/inherit automatically uses Full access and approval policy never (no command approval prompts).'
    Write-Host 'Inherited commands run without sandboxing. Other chats keep their existing permissions.'
    Write-Host "Runtime files are also refreshed in $(Join-Path $XDir 'bin')."
    Write-Host 'Why /inherit over --continue: a fresh conversation reads saved history on demand.'
    Write-Host '--continue forks the saved conversation; copied history can still hit a turn limit.'
    Write-Host 'If the old chat is closed: xingchi-codex /inherit (Astra: xingchi-codex --astra /inherit).'
    Write-Host 'After updating, exit any running Codex and relaunch xingchi-codex to load the update.'
    Write-Host 'Optional: xingchi-codex --continue forks the latest saved conversation.'
    return
}

$SelfDir = $PSScriptRoot
if (-not $SelfDir -or -not (Test-Path (Join-Path $SelfDir 'lib\config.py')) -or -not (Test-Path (Join-Path $SelfDir 'lib\models.json'))) {
    $tmp = Join-Path $env:TEMP ("xingchi-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $zip = Join-Path $tmp 'src.zip'
    Write-Host "download $Repo ($Branch)..."
    Invoke-WebRequest -UseBasicParsing "https://codeload.github.com/$Repo/zip/refs/heads/$Branch" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $src = Get-ChildItem $tmp -Directory | Select-Object -First 1
    $childArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $src.FullName 'install.ps1'))
    if ($Yes) { $childArgs += '-Yes' }
    if ($NoPath) { $childArgs += '-NoPath' }
    & powershell @childArgs
    if ($LASTEXITCODE -ne 0) { Write-Error "installer failed (exit $LASTEXITCODE)" }
    return
}

function Test-PythonExe($exe) {
    try {
        & $exe -c "import tomllib" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Protect-UserFile($Path) {
    $acl = New-Object System.Security.AccessControl.FileSecurity
    $acl.SetAccessRuleProtection($true, $false)
    $allow = [System.Security.AccessControl.AccessControlType]::Allow
    $rights = [System.Security.AccessControl.FileSystemRights]::FullControl
    foreach ($sid in @(
        [System.Security.Principal.WindowsIdentity]::GetCurrent().User,
        (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')),
        (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544'))
    )) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, $rights, $allow)
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

$python = $null
foreach ($candidate in @('python3', 'python', 'py')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd -and (Test-PythonExe $cmd.Source)) { $python = $cmd.Source; break }
}
if (-not $python) {
    Write-Host 'Python 3.11+ missing, installing with winget...'
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    }
    foreach ($candidate in @('python3', 'python', 'py')) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd -and (Test-PythonExe $cmd.Source)) { $python = $cmd.Source; break }
    }
}
if (-not $python) {
    throw 'install Python 3.11 or newer from https://www.python.org/downloads/ then re-run'
}

New-Item -ItemType Directory -Force -Path $XDir, $Bin | Out-Null

Write-Host "`n[1/3] GPT公益/Sol API key + optional Astra-专属余额 API key"
$ApiKey = $env:XINGCHI_API_KEY
if (-not $ApiKey -and (Test-Path $KeyFile)) {
    $ApiKey = (Get-Content $KeyFile -Raw).Trim()
}
if (-not $ApiKey) {
    if ($Yes) { throw 'set XINGCHI_API_KEY (your xingchiapi key) or run without -Yes' }
    Write-Host "`nCreate a GPT公益/Sol key at https://xingchiapi.com/keys, copy it, then paste it here (input is hidden)."
    $secure = Read-Host 'Paste your GPT公益/Sol xingchiapi API key' -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::FreeBSTR($bstr)
    }
}
# Pasting from a browser can carry spaces or CR; trim or the key fails with 401.
$ApiKey = "$ApiKey".Trim()
if (-not $ApiKey) { throw 'empty API key' }
[IO.File]::WriteAllText($KeyFile, "$ApiKey`n")
Protect-UserFile $KeyFile

$AstraKey = $env:XINGCHI_ASTRA_API_KEY
if (-not $AstraKey -and (Test-Path $AstraKeyFile)) {
    $AstraKey = (Get-Content $AstraKeyFile -Raw).Trim()
    if ($AstraKey) { Write-Host "  reusing optional Astra key from $AstraKeyFile" }
}
if (-not $AstraKey -and -not $Yes) {
    Write-Host "`nOptional Astra-专属余额 key (press Enter to use GPT公益/Sol only; input is hidden)."
    $secureAstra = Read-Host 'Paste your Astra-专属余额 xingchiapi API key' -AsSecureString
    $bstrAstra = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureAstra)
    try {
        $AstraKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstrAstra)
    } finally {
        [Runtime.InteropServices.Marshal]::FreeBSTR($bstrAstra)
    }
}
$AstraKey = if ($AstraKey) { "$AstraKey".Trim() } else { '' }
if ($AstraKey) {
    [IO.File]::WriteAllText($AstraKeyFile, "$AstraKey`n")
    Protect-UserFile $AstraKeyFile
    Write-Host '  optional Astra key configured'
} else {
    Write-Host '  optional Astra key not configured (xingchi-codex --astra unavailable)'
}

Write-Host "`n[2/3] Codex CLI"
$CliCompatible = $false
if (Get-Command codex -ErrorAction SilentlyContinue) {
    try {
        $CliVersion = (& codex --version 2>$null | Out-String).Trim()
        if ($CliVersion) {
            & $python (Join-Path $SelfDir 'lib\config.py') check-cli $CliVersion
            $CliCompatible = ($LASTEXITCODE -eq 0)
        }
    } catch { $CliCompatible = $false }
}
if (-not $CliCompatible) {
    Write-Host '  installing/updating @openai/codex (0.170.0 or newer required)...'
    if (-not (Get-Command npm -ErrorAction SilentlyContinue) -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host '  installing Node.js...'
        winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements --silent
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'npm is missing. Install Node.js, then: npm install -g @openai/codex'
    }
    & npm install -g @openai/codex
    if ($LASTEXITCODE -ne 0) { throw 'npm install -g @openai/codex failed' }
    # This session still has the pre-install PATH, so codex.cmd (dropped in
    # %APPDATA%\npm) is not visible yet. Refresh before the launchers rely on it.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    $npmBin = Join-Path $env:APPDATA 'npm'
    if (-not (Get-Command codex -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $npmBin 'codex.cmd'))) {
        $env:Path = "$npmBin;$env:Path"
    }
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw 'codex is not on PATH; add npm to PATH, then rerun the installer'
}
$CliVersion = (& codex --version 2>$null | Out-String).Trim()
& $python (Join-Path $SelfDir 'lib\config.py') check-cli $CliVersion
if ($LASTEXITCODE -ne 0) { throw 'Codex update did not install a compatible CLI' }

Write-Host "`n[3/3] Installing Codex configuration, model catalog and launchers"
$env:XINGCHI_API_KEY = $ApiKey
$env:XINGCHI_ASTRA_API_KEY = $AstraKey
$env:XINGCHI_UPSTREAM = $BaseUrl
$env:XINGCHI_HOME = $XDir
& $python (Join-Path $SelfDir 'lib\config.py') codex
if ($LASTEXITCODE -ne 0) { throw 'config for codex failed' }
$env:XINGCHI_API_KEY = $null
$env:XINGCHI_ASTRA_API_KEY = $null

$runnerPath = Join-Path $Bin 'xingchi-codex-runner.py'
Copy-Item (Join-Path $SelfDir 'bin\xingchi-codex-runner.py') $runnerPath -Force
Copy-Item (Join-Path $SelfDir 'bin\xingchi_history.py') (Join-Path $Bin 'xingchi_history.py') -Force
Copy-Item (Join-Path $SelfDir 'bin\xingchi_tui.py') (Join-Path $Bin 'xingchi_tui.py') -Force
Copy-Item (Join-Path $SelfDir 'bin\xingchi_conpty.py') (Join-Path $Bin 'xingchi_conpty.py') -Force

# Single-quoted here-strings: nothing here is expanded by PowerShell. Values are
# filled in below with literal .Replace() calls, and no API key is embedded.
$xingchiCmd = @'
@echo off
setlocal
set "XINGCHI_HOME=__XINGCHI_HOME__"
set "XINGCHI_UPSTREAM=__BASE_URL__"
set "XINGCHI_PYTHON=__PYTHON__"
set "XINGCHI_RUNNER=__RUNNER__"
if not exist "%XINGCHI_RUNNER%" (
  echo error: Xingchi runner missing at "%XINGCHI_RUNNER%"; rerun the installer 1>&2
  exit /b 1
)
"%XINGCHI_PYTHON%" "%XINGCHI_RUNNER%" %*
exit /b %ERRORLEVEL%
'@
$xingchiCmd = $xingchiCmd.Replace('__XINGCHI_HOME__', $XDir).Replace('__BASE_URL__', $BaseUrl).Replace('__PYTHON__', $python).Replace('__RUNNER__', $runnerPath)
[IO.File]::WriteAllText((Join-Path $Bin 'xingchi-codex.cmd'), $xingchiCmd.TrimEnd() + "`r`n")

$statusCmd = @'
@echo off
echo API:   __BASE_URL__ (direct)
echo models and reasoning: use /model in Codex
echo catalogs: __CODEX_DIR__\xingchi-models.json (GPT公益), __CODEX_DIR__\xingchi-models-astra.json (Astra)
if exist "__KEY_FILE__" (echo Sol key   set) else (echo Sol key   missing)
if exist "__ASTRA_KEY_FILE__" (echo Astra key configured) else (echo Astra key optional; not configured)
if exist "__SHARED_SKILLS__" (echo skills    __SHARED_SKILLS__ [unified]) else (echo skills    missing)
where codex >NUL 2>&1
if errorlevel 1 (echo codex   missing) else (echo codex   installed)
echo.
echo start with: xingchi-codex
echo Astra key:  xingchi-codex --astra
echo Sol model:  xingchi-codex -m gpt-6.1-sol
echo Astra model: xingchi-codex --astra -m gpt-6-astra
'@
# The status command shows that the key is present, never the key itself.
$statusCmd = $statusCmd.Replace('__BASE_URL__', $BaseUrl).Replace('__KEY_FILE__', $KeyFile).Replace('__ASTRA_KEY_FILE__', $AstraKeyFile).Replace('__CODEX_DIR__', $CodexDir).Replace('__SHARED_SKILLS__', $SharedSkills)
[IO.File]::WriteAllText((Join-Path $Bin 'xingchi.cmd'), $statusCmd.TrimEnd() + "`r`n")

# Refresh the complete runtime in XINGCHI_HOME too, not just the PATH directory.
$RuntimeBin = Join-Path $XDir 'bin'
if ([IO.Path]::GetFullPath($RuntimeBin).TrimEnd([char[]]'\/') -ne [IO.Path]::GetFullPath($Bin).TrimEnd([char[]]'\/')) {
    New-Item -ItemType Directory -Path $RuntimeBin -Force | Out-Null
    foreach ($runtime in @('xingchi-codex.cmd', 'xingchi.cmd', 'xingchi-codex-runner.py', 'xingchi_history.py', 'xingchi_tui.py', 'xingchi_conpty.py')) {
        Copy-Item (Join-Path $Bin $runtime) (Join-Path $RuntimeBin $runtime) -Force
    }
}
Write-Host "  runtime copy: $RuntimeBin"

# Run the optional integration step last. The config above names
# XINGCHI_API_KEY as the provider env key, so an old launcher left in place by
# a later integration error makes Codex report a missing environment variable.
if ($env:XINGCHI_SKIP_INTEGRATIONS -ne '1') {
    & $python (Join-Path $SelfDir 'lib\integrations.py')
    if ($LASTEXITCODE -ne 0) { throw 'skill and MCP configuration failed' }
    Write-Host "  unified skills root: $SharedSkills"
    Write-Host "  MCP definitions merged into $(Join-Path $CodexDir 'config.toml'); credentialed servers stay inactive until configured"
} else {
    Write-Host '  integrations skipped: existing skills and MCP settings were left untouched'
}

if ($SkipPath) {
    Write-Host "leaving user PATH untouched (-NoPath)"
} else {
    # Compare whole PATH entries; a substring test also matched "...\bin2".
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not $userPath) { $userPath = '' }
    $segments = @($userPath.Split(';') | Where-Object { $_ })
    if ($segments -notcontains $Bin) {
        [Environment]::SetEnvironmentVariable('Path', ((@($segments) + $Bin) -join ';'), 'User')
        Write-Host "PATH updated with $Bin (open a new terminal)"
    }
}
$env:Path = "$Bin;$env:Path"

Write-Host "`n Installation complete"
Write-Host "  api:   $BaseUrl"
Write-Host "  Sol key:   $KeyFile (GPT公益; default)"
if (Test-Path $AstraKeyFile) {
    Write-Host "  Astra key: $AstraKeyFile (Astra-专属余额; --astra)"
} else {
    Write-Host '  Astra key: not configured (optional; add XINGCHI_ASTRA_API_KEY or rerun interactively)'
}
Write-Host "  catalogs:  $(Join-Path $CodexDir 'xingchi-models.json')"
Write-Host "             $(Join-Path $CodexDir 'xingchi-models-astra.json')"
if ($env:XINGCHI_SKIP_INTEGRATIONS -eq '1') {
    Write-Host '  skills/MCP: skipped (XINGCHI_SKIP_INTEGRATIONS=1)'
} else {
    Write-Host "  skills:    $SharedSkills (shared with local Codex/Claude installs)"
    Write-Host "  conflicts: $(Join-Path $XDir 'skill-conflicts.json')"
}
Write-Host "`nStart Codex with: xingchi-codex"
Write-Host '  xingchi-codex --astra      (Astra-专属余额, if astra.key is configured)'
Write-Host '  xingchi-codex -m gpt-6.1-sol'
Write-Host '  xingchi-codex --astra -m gpt-6-astra'
Write-Host 'Choose your model and reasoning level with /model in Codex.'
Write-Host 'Type / to select /inherit, then Enter to choose a saved session and continue in a fresh chat.'
Write-Host 'Continue saved work with /inherit (recommended for session limits):'
Write-Host '  1. Launch xingchi-codex in the same project directory.'
Write-Host '  2. Type /inherit and press Enter to open the session list.'
Write-Host '  3. Use Up/Down or Page Up/Down; type a title or ID to filter. Esc cancels.'
Write-Host '  4. Press Enter on a session; a fresh chat automatically reads saved history and continues the work.'
Write-Host '/inherit automatically uses Full access and approval policy never (no command approval prompts).'
Write-Host 'Inherited commands run without sandboxing. Other chats keep their existing permissions.'
Write-Host 'Why /inherit over --continue: a fresh conversation reads saved history on demand.'
Write-Host '--continue forks the saved conversation; copied history can still hit a turn limit.'
Write-Host 'If the old chat is closed: xingchi-codex /inherit (Astra: xingchi-codex --astra /inherit).'
Write-Host 'After updating, exit any running Codex and relaunch xingchi-codex to load the update.'
Write-Host 'The key group is selected at launch; /model never switches API keys.'
Write-Host 'After session_request_limit_exceeded or session_turn_limit_exceeded: use /inherit.'
Write-Host 'Check the setup with: xingchi'
