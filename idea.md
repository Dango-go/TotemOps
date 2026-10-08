Jenkins замість GitHub Actions як єдиний CI. GitHub залишається SCM, Actions не використовуємо.
Hetzner → AWS EKS. Через це MinIO замінюється S3, а Longhorn переїжджає в lab: на EKS він ляже поверх EBS і дасть подвійну реплікацію без користі. Для CNPG, Kafka, ES береш EBS gp3.
Image Updater не потрібен: Jenkins сам комітить bump тега в gitops-репо (явніше й аудитованіше).
Kaniko заархівований Google (2025) → збірка образів через rootless BuildKit або Buildah.
tfsec фактично влитий у Trivy (trivy config), підтримка мінімальна. Лишаємо його в порівнянні трьох сканерів, але з приміткою в README.
Cosign через AWS KMS (awskms://), бо Jenkins не має вбудованого OIDC-ідентифікатора для keyless-підпису.
Хмара (AWS)
EKS [C] + managed node group для системних подів, Karpenter [C] для решти (Spot де можна)
VPC (3 AZ, private/public subnets), NAT: один у dev (або fck-nat), VPC endpoints для S3/ECR/STS
IAM: EKS Pod Identity (або IRSA), OIDC для Jenkins-агентів, окремі ролі на сервіс (Vault/ESO/Crossplane/Velero/CNPG-Barman)
S3 [C]: Terraform state (нативний lockfile, use_lockfile), бекапи CNPG, сховище Loki/Tempo/Harbor/Velero
KMS [C]: SOPS, auto-unseal Vault, cosign-ключ, шифрування EBS/S3
Route 53 + external-dns [C], AWS Load Balancer Controller (NLB перед Istio Gateway) [C]
EBS CSI (gp3) [C], EFS CSI [L, якщо потрібен RWX]
Secrets Manager [C]: бекенд для External Secrets (bootstrap-секрети)
CloudTrail, GuardDuty (EKS protection), VPC Flow Logs [F], Security Hub [L]
AWS Budgets + Infracost (у CI) + OpenCost [F]: контроль вартості обов'язковий, EKS сам по собі платний щогодини
ECR [L]: лише як dr-репліка Harbor
IaC та конфігурація
Terraform + Terragrunt [C]: модулі vpc, eks, iam, s3, kms, route53; середовища dev/stage/prod
Ansible [L]: bootstrap самокерованих нод для окремих експериментів (на EKS майже непотрібний, не вигадуй для нього роль)
Crossplane (+provider-aws) [F]: платформні абстракції ObjectStorage, Database
tflint, terraform-docs, pre-commit, Terratest [C]
Helm + Kustomize [C]: umbrella chart + library chart; Kustomize для overlay-ів середовищ
Renovate [C]: оновлення залежностей, образів, чартів, Terraform-провайдерів
CI/CD
Jenkins [C] на EKS: JCasC, Multibranch + shared library, Kubernetes-plugin (ephemeral pod-агенти), Job DSL, Vault/AWS credentials без статичних ключів
Pipeline застосунку: gitleaks → unit/integration (Testcontainers) → semgrep → hadolint → buf lint/breaking → BuildKit → trivy image → syft SBOM → grype → cosign sign + attest → push у Harbor → bump gitops-репо → Slack
Pipeline інфри: fmt/validate → tflint → checkov + tfsec + KICS + trivy config → infracost → plan (артефакт) → ручне схвалення → apply
Argo CD [C]: App-of-Apps + ApplicationSet, sync waves, Argo Rollouts (canary поверх Istio) [C], Argo Workflows [F]: restore-drill, k6, chaos-оркестрація
Tekton [L]: порівняння з Jenkins, лише якщо буде час
Harbor [C]: Trivy-сканер, cosign-підписи, proxy cache, robot accounts, S3-сховище, БД на CNPG
Mesh, мережа, ingress
Istio [C]: mTLS STRICT, AuthN/AuthZ, VirtualService/DestinationRule, fault injection, egress gateway, ServiceEntry, WasmPlugin/EnvoyFilter [F]; ambient vs sidecar порівняння [F]
Envoy [C]: config_dump, ext_authz, локальний rate limit, Lua/WASM
Kubernetes Gateway API [C]
Cilium [C] (Hubble, CiliumNetworkPolicy; на EKS або chaining із VPC CNI, або ENI-режим; перевір сумісність з Istio CNI: socketLB.hostNamespaceOnly, cni.exclusive=false)
Traefik [F]: ingress для адмін-UI (Grafana, Argo, Harbor, Backstage). Ingress-nginx не використовуємо (виведений з підтримки)
cert-manager + istio-csr + Vault PKI [C]
Linkerd [L]: бенчмарк-близнюк. Envoy Gateway [L]. Consul не потрібен.
Спостережуваність
OpenTelemetry [C]: SDK (Go, Python), Collector (агент DaemonSet + gateway), OTel Operator (auto-instrumentation, Target Allocator), tail-sampling, spanmetrics, k8sattributes, redaction
Jaeger [C] (v2 працює на базі OTel Collector): основний UI трейсів, сховище OpenSearch/ES
Tempo [C]: Grafana-інтеграція, TraceQL, exemplars, metrics-generator. Ролі розділені: Jaeger для розслідування, Tempo для зв'язки з метриками/логами
SigNoz [F] (ClickHouse): повний APM для порівняння. Zipkin лише як формат exporter-а [F]
Prometheus + kube-prometheus-stack, Alertmanager, kube-state-metrics, node-exporter, blackbox [C]; Pyrra/Sloth (SLO) [C]
Grafana [C]: дашборди як код (Terraform grafana provider або grafonnet)
Loki + Fluent Bit [C]; ELK (ECK: Elasticsearch, Kibana) [F]: бізнес-події/audit/CQRS-пошук каталогу
Thanos або Mimir [L]: довгострокове сховище метрик у S3
PagerDuty + Slack [C], runbook-и в репо + Backstage TechDocs
k6 + k6-operator, Chaos Mesh [F]
Безпека

Shift-left (Jenkins):

Секрети: gitleaks
SAST: Semgrep (Go/Python)
Dockerfile: hadolint
IaC: Checkov, tfsec, KICS, Trivy config (порівняльна таблиця знахідок)
Манифести: kubeconform + kube-linter (або Kubescape/Polaris)
Образи: Trivy, Grype (порівняння), Syft SBOM, cosign (підпис + attestations), ідеально SLSA provenance
DAST [L]: OWASP ZAP baseline на staging
Агрегація знахідок: DefectDojo [L]

Runtime / кластер:

Kyverno [C]: verifyImages, заборона latest, ресурси, non-root, PSS
Falco + Falcosidekick [C], Trivy Operator [C], kube-bench [F], Tetragon [L]
Vault [C]: dynamic DB creds для CNPG, PKI, auto-unseal через KMS; External Secrets [C]; SOPS (з KMS) для bootstrap у git [C]
mTLS і AuthZ в Istio, CiliumNetworkPolicy як другий шар, Pod Security Admission, IMDSv2
Дані та повідомлення
CNPG [C]: кластери, Pooler (PgBouncer), Barman Cloud → S3, PITR, PodMonitor, declarative roles/Database CRD
Kafka (Strimzi) [C], Kafka Connect + Debezium [C], Schema Registry (Apicurio/Karapace) [C], KEDA [F] (масштабування консюмерів за lag)
Redis (оператор) [C], MongoDB (оператор) [F], MySQL (Percona оператор) [L], Elasticsearch (ECK) [F], TimescaleDB [F], ClickHouse [F] (для SigNoz)
Velero [F]: бекап кластерних об'єктів
Платформа
Backstage [F] (каталог, scaffolder-шаблони, TechDocs, плагіни Argo/K8s/Grafana)
Harbor (див. вище), Longhorn [L] (лише порівняльні заміри)
Автоскейлінг: HPA, VPA, Karpenter, KEDA; PDB, topology spread constraints
Застосунок
Go, Python (FastAPI); gRPC + protobuf + buf, OpenAPI, AsyncAPI
Спільні libs/: OTel-ініціалізація, Kafka-обгортка з пропагацією traceparent, outbox/inbox, idempotency, gRPC interceptor-и
Тести: Testcontainers, k6, Terratest