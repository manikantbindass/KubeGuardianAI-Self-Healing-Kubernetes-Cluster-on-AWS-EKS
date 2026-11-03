package recovery

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"time"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
)

func ApprovalMessage(namespace string, spec v1.ApprovalSpec) []byte {
	// Fixed JSON field order, timestamps normalized to UTC, no signature in signed payload.
	body, _ := json.Marshal([]string{"kubesentinel-approval-v1", namespace, spec.ActionUID, spec.ActionDigest, spec.ExpiresAt.UTC().Format(time.RFC3339), spec.KeyID})
	return body
}

func VerifyApproval(a *v1.RemediationAction, approval *v1.RemediationApproval, keys map[string]ed25519.PublicKey, now time.Time) bool {
	s := approval.Spec
	signature, err := base64.StdEncoding.DecodeString(s.Signature)
	key := keys[s.KeyID]
	return err == nil && len(key) == ed25519.PublicKeySize && approval.Namespace == a.Namespace && s.ActionUID == string(a.UID) && s.ActionDigest == Digest(a.Spec) && now.Before(s.ExpiresAt.Time) && !s.ExpiresAt.After(a.Spec.ExpiresAt.Time) && ed25519.Verify(key, ApprovalMessage(a.Namespace, s), signature)
}
