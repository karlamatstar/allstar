# 관리자 권한 PowerShell에서 실행하세요.
# 옆자리 동료가 내 IP(192.168.0.22)로 챗봇 API / Streamlit 대시보드 / Prometheus / Grafana에
# 접속할 수 있도록 인바운드 방화벽 규칙을 추가합니다.

$rules = @(
    @{ Name = "AI-Portfolio-API-8000";        Port = 8000 },
    @{ Name = "AI-Portfolio-Streamlit-8501";  Port = 8501 },
    @{ Name = "AI-Portfolio-Prometheus-9090"; Port = 9090 },
    @{ Name = "AI-Portfolio-Grafana-3000";    Port = 3000 }
)

foreach ($rule in $rules) {
    if (Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue) {
        Write-Host "이미 존재함: $($rule.Name)"
        continue
    }
    New-NetFirewallRule -DisplayName $rule.Name `
        -Direction Inbound -Action Allow -Protocol TCP `
        -LocalPort $rule.Port -Profile Any | Out-Null
    Write-Host "추가됨: $($rule.Name) (TCP $($rule.Port))"
}

Write-Host ""
Write-Host "완료. 동료는 다음 주소로 접속하면 됩니다:"
Write-Host "  챗봇 API(Swagger) : http://192.168.0.22:8000/docs"
Write-Host "  Streamlit 대시보드: http://192.168.0.22:8501"
Write-Host "  Prometheus        : http://192.168.0.22:9090"
Write-Host "  Grafana           : http://192.168.0.22:3000"
