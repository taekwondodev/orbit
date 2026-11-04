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

## 2. Create the orb

Choose:

- `size`: the processors, memory and disk the work needs. The operator caps each value; a `400` names the cap you exceeded.
- `public_key`: the public half of a key pair you hold. orbit never sees the private key.
- `ssh_allowed_cidr`: the source address the orb will see for your SSH connection, as `<address>/32`. Account for routing or NAT with the operator; the address used to reach orbit's API need not be the SSH source.
- `image`: choose an operator-supported image, or omit it when a default is configured.

```console
$ jq -n --arg key "$(cat ~/.ssh/id_ed25519.pub)" --arg cidr <address>/32 \
      '{size: {vcpus: 1, memory_mb: 512, disk_gb: 1},
        public_key: $key, ssh_allowed_cidr: $cidr}' \
      | curl -sS -X POST "$ORBIT/v1/orbs" -H "X-Auth-Token: $TOKEN" \
            -H 'Content-Type: application/json' -d @- | tee orb.json | jq
```

Record the orb's `id` at once: from here on, every exit path of your task ends with step 5.

Continue to step 3 on `202`. On `400`, fix the field named by `error.message` and retry. On `409`, request a smaller size or report unavailable capacity. For other failures, use the API contract's error codes to decide whether to retry or report the failure.

## 3. Wait until it is `ACTIVE`

Poll the orb within the task's waiting budget. The creation task follows boot in the background; reads also refresh the status. If the waiting budget expires, report the latest status and go to step 5 rather than polling indefinitely.

```console
$ curl -sS "$ORBIT/v1/orbs/<id>" -H "X-Auth-Token: $TOKEN" | tee orb.json | jq .status
```

- `RESERVING`, `BUILDING`: keep reading. `BUILDING` lasts until the machine has booted and published its host keys.
- `ACTIVE`: go to step 4.
- `ERROR`: `fault` holds the reason. The resources stay up for diagnosis; report the fault, then go to step 5.

## 4. Work inside the orb

Connect as `ssh_user` to `ssh_host`, trusting only the returned host keys. Select the private half of the `public_key` from step 2 explicitly, rather than relying on the SSH agent's default key selection:

```console
$ jq -r '.ssh_host as $h | .ssh_host_keys[] | "\($h) \(.)"' orb.json > orb_known_hosts
$ ssh -i <private-key> -o IdentitiesOnly=yes -o UserKnownHostsFile=orb_known_hosts -o StrictHostKeyChecking=yes \
      "$(jq -r .ssh_user orb.json)@$(jq -r .ssh_host orb.json)" '<command>'
```

Use HTTPS Git remotes for destinations reached through the operator's egress proxy: SSH does not use the HTTP proxy environment variables. If a dependency is unreachable, check the SSH session's `http_proxy`, `https_proxy` and `no_proxy` values, then ask the operator to check the allowed destinations and the image's proxy setup. A connection failure alone does not identify the cause.

## 5. Delete the orb

When the work ends, successful, failed or abandoned:

```console
$ curl -sS -X DELETE "$ORBIT/v1/orbs/<id>" -H "X-Auth-Token: $TOKEN" | jq .status
```

Deletion is repeatable: on an orb already deleting or gone it answers the same way. Read the orb until it is `DELETED`; if it turns `ERROR` instead, the removal failed and another `DELETE` retries it.

Delete only orbs you created: `GET /v1/orbs` lists the whole project's orbs, other consumers' included, and keeps the `DELETED` ones as history. A `DELETED` orb holds no capacity.

Done when the orb you created reads `DELETED`.
