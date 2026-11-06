# Proposal

## Why

Both operator keys were disabled by the automatic `/v1/profile` probe even though the inference gateway accepted them. The provider's account/profile access-token boundary is not a valid test of a research inference key. Fake fixtures incorrectly accepted research keys at the profile endpoint and hid this defect.

## What Changes

- Validate add/replace/manual probes at the inference authentication boundary, using an intentionally unnamespaced, nonexistent model and empty messages so no model can execute.
- Recognize only the observed 404 invalid-model rejection as authenticated; inference 401 remains invalid. Other responses/network failures are inconclusive and do not change existing key health.
- A successful explicit re-probe clears the old false invalid state through the existing generation-fenced health operation, without replacing secrets or editing the database manually.
- Correct fake-provider profile behavior and add product-path regressions, including recovery of existing invalid keys.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `swissai-key-pool`: distinguish inference authentication from account-profile login and make key probes non-generating and conservative.

## Impact

SwissAI probe API/policy, fake HTTP fixtures and tests, owning spec/context. No schema migration, credential replacement, process restart or operator-database write is performed by the implementation task itself; the operator restarts and uses Probe to apply the fix to saved keys.
