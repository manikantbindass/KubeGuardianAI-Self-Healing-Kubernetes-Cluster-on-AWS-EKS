package recovery

import (
	"context"
	"fmt"
	"io"
	"net"
	"net/http"
	"sort"
	"time"

	v1 "github.com/manikantbindass/KubeSentinel-AI/operator/api/v1alpha1"
	apps "k8s.io/api/apps/v1"
	core "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

type Prober interface {
	Probe(context.Context, *apps.Deployment, v1.VerificationRules) (*v1.ProbeResult, error)
}

type ServiceProber struct{ Client client.Client }

func (p ServiceProber) Probe(ctx context.Context, deployment *apps.Deployment, rules v1.VerificationRules) (*v1.ProbeResult, error) {
	service := &core.Service{}
	if err := p.Client.Get(ctx, types.NamespacedName{Namespace: deployment.Namespace, Name: deployment.Name}, service); err != nil {
		return nil, err
	}
	if service.Spec.Type != core.ServiceTypeClusterIP || net.ParseIP(service.Spec.ClusterIP) == nil || len(service.Spec.Selector) == 0 {
		return nil, fmt.Errorf("unsafe or missing ClusterIP Service")
	}
	// Every service selector must bind the same workload pod template, not arbitrary peers.
	for key, value := range service.Spec.Selector {
		if deployment.Spec.Template.Labels[key] != value {
			return nil, fmt.Errorf("service selector mismatch")
		}
	}
	if service.Spec.Selector["app"] != deployment.Name {
		return nil, fmt.Errorf("service must select app=deployment-name")
	}
	found := false
	for _, port := range service.Spec.Ports {
		if int(port.Port) == rules.ServicePort && port.Protocol == core.ProtocolTCP {
			found = true
		}
	}
	if !found || (rules.Path != "/health" && rules.Path != "/ready") || rules.Samples < 3 || rules.Samples > 20 {
		return nil, fmt.Errorf("invalid probe contract")
	}
	transport := &http.Transport{Proxy: nil, DisableKeepAlives: true}
	defer transport.CloseIdleConnections()
	httpClient := &http.Client{Transport: transport, Timeout: 2 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	url := "http://" + net.JoinHostPort(service.Spec.ClusterIP, fmt.Sprint(rules.ServicePort)) + rules.Path
	result := &v1.ProbeResult{At: metav1.Now(), Requests: rules.Samples}
	latencies := make([]int, 0, rules.Samples)
	for i := 0; i < rules.Samples; i++ {
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		started := time.Now()
		request, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		response, err := httpClient.Do(request)
		if err != nil {
			result.Errors++
		} else {
			if response.StatusCode < 200 || response.StatusCode >= 300 {
				result.Errors++
			}
			_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, 4096))
			_ = response.Body.Close()
		}
		latencies = append(latencies, int(time.Since(started).Milliseconds()))
	}
	sort.Ints(latencies)
	index := (95*len(latencies)+99)/100 - 1
	result.P95Milliseconds = latencies[index]
	return result, nil
}

func GoodProbe(after, before *v1.ProbeResult, rules v1.VerificationRules) bool {
	if after == nil || after.Requests < rules.Samples || after.Errors*10000 > rules.MaxErrorBasisPoints*after.Requests || after.P95Milliseconds > rules.MaxP95Milliseconds {
		return false
	}
	if before != nil && before.Requests > 0 {
		if after.Errors*before.Requests > before.Errors*after.Requests {
			return false
		}
		if before.Errors == 0 && after.P95Milliseconds > max(before.P95Milliseconds, 20)*rules.MaxLatencyPercent/100 {
			return false
		}
	}
	return true
}
