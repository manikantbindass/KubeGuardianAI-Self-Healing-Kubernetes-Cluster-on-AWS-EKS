package recovery

import (
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"testing"
	"time"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
	apps "k8s.io/api/apps/v1"
	core "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"
)

type testProbe struct {
	errors  int
	latency int
}

func (p *testProbe) Probe(_ context.Context, _ *apps.Deployment, rules v1.VerificationRules) (*v1.ProbeResult, error) {
	return &v1.ProbeResult{At: metav1.Now(), Requests: rules.Samples, Errors: p.errors, P95Milliseconds: p.latency}, nil
}

func testController(t *testing.T) (*Reconciler, *v1.RemediationPolicy, *apps.Deployment, *testProbe) {
	t.Helper()
	p, d, _, now := fixtures()
	scheme := runtime.NewScheme()
	_ = v1.AddToScheme(scheme)
	_ = apps.AddToScheme(scheme)
	_ = core.AddToScheme(scheme)
	c := fake.NewClientBuilder().WithScheme(scheme).WithStatusSubresource(&apps.Deployment{}, &v1.RemediationAction{}, &v1.VerifiedRevision{}).WithObjects(p, d).Build()
	probe := &testProbe{latency: 10}
	r := &Reconciler{Client: c, Prober: probe, Namespace: d.Namespace, Workloads: map[string]bool{d.Name: true}, Execute: true, Actor: "test-controller", Keys: map[string]ed25519.PublicKey{}, Now: func() time.Time { return now }}
	return r, p, d, probe
}

func newAction(t *testing.T, r *Reconciler, p *v1.RemediationPolicy, d *apps.Deployment) *v1.RemediationAction {
	t.Helper()
	incident, err := Observe(context.Background(), r.Client, d, r.Now())
	if err != nil || incident == nil {
		t.Fatal(err, "no incident")
	}
	incident.ObservedAt = metav1.NewTime(r.Now().Add(-10 * time.Second))
	a := &v1.RemediationAction{ObjectMeta: metav1.ObjectMeta{Name: "test-action", Namespace: d.Namespace, UID: "action-uid", CreationTimestamp: metav1.NewTime(r.Now().Add(-10 * time.Second))}, Spec: Plan(p, d, *incident, "", r.Now())}
	if err := r.Client.Create(context.Background(), a); err != nil {
		t.Fatal(err)
	}
	return a
}

func TestDryRunAndDuplicateReconciliation(t *testing.T) {
	r, p, d, _ := testController(t)
	a := newAction(t, r, p, d)
	if err := r.advance(context.Background(), d, a, []v1.RemediationAction{*a}); err != nil {
		t.Fatal(err)
	}
	if a.Status.Phase != "DryRun" || a.Status.AttemptedAt != nil {
		t.Fatalf("dry run mutated %#v", a.Status)
	}
	fresh := &apps.Deployment{}
	_ = r.Client.Get(context.Background(), client.ObjectKeyFromObject(d), fresh)
	if Replicas(fresh) != 2 {
		t.Fatal("dry-run changed replicas")
	}
	for i := 0; i < 3; i++ {
		_, err := r.Reconcile(context.Background(), ctrl.Request{NamespacedName: client.ObjectKeyFromObject(d)})
		if err != nil {
			t.Fatal(err)
		}
	}
	list := &v1.RemediationActionList{}
	_ = r.Client.List(context.Background(), list)
	// Manual fixture action has a different deterministic name; the auto path creates one stable ID only.
	if len(list.Items) > 2 {
		t.Fatal("duplicate actions created")
	}
}

func TestApprovalExecutionAndVerifiedSuccess(t *testing.T) {
	r, p, d, _ := testController(t)
	p.Spec.DryRun = false
	_ = r.Client.Update(context.Background(), p)
	a := newAction(t, r, p, d)
	if err := r.advance(context.Background(), d, a, nil); err != nil {
		t.Fatal(err)
	}
	if a.Status.Phase != "AwaitingApproval" {
		t.Fatal(a.Status.Phase)
	}
	pub, private, _ := ed25519.GenerateKey(rand.Reader)
	r.Keys["alice"] = pub
	approval := &v1.RemediationApproval{ObjectMeta: metav1.ObjectMeta{Name: "approval", Namespace: d.Namespace, UID: "approval-uid"}, Spec: v1.ApprovalSpec{ActionUID: string(a.UID), ActionDigest: Digest(a.Spec), ExpiresAt: metav1.NewTime(r.Now().Add(time.Minute)), KeyID: "alice"}}
	approval.Spec.Signature = base64.StdEncoding.EncodeToString(ed25519.Sign(private, ApprovalMessage(d.Namespace, approval.Spec)))
	_ = r.Client.Create(context.Background(), approval)
	if err := r.advance(context.Background(), d, a, nil); err != nil {
		t.Fatal(err)
	}
	if a.Status.Phase != "Verifying" || a.Status.AttemptedAt == nil || a.Status.ApprovalActor != "alice" {
		t.Fatalf("not executing %#v", a.Status)
	}
	_ = r.Client.Get(context.Background(), client.ObjectKeyFromObject(d), d)
	if Replicas(d) != 3 {
		t.Fatal("scale did not apply")
	}
	d.Status = apps.DeploymentStatus{ObservedGeneration: d.Generation, Replicas: 3, ReadyReplicas: 3, UpdatedReplicas: 3, AvailableReplicas: 3}
	_ = r.Client.Status().Update(context.Background(), d)
	for i := 0; i < 2; i++ {
		if err := r.resume(context.Background(), d, p, a); err != nil {
			t.Fatal(err)
		}
	}
	if a.Status.Phase != "Succeeded" || a.Status.MutationCount != 1 || len(a.Status.Audit) < 3 {
		t.Fatalf("success not verified %#v", a.Status)
	}
}

func TestUncertainIntentAndVerificationFailureHold(t *testing.T) {
	r, p, d, probe := testController(t)
	a := newAction(t, r, p, d)
	a.Status.Phase = "Applying"
	_ = r.Client.Status().Update(context.Background(), a)
	if err := r.resume(context.Background(), d, p, a); err != nil {
		t.Fatal(err)
	}
	if !a.Status.Hold || a.Status.Phase != "Failed" {
		t.Fatal("uncertain intent did not hold")
	}
	a.Status.Phase = "Verifying"
	a.Status.Hold = false
	a.Status.AppliedGeneration = d.Generation
	a.Status.ExpectedReplicas = Replicas(d)
	a.Status.ExpectedTemplate = Digest(d.Spec.Template)
	a.Status.VerificationStartedAt = &metav1.Time{Time: r.Now().Add(-time.Minute)}
	d.Annotations = map[string]string{ActionMarker: string(a.UID) + ":Verifying"}
	_ = r.Client.Update(context.Background(), d)
	_ = r.Client.Status().Update(context.Background(), a)
	probe.errors = 3
	if err := r.resume(context.Background(), d, p, a); err != nil {
		t.Fatal(err)
	}
	if !a.Status.Hold || a.Status.Phase != "Escalated" {
		t.Fatal("verification failure claimed success")
	}
}

func TestProtectedAndUnlistedWorkloadsDoNothing(t *testing.T) {
	r, _, d, _ := testController(t)
	for _, key := range []types.NamespacedName{{Namespace: "kube-system", Name: d.Name}, {Namespace: d.Namespace, Name: "arbitrary"}} {
		if _, err := r.Reconcile(context.Background(), ctrl.Request{NamespacedName: key}); err != nil {
			t.Fatal(err)
		}
	}
	list := &v1.RemediationActionList{}
	_ = r.Client.List(context.Background(), list)
	if len(list.Items) != 0 {
		t.Fatal("unsafe action created")
	}
}
