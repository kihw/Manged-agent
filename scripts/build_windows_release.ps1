param(
    [switch]$SkipTests,
    [switch]$SkipSmoke,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distDir = Join-Path $repoRoot "dist"
$buildDir = Join-Path $repoRoot "build"
$specPath = Join-Path $repoRoot "ops\windows\ManagedAgent.spec"
$installerScript = Join-Path $repoRoot "ops\windows\ManagedAgent.iss"
$exePath = Join-Path $distDir "Managed Agent\Managed Agent.exe"

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

function Invoke-SignFile {
    param([string]$TargetPath)

    if (-not $env:SIGNTOOL_EXE -or -not $env:WINDOWS_SIGN_CERT_FILE -or -not $env:WINDOWS_SIGN_CERT_PASSWORD) {
        return
    }

    & $env:SIGNTOOL_EXE sign /f $env:WINDOWS_SIGN_CERT_FILE /p $env:WINDOWS_SIGN_CERT_PASSWORD /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $TargetPath
}

Push-Location $repoRoot
try {
    if (-not $SkipTests) {
        Invoke-Step -Description "pytest" -Action { python -m pytest -q }
    }

    Invoke-Step -Description "pip install" -Action { python -m pip install -r requirements.txt -r requirements-build.txt }

    if (Test-Path $buildDir) {
        Remove-Item -LiteralPath $buildDir -Recurse -Force
    }
    if (Test-Path $distDir) {
        Remove-Item -LiteralPath $distDir -Recurse -Force
    }

    Invoke-Step -Description "PyInstaller build" -Action { python -m PyInstaller --noconfirm --clean $specPath }

    if (-not (Test-Path $exePath)) {
        throw "Expected executable not found: $exePath"
    }

    Invoke-SignFile -TargetPath $exePath

    if (-not $SkipSmoke) {
        Invoke-Step -Description "packaged smoke test" -Action { python scripts\smoke_test_windows_release.py --exe $exePath }
    }

    if (-not $SkipInstaller) {
        $iscc = $env:INNOSETUP_COMPILER
        if (-not $iscc) {
            $candidate = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
            if (Test-Path $candidate) {
                $iscc = $candidate
            }
        }
        if (-not $iscc -or -not (Test-Path $iscc)) {
            throw "Inno Setup compiler not found. Set INNOSETUP_COMPILER or install Inno Setup 6."
        }

        Invoke-Step -Description "Inno Setup build" -Action { & $iscc $installerScript }

        $installer = Get-ChildItem -Path (Join-Path $repoRoot "artifacts\windows") -Filter "ManagedAgentSetup*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($null -eq $installer) {
            throw "Installer was not generated."
        }
        Invoke-SignFile -TargetPath $installer.FullName
    }
}
finally {
    Pop-Location
}
