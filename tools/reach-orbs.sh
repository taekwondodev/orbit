#!/usr/bin/env bash
# Usage and setups: skills/orbit/SKILL.md, "Reach the orbs on a DevStack".
FLOATING_RANGE=${FLOATING_RANGE:-172.24.4.0/24}
PUBLIC_NETWORK_GATEWAY=${PUBLIC_NETWORK_GATEWAY:-172.24.4.1}
PUBLIC_BRIDGE=${PUBLIC_BRIDGE:-br-ex}

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 <devstack-host>" >&2
    exit 2
fi
host=$1
host_ip=$(ssh -G "$host" | awk '$1 == "hostname" { print $2 }')
prefix=${FLOATING_RANGE#*/}

# On the host: stack.sh gives the public bridge the network's gateway
# address and NATs the network's way out, and neither is persistent.
echo "On $host: $PUBLIC_NETWORK_GATEWAY/$prefix on $PUBLIC_BRIDGE"
nat="POSTROUTING -o \$dev -s $FLOATING_RANGE -j MASQUERADE"
remote="set -e;
ip addr replace $PUBLIC_NETWORK_GATEWAY/$prefix dev $PUBLIC_BRIDGE;
ip link set $PUBLIC_BRIDGE up;
for dev in \$(ip -4 route show default | awk '{ print \$5 }'); do
    iptables -t nat -C $nat 2>/dev/null || iptables -t nat -A $nat;
done"
# One line, so that any login shell on the host passes it to bash intact.
ssh -t "$host" "sudo bash -c $(printf '%q' "${remote//$'\n'/ }")"

# Here: send the public network to the host. macOS refuses to add a route
# that exists, so replace it only when it points elsewhere.
echo "Here: $FLOATING_RANGE via $host_ip"
case $(uname -s) in
    Darwin)
        gateway=$(route -n get "$PUBLIC_NETWORK_GATEWAY" 2>/dev/null |
            awk '$1 == "gateway:" { print $2 }')
        if [[ "$gateway" != "$host_ip" ]]; then
            sudo route -n delete -net "$FLOATING_RANGE" >/dev/null 2>&1 || true
            sudo route -n add -net "$FLOATING_RANGE" "$host_ip"
        fi
        ;;
    Linux)
        sudo ip route replace "$FLOATING_RANGE" via "$host_ip"
        ;;
    *)
        echo "Unsupported system: add a route to $FLOATING_RANGE via $host_ip." >&2
        exit 1
        ;;
esac
