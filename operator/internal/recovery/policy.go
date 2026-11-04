// Package recovery separates deterministic safety decisions from cluster mutation.
package recovery

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"slices"
	"strings"
	"time"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
	apps "k8s.io/api/apps/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/labels"
)

const OptIn = "recovery.kubesentinel.ai/enabled"
const ActionMarker = "recovery.kubesentinel.ai/action"

func Digest(value any) string {
	data, err := json.Marshal(value)
	if err != nil {
		panic(err)
	} // Internal typed finite contracts only.
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func Protected(namespace string) bool {
	return strings.HasPrefix(namespace, "kube-") || slices.Contains([]string{"default", "kubesentinel", "sentinel-telemetry", "cert-manager", "ingress-nginx", "argocd"}, namespace)
}

func Matches(policy *v1.RemediationPolicy, deployment *apps.Deployment) bool {
	selector, err := metav1.LabelSelectorAsSelector(&policy.Spec.WorkloadSelector)
	return err == nil && len(policy.Spec.WorkloadSelector.MatchLabels) > 0 && selector.Matches(labels.Set(deployment.Labels))
}

func Healthy(d *apps.Deployment, minimum int32) bool {
	replicas := Replicas(d)
	return replicas >= minimum && d.Status.ObservedGeneration >= d.Generation && d.Status.UpdatedReplicas == replicas && d.Status.ReadyReplicas == replicas && d.Status.AvailableReplicas == replicas && d.Status.Replicas == replicas && d.Status.UnavailableReplicas == 0
}

func Replicas(d *apps.Deployment) int32 {
	if d.Spec.Replicas == nil {
		return 1
	}
	return *d.Spec.Replicas
}

func DuringMaintenance(p v1.PolicySpec, now time.Time) bool {
	now = now.UTC()
	for _, window := range p.MaintenanceWindows {
		if window.StartHour < window.EndHour && slices.Contains(window.Weekdays, int(now.Weekday())) && now.Hour() >= window.StartHour && now.Hour() < window.EndHour {
			return true
		}
	}
	return false
}

func Terminal(phase string) bool {
	return slices.Contains([]string{"Succeeded", "Rejected", "DryRun", "Escalated", "RolledBack", "Failed"}, phase)
}

func KindFor(incident v1.IncidentType) v1.ActionKind {
	switch incident {
	case "CrashLoopBackOff", "OOMKilled", "StuckRollout":
		return "Rollback"
	case "ReplicaShortage":
		return "Scale"
	case "ReadinessProbeFailure", "ExcessiveRestarts":
		return "Restart"
	default:
		return "Escalate" // Latency alone never justifies mutation.
	}
}

func NeedsApproval(p v1.PolicySpec, action v1.ActionSpec) bool {
	return p.ApprovalRequired || action.Kind == "Scale" || action.Kind == "Rollback" || action.RollbackEnabled
}

// Check is rerun immediately before every initial mutation; status/audit is durable first.
func Check(p *v1.RemediationPolicy, d *apps.Deployment, plan v1.ActionSpec, records []v1.RemediationAction, now time.Time) string {
	s := p.Spec
	if Protected(d.Namespace) || p.Namespace != d.Namespace || !slices.Contains(s.NamespaceAllowlist, d.Namespace) {
		return "ProtectedOrUnlistedNamespace"
	}
	if !Matches(p, d) || d.Labels[OptIn] != "true" || d.Labels["app.kubernetes.io/part-of"] == "kubesentinel" || d.Spec.Template.Spec.PriorityClassName == "system-cluster-critical" || d.Spec.Template.Spec.PriorityClassName == "system-node-critical" {
		return "WorkloadNotOptedIn"
	}
	if string(p.UID) != plan.PolicyUID || p.ResourceVersion != plan.PolicyVersion {
		return "PolicyChanged"
	}
	if string(d.UID) != plan.Target.UID || d.Generation != plan.Target.Generation || Digest(d.Spec.Template) != plan.Target.TemplateDigest || Replicas(d) != plan.Target.Replicas {
		return "WorkloadChanged"
	}
	if d.Spec.Paused || d.DeletionTimestamp != nil {
		return "PausedOrDeleting"
	}
	if plan.Incident.Source != "kubernetes" && plan.Incident.Source != "alertmanager" && !(plan.Incident.Source == "service-probe" && plan.Incident.Type == "LatencyDegradation") {
		return "UntrustedIncidentSource"
	}
	if !slices.Contains(s.IncidentTypes, plan.Incident.Type) || !slices.Contains(s.AllowedActions, plan.Kind) {
		return "IncidentOrActionNotAllowed"
	}
	if plan.Kind != KindFor(plan.Incident.Type) && plan.Kind != "Escalate" {
		return "ActionDoesNotMatchIncident"
	}
	if now.Before(plan.Incident.ObservedAt.Time) || now.Sub(plan.Incident.ObservedAt.Time) > time.Duration(s.MaxIncidentAgeSeconds)*time.Second || !now.Before(plan.ExpiresAt.Time) {
		return "StaleIncident"
	}
	if s.MinimumSeverity == "critical" && plan.Incident.Severity != "critical" {
		return "SeverityBelowThreshold"
	}
	if !DuringMaintenance(s, now) {
		return "OutsideMaintenanceWindow"
	}
	if s.MinimumHealthyReplicas < 1 || s.MinimumReplicas < s.MinimumHealthyReplicas || s.MaximumReplicas < s.MinimumReplicas || s.MaximumReplicas > 100 || s.ScaleStep < 1 || s.MaxActionsPerWindow < 1 || s.Verification.Samples < 3 || s.Verification.ConsecutiveSuccesses < 2 {
		return "InvalidSafetyBounds"
	}
	if d.Status.AvailableReplicas < s.MinimumHealthyReplicas {
		return "MinimumHealthyReplicasAtRisk"
	}
	if plan.Kind == "Scale" {
		if plan.ScaleTo != Replicas(d)+s.ScaleStep || plan.ScaleTo > s.MaximumReplicas || plan.ScaleTo < s.MinimumReplicas {
			return "ScaleBounds"
		}
	} else if plan.Kind != "Escalate" {
		if d.Spec.Strategy.Type != apps.RollingUpdateDeploymentStrategyType || d.Spec.Strategy.RollingUpdate == nil || d.Spec.Strategy.RollingUpdate.MaxUnavailable == nil || d.Spec.Strategy.RollingUpdate.MaxUnavailable.String() != "0" || d.Spec.Strategy.RollingUpdate.MaxSurge == nil || d.Spec.Strategy.RollingUpdate.MaxSurge.String() == "0" {
			return "UnsafeRolloutStrategy"
		}
	}
	used := 0
	for _, record := range records {
		if record.Spec.Target.UID == plan.Target.UID && (!Terminal(record.Status.Phase) || record.Status.Hold) && Digest(record.Spec) != Digest(plan) {
			return "ConflictingActionOrSafetyHold"
		}
		if record.Status.AttemptedAt == nil {
			continue
		}
		age := now.Sub(record.Status.AttemptedAt.Time)
		if record.Spec.PolicyUID == plan.PolicyUID && age < time.Duration(s.ActionWindowSeconds)*time.Second {
			used += record.Spec.BudgetCost
		}
		if record.Spec.Target.UID == plan.Target.UID && age < time.Duration(s.CooldownSeconds)*time.Second {
			return "CooldownActive"
		}
	}
	expected := 1
	if plan.RollbackEnabled {
		expected = 2
	}
	if plan.BudgetCost != expected || plan.RollbackEnabled != s.Rollback.Enabled {
		return "InvalidBudgetReservation"
	}
	if used+expected > s.MaxActionsPerWindow {
		return "ActionBudgetExhausted"
	}
	return ""
}

func Plan(p *v1.RemediationPolicy, d *apps.Deployment, incident v1.Incident, previous string, now time.Time) v1.ActionSpec {
	kind := KindFor(incident.Type)
	plan := v1.ActionSpec{Incident: incident, PolicyName: p.Name, PolicyUID: string(p.UID), PolicyVersion: p.ResourceVersion,
		Target: v1.Target{Name: d.Name, UID: string(d.UID), Generation: d.Generation, TemplateDigest: Digest(d.Spec.Template), Replicas: Replicas(d)}, Kind: kind,
		BeforeRevision: previous, RollbackEnabled: p.Spec.Rollback.Enabled, BudgetCost: 1,
		ExpiresAt: metav1.NewTime(incident.ObservedAt.Add(time.Duration(p.Spec.MaxIncidentAgeSeconds) * time.Second))}
	if plan.RollbackEnabled {
		plan.BudgetCost = 2
	}
	if kind == "Scale" {
		plan.ScaleTo = Replicas(d) + p.Spec.ScaleStep
	}
	if kind == "Rollback" {
		plan.RevisionName = previous
	}
	return plan
}

func ActionName(plan v1.ActionSpec) string {
	// Replays share an identity; policy edits require fresh approval, not a reset action budget.
	return "recovery-" + Digest([]string{plan.Incident.ID, plan.Target.UID, fmt.Sprint(plan.Target.Generation), plan.PolicyUID, plan.PolicyVersion})[:32]
}
