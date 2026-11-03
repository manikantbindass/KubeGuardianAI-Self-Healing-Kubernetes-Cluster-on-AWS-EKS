import http from 'k6/http';
import { check, sleep } from 'k6';

// The operator prepares a schema-valid synthetic fixture; no token is written to results.
const payload = open(__ENV.PAYLOAD_FILE || './payload.json');
export const options = {
  vus: 4, duration: '30s',
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
  thresholds: { http_req_failed: ['rate<0.01'], http_req_duration: ['p(95)<1000'] },
};
export function setup() {
  if (__ENV.AUTHORIZED_TARGET !== 'true' || !__ENV.ENDPOINT) {
    throw new Error('Explicit authorized endpoint and fixture required');
  }
}
export default function () {
  const headers = { 'Content-Type': 'application/json' };
  if (__ENV.TOKEN) headers.Authorization = `Bearer ${__ENV.TOKEN}`;
  const r = http.post(__ENV.ENDPOINT, payload, { headers, tags: { route: 'fixed-ingestion' } });
  check(r, { 'accepted': r => r.status >= 200 && r.status < 300 });
  sleep(0.1);
}
