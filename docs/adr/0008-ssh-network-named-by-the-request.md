# Each creation request names the network the orb admits SSH from

Each creation request names the network admitted for SSH. The service cannot choose it because the API path need not match the client's SSH path, especially with routing, NAT or proxies. Restricting network breadth fits a single source address or small NAT pool while an operator-controlled cap can constrain the installation. The [API contract](../design/api.md#creation) owns the field and validation rules; [orbit/conf.py](../../orbit/conf.py) defines the configurable limits.

## Rejected alternatives

**One network for the whole installation, from the configuration.** Enough for a single client, but every client of every user would share the rule, and each orb would be reachable from all of them.

**The caller's address as the network.** Dynamic without asking anything of the client, but orbit-api sees the address of whatever proxy or load balancer stands in front of it, a forwarded address can be forged by the client, and the path to the API may differ from the path to the orb's floating IP, for example IPv6 to the API and IPv4 to the orb. The rule would admit the wrong address and lock the client out.

## Accepted consequence

The rule is fixed in the orb's security group when the stack is created: changing it means creating another orb.
