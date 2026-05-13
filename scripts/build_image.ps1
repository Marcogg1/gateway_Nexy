# Build dev Docker image and write a tar for LuCI upload.
#
# Output is a classic single-manifest Docker tar (no attestations, no manifest
# list) so the legacy dockerd on the gateway / LuCI dockerman can parse it.
#
# Each build gets a short timestamp tag (e.g. gateway:dev05121525, encoding
# month/day/hour/minute) so re-uploading does not strip the tag from a
# previous image and break the container's image reference. Override with
# $env:IMAGE_TAG.
#
# The .tar is written to build/gateway-dev.tar (fixed filename, overwritten
# each run) so only the latest build is kept locally. The build/ directory
# is gitignored and dockerignored so old tars do not bloat the next image.
# Override with $env:OUTPUT.
#
# Deploy:
#   1. LuCI > Docker > Images > Load             -> upload the .tar
#   2. LuCI > Docker > Containers > <slot>       -> edit Image field to the
#                                                   new tag, Save -> recreate
#   3. Run Application = ON so ENTRYPOINT fires (starts sshd).
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Stamp      = Get-Date -Format 'MMddHHmm'
$ImageTag   = if ($env:IMAGE_TAG)  { $env:IMAGE_TAG }  else { "gateway:dev$Stamp" }
$Dockerfile = if ($env:DOCKERFILE) { $env:DOCKERFILE } else { 'Dockerfile.dev' }
$Platform   = if ($env:PLATFORM)   { $env:PLATFORM }   else { 'linux/arm64' }
$BuildDir = Join-Path (Get-Location) 'build'
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
$Output   = if ($env:OUTPUT) { $env:OUTPUT } else { Join-Path $BuildDir 'gateway-dev.tar' }

$env:DOCKER_BUILDKIT = '1'

Write-Host "==> Building $ImageTag ($Platform) from $Dockerfile -> $Output"
docker buildx build `
    --platform $Platform `
    -f $Dockerfile `
    -t $ImageTag `
    --provenance=false `
    --sbom=false `
    --output "type=docker,dest=$Output" `
    .
if ($LASTEXITCODE -ne 0) { throw "docker buildx build failed (exit $LASTEXITCODE)" }

$Size = '{0:N1} MB' -f ((Get-Item $Output).Length / 1MB)
Write-Host ""
Write-Host "Built: $Output ($Size)"
Write-Host "Tag:   $ImageTag"
Write-Host ""
Write-Host "Next:"
Write-Host "  1. LuCI > Docker > Images > Load -> upload $Output"
Write-Host "  2. LuCI > Docker > Containers > <slot> -> edit Image to '$ImageTag' -> Save"
