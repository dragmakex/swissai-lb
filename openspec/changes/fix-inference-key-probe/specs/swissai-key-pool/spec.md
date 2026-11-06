## ADDED Requirements

### Requirement: Non-generating inference-key probes
Key add, replacement and manual probes SHALL check inference-key authentication rather than account-profile login. The check SHALL use an intentionally unroutable model identity and empty messages. Public model listings SHALL NOT be treated as authentication proof. No valid model SHALL be selected for a probe.

#### Scenario: Research key cannot access account profile
- **WHEN** an inference key receives a profile access-token rejection but the inference gateway returns the known sentinel-model rejection
- **THEN** the key is eligible and is not marked invalid because of profile authentication

### Requirement: Conservative probe health changes
Only the recognized sentinel-model rejection SHALL count as authenticated and only an inference 401 SHALL invalidate a key during probing. Other status/body combinations and network failures SHALL be reported as inconclusive without changing existing health. A recognized successful re-probe SHALL clear stale invalidity only for the credential generation that was checked.

#### Scenario: Recover a falsely invalid key
- **WHEN** an explicit probe of a saved invalid key receives the recognized authenticated rejection
- **THEN** its existing identity and secret generation are preserved and its invalid state is cleared

#### Scenario: Unrecognized probe response
- **WHEN** a probe receives a generic 404, an unexpected success, a server failure or an unreachable-provider error
- **THEN** no health state is changed and the result does not claim authentication succeeded
