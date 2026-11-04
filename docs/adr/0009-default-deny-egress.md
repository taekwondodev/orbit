# An orb opens outbound connections only to the destinations the operator lists

Deny outbound connections by default in the orb's Neutron security group, with explicit destinations and an HTTP egress proxy selected by the operator. The rules belong to the [Heat template](../../orbit/templates/orb.yaml), following [0001](0001-provisioning-delegated-to-heat.md), so the orb's root user cannot remove them from inside the guest. A proxy can restrict external access by hostname where security groups can match only addresses.

The operator owns the trust boundary: allowed destinations must exclude control-plane services, hypervisors and the networks clients connect from. orbit validates destination syntax, not whether a host is safe to expose. Option formats and defaults belong to [orbit/conf.py](../../orbit/conf.py).

## Rejected alternatives

**Public Internet allowed, private networks denied.** Any public host could receive uploaded code. Explicit destinations let the operator limit both infrastructure access and where work can send data.

**External destinations listed by address.** Services behind changing CDN addresses cannot be represented by one stable address, and provider-wide ranges admit unrelated destinations. Neutron FWaaS also matches addresses and is not available in every cloud.

**A guest firewall.** The orb's user has passwordless sudo and can remove it.

**A proxy inside a DevStack instance.** The lab's guest DNS and HTTPS failures were recorded in [#11](https://github.com/taekwondodev/orbit/issues/11) and [#17](https://github.com/taekwondodev/orbit/issues/17). Running the lab proxy on the host avoids that guest network path. Smokescreen provides hostname allowlists, address checks and a self-connection guard without intercepting TLS; its behavior is documented [upstream](https://github.com/stripe/smokescreen#readme). Other deployments supply their own proxy or mirror.

## Accepted consequences

- Allowed destinations, admitted proxy domains and the SSH connection can carry data out. A domain allowlist does not restrict repositories: admitting `github.com` can permit pushes to other repositories.
- On DevStack, orbs reach a proxy port on the host that runs the control plane. A proxy vulnerability could give them a foothold there; address checks and the self-connection guard are part of that boundary. Read this decision before moving the proxy or relaxing those checks.
- Proxy settings come from sshd's `SetEnv`, rather than a login shell or PAM, because clients run non-login SSH commands and some images do not use PAM. Required image behavior and its acceptance check belong to [Images other than CirrOS](../architecture.md#images-other-than-cirros); client workflow belongs to the [orbit skill](../../skills/orbit/SKILL.md#4-work-inside-the-orb).
- The [template](../../orbit/templates/orb.yaml) owns the DHCP exceptions, Heat's default-egress removal workaround and the config drive needed without metadata access. Preserve those boot requirements when changing the network policy.
- Rules are fixed when a stack is created. Configuration changes affect new orbs, not existing ones.

## Sources

- Discussion and owner decision: [#16](https://github.com/taekwondodev/orbit/issues/16).
- Heat's default egress handling: `_create_rules` in [OS::Neutron::SecurityGroup](https://opendev.org/openstack/heat/src/branch/master/heat/engine/resources/openstack/neutron/security_group.py).
- The lab proxy's pinned release and configuration: [devstack/plugin.sh](../../devstack/plugin.sh). Smokescreen's `allow_missing_role` handling: [main.go at v0.1.0](https://github.com/stripe/smokescreen/blob/v0.1.0/main.go).
