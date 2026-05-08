# Build dev Docker image and write a tar for LuCI upload.
#
# Output is a classic single-manifest Docker tar (no attestations, no manifest
# list) so the legacy dockerd on the gateway / LuCI dockerman can parse it.
#
# Each build gets a unique timestamp tag (e.g. gateway:dev-20260508-152300) so
# re-uploading does not strip the tag from the previous image and break the
# container's image reference. Override with $env:IMAGE_TAG if needed.
#
# Deploy:
#   1. LuCI > Docker > Images > Load             -> upload the .tar
#   2. LuCI > Docker > Containers > <slot>       -> edit Image field to the
#                                                   new tag, Save -> recreate
#   3. Run Application = ON so ENTRYPOINT fires (starts sshd).
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Stamp      = Get-Date -Format 'yyyyMMdd-HHmmss'
$ImageTag   = if ($env:IMAGE_TAG)  { $env:IMAGE_TAG }  else { "gateway:dev-$Stamp" }
$Dockerfile = if ($env:DOCKERFILE) { $env:DOCKERFILE } else { 'Dockerfile.dev' }
$Platform   = if ($env:PLATFORM)   { $env:PLATFORM }   else { 'linux/arm64' }
$Output     = if ($env:OUTPUT)     { $env:OUTPUT }     else { ($ImageTag -replace ':', '-') + '.tar' }
$Output     = $Output -replace '/', '-'

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
