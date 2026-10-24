{{/*
Chart name.
*/}}
{{- define "sciagent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Chart label value.
*/}}
{{- define "sciagent.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Component resource name: <release>-<component>. Service names derived from
this are referenced by the shared ConfigMap (e.g. <release>-vllm,
<release>-mcp-imaging), so keep the two in sync.
Usage: include "sciagent.componentName" (list $ "api")
*/}}
{{- define "sciagent.componentName" -}}
{{- $root := index . 0 -}}
{{- $component := index . 1 -}}
{{- printf "%s-%s" $root.Release.Name $component | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "sciagent.labels" -}}
helm.sh/chart: {{ include "sciagent.chart" . }}
app.kubernetes.io/name: {{ include "sciagent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: sciagent
sciagent.io/environment: {{ .Values.environment | quote }}
{{- end }}

{{/*
Release-wide selector (all pods of this release).
*/}}
{{- define "sciagent.releaseSelectorLabels" -}}
app.kubernetes.io/name: {{ include "sciagent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component selector labels.
Usage: include "sciagent.selectorLabels" (list $ "api")
*/}}
{{- define "sciagent.selectorLabels" -}}
{{- $root := index . 0 -}}
{{- $component := index . 1 -}}
{{ include "sciagent.releaseSelectorLabels" $root }}
app.kubernetes.io/component: {{ $component }}
{{- end }}

{{/*
Component labels = common labels + component selector.
Usage: include "sciagent.componentLabels" (list $ "api")
*/}}
{{- define "sciagent.componentLabels" -}}
{{- $root := index . 0 -}}
{{- $component := index . 1 -}}
{{ include "sciagent.labels" $root }}
app.kubernetes.io/component: {{ $component }}
{{- end }}

{{/*
Container image reference. Registry: image.registry, else global.imageRegistry.
Tag falls back to .Chart.AppVersion.
Usage: include "sciagent.image" (list $ .Values.api.image)
*/}}
{{- define "sciagent.image" -}}
{{- $root := index . 0 -}}
{{- $image := index . 1 -}}
{{- $registry := $image.registry | default $root.Values.global.imageRegistry -}}
{{- $tag := $image.tag | default $root.Chart.AppVersion -}}
{{- if $image.digest -}}
{{- if $registry }}{{ printf "%s/%s@%s" $registry $image.repository $image.digest }}{{ else }}{{ printf "%s@%s" $image.repository $image.digest }}{{ end -}}
{{- else -}}
{{- if $registry }}{{ printf "%s/%s:%s" $registry $image.repository $tag }}{{ else }}{{ printf "%s:%s" $image.repository $tag }}{{ end -}}
{{- end -}}
{{- end }}

{{/*
Service account name.
Usage: include "sciagent.serviceAccountName" (list $ .Values.api.serviceAccount "api")
*/}}
{{- define "sciagent.serviceAccountName" -}}
{{- $root := index . 0 -}}
{{- $sa := index . 1 -}}
{{- $component := index . 2 -}}
{{- if $sa.create -}}
{{- default (include "sciagent.componentName" (list $root $component)) $sa.name }}
{{- else -}}
{{- default "default" $sa.name }}
{{- end -}}
{{- end }}

{{/*
ServiceAccount manifest.
Usage: include "sciagent.serviceAccount" (list $ .Values.api.serviceAccount "api")
*/}}
{{- define "sciagent.serviceAccount" -}}
{{- $root := index . 0 -}}
{{- $sa := index . 1 -}}
{{- $component := index . 2 -}}
{{- if $sa.create }}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "sciagent.serviceAccountName" (list $root $sa $component) }}
  labels:
    {{- include "sciagent.componentLabels" (list $root $component) | nindent 4 }}
  {{- with $sa.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
automountServiceAccountToken: {{ $sa.automountToken }}
{{- end }}
{{- end }}

{{/*
Pod-level security context (merged: global defaults <- component overrides).
Usage: include "sciagent.podSecurityContext" (list $ .Values.api.podSecurityContext)
*/}}
{{- define "sciagent.podSecurityContext" -}}
{{- $root := index . 0 -}}
{{- $override := index . 1 | default dict -}}
{{- toYaml (mergeOverwrite (deepCopy $root.Values.podSecurityContext) $override) }}
{{- end }}

{{/*
Container-level security context (merged: global defaults <- component overrides).
*/}}
{{- define "sciagent.containerSecurityContext" -}}
{{- $root := index . 0 -}}
{{- $override := index . 1 | default dict -}}
{{- toYaml (mergeOverwrite (deepCopy $root.Values.containerSecurityContext) $override) }}
{{- end }}

{{/*
Name of the Secret providing SCIAGENT_DATABASE_URL and SCIAGENT_API_KEYS.
*/}}
{{- define "sciagent.secretName" -}}
{{- required "secrets.existingSecret is required (Secret with SCIAGENT_DATABASE_URL and SCIAGENT_API_KEYS)" .Values.secrets.existingSecret }}
{{- end }}

{{/*
Pod annotations that roll pods when the shared ConfigMap changes.
*/}}
{{- define "sciagent.configChecksum" -}}
checksum/config: {{ include (print .Template.BasePath "/configmap.yaml") . | sha256sum }}
{{- end }}

{{/*
In-cluster URLs, shared by the ConfigMap and NOTES.txt.
*/}}
{{- define "sciagent.vllmUrl" -}}
{{- printf "http://%s:%d/v1" (include "sciagent.componentName" (list . "vllm")) (int .Values.vllm.service.port) }}
{{- end }}

{{/*
Usage: include "sciagent.mcpUrl" (list $ $server)
*/}}
{{- define "sciagent.mcpUrl" -}}
{{- $root := index . 0 -}}
{{- $server := index . 1 -}}
{{- printf "http://%s:%d%s" (include "sciagent.componentName" (list $root (printf "mcp-%s" $server.name))) (int $server.port) ($root.Values.mcp.path | default "/mcp") }}
{{- end }}
