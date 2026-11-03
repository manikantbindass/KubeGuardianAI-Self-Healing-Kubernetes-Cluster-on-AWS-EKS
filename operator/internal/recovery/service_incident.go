package recovery

import (
	"context"
	"fmt"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
	apps "k8s.io/api/apps/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func (r *Reconciler) observe(ctx context.Context, d *apps.Deployment, p *v1.RemediationPolicy) (*v1.Incident, error) {
	incident, err := Observe(ctx, r.Client, d, r.Now())
	if err != nil || incident != nil {
		return incident, err
	}
	probe, err := r.Prober.Probe(ctx, d, p.Spec.Verification)
	if err != nil {
		return nil, err
	}
	if probe.P95Milliseconds > p.Spec.Verification.MaxP95Milliseconds || probe.Errors*10000 > p.Spec.Verification.MaxErrorBasisPoints*probe.Requests {
		return &v1.Incident{ID: Digest([]string{string(d.UID), fmt.Sprint(d.Generation), "service-slo"}), Type: "LatencyDegradation", Source: "service-probe", Severity: "warning", ObservedAt: metav1.NewTime(r.Now())}, nil
	}
	return nil, nil
}
