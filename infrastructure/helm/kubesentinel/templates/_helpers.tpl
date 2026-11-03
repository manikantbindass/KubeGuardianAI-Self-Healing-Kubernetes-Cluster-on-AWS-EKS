{{/* Release environments must provide independently pinned image digests. */}}
{{- define "sentinel.image" -}}
{{- $values := index . 0 -}}
{{- $component := index . 1 -}}
{{- $repository := index $values.image $component -}}
{{- $digest := index $values.image.digests $component | default "" -}}
{{- if $digest -}}
  {{- if not (regexMatch "^sha256:[a-f0-9]{64}$" $digest) -}}
    {{- fail (printf "invalid %s image digest" $component) -}}
  {{- end -}}
  {{- printf "%s@%s" $repository $digest -}}
{{- else -}}
  {{- if $values.image.requireDigests -}}
    {{- fail (printf "%s image digest is required for delivery" $component) -}}
  {{- end -}}
  {{- printf "%s:%s" $repository $values.image.tag -}}
{{- end -}}
{{- end -}}
