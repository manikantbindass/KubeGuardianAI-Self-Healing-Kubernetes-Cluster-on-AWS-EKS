package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"sigs.k8s.io/controller-runtime/pkg/scheme"
)

var GroupVersion = schema.GroupVersion{Group: "recovery.kubesentinel.ai", Version: "v1alpha1"}
var SchemeBuilder = &scheme.Builder{GroupVersion: GroupVersion}
var AddToScheme = SchemeBuilder.AddToScheme

// +kubebuilder:validation:Enum=CrashLoopBackOff;OOMKilled;ReadinessProbeFailure;StuckRollout;ExcessiveRestarts;ReplicaShortage;SustainedPressure;LatencyDegradation
type IncidentType string

// +kubebuilder:validation:Enum=Restart;Scale;Rollback;Escalate
type ActionKind string

type MaintenanceWindow struct {
	// Weekdays are UTC: Sunday=0 through Saturday=6. Empty means no permitted days.
	// +kubebuilder:validation:MinItems=1
	// +kubebuilder:validation:MaxItems=7
	// +kubebuilder:validation:items:Minimum=0
	// +kubebuilder:validation:items:Maximum=6
	Weekdays []int `json:"weekdays"`
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:validation:Maximum=23
	StartHour int `json:"startHour"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=24
	EndHour int `json:"endHour"`
}

type VerificationRules struct {
	// Service must have the same name as the allowed Deployment; ExternalName is rejected.
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=65535
	// +kubebuilder:default=8080
	ServicePort int `json:"servicePort"`
	// +kubebuilder:validation:Enum=/health;/ready
	// +kubebuilder:default="/health"
	Path string `json:"path"`
	// +kubebuilder:validation:Minimum=10
	// +kubebuilder:validation:Maximum=900
	// +kubebuilder:default=120
	TimeoutSeconds int `json:"timeoutSeconds"`
	// +kubebuilder:validation:Minimum=2
	// +kubebuilder:validation:Maximum=10
	// +kubebuilder:default=3
	ConsecutiveSuccesses int `json:"consecutiveSuccesses"`
	// +kubebuilder:validation:Minimum=3
	// +kubebuilder:validation:Maximum=20
	// +kubebuilder:default=5
	Samples int `json:"samples"`
	// Integer basis points avoid ambiguous probability/float policy encodings.
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:validation:Maximum=1000
	// +kubebuilder:default=100
	MaxErrorBasisPoints int `json:"maxErrorBasisPoints"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=5000
	// +kubebuilder:default=500
	MaxP95Milliseconds int `json:"maxP95Milliseconds"`
	// Maximum increase over a healthy baseline. Both relative and absolute bounds apply.
	// +kubebuilder:validation:Minimum=100
	// +kubebuilder:validation:Maximum=300
	// +kubebuilder:default=150
	MaxLatencyPercent int `json:"maxLatencyPercent"`
}

type RollbackRules struct {
	// Enabling this reserves two budget units and always requires signed approval.
	// +kubebuilder:default=false
	Enabled bool `json:"enabled"`
	// +kubebuilder:validation:Minimum=60
	// +kubebuilder:validation:Maximum=86400
	// +kubebuilder:default=3600
	MaxRevisionAgeSeconds int `json:"maxRevisionAgeSeconds"`
}

type PolicySpec struct {
	// +kubebuilder:validation:MinItems=1
	// +kubebuilder:validation:MaxItems=16
	NamespaceAllowlist []string `json:"namespaceAllowlist"`
	// +kubebuilder:validation:XValidation:rule="size(self.matchLabels) > 0",message="explicit workload labels required"
	WorkloadSelector metav1.LabelSelector `json:"workloadSelector"`
	// +kubebuilder:validation:MinItems=1
	// +kubebuilder:validation:MaxItems=8
	IncidentTypes []IncidentType `json:"incidentTypes"`
	// +kubebuilder:validation:MinItems=1
	// +kubebuilder:validation:MaxItems=4
	AllowedActions []ActionKind `json:"allowedActions"`
	// +kubebuilder:default=true
	DryRun bool `json:"dryRun"`
	// +kubebuilder:validation:Enum=warning;critical
	// +kubebuilder:default=warning
	MinimumSeverity string `json:"minimumSeverity"`
	// False only permits unsigned Restart. Scale/Rollback/automatic undo always require approval.
	// +kubebuilder:default=true
	ApprovalRequired bool `json:"approvalRequired"`
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:validation:Maximum=86400
	// +kubebuilder:default=300
	CooldownSeconds int `json:"cooldownSeconds"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=20
	// +kubebuilder:default=2
	MaxActionsPerWindow int `json:"maxActionsPerWindow"`
	// +kubebuilder:validation:Minimum=60
	// +kubebuilder:validation:Maximum=86400
	// +kubebuilder:default=3600
	ActionWindowSeconds int `json:"actionWindowSeconds"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=100
	// +kubebuilder:default=1
	MinimumHealthyReplicas int32 `json:"minimumHealthyReplicas"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=100
	// +kubebuilder:default=1
	MinimumReplicas int32 `json:"minimumReplicas"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=100
	// +kubebuilder:default=4
	MaximumReplicas int32 `json:"maximumReplicas"`
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=5
	// +kubebuilder:default=1
	ScaleStep int32 `json:"scaleStep"`
	// Empty maintenance windows means no execution time is authorized.
	// +kubebuilder:validation:MaxItems=16
	MaintenanceWindows []MaintenanceWindow `json:"maintenanceWindows"`
	// +kubebuilder:validation:MaxLength=128
	// +kubebuilder:validation:MinLength=1
	EscalationDestination string `json:"escalationDestination"`
	// +kubebuilder:validation:Minimum=30
	// +kubebuilder:validation:Maximum=3600
	// +kubebuilder:default=300
	MaxIncidentAgeSeconds int `json:"maxIncidentAgeSeconds"`
	// +kubebuilder:validation:Minimum=2
	// +kubebuilder:validation:Maximum=600
	// +kubebuilder:default=60
	SustainSeconds int               `json:"sustainSeconds"`
	Verification   VerificationRules `json:"verification"`
	Rollback       RollbackRules     `json:"rollback"`
}

// +kubebuilder:object:root=true
// +kubebuilder:resource:shortName=rpolicy,scope=Namespaced
// +kubebuilder:validation:XValidation:rule="self.spec.minimumReplicas <= self.spec.maximumReplicas",message="replica bounds inverted"
type RemediationPolicy struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Spec              PolicySpec `json:"spec"`
}

// +kubebuilder:object:root=true
type RemediationPolicyList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []RemediationPolicy `json:"items"`
}

type Incident struct {
	// +kubebuilder:validation:MaxLength=256
	ID   string       `json:"id"`
	Type IncidentType `json:"type"`
	// ML/LLM sources are intentionally not accepted here.
	// +kubebuilder:validation:Enum=kubernetes;alertmanager;service-probe
	Source string `json:"source"`
	// +kubebuilder:validation:Enum=warning;critical
	Severity   string      `json:"severity"`
	ObservedAt metav1.Time `json:"observedAt"`
}

type Target struct {
	Name           string `json:"name"`
	UID            string `json:"uid"`
	Generation     int64  `json:"generation"`
	TemplateDigest string `json:"templateDigest"`
	Replicas       int32  `json:"replicas"`
}

// ActionSpec is immutable, including policy/workload versions and rollback consent.
type ActionSpec struct {
	Incident        Incident    `json:"incident"`
	PolicyName      string      `json:"policyName"`
	PolicyUID       string      `json:"policyUID"`
	PolicyVersion   string      `json:"policyVersion"`
	Target          Target      `json:"target"`
	Kind            ActionKind  `json:"kind"`
	ScaleTo         int32       `json:"scaleTo,omitempty"`
	RevisionName    string      `json:"revisionName,omitempty"`
	BeforeRevision  string      `json:"beforeRevision,omitempty"`
	RollbackEnabled bool        `json:"rollbackEnabled"`
	BudgetCost      int         `json:"budgetCost"`
	ExpiresAt       metav1.Time `json:"expiresAt"`
}

type ProbeResult struct {
	At              metav1.Time `json:"at"`
	Requests        int         `json:"requests"`
	Errors          int         `json:"errors"`
	P95Milliseconds int         `json:"p95Milliseconds"`
}

type AuditEvent struct {
	At     metav1.Time `json:"at"`
	Actor  string      `json:"actor"`
	State  string      `json:"state"`
	Reason string      `json:"reason"`
}

type ActionStatus struct {
	Phase                 string       `json:"phase,omitempty"`
	Reason                string       `json:"reason,omitempty"`
	AttemptedAt           *metav1.Time `json:"attemptedAt,omitempty"`
	VerificationStartedAt *metav1.Time `json:"verificationStartedAt,omitempty"`
	CompletedAt           *metav1.Time `json:"completedAt,omitempty"`
	AppliedGeneration     int64        `json:"appliedGeneration,omitempty"`
	ExpectedTemplate      string       `json:"expectedTemplate,omitempty"`
	ExpectedReplicas      int32        `json:"expectedReplicas,omitempty"`
	MutationCount         int          `json:"mutationCount,omitempty"`
	Successes             int          `json:"successes,omitempty"`
	ApprovalUID           string       `json:"approvalUID,omitempty"`
	ApprovalActor         string       `json:"approvalActor,omitempty"`
	Before                *ProbeResult `json:"before,omitempty"`
	After                 *ProbeResult `json:"after,omitempty"`
	// Blocks competing actions after an ambiguous timeout or external mutation.
	Hold bool `json:"hold,omitempty"`
	// +kubebuilder:validation:MaxItems=64
	Audit []AuditEvent `json:"audit,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:resource:shortName=raction,scope=Namespaced
// +kubebuilder:subresource:status
// +kubebuilder:validation:XValidation:rule="self.spec == oldSelf.spec",message="action plans are immutable"
// +kubebuilder:printcolumn:name="State",type=string,JSONPath=".status.phase"
// +kubebuilder:printcolumn:name="Action",type=string,JSONPath=".spec.kind"
// +kubebuilder:printcolumn:name="Workload",type=string,JSONPath=".spec.target.name"
type RemediationAction struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Spec              ActionSpec   `json:"spec"`
	Status            ActionStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true
type RemediationActionList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []RemediationAction `json:"items"`
}

type ApprovalSpec struct {
	ActionUID    string      `json:"actionUID"`
	ActionDigest string      `json:"actionDigest"`
	ExpiresAt    metav1.Time `json:"expiresAt"`
	KeyID        string      `json:"keyID"`
	// +kubebuilder:validation:MaxLength=128
	Signature string `json:"signature"`
}

// +kubebuilder:object:root=true
// +kubebuilder:resource:shortName=rapproval,scope=Namespaced
// +kubebuilder:validation:XValidation:rule="self.spec == oldSelf.spec",message="approvals are immutable"
type RemediationApproval struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Spec              ApprovalSpec `json:"spec"`
}

// +kubebuilder:object:root=true
type RemediationApprovalList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []RemediationApproval `json:"items"`
}

type RevisionSpec struct {
	WorkloadUID    string `json:"workloadUID"`
	WorkloadName   string `json:"workloadName"`
	Revision       string `json:"revision"`
	TemplateDigest string `json:"templateDigest"`
	// +kubebuilder:pruning:PreserveUnknownFields
	// +kubebuilder:validation:Schemaless
	// +kubebuilder:validation:Type=object
	Template runtime.RawExtension `json:"template"`
}

type RevisionStatus struct {
	VerifiedAt *metav1.Time `json:"verifiedAt,omitempty"`
	Actor      string       `json:"actor,omitempty"`
	Probe      *ProbeResult `json:"probe,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:resource:shortName=vrevision,scope=Namespaced
// +kubebuilder:subresource:status
// +kubebuilder:validation:XValidation:rule="self.spec == oldSelf.spec",message="revision snapshots are immutable"
type VerifiedRevision struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Spec              RevisionSpec   `json:"spec"`
	Status            RevisionStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true
type VerifiedRevisionList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []VerifiedRevision `json:"items"`
}

func init() {
	SchemeBuilder.Register(&RemediationPolicy{}, &RemediationPolicyList{}, &RemediationAction{}, &RemediationActionList{}, &RemediationApproval{}, &RemediationApprovalList{}, &VerifiedRevision{}, &VerifiedRevisionList{})
}
