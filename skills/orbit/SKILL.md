---
name: orbit
description: Run work on an orbit orb, a disposable machine reachable over SSH that an OpenStack cloud creates on request and destroys whole. Use when a task needs an isolated machine for untrusted or destructive work, such as builds, tests or an agent editing a repository.
---

# Orbit

An orb is an isolated machine of the size you ask for, reachable over SSH with your public key. orbit hands over the address and steps aside: you enter the orb, do the work, and delete it. An orb never expires, so **you own its deletion**: until you delete it, it holds reserved capacity and your project's quota.

The HTTP contract, with every field, status and error code, is the [API contract](https://github.com/taekwondodev/orbit/blob/main/docs/design/api.md). This skill covers the procedure and what to do with each outcome.

## 1. Get the endpoint and a token

Needs `openstack`, `curl`, `jq`, `ssh` and your project's credentials in the environment.

```console
$ ORBIT=$(openstack catalog show orbit -f json \
      | jq -r '.endpoints[] | select(.interface == "public") | .url')
$ TOKEN=$(openstack token issue -f value -c id)
```

The token lasts about an hour. On a `401`, issue a new one and repeat the request. On a `403` about the scope, the credentials lack a project: an orb always belongs to one.

Done when `$ORBIT` is a URL and `curl -sS "$ORBIT/v1/orbs" -H "X-Auth-Token: $TOKEN"` answers with an `orbs` list.

## 2. Create the orb

Choose:

- `size`: the processors, memory and disk the work needs. The operator caps each value; a `400` names the cap you exceeded.
- `public_key`: the public half of a key pair you hold. orbit never sees the private key.
- `ssh_allowed_cidr`: the address the orb sees you connect from, as `<address>/32`. The orb's firewall admits SSH from that network only. On a DevStack host it is `172.24.4.1`. On another machine the operator has routed the orbs' network through the DevStack host, and the address is this machine's own address toward that host.
- `image`: optional; without it the operator's default applies.

```console
$ jq -n --arg key "$(cat ~/.ssh/id_ed25519.pub)" --arg cidr <address>/32 \
      '{size: {vcpus: 1, memory_mb: 512, disk_gb: 1},
        public_key: $key, ssh_allowed_cidr: $cidr}' \
      | curl -sS -X POST "$ORBIT/v1/orbs" -H "X-Auth-Token: $TOKEN" \
            -H 'Content-Type: application/json' -d @- | tee orb.json | jq
```

Record the orb's `id` at once: from here on, every exit path of your task ends with step 5.

| Response | Meaning |
| --- | --- |
| `202`, status `RESERVING` | capacity reserved; go to step 3 |
| `400` | fix the field the message names and retry |
| `409` | no host has room for this size; nothing was created |
| `502`, `503` | a component behind orbit refused or is down; nothing was created |

Errors arrive as `{"error": {"code": ..., "message": ...}}`.

## 3. Wait until it is `ACTIVE`

Read the orb until it leaves `RESERVING` and `BUILDING`. Reads are what advance its status, and the service moves an orb stuck in creation to `ERROR` by itself, so the loop always ends.

```console
$ curl -sS "$ORBIT/v1/orbs/<id>" -H "X-Auth-Token: $TOKEN" | tee orb.json | jq .status
```

- `RESERVING`, `BUILDING`: keep reading. `BUILDING` lasts until the machine has booted and published its host keys.
- `ACTIVE`: go to step 4.
- `ERROR`: `fault` holds the reason. The resources stay up for diagnosis; report the fault, then go to step 5.

## 4. Work inside the orb

Connect as `ssh_user` to `ssh_host`, with the private half of the `public_key` you gave in step 2 and trusting only the host keys orbit read from the machine. The orb accepts no other key, so always pass it with `-i`:

```console
$ jq -r '.ssh_host as $h | .ssh_host_keys[] | "\($h) \(.)"' orb.json > orb_known_hosts
$ ssh -i <private-key> -o UserKnownHostsFile=orb_known_hosts -o StrictHostKeyChecking=yes \
      "$(jq -r .ssh_user orb.json)@$(jq -r .ssh_host orb.json)" '<command>'
```

## 5. Delete the orb

When the work ends, successful, failed or abandoned:

```console
$ curl -sS -X DELETE "$ORBIT/v1/orbs/<id>" -H "X-Auth-Token: $TOKEN" | jq .status
```

Deletion is repeatable: on an orb already deleting or gone it answers the same way. Read the orb until it is `DELETED`; if it turns `ERROR` instead, the removal failed and another `DELETE` retries it.

Delete only orbs you created: `GET /v1/orbs` lists the whole project's orbs, other consumers' included, and keeps the `DELETED` ones as history. A `DELETED` orb holds no capacity.

Done when the orb you created reads `DELETED`.
