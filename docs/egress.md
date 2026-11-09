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

## Commands

Enable the DevStack proxy, in `local.conf`:

```sh
ORBIT_EGRESS_PROXY=True
```

Set the allowed domains, in `local.conf`. The list replaces the default in [settings](../devstack/settings):

```sh
ORBIT_EGRESS_PROXY_DOMAINS=github.com,codeload.github.com,objects.githubusercontent.com,proxy.golang.org
```

Apply `local.conf`:

```console
$ ./unstack.sh && ./stack.sh
```

Apply the domains without restacking:

```console
$ sudoedit /etc/orbit/smokescreen-acl.yaml
$ sudo systemctl restart devstack@orbit-egress-proxy
```

Check a domain from the DevStack host, where `200` means admitted and `407` refused:

```console
$ grep '^egress_proxy' /etc/orbit/orbit.conf
$ curl -sS -o /dev/null -w '%{http_code}\n' -x http://<egress_proxy> https://github.com
```

Check a domain from an orb:

```console
$ ssh <user>@<orb address> 'curl -sS -o /dev/null -w "%{http_code}\n" https://github.com'
```

See the proxy's decisions:

```console
$ journalctl -u devstack@orbit-egress-proxy | grep CANONICAL-PROXY-DECISION
```

Allow an internal address, in `local.conf`:

```ini
[[post-config|$ORBIT_CONF]]
[orbs]
egress_destinations = tcp:192.0.2.10:443
```

Allow it without restacking:

```console
$ sudoedit /etc/orbit/orbit.conf
$ sudo systemctl restart devstack@orbit-api
```
