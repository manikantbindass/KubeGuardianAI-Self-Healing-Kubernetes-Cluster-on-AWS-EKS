package recovery

import (
	"context"
	"crypto/ed25519"
	"encoding/json"
	"fmt"
	"time"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
	apps "k8s.io/api/apps/v1"
	core "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller"
)

type Reconciler struct {
	Client    client.Client // Uncached direct API reads; writes use resourceVersion preconditions.
	Prober    Prober
	Namespace string
	Workloads map[string]bool // Independent installation allowlist, also enforced by RBAC resourceNames.
	Execute   bool
	Actor     string
	Keys      map[string]ed25519.PublicKey
	Now       func() time.Time
}

func (r *Reconciler) Setup(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&apps.Deployment{}).WithOptions(controller.Options{MaxConcurrentReconciles: 1}).Complete(r)
}

func (r *Reconciler) audit(ctx context.Context, a *v1.RemediationAction, phase, reason string) error {
	a.Status.Phase = phase
	a.Status.Reason = reason
	if len(a.Status.Audit) >= 64 {
		return fmt.Errorf("audit limit exceeded; refusing further transitions")
	}
	a.Status.Audit = append(a.Status.Audit, v1.AuditEvent{At: metav1.NewTime(r.Now()), Actor: r.Actor, State: phase, Reason: reason})
	if Terminal(phase) {
		at := metav1.NewTime(r.Now())
		a.Status.CompletedAt = &at
	}
	return r.Client.Status().Update(ctx, a)
}

func (r *Reconciler) Reconcile(ctx context.Context, request ctrl.Request) (ctrl.Result, error) {
	result := ctrl.Result{RequeueAfter: 5 * time.Second}
	if request.Namespace != r.Namespace || Protected(request.Namespace) || !r.Workloads[request.Name] {
		return ctrl.Result{}, nil
	}
	d := &apps.Deployment{}
	if err := r.Client.Get(ctx, request.NamespacedName, d); err != nil {
		return result, client.IgnoreNotFound(err)
	}
	policies := &v1.RemediationPolicyList{}
	if err := r.Client.List(ctx, policies, client.InNamespace(r.Namespace)); err != nil {
		return result, err
	}
	actions := &v1.RemediationActionList{}
	if err := r.Client.List(ctx, actions, client.InNamespace(r.Namespace)); err != nil {
		return result, err
	}
	if len(actions.Items) > 1000 {
		return result, fmt.Errorf("action retention limit; operator intervention required")
	}
	// Outstanding intent takes precedence over newly observed symptoms or policy ordering.
	for i := range actions.Items {
		a := &actions.Items[i]
		if a.Spec.Target.UID == string(d.UID) && !Terminal(a.Status.Phase) {
			return result, r.advance(ctx, d, a, actions.Items)
		}
	}
	for _, a := range actions.Items {
		if a.Spec.Target.UID == string(d.UID) && a.Status.Hold {
			return result, nil
		}
	}
	var policy *v1.RemediationPolicy
	for i := range policies.Items {
		p := &policies.Items[i]
		if Matches(p, d) {
			if policy != nil {
				return result, fmt.Errorf("overlapping policies; refusing ambiguity")
			}
			policy = p
		}
	}
	if policy == nil {
		return result, nil
	}
	if Healthy(d, policy.Spec.MinimumHealthyReplicas) {
		if err := r.snapshot(ctx, d, policy); err != nil {
			return result, err
		}
	}
	incident, err := r.observe(ctx, d, policy)
	if err != nil {
		return result, err
	}
	if incident == nil {
		return result, nil
	}
	// Sustain evidence in the object itself; no process-memory debounce that resets approvals.
	name := "pending-" + incident.ID[:32]
	a := &v1.RemediationAction{}
	if err := r.Client.Get(ctx, types.NamespacedName{Namespace: r.Namespace, Name: name}, a); err == nil {
		if Terminal(a.Status.Phase) {
			return result, nil
		}
		return result, r.advance(ctx, d, a, actions.Items)
	} else if !apierrors.IsNotFound(err) {
		return result, err
	}
	previous, err := r.previous(ctx, d, policy, KindFor(incident.Type) != "Rollback")
	if err != nil {
		return result, err
	}
	plan := Plan(policy, d, *incident, previous, r.Now())
	a = &v1.RemediationAction{ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: r.Namespace}, Spec: plan}
	if err := r.Client.Create(ctx, a); err != nil {
		return result, client.IgnoreAlreadyExists(err)
	}
	return result, r.audit(ctx, a, "Observing", "NativeIncidentDetected")
}

func (r *Reconciler) policy(ctx context.Context, a *v1.RemediationAction) (*v1.RemediationPolicy, error) {
	p := &v1.RemediationPolicy{}
	err := r.Client.Get(ctx, types.NamespacedName{Namespace: a.Namespace, Name: a.Spec.PolicyName}, p)
	return p, err
}

func (r *Reconciler) approval(ctx context.Context, a *v1.RemediationAction) bool {
	list := &v1.RemediationApprovalList{}
	if r.Client.List(ctx, list, client.InNamespace(a.Namespace)) != nil {
		return false
	}
	for _, approval := range list.Items {
		if VerifyApproval(a, &approval, r.Keys, r.Now()) {
			a.Status.ApprovalUID = string(approval.UID)
			a.Status.ApprovalActor = approval.Spec.KeyID
			return true
		}
	}
	return false
}

func (r *Reconciler) advance(ctx context.Context, d *apps.Deployment, a *v1.RemediationAction, records []v1.RemediationAction) error {
	p, err := r.policy(ctx, a)
	if err != nil {
		return err
	} // API outages never permit execution.
	phase := a.Status.Phase
	if phase == "Applying" || phase == "Verifying" || phase == "RollingBack" || phase == "VerifyingRollback" {
		return r.resume(ctx, d, p, a)
	}
	if reason := Check(p, d, a.Spec, records, r.Now()); reason != "" {
		return r.audit(ctx, a, "Rejected", reason)
	}
	if r.Now().Sub(a.CreationTimestamp.Time) < time.Duration(p.Spec.SustainSeconds)*time.Second {
		return nil
	}
	current, err := r.observe(ctx, d, p)
	if err != nil {
		return err
	}
	if current == nil || current.Type != a.Spec.Incident.Type || current.ID != a.Spec.Incident.ID {
		return r.audit(ctx, a, "Rejected", "IncidentNoLongerConfirmed")
	}
	if a.Spec.Kind == "Escalate" {
		return r.audit(ctx, a, "Escalated", "AlertOnly:"+p.Spec.EscalationDestination)
	}
	if !r.Execute || p.Spec.DryRun {
		return r.audit(ctx, a, "DryRun", "NoMutationAuthorized")
	}
	if a.Spec.Kind == "Rollback" && a.Spec.RevisionName == "" {
		return r.audit(ctx, a, "Escalated", "NoVerifiedPreviousRevision:"+p.Spec.EscalationDestination)
	}
	if a.Spec.RollbackEnabled && a.Spec.BeforeRevision == "" {
		return r.audit(ctx, a, "Rejected", "NoVerifiedUndoSnapshot")
	}
	if NeedsApproval(p.Spec, a.Spec) && !r.approval(ctx, a) {
		if phase != "AwaitingApproval" {
			return r.audit(ctx, a, "AwaitingApproval", "SignedPlanApprovalRequired")
		}
		return nil
	}
	before, err := r.Prober.Probe(ctx, d, p.Spec.Verification)
	if err != nil {
		return r.audit(ctx, a, "Rejected", "VerificationServiceUnavailable")
	}
	a.Status.Before = before
	// Native evidence and safety get a fresh direct API check after potentially slow probes.
	fresh := &apps.Deployment{}
	if err := r.Client.Get(ctx, client.ObjectKeyFromObject(d), fresh); err != nil {
		return err
	}
	if reason := Check(p, fresh, a.Spec, records, r.Now()); reason != "" {
		return r.audit(ctx, a, "Rejected", reason)
	}
	confirmed, err := Observe(ctx, r.Client, fresh, r.Now())
	if err != nil {
		return err
	}
	if confirmed == nil || confirmed.Type != a.Spec.Incident.Type || confirmed.ID != a.Spec.Incident.ID {
		return r.audit(ctx, a, "Rejected", "IncidentResolvedDuringProbe")
	}
	a.Status.ExpectedReplicas = Replicas(fresh)
	template := fresh.Spec.Template.DeepCopy()
	switch a.Spec.Kind {
	case "Restart":
		if template.Annotations == nil {
			template.Annotations = map[string]string{}
		}
		template.Annotations[ActionMarker] = string(a.UID)
	case "Scale":
		a.Status.ExpectedReplicas = a.Spec.ScaleTo
	case "Rollback":
		revision, err := r.revision(ctx, a.Spec.RevisionName, fresh, p)
		if err != nil {
			return r.audit(ctx, a, "Rejected", "InvalidVerifiedRevision")
		}
		*template = core.PodTemplateSpec{}
		if err := json.Unmarshal(revision.Spec.Template.Raw, template); err != nil {
			return err
		}
	default:
		return r.audit(ctx, a, "Rejected", "UnsupportedAction")
	}
	a.Status.ExpectedTemplate = Digest(*template)
	a.Status.MutationCount = 1
	at := metav1.NewTime(r.Now())
	a.Status.AttemptedAt = &at
	a.Status.VerificationStartedAt = &at
	if err := r.audit(ctx, a, "Applying", "IntentPersistedBeforeMutation"); err != nil {
		return err
	}
	return r.mutate(ctx, fresh, a, template, a.Status.ExpectedReplicas, "Verifying")
}

func (r *Reconciler) mutate(ctx context.Context, d *apps.Deployment, a *v1.RemediationAction, template any, replicas int32, next string) error {
	// JSON Patch tests fence stale leaders/external edits and avoid blind merge patches.
	ops := []map[string]any{
		{"op": "test", "path": "/metadata/uid", "value": string(d.UID)},
		{"op": "test", "path": "/metadata/resourceVersion", "value": d.ResourceVersion},
		{"op": "test", "path": "/metadata/generation", "value": d.Generation},
		{"op": "add", "path": "/spec/replicas", "value": replicas},
		{"op": "replace", "path": "/spec/template", "value": template},
	}
	annotations := d.Annotations
	if annotations == nil {
		annotations = map[string]string{}
	}
	annotations[ActionMarker] = string(a.UID) + ":" + next
	ops = append(ops, map[string]any{"op": "add", "path": "/metadata/annotations", "value": annotations})
	data, _ := json.Marshal(ops)
	if err := r.Client.Patch(ctx, d, client.RawPatch(types.JSONPatchType, data)); err != nil {
		a.Status.Hold = true
		return r.audit(ctx, a, "Failed", "MutationOutcomeUncertain:InspectBeforeClearingHold")
	}
	a.Status.AppliedGeneration = d.Generation
	return r.audit(ctx, a, next, "MutationObservedByAPIServer")
}

func (r *Reconciler) resume(ctx context.Context, d *apps.Deployment, p *v1.RemediationPolicy, a *v1.RemediationAction) error {
	if p.ResourceVersion != a.Spec.PolicyVersion || string(p.UID) != a.Spec.PolicyUID {
		a.Status.Hold = true
		return r.audit(ctx, a, "Escalated", "PolicyChangedDuringVerification")
	}
	rollback := a.Status.Phase == "RollingBack" || a.Status.Phase == "VerifyingRollback"
	next := "Verifying"
	if rollback {
		next = "VerifyingRollback"
	}
	if string(d.UID) != a.Spec.Target.UID || d.Annotations[ActionMarker] != string(a.UID)+":"+next || Digest(d.Spec.Template) != a.Status.ExpectedTemplate || Replicas(d) != a.Status.ExpectedReplicas {
		a.Status.Hold = true
		return r.audit(ctx, a, "Failed", "ExternalChangeOrAmbiguousIntent:InspectSafetyHold")
	}
	if a.Status.Phase == "Applying" || a.Status.Phase == "RollingBack" {
		a.Status.AppliedGeneration = d.Generation
		return r.audit(ctx, a, next, "RecoveredPersistedIntent")
	}
	if d.Generation != a.Status.AppliedGeneration {
		a.Status.Hold = true
		return r.audit(ctx, a, "Failed", "GenerationChangedDuringVerification")
	}
	probe, err := r.Prober.Probe(ctx, d, p.Spec.Verification)
	if err == nil {
		a.Status.After = probe
	}
	good := err == nil && Healthy(d, p.Spec.MinimumHealthyReplicas) && GoodProbe(probe, a.Status.Before, p.Spec.Verification)
	if good {
		a.Status.Successes++
	} else {
		a.Status.Successes = 0
	}
	if a.Status.Successes >= p.Spec.Verification.ConsecutiveSuccesses {
		phase := "Succeeded"
		if rollback {
			phase = "RolledBack"
		}
		return r.audit(ctx, a, phase, "RolloutReplicasAndSampledSLIVerified")
	}
	if a.Status.VerificationStartedAt == nil {
		return fmt.Errorf("verification timestamp missing")
	}
	if r.Now().Sub(a.Status.VerificationStartedAt.Time) > time.Duration(p.Spec.Verification.TimeoutSeconds)*time.Second {
		if !rollback && a.Spec.RollbackEnabled && a.Status.ApprovalUID != "" && r.Execute && !p.Spec.DryRun && p.ResourceVersion == a.Spec.PolicyVersion && DuringMaintenance(p.Spec, r.Now()) && d.Status.AvailableReplicas >= p.Spec.MinimumHealthyReplicas {
			revision, err := r.revision(ctx, a.Spec.BeforeRevision, d, p)
			if err == nil {
				template := d.Spec.Template.DeepCopy()
				*template = core.PodTemplateSpec{}
				if err := json.Unmarshal(revision.Spec.Template.Raw, template); err != nil {
					return err
				}
				a.Status.ExpectedTemplate = Digest(*template)
				a.Status.ExpectedReplicas = a.Spec.Target.Replicas
				a.Status.Successes = 0
				a.Status.MutationCount = 2
				at := metav1.NewTime(r.Now())
				a.Status.VerificationStartedAt = &at
				if err := r.audit(ctx, a, "RollingBack", "ApprovedBudgetedUndoIntentPersisted"); err != nil {
					return err
				}
				return r.mutate(ctx, d, a, template, a.Status.ExpectedReplicas, "VerifyingRollback")
			}
		}
		a.Status.Hold = true
		return r.audit(ctx, a, "Escalated", "VerificationFailed:"+p.Spec.EscalationDestination)
	}
	return r.Client.Status().Update(ctx, a)
}

func (r *Reconciler) revision(ctx context.Context, name string, d *apps.Deployment, p *v1.RemediationPolicy) (*v1.VerifiedRevision, error) {
	row := &v1.VerifiedRevision{}
	if name == "" {
		return nil, fmt.Errorf("no revision")
	}
	if err := r.Client.Get(ctx, types.NamespacedName{Namespace: d.Namespace, Name: name}, row); err != nil {
		return nil, err
	}
	if row.Spec.WorkloadUID != string(d.UID) || row.Status.VerifiedAt == nil || r.Now().Sub(row.Status.VerifiedAt.Time) > time.Duration(p.Spec.Rollback.MaxRevisionAgeSeconds)*time.Second || !GoodProbe(row.Status.Probe, nil, p.Spec.Verification) {
		return nil, fmt.Errorf("revision not verified or expired")
	}
	var template core.PodTemplateSpec
	if json.Unmarshal(row.Spec.Template.Raw, &template) != nil || Digest(template) != row.Spec.TemplateDigest {
		return nil, fmt.Errorf("revision digest mismatch")
	}
	if template.Spec.PriorityClassName == "system-cluster-critical" || template.Spec.PriorityClassName == "system-node-critical" {
		return nil, fmt.Errorf("critical-priority rollback target refused")
	}
	return row, nil
}

func (r *Reconciler) previous(ctx context.Context, d *apps.Deployment, p *v1.RemediationPolicy, includeCurrent bool) (string, error) {
	list := &v1.VerifiedRevisionList{}
	if err := r.Client.List(ctx, list, client.InNamespace(d.Namespace)); err != nil {
		return "", err
	}
	name := ""
	var latest time.Time
	for _, row := range list.Items {
		if row.Spec.WorkloadUID != string(d.UID) || (!includeCurrent && row.Spec.TemplateDigest == Digest(d.Spec.Template)) {
			continue
		}
		if _, err := r.revision(ctx, row.Name, d, p); err == nil && row.Status.VerifiedAt.After(latest) {
			name = row.Name
			latest = row.Status.VerifiedAt.Time
		}
	}
	return name, nil
}

func (r *Reconciler) snapshot(ctx context.Context, d *apps.Deployment, p *v1.RemediationPolicy) error {
	if !r.Workloads[d.Name] || d.Labels[OptIn] != "true" {
		return nil
	}
	name := "verified-" + Digest([]string{string(d.UID), Digest(d.Spec.Template)})[:32]
	row := &v1.VerifiedRevision{}
	err := r.Client.Get(ctx, types.NamespacedName{Namespace: d.Namespace, Name: name}, row)
	if err == nil {
		return nil
	}
	if !apierrors.IsNotFound(err) {
		return err
	}
	probe, err := r.Prober.Probe(ctx, d, p.Spec.Verification)
	if err != nil || !GoodProbe(probe, nil, p.Spec.Verification) {
		return nil
	}
	// Re-read after probing; never certify a template that changed during the sample.
	fresh := &apps.Deployment{}
	if err := r.Client.Get(ctx, client.ObjectKeyFromObject(d), fresh); err != nil {
		return err
	}
	if fresh.Generation != d.Generation || !Healthy(fresh, p.Spec.MinimumHealthyReplicas) {
		return nil
	}
	data, _ := json.Marshal(d.Spec.Template)
	row = &v1.VerifiedRevision{ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: d.Namespace}, Spec: v1.RevisionSpec{WorkloadUID: string(d.UID), WorkloadName: d.Name, Revision: d.Annotations["deployment.kubernetes.io/revision"], TemplateDigest: Digest(d.Spec.Template), Template: runtime.RawExtension{Raw: data}}}
	if err := r.Client.Create(ctx, row); err != nil {
		return client.IgnoreAlreadyExists(err)
	}
	at := metav1.NewTime(r.Now())
	row.Status = v1.RevisionStatus{VerifiedAt: &at, Actor: r.Actor, Probe: probe}
	return r.Client.Status().Update(ctx, row)
}
