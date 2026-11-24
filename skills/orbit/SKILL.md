---
name: orbit
description: Run work on an orbit orb, a disposable machine reachable over SSH that an OpenStack cloud creates on request and destroys whole. Use when a task needs an isolated machine for untrusted or destructive work, such as builds, tests or an agent editing a repository.
---

# Orbit

An orb is an isolated machine of the size you ask for, reachable over SSH with your public key. orbit hands over the address and steps aside: you enter the orb, do the work, and delete it. An orb never expires, so **you own its deletion**: until you delete it, it holds reserved capacity and your project's quota.

When constructing requests or interpreting a response not covered below, read the [API contract](https://github.com/taekwondodev/orbit/blob/main/docs/design/api.md) for fields, statuses and errors. This skill owns the client procedure.

## 1. Get the endpoint and a token

Needs `openstack`, `curl`, `jq`, `ssh` and your project's credentials in the environment.

```console
$ ORBIT=$(openstack catalog show orbit -f json \
      | jq -r '.endpoints[] | select(.interface == "public") | .url')
$ TOKEN=$(openstack token issue -f value -c id)
```

On a `401`, issue a new token and repeat the request. On a `403`, inspect the message and check project scope or downstream roles as indicated; refreshing the token alone does not grant missing permissions.

Done when `$ORBIT` is a URL and `curl -sS "$ORBIT/v1/orbs" -H "X-Auth-Token: $TOKEN"` answers with an `orbs` list.

## 2. Reach the orbs on a DevStack

Skip this step unless orbit runs on a DevStack and you run somewhere other than its host. There, the orbs' floating IPs live on DevStack's public network, `172.24.4.0/24` by default, which only the DevStack host reaches. Route that network through the host with [tools/reach-orbs.sh](https://github.com/taekwondodev/orbit/blob/main/tools/reach-orbs.sh), from your machine; it runs `sudo` on both machines:

```console
$ tools/reach-orbs.sh <devstack-host>
```

`<devstack-host>` is an SSH destination whose host name is the host's IP address. The route goes straight to that address, and nothing translates your connections on the way in, so the orb sees your address on the network you share with the host. Your setup decides which network that is and when the route is lost:

| Setup | Network shared with the host | Run the script again |
| --- | --- | --- |
| DevStack in a VM on your computer | the virtualizer's network: your address is its host side, such as `192.168.x.1` | every time the VM starts: the host's setup does not outlive the VM, and your route can go with the VM's network interface |
| DevStack on a separate Ubuntu machine | your local network, with no router between the two machines | after either machine restarts, or when the host's address changes |

Your address on that network is the source address towards the host. Use it as `<address>/32` in step 3:

```console
$ HOST_IP=$(ssh -G <devstack-host> | awk '$1 == "hostname" { print $2 }')
$ ip -4 route get "$HOST_IP" | grep -o 'src [0-9.]*'                                     # Linux
$ ipconfig getifaddr "$(route -n get "$HOST_IP" | awk '$1 == "interface:" { print $2 }')"   # macOS
```

Done when SSH to an orb's `ssh_host` reaches the orb in step 5; a timeout there means the route is missing.

## 3. Create the orb

Choose:

- `size`: the processors, memory and disk the work needs. The operator caps each value; a `400` names the cap you exceeded.
- `public_key`: the public half of a key pair you hold. orbit never sees the private key.
- `ssh_allowed_cidr`: the source address the orb will see for your SSH connection, as `<address>/32`. On a DevStack, step 2 gives it; elsewhere, account for routing or NAT with the operator. The address used to reach orbit's API need not be the SSH source.

```console
$ jq -n --arg key "$(cat ~/.ssh/id_ed25519.pub)" --arg cidr <address>/32 \
      '{size: {vcpus: 1, memory_mb: 512, disk_gb: 1},
        public_key: $key, ssh_allowed_cidr: $cidr}' \
      | curl -sS -X POST "$ORBIT/v1/orbs" -H "X-Auth-Token: $TOKEN" \
            -H 'Content-Type: application/json' -d @- | tee orb.json | jq
```

Record the orb's `id` at once: from here on, every exit path of your task ends with step 6.

Continue to step 4 on `202`. On `400`, fix the field named by `error.message` and retry. On `409`, request a smaller size or report unavailable capacity. For other failures, use the API contract's error codes to decide whether to retry or report the failure.

## 4. Wait until it is `ACTIVE`

Poll the orb within the task's waiting budget. The creation task follows boot in the background; reads also refresh the status. If the waiting budget expires, report the latest status and go to step 6 rather than polling indefinitely.

```console
$ curl -sS "$ORBIT/v1/orbs/<id>" -H "X-Auth-Token: $TOKEN" | tee orb.json | jq .status
```

- `RESERVING`, `BUILDING`: keep reading. `BUILDING` lasts until the machine has booted and published its host keys.
- `ACTIVE`: go to step 5.
- `ERROR`: `fault` holds the reason. The resources stay up for diagnosis; report the fault, then go to step 6.

## 5. Work inside the orb

Connect as `ssh_user` to `ssh_host`, trusting only the returned host keys. Select the private half of the `public_key` from step 3 explicitly, rather than relying on the SSH agent's default key selection:

```console
$ jq -r '.ssh_host as $h | .ssh_host_keys[] | "\($h) \(.)"' orb.json > orb_known_hosts
$ ssh -i <private-key> -o IdentitiesOnly=yes -o UserKnownHostsFile=orb_known_hosts -o StrictHostKeyChecking=yes \
      "$(jq -r .ssh_user orb.json)@$(jq -r .ssh_host orb.json)" '<command>'
```

Use HTTPS Git remotes for destinations reached through the operator's egress proxy: SSH does not use the HTTP proxy environment variables. If a dependency is unreachable, check the SSH session's `http_proxy`, `https_proxy` and `no_proxy` values, then ask the operator to check the allowed destinations and the image's proxy setup. A connection failure alone does not identify the cause.

## 6. Delete the orb

When the work ends, successful, failed or abandoned:

```console
$ curl -sS -X DELETE "$ORBIT/v1/orbs/<id>" -H "X-Auth-Token: $TOKEN" | jq .status
```

Deletion is repeatable: on an orb already deleting or gone it answers the same way. Read the orb until it is `DELETED`; if it turns `ERROR` instead, the removal failed and another `DELETE` retries it.

Delete only orbs you created: `GET /v1/orbs` lists the whole project's orbs, other consumers' included, and keeps the `DELETED` ones as history. A `DELETED` orb holds no capacity.

Done when the orb you created reads `DELETED`.
