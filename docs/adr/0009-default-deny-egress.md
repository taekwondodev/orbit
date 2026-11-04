# An orb opens outbound connections only to the destinations the operator lists

An orb's firewall denies all outbound traffic. The operator lists, in `[orbs] egress_destinations`, the single hosts with protocol and port every orb may reach, and in `[orbs] egress_proxy` an HTTP proxy through which orbs reach external destinations. The proxy decides which hostnames are reachable; orbit knows only its address, opens the firewall towards it and, through cloud-config user data, has sshd set it in the environment of every SSH session, sudo keep it and apt use it. The rules are part of the orb's template ([0001](0001-provisioning-delegated-to-heat.md)), so they hold outside the reach of the orb's root user, and the behavior verified on DevStack holds on any OpenStack.

The orb's value is moving work off the client and isolating it: the client's machine, its credentials and the disposable environment do not depend on the orb's network. The network decides only whether the orb reaches internal infrastructure and where the uploaded code can be sent; default deny keeps both closed and the operator opens what the work needs. Never list a control-plane service (Keystone, Nova, Neutron, Heat and the other service APIs, hypervisors) or the networks clients connect from: orbit cannot recognize them, so this is the operator's duty.

On DevStack the plugin runs [Smokescreen](https://github.com/stripe/smokescreen) as the lab's proxy when `ORBIT_EGRESS_PROXY=True`, on the host, listening only on the public network's gateway address. It admits only the hostnames in `ORBIT_EGRESS_PROXY_DOMAINS`, resolves them itself and refuses private addresses and the host's own. A company deployment uses its own proxy or package mirror instead.

## Rejected alternatives

**Public Internet allowed, private networks denied**, the target first recorded in [dev #252](https://github.com/taekwondodev/dev/issues/252). Simple, but any public host could receive the uploaded code, and a company deployment wants its dependencies from its own mirror anyway.

**External destinations listed by address.** Public services such as GitHub or package registries sit behind changing CDN addresses: a single address does not hold, and the provider's ranges cover a large part of the Internet. Security groups match addresses, not names.

**Neutron FWaaS.** It matches addresses too, and a cloud need not offer it.

**A guest firewall**, for example rules written by cloud-init. The orb's user has passwordless `sudo` and removes them.

**For the lab proxy:** Squid reaches the same result only through hand-written rules, and its cache does not apply to HTTPS tunnels; tinyproxy does not check the address a name resolves to; SNI proxies such as nginx, HAProxy or Envoy need the orb's traffic redirected through Neutron; intercepting proxies such as mitmproxy break end-to-end TLS and need a CA inside the orb. A proxy on an instance would send its own traffic through the same OVN and NAT path where the lab's guest DNS and HTTPS fail ([#11](https://github.com/taekwondodev/orbit/issues/11), [#17](https://github.com/taekwondodev/orbit/issues/17)), while the host's HTTPS works.

## Accepted consequences

- Heat removes Neutron's default allow-all egress rules only when a security group declares an egress rule, so the template always declares one towards loopback, which never leaves the machine. It also declares DHCP (UDP port 67) towards the broadcast address and the orb's own network: Neutron's OVN driver applies the group's egress rules to the machine's DHCP requests, and without a lease the machine has no address.
- The machine cannot reach the metadata service, so the template asks for a config drive, from which cloud-init reads the key and the user data.
- The environment comes from sshd's `SetEnv`, not from `/etc/environment` or a login shell: clients run commands over SSH without a login shell, and sshd may not use PAM, as on Alpine. An image gets the proxy only if its initializer, cloud-init or tiny-cloud, writes the files before sshd starts, its `sshd_config` includes `sshd_config.d` and its `sudoers` includes `sudoers.d`. CirrOS ignores the user data.
- Tools that ignore `https_proxy` reach no external destination. SSH is one of them, so Git in an orb needs HTTPS remotes.
- Listed destinations, the domains the proxy admits and the SSH connection can carry data out. The proxy filters by domain, not by repository: with `github.com` admitted, a push to another repository is possible.
- On DevStack, orbs reach one port of the host that runs the control plane: a flaw in Smokescreen would give them a foothold there. Smokescreen's self-connection guard keeps the host's other services out of reach through the proxy.
- The rules are fixed when the stack is created: changing the options affects only new orbs.

## Sources

- Heat's `OS::Neutron::SecurityGroup` deletes the default egress rules only when the declared rules include an egress one (`_create_rules`): <https://opendev.org/openstack/heat/src/branch/master/heat/engine/resources/openstack/neutron/security_group.py>
- Smokescreen's hostname ACL, private-address refusal and self-connection guard: <https://github.com/stripe/smokescreen#readme>; `allow_missing_role` applies the default rule to clients without a certificate: `main.go` of release v0.1.0
- Discussion and owner decision: [#16](https://github.com/taekwondodev/orbit/issues/16)
