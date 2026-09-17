$ErrorActionPreference = "Stop"

docker build -t ah-dawn-al:latest .

$existing = docker ps -a --filter "name=^ah-dawn-al$" --format "{{.Names}}"
if ($existing -eq "ah-dawn-al") {
    docker rm -f ah-dawn-al | Out-Null
}

New-Item -ItemType Directory -Force -Path ".\downloads" | Out-Null

docker run -d `
    --name ah-dawn-al `
    -p 5000:5000 `
    -v "${PWD}\downloads:/app/downloads" `
    --restart unless-stopped `
    ah-dawn-al:latest

Write-Host "ah-dawn-al is running on http://localhost:5000"
