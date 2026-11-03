// Approval is an offline signing tool. Private keys never enter the controller or Kubernetes.
package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
	"github.com/manikantbindass/KubeSentinel-AI/operator/internal/recovery"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func main() {
	var command, private, public, actionFile, id, output string
	flag.StringVar(&command, "command", "sign", "keygen or sign")
	flag.StringVar(&private, "private-key", "../.cache/operator/approver.key", "Private key file (never commit)")
	flag.StringVar(&public, "public-keys", "../.cache/operator/public-keys.json", "Public trust map")
	flag.StringVar(&actionFile, "action", "", "Reviewed RemediationAction JSON")
	flag.StringVar(&id, "key-id", "local-operator", "Approved human/key identity")
	flag.StringVar(&output, "output", "../.cache/operator/approval.json", "Output approval resource")
	flag.Parse()
	if command == "keygen" {
		pub, key, err := ed25519.GenerateKey(rand.Reader)
		must(err)
		file, err := os.OpenFile(private, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		must(err)
		_, err = file.WriteString(base64.StdEncoding.EncodeToString(key))
		must(err)
		must(file.Close())
		body, _ := json.MarshalIndent(map[string]string{id: base64.StdEncoding.EncodeToString(pub)}, "", "  ")
		must(os.WriteFile(public, body, 0644))
		return
	}
	if command != "sign" || actionFile == "" {
		panic("sign requires --action with reviewed plan")
	}
	data, err := os.ReadFile(actionFile)
	must(err)
	action := &v1.RemediationAction{}
	must(json.Unmarshal(data, action))
	if action.Status.Phase != "AwaitingApproval" || action.UID == "" || !time.Now().Before(action.Spec.ExpiresAt.Time) {
		panic("plan is not an unexpired AwaitingApproval action")
	}
	encoded, err := os.ReadFile(private)
	must(err)
	key, err := base64.StdEncoding.DecodeString(string(encoded))
	must(err)
	if len(key) != ed25519.PrivateKeySize {
		panic("invalid key")
	}
	expires := time.Now().UTC().Add(5 * time.Minute).Truncate(time.Second)
	if expires.After(action.Spec.ExpiresAt.Time) {
		expires = action.Spec.ExpiresAt.Time
	}
	spec := v1.ApprovalSpec{ActionUID: string(action.UID), ActionDigest: recovery.Digest(action.Spec), ExpiresAt: metav1.NewTime(expires), KeyID: id}
	spec.Signature = base64.StdEncoding.EncodeToString(ed25519.Sign(ed25519.PrivateKey(key), recovery.ApprovalMessage(action.Namespace, spec)))
	approval := v1.RemediationApproval{TypeMeta: metav1.TypeMeta{APIVersion: v1.GroupVersion.String(), Kind: "RemediationApproval"}, ObjectMeta: metav1.ObjectMeta{Name: "approve-" + string(action.UID), Namespace: action.Namespace}, Spec: spec}
	body, err := json.MarshalIndent(approval, "", "  ")
	must(err)
	must(os.WriteFile(output, body, 0600))
	fmt.Println(output)
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
