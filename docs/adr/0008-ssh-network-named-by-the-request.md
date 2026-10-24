# Each creation request names the network the orb admits SSH from

The orb's firewall admits SSH only from the IPv4 network named in the creation request (`ssh_allowed_cidr`, required); IPv4 because the orb's network and floating IP are IPv4 only. The service does not choose it: orbit serves several clients of different users, and only the client knows where it will connect from. A request wider than `[orbs] ssh_min_prefix` is rejected, because a client connects from one address or a small NAT pool. The operator may lower that limit for a client that needs a wider range, and may also cap the admitted networks with `[orbs] ssh_allowed_cidr`.

## Rejected alternatives

**One network for the whole installation, from the configuration.** Enough for a single client, but every client of every user would share the rule, and each orb would be reachable from all of them.

**The caller's address as the network.** Dynamic without asking anything of the client, but orbit-api sees the address of whatever proxy or load balancer stands in front of it, a forwarded address can be forged by the client, and the path to the API may differ from the path to the orb's floating IP, for example IPv6 to the API and IPv4 to the orb. The rule would admit the wrong address and lock the client out.

## Accepted consequence

The rule is fixed in the orb's security group when the stack is created: changing it means creating another orb.
