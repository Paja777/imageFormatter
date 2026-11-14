# Build dist\ImageResizer\ImageResizer.exe and installer\ImageResizer-Setup-<version>.exe.
# Requires 64-bit Windows, Python 3.12 or newer, and Inno Setup 6.3 or newer.
# A virtual environment created on another operating system cannot be reused.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
# Failed probes must not abort the script. Exit codes are checked explicitly.
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

if ($env:OS -ne "Windows_NT") {
    throw "This script builds the Windows executable and installer. Run it on 64-bit Windows."
}
if (-not [Environment]::Is64BitOperatingSystem) {
    throw "A 64-bit Windows system is required."
}

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$File,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )
    if ($null -eq $Arguments) {
        & $File
    } else {
        & $File @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        $rendered = @($File) + @($Arguments)
        throw "Command failed with exit code ${LASTEXITCODE}: $($rendered -join ' ')"
    }
}

function Get-BasePython {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        & $launcher.Source -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
        if ($LASTEXITCODE -eq 0) {
            $executable = (& $launcher.Source -3.12 -c "import sys; print(sys.executable)").Trim()
            if ($executable) {
                return $executable
            }
        }
    }
    foreach ($name in @("python", "python3")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -eq $command) {
            continue
        }
        & $command.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
        if ($LASTEXITCODE -eq 0) {
            return $command.Source
        }
    }
    throw "Python 3.12 or newer was not found. Install it and run this script again."
}

function Find-Iscc {
    $candidates = @()
    if ($env:LOCALAPPDATA) {
        $candidates += Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
    }
    if ($env:ProgramFiles) {
        $candidates += Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    if ($programFilesX86) {
        $candidates += Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe"
    }
    foreach ($candidate in @($candidates)) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    $onPath = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($null -ne $onPath) {
        return $onPath.Source
    }
    $registryKeys = @(
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
    )
    foreach ($key in $registryKeys) {
        try {
            $property = Get-ItemProperty -Path $key -ErrorAction Stop
        } catch {
            continue
        }
        $names = @($property.PSObject.Properties.Name)
        if ($names -notcontains "InstallLocation") {
            continue
        }
        $location = [string]$property.InstallLocation
        if (-not $location) {
            continue
        }
        $iscc = Join-Path $location "ISCC.exe"
        if (Test-Path -LiteralPath $iscc) {
            return $iscc
        }
    }
    throw "Inno Setup 6 compiler (ISCC.exe) was not found. Install Inno Setup 6.3 or newer and run this script again."
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    & $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "The existing .venv is not Python 3.12 or newer. Recreate it, then run this script again."
    }
} else {
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot ".venv")) {
        throw "Found .venv without .venv\Scripts\python.exe. Remove that environment and run this script again so it can create a Windows virtual environment."
    }
    $BasePython = Get-BasePython
    Invoke-Native $BasePython -m venv (Join-Path $ProjectRoot ".venv")
}

$pointerSize = (& $VenvPython -c "import struct; print(struct.calcsize('P') * 8)").Trim()
if ($pointerSize -ne "64") {
    throw "The virtual environment is using ${pointerSize}-bit Python. Recreate .venv with 64-bit Python 3.12 or newer."
}

Invoke-Native $VenvPython -m pip install -e ".[packaging]"

$version = (& $VenvPython -c "import image_resizer; print(image_resizer.__version__)").Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Refusing to build installer version '$version'. Expected MAJOR.MINOR.PATCH from image_resizer.__version__."
}

$DistDir = Join-Path $ProjectRoot "dist\ImageResizer"
if (Test-Path -LiteralPath $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
}

$Spec = Join-Path $ProjectRoot "packaging\pyinstaller.spec"
Invoke-Native $VenvPython -m PyInstaller --noconfirm --clean $Spec

$Exe = Join-Path $DistDir "ImageResizer.exe"
if (-not (Test-Path -LiteralPath $Exe)) {
    throw "PyInstaller finished without creating $Exe."
}

$Iscc = Find-Iscc
$Iss = Join-Path $ProjectRoot "packaging\installer.iss"
Invoke-Native $Iscc "/DAppVersion=$version" $Iss

$Setup = Join-Path $ProjectRoot "installer\ImageResizer-Setup-$version.exe"
if (-not (Test-Path -LiteralPath $Setup)) {
    throw "Inno Setup finished without creating $Setup."
}

Write-Host "Executable: $Exe"
Write-Host "Installer: $Setup"
