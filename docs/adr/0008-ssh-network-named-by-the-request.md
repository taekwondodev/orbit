# Each creation request names the network the orb admits SSH from

The orb's firewall admits SSH only from the IPv4 network named in the creation request (`ssh_allowed_cidr`, required); IPv4 because the orb's network and floating IP are IPv4 only. The service does not choose it: orbit serves several harnesses of different users, and only the harness knows where it will connect from. The operator may cap the admitted networks with `[orbs] ssh_allowed_cidr`; a request outside the cap, or one admitting the whole Internet, is rejected with `400`. The network is stored with the orb, like size and image, because it is part of the request the service owns.

## Rejected alternatives

**One network for the whole installation, from the configuration.** Enough for a single harness, but every harness of every user would share the rule, and each orb would be reachable from all of them.

**The caller's address as the network.** Dynamic without asking anything of the client, but orbit-api sees the address of whatever proxy or load balancer stands in front of it, a forwarded address can be forged by the client, and the path to the API may differ from the path to the orb's floating IP, for example IPv6 to the API and IPv4 to the orb. The rule would admit the wrong address and lock the harness out.

## Accepted consequence

The rule is fixed in the orb's security group when the stack is created: changing it means creating another orb.
