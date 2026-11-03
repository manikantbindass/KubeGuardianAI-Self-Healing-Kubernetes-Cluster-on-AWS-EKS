package recovery

import (
	"context"
	"fmt"
	"time"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
	apps "k8s.io/api/apps/v1"
	core "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

// Observe checks native state independently of incident/ML suggestions. No model chooses actions.
func Observe(ctx context.Context, c client.Client, d *apps.Deployment, now time.Time) (*v1.Incident, error) {
	sets := &apps.ReplicaSetList{}
	if err := c.List(ctx, sets, client.InNamespace(d.Namespace)); err != nil {
		return nil, err
	}
	owners := map[string]bool{}
	for _, set := range sets.Items {
		for _, owner := range set.OwnerReferences {
			if owner.UID == d.UID && owner.Controller != nil && *owner.Controller {
				owners[string(set.UID)] = true
			}
		}
	}
	pods := &core.PodList{}
	if err := c.List(ctx, pods, client.InNamespace(d.Namespace), client.MatchingLabels(d.Spec.Selector.MatchLabels)); err != nil {
		return nil, err
	}
	makeIncident := func(kind v1.IncidentType, identity string, severity string) *v1.Incident {
		return &v1.Incident{ID: Digest([]string{string(d.UID), fmt.Sprint(d.Generation), string(kind), identity}), Type: kind, Source: "kubernetes", Severity: severity, ObservedAt: metav1.NewTime(now)}
	}
	for _, pod := range pods.Items {
		owned := false
		for _, owner := range pod.OwnerReferences {
			if owners[string(owner.UID)] && owner.Controller != nil && *owner.Controller {
				owned = true
			}
		}
		if !owned || pod.DeletionTimestamp != nil {
			continue
		}
		if pod.Status.Reason == "Evicted" {
			return makeIncident("SustainedPressure", string(pod.UID), "critical"), nil
		}
		for _, status := range pod.Status.ContainerStatuses {
			identity := fmt.Sprintf("%s:%s", pod.UID, status.Name)
			if status.LastTerminationState.Terminated != nil && status.LastTerminationState.Terminated.Reason == "OOMKilled" && now.Sub(status.LastTerminationState.Terminated.FinishedAt.Time) < 5*time.Minute {
				return makeIncident("OOMKilled", identity, "critical"), nil
			}
			if status.State.Waiting != nil && status.State.Waiting.Reason == "CrashLoopBackOff" {
				return makeIncident("CrashLoopBackOff", identity, "critical"), nil
			}
			if status.RestartCount >= 3 && !status.Ready {
				return makeIncident("ExcessiveRestarts", identity, "warning"), nil
			}
		}
		startedNotReady := false
		for _, status := range pod.Status.ContainerStatuses {
			if status.Started != nil && *status.Started && status.State.Running != nil && !status.Ready {
				startedNotReady = true
			}
		}
		for _, condition := range pod.Status.Conditions {
			if condition.Type == core.PodScheduled && condition.Status == core.ConditionFalse && condition.Reason == "Unschedulable" {
				return makeIncident("SustainedPressure", string(pod.UID)+condition.LastTransitionTime.String(), "warning"), nil
			}
			if condition.Type == core.PodReady && condition.Status == core.ConditionFalse && pod.Status.Phase == core.PodRunning && startedNotReady {
				return makeIncident("ReadinessProbeFailure", string(pod.UID)+condition.LastTransitionTime.String(), "warning"), nil
			}
		}
	}
	for _, condition := range d.Status.Conditions {
		if condition.Type == apps.DeploymentProgressing && condition.Status == core.ConditionFalse && condition.Reason == "ProgressDeadlineExceeded" {
			return makeIncident("StuckRollout", condition.LastUpdateTime.String(), "critical"), nil
		}
	}
	if d.Status.AvailableReplicas < Replicas(d) && d.Status.ObservedGeneration >= d.Generation {
		return makeIncident("ReplicaShortage", fmt.Sprint(Replicas(d)), "warning"), nil
	}
	return nil, nil
}
