# Outbound access from orbs

An orb opens no outbound connection unless the operator allows it. This guide is for the operator: what an orb can reach, how to admit an external hostname through the DevStack egress proxy, how to allow an internal address, and how to check the result. Why outbound traffic is denied, and what each allowance can carry out, is recorded in [0009](adr/0009-default-deny-egress.md); read its consequences before adding a destination.

## What an orb can reach

The orb's security group is declared in the [template](../orbit/templates/orb.yaml):

| Traffic | Allowed | Set by |
| --- | --- | --- |
| Inbound SSH | TCP 22 from the request's `ssh_allowed_cidr`, and the replies on those connections. The orb cannot open a connection back to the client. | the client, per orb, within the operator's `[orbs] ssh_allowed_cidr` cap ([API](design/api.md)) |
| Other inbound | none | |
| Boot | DHCP requests: UDP to port 67 on the orb's own subnet and on the broadcast address. They reach only the network's DHCP service. | the template |
| Outbound to listed destinations | each protocol, IPv4 address and port in `[orbs] egress_destinations`, which is empty by default | the operator, for all new orbs |
| Outbound to the egress proxy | TCP to the `[orbs] egress_proxy` address and port. The proxy decides which hostnames are reachable. | the operator, for all new orbs |
| Other outbound | none: no Internet, DNS, metadata service or cloud service | |

Without a proxy and with no listed destinations, an orb gets its address and accepts SSH, but opens no connection to the Internet or to any other host. Disabling the proxy does not restore direct Internet access.

Three settings are easy to confuse:

- `ssh_allowed_cidr` names where SSH may come **from**. It is a field of each creation request; the `[orbs]` option of the same name only caps it. It never permits outbound traffic.
- `egress_destinations` is an orbit option listing **addresses** the orb may connect to directly.
- `ORBIT_EGRESS_PROXY_DOMAINS` is a DevStack variable listing the **hostnames** the DevStack proxy admits. orbit never reads it.

The orbit options become security group rules and user data when an orb's stack is created, so changing them affects new orbs only. The proxy's domain list belongs to the shared proxy instead: once the proxy restarts with a new list, every orb that reaches it, existing ones included, gets the new list.

## The DevStack egress proxy

On DevStack, the [plugin](../devstack/plugin.sh) can run Smokescreen on the host as the orbs' egress proxy. [devstack/settings](../devstack/settings) defines its variables and their defaults.

- `ORBIT_EGRESS_PROXY=True` in `local.conf` enables the proxy service. `stack.sh` then installs Smokescreen, generates its configuration from the variables and sets `[orbs] egress_proxy` in `orbit.conf` to the public network's gateway address and `ORBIT_EGRESS_PROXY_PORT`, TCP 4750 unless set.
- `[orbs] egress_proxy` is orbit's own option and can name any HTTP proxy, such as one a non-DevStack deployment runs. Setting it does not start a proxy.

The proxy admits only listed hostnames and refuses destinations that resolve to private addresses, so internal hosts are reached through `egress_destinations` instead. Its address checks do not cover every service on the DevStack host: [0009](adr/0009-default-deny-egress.md) leaves the safety of each admitted destination to the operator.

Each orb also needs an image that applies the proxy settings from its user data; enabling the proxy configures no tools in an image that ignores them. The requirements are in [Images other than CirrOS](architecture.md#images-other-than-cirros).

### Change the allowed domains

The durable list is `ORBIT_EGRESS_PROXY_DOMAINS` in the `[[local|localrc]]` section of DevStack's `local.conf`: hostnames separated by commas, without spaces. Setting it **replaces** the default list in [settings](../devstack/settings) rather than adding to it. To add a hostname, copy the default value, keep the entries your work still needs and append the new one. For example, a deployment that needs only GitHub over HTTPS and Go modules sets:

```sh
ORBIT_EGRESS_PROXY_DOMAINS=github.com,codeload.github.com,objects.githubusercontent.com,proxy.golang.org
```

List every hostname a tool contacts, including the hosts it is redirected to for downloads. Smokescreen's wildcard syntax is described [upstream](https://github.com/stripe/smokescreen/blob/v0.1.0/README.md#hostname-acls).

Apply the change in one of two ways:

- **Restack.** `./unstack.sh`, then `./stack.sh`, regenerates the proxy configuration from `local.conf`. `stack.sh` also recreates the services' databases, orbit's included, so existing orbs do not survive it: delete them through orbit first.
- **Keep the running stack.** After updating `local.conf`, edit the same list under `allowed_domains` in the generated `smokescreen-acl.yaml`, in orbit's configuration directory (`/etc/orbit` by default), and restart the proxy:

  ```console
  $ sudo systemctl restart devstack@orbit-egress-proxy
  ```

  Smokescreen reads its ACL only when it starts. The restart keeps the orbs but closes their open proxy connections, so downloads in progress fail and must be retried. The next `stack.sh` overwrites the generated file from `local.conf`, so a change made only there is lost.

### Check access

On the DevStack host, read the proxy's address from `orbit.conf` and ask it for an admitted and an unlisted hostname:

```console
$ grep '^egress_proxy' /etc/orbit/orbit.conf
egress_proxy = <address>:<port>
$ curl -sS -o /dev/null -w '%{http_code}\n' -x http://<address>:<port> https://github.com
200
$ curl -sS -o /dev/null -x http://<address>:<port> https://example.com
curl: (56) CONNECT tunnel failed, response 407
```

Then check from an orb, which must use an image that applies the proxy settings. The quotes keep the variable for the orb's shell:

```console
$ ssh <user>@<orb address> 'echo "$https_proxy"; curl -sS -o /dev/null -w "%{http_code}\n" https://github.com'
http://<address>:<port>
200
```

Only a 407 identifies a refusal by the proxy; other errors narrow the search without naming the cause:

| curl error | What to check |
| --- | --- |
| `CONNECT tunnel failed, response 407` | The proxy refused the destination. Its log gives the reason, such as a hostname missing from the list or a private address. |
| `CONNECT tunnel failed, response 502` | The proxy admitted the hostname but could not resolve it or connect to it from the host. |
| `Failed to connect to <address> port <port>` | Whether the proxy runs (`systemctl status devstack@orbit-egress-proxy`), whether the session's proxy endpoint matches the current `egress_proxy`, and whether the orb's security group allows it. An orb keeps the endpoint and rule it was created with. |
| `Could not resolve host` | The session's `https_proxy` and `no_proxy` values. Without proxy variables, or for a host in `no_proxy`, curl resolves the name itself and the orb has no DNS. Check a fresh SSH session: if the variables are still missing, the orb was created without `egress_proxy` or its image did not apply the user data. |

The proxy logs each decision in `journalctl -u devstack@orbit-egress-proxy`, as `CANONICAL-PROXY-DECISION` entries with the fields `allow` and `decision_reason`.

Git over SSH, such as a `git@github.com:` remote, does not use the HTTP proxy variables. Clients use HTTPS remotes, as the [orbit skill](../skills/orbit/SKILL.md#4-work-inside-the-orb) says.

## Allow an internal address

`[orbs] egress_destinations` lists `protocol:address:port` exceptions; [orbit/conf.py](../orbit/conf.py) defines the format. Each entry permits that protocol to that single IPv4 address and port, with or without a proxy, and nothing else. When a proxy is configured, listed addresses are excluded from it through `no_proxy`, so tools connect to them directly. [0009](adr/0009-default-deny-egress.md) states which hosts must never be listed.

For example, to let new orbs reach an HTTPS mirror at `192.0.2.10`:

```ini
[orbs]
egress_destinations = tcp:192.0.2.10:443
```

On DevStack, `stack.sh` rewrites `orbit.conf`, so keep the option in `local.conf`. DevStack applies a `post-config` section after the plugin writes the file and before orbit-api starts:

```ini
[[post-config|$ORBIT_CONF]]
[orbs]
egress_destinations = tcp:192.0.2.10:443
```

To apply it without restacking, add the same line under `[orbs]` in `/etc/orbit/orbit.conf` and restart orbit-api, which reads its options at start and refuses to start with an invalid entry. The restart ends the creation tasks running in orbit-api, and their orbs can end in `ERROR` ([reconciliation](design/state.md#reconciliation)). Restart while no client is creating orbs:

```console
$ sudo systemctl restart devstack@orbit-api
```

Orbs created afterwards get the rule; existing orbs keep the rules they were created with.
