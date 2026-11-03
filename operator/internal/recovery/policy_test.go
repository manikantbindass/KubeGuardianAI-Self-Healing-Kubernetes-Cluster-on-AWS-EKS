package recovery

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"testing"
	"time"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
	apps "k8s.io/api/apps/v1"
	core "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
)

func fixtures() (*v1.RemediationPolicy, *apps.Deployment, v1.Incident, time.Time) {
	now := time.Date(2026, 11, 3, 12, 0, 0, 0, time.UTC)
	replicas := int32(2)
	zero := intstr.FromInt32(0)
	one := intstr.FromInt32(1)
	p := &v1.RemediationPolicy{ObjectMeta: metav1.ObjectMeta{Name: "safe", Namespace: "sentinel-lab", UID: "policy-uid", ResourceVersion: "1"}, Spec: v1.PolicySpec{
		NamespaceAllowlist: []string{"sentinel-lab"}, WorkloadSelector: metav1.LabelSelector{MatchLabels: map[string]string{"app": "demo-recovery"}},
		IncidentTypes: []v1.IncidentType{"ReplicaShortage", "ReadinessProbeFailure", "CrashLoopBackOff", "OOMKilled", "StuckRollout", "ExcessiveRestarts", "SustainedPressure", "LatencyDegradation"}, AllowedActions: []v1.ActionKind{"Scale", "Restart", "Rollback", "Escalate"},
		DryRun: true, MinimumSeverity: "warning", ApprovalRequired: true, CooldownSeconds: 300, MaxActionsPerWindow: 4, ActionWindowSeconds: 3600, MinimumHealthyReplicas: 1, MinimumReplicas: 1, MaximumReplicas: 4, ScaleStep: 1,
		MaintenanceWindows: []v1.MaintenanceWindow{{Weekdays: []int{0, 1, 2, 3, 4, 5, 6}, StartHour: 0, EndHour: 24}}, EscalationDestination: "local-platform-team", MaxIncidentAgeSeconds: 300, SustainSeconds: 2,
		Verification: v1.VerificationRules{ServicePort: 8080, Path: "/health", Samples: 3, ConsecutiveSuccesses: 2, TimeoutSeconds: 10, MaxErrorBasisPoints: 100, MaxP95Milliseconds: 500, MaxLatencyPercent: 150}, Rollback: v1.RollbackRules{MaxRevisionAgeSeconds: 3600}}}
	d := &apps.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "demo-recovery", Namespace: "sentinel-lab", UID: "workload-uid", ResourceVersion: "1", Generation: 1, Labels: map[string]string{"app": "demo-recovery", OptIn: "true"}}, Spec: apps.DeploymentSpec{Replicas: &replicas, Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"app": "demo-recovery"}}, Template: core.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"app": "demo-recovery"}}, Spec: core.PodSpec{Containers: []core.Container{{Name: "demo", Image: "demo:v1"}}}}, Strategy: apps.DeploymentStrategy{Type: apps.RollingUpdateDeploymentStrategyType, RollingUpdate: &apps.RollingUpdateDeployment{MaxUnavailable: &zero, MaxSurge: &one}}}, Status: apps.DeploymentStatus{ObservedGeneration: 1, Replicas: 2, ReadyReplicas: 1, AvailableReplicas: 1, UpdatedReplicas: 2}}
	incident := v1.Incident{ID: "incident-1", Type: "ReplicaShortage", Source: "kubernetes", Severity: "warning", ObservedAt: metav1.NewTime(now.Add(-10 * time.Second))}
	return p, d, incident, now
}

func TestPolicySafetyMatrix(t *testing.T) {
	cases := []struct {
		name, want string
		change     func(*v1.RemediationPolicy, *apps.Deployment, *v1.ActionSpec)
	}{
		{"accepted", "", func(*v1.RemediationPolicy, *apps.Deployment, *v1.ActionSpec) {}},
		{"protected", "ProtectedOrUnlistedNamespace", func(_ *v1.RemediationPolicy, d *apps.Deployment, _ *v1.ActionSpec) { d.Namespace = "kube-system" }},
		{"not-opted-in", "WorkloadNotOptedIn", func(_ *v1.RemediationPolicy, d *apps.Deployment, _ *v1.ActionSpec) { delete(d.Labels, OptIn) }},
		{"critical-priority", "WorkloadNotOptedIn", func(_ *v1.RemediationPolicy, d *apps.Deployment, _ *v1.ActionSpec) {
			d.Spec.Template.Spec.PriorityClassName = "system-cluster-critical"
		}},
		{"stale", "StaleIncident", func(_ *v1.RemediationPolicy, _ *apps.Deployment, a *v1.ActionSpec) {
			a.Incident.ObservedAt = metav1.NewTime(time.Time{})
		}},
		{"future", "StaleIncident", func(_ *v1.RemediationPolicy, _ *apps.Deployment, a *v1.ActionSpec) {
			a.Incident.ObservedAt.Time = a.Incident.ObservedAt.Add(time.Hour)
		}},
		{"ml", "UntrustedIncidentSource", func(_ *v1.RemediationPolicy, _ *apps.Deployment, a *v1.ActionSpec) {
			a.Incident.Source = "anomaly-detector"
		}},
		{"changed", "WorkloadChanged", func(_ *v1.RemediationPolicy, d *apps.Deployment, _ *v1.ActionSpec) { d.Generation++ }},
		{"policychanged", "PolicyChanged", func(p *v1.RemediationPolicy, _ *apps.Deployment, _ *v1.ActionSpec) { p.ResourceVersion = "2" }},
		{"availability", "MinimumHealthyReplicasAtRisk", func(_ *v1.RemediationPolicy, d *apps.Deployment, _ *v1.ActionSpec) { d.Status.AvailableReplicas = 0 }},
		{"scale", "ScaleBounds", func(_ *v1.RemediationPolicy, _ *apps.Deployment, a *v1.ActionSpec) { a.ScaleTo = 99 }},
		{"maintenance", "OutsideMaintenanceWindow", func(p *v1.RemediationPolicy, _ *apps.Deployment, _ *v1.ActionSpec) { p.Spec.MaintenanceWindows = nil }},
		{"severity", "SeverityBelowThreshold", func(p *v1.RemediationPolicy, _ *apps.Deployment, _ *v1.ActionSpec) {
			p.Spec.MinimumSeverity = "critical"
		}},
		{"budget", "InvalidBudgetReservation", func(_ *v1.RemediationPolicy, _ *apps.Deployment, a *v1.ActionSpec) { a.BudgetCost = 0 }},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			p, d, i, now := fixtures()
			plan := Plan(p, d, i, "", now)
			tc.change(p, d, &plan)
			if got := Check(p, d, plan, nil, now); got != tc.want {
				t.Fatalf("got %s want %s", got, tc.want)
			}
		})
	}
}

func TestBudgetCooldownAndConflict(t *testing.T) {
	p, d, i, now := fixtures()
	plan := Plan(p, d, i, "", now)
	old := v1.RemediationAction{Spec: plan, Status: v1.ActionStatus{Phase: "Succeeded", AttemptedAt: &metav1.Time{Time: now.Add(-time.Minute)}}}
	if got := Check(p, d, plan, []v1.RemediationAction{old}, now); got != "CooldownActive" {
		t.Fatal(got)
	}
	old.Status.AttemptedAt.Time = now.Add(-10 * time.Minute)
	p.Spec.MaxActionsPerWindow = 1
	if got := Check(p, d, plan, []v1.RemediationAction{old}, now); got != "ActionBudgetExhausted" {
		t.Fatal(got)
	}
	old.Spec.Incident.ID = "other"
	old.Status.Phase = "Applying"
	if got := Check(p, d, plan, []v1.RemediationAction{old}, now); got != "ConflictingActionOrSafetyHold" {
		t.Fatal(got)
	}
	old.Status.Phase = "Failed"
	old.Status.Hold = true
	if got := Check(p, d, plan, []v1.RemediationAction{old}, now); got != "ConflictingActionOrSafetyHold" {
		t.Fatal(got)
	}
}

func TestSignaturesBindExactPlanAndIdentity(t *testing.T) {
	p, d, i, now := fixtures()
	a := &v1.RemediationAction{ObjectMeta: metav1.ObjectMeta{Namespace: d.Namespace, UID: "action-uid"}, Spec: Plan(p, d, i, "", now)}
	pub, private, _ := ed25519.GenerateKey(rand.Reader)
	keys := map[string]ed25519.PublicKey{"alice": pub}
	approval := &v1.RemediationApproval{ObjectMeta: metav1.ObjectMeta{Namespace: d.Namespace}, Spec: v1.ApprovalSpec{ActionUID: string(a.UID), ActionDigest: Digest(a.Spec), ExpiresAt: metav1.NewTime(now.Add(time.Minute)), KeyID: "alice"}}
	approval.Spec.Signature = base64.StdEncoding.EncodeToString(ed25519.Sign(private, ApprovalMessage(a.Namespace, approval.Spec)))
	if !VerifyApproval(a, approval, keys, now) {
		t.Fatal("valid signature rejected")
	}
	a.Spec.ScaleTo++
	if VerifyApproval(a, approval, keys, now) {
		t.Fatal("changed plan accepted")
	}
	a.Spec.ScaleTo--
	if VerifyApproval(a, approval, keys, now.Add(2*time.Minute)) {
		t.Fatal("expired approval accepted")
	}
	approval.Namespace = "other"
	if VerifyApproval(a, approval, keys, now) {
		t.Fatal("cross namespace approval accepted")
	}
}

func TestVerificationCannotDeclareSuccessWithBadSLIs(t *testing.T) {
	p, _, _, _ := fixtures()
	healthy := &v1.ProbeResult{Requests: 3, P95Milliseconds: 10}
	if !GoodProbe(healthy, healthy, p.Spec.Verification) {
		t.Fatal("healthy failed")
	}
	for _, bad := range []*v1.ProbeResult{nil, {Requests: 3, Errors: 1}, {Requests: 3, P95Milliseconds: 501}, {Requests: 3, P95Milliseconds: 31}} {
		if GoodProbe(bad, healthy, p.Spec.Verification) {
			t.Fatalf("bad probe accepted %#v", bad)
		}
	}
}
