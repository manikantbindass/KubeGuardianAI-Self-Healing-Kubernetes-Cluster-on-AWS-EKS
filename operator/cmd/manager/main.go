package main

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
	"github.com/manikantbindass/KubeSentinel-AI/operator/internal/recovery"
	apps "k8s.io/api/apps/v1"
	coordination "k8s.io/api/coordination/v1"
	core "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
)

func main() {
	var namespace, workloads, keyfile string
	var execute bool
	flag.StringVar(&namespace, "namespace", "sentinel-lab", "Single authorized namespace")
	flag.StringVar(&workloads, "workloads", "demo-recovery", "Comma-separated installation allowlist")
	flag.StringVar(&keyfile, "approval-keys", "", "JSON map key ID to base64 Ed25519 public key")
	flag.BoolVar(&execute, "execute", false, "Enable policy-authorized mutation; false by default")
	flag.Parse()
	ctrl.SetLogger(zap.New(zap.UseDevMode(false)))
	if recovery.Protected(namespace) || namespace == "" {
		panic("protected namespace installation refused")
	}
	allowed := map[string]bool{}
	for _, name := range strings.Split(workloads, ",") {
		if name == "" {
			panic("empty workload name")
		}
		allowed[name] = true
	}
	keys := map[string]ed25519.PublicKey{}
	if keyfile != "" {
		raw, err := os.ReadFile(keyfile)
		if err != nil {
			panic(err)
		}
		values := map[string]string{}
		if err := json.Unmarshal(raw, &values); err != nil {
			panic(err)
		}
		for id, value := range values {
			key, err := base64.StdEncoding.DecodeString(value)
			if err != nil || len(key) != 32 {
				panic("invalid approval key")
			}
			keys[id] = ed25519.PublicKey(key)
		}
	}
	scheme := runtime.NewScheme()
	for _, add := range []func(*runtime.Scheme) error{apps.AddToScheme, core.AddToScheme, coordination.AddToScheme, v1.AddToScheme} {
		if err := add(scheme); err != nil {
			panic(err)
		}
	}
	config := ctrl.GetConfigOrDie()
	config.Timeout = 10 * time.Second
	config.QPS = 10
	config.Burst = 20
	mgr, err := ctrl.NewManager(config, ctrl.Options{Scheme: scheme, Cache: cache.Options{DefaultNamespaces: map[string]cache.Config{namespace: {}}},
		LeaderElection: true, LeaderElectionID: "kubesentinel-recovery", LeaderElectionNamespace: namespace, LeaderElectionResourceLock: "leases",
		LeaderElectionReleaseOnCancel: false, HealthProbeBindAddress: ":8081", Metrics: metricsserver.Options{BindAddress: "0"}})
	if err != nil {
		panic(err)
	}
	direct, err := client.New(config, client.Options{Scheme: scheme})
	if err != nil {
		panic(err)
	}
	actor := os.Getenv("POD_NAME")
	if actor == "" {
		actor = fmt.Sprintf("local-%d", os.Getpid())
	}
	r := &recovery.Reconciler{Client: direct, Prober: recovery.ServiceProber{Client: direct}, Namespace: namespace, Workloads: allowed, Execute: execute, Actor: actor, Keys: keys, Now: time.Now}
	if err := r.Setup(mgr); err != nil {
		panic(err)
	}
	if err := mgr.AddHealthzCheck("health", healthz.Ping); err != nil {
		panic(err)
	}
	if err := mgr.AddReadyzCheck("ready", healthz.Ping); err != nil {
		panic(err)
	}
	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
		panic(err)
	}
}
