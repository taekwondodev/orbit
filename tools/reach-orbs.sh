#!/usr/bin/env bash
# Route DevStack's public network from this machine through the DevStack
# host, so that this machine can SSH to the orbs' floating IPs.
#
#   tools/reach-orbs.sh <devstack-host>
#
# Run it on the machine that connects to the orbs, when that machine is not
# the DevStack host: the computer running DevStack in a VM, or a machine on
# the same local network as a separate DevStack host. <devstack-host> is an
# SSH destination, an alias from ~/.ssh/config too, whose host name is the
# host's IP address. It runs sudo on both machines.
#
# The route goes straight to the host's address, so no router may stand
# between the two machines. Nothing translates the connections on the way in:
# an orb sees this machine's address on the network it shares with the host,
# the host side of the virtualizer's network for a VM. Pass that address as
# ssh_allowed_cidr.
#
# Neither side outlives the machine it is on, and on a computer running the
# VM the route can go with the VM's network interface. Run it again every
# time the VM starts; for a separate host, after either machine restarts or
# the host's address changes. The orbit skill, skills/orbit/SKILL.md, says
# how to find this machine's address.
# Repeatable: what is already in place is left as it is.
#
# DevStack's defaults; override them as in local.conf.
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
