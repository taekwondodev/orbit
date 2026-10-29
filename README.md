<p align="center">
  <img src="docs/img/logo.svg" alt="orbit logo: an orb circled by a satellite" width="160">
</p>

<h1 align="center">orbit</h1>

<p align="center">
  <img alt="OpenStack: new service" src="https://img.shields.io/badge/OpenStack-new%20service-ED1944?logo=openstack&logoColor=white">
  <img alt="DevStack: plugin" src="https://img.shields.io/badge/DevStack-plugin-ED1944">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <br>
  <img alt="Integrates: Keystone, Blazar, Heat" src="https://img.shields.io/badge/integrates-Keystone%20%C2%B7%20Blazar%20%C2%B7%20Heat-334155">
  <img alt="Interfaces: REST API, Horizon" src="https://img.shields.io/badge/interfaces-REST%20API%20%C2%B7%20Horizon-334155">
</p>

**Ephemeral sandboxes as an OpenStack service.** A client asks for "a machine with these resources"; the service hands it over isolated and reachable over SSH, and when the client is done it makes it disappear entirely. Each sandbox is an **orb**.

---

## The problem

Whoever runs untrusted or destructive work, such as builds, tests or an agent editing a repository, needs a whole machine, not a folder. That machine must be **isolated**, **sized to the work** and, when the work ends, it must disappear **without leaving anything behind**: not the machine, not the key, not the firewall, not the address.

Done by hand, with a handful of `openstack` commands, each of these points breaks: the available sizes are those in the catalog, a machine may find no room after everything else has been created, a creation that fails halfway leaves scattered pieces, a forgotten deletion leaves an address taken. `orbit` treats the sandbox as a single object, the orb, which is born whole and dies whole.

## What it does

- Accepts the requested **size** (processors, memory, disk) orb by orb, without catalogs of fixed sizes.
- **Reserves the capacity** before building: if there is no room it says so right away, instead of failing halfway.
- Creates the orb in the **project of whoever asks for it**: it appears among their resources and consumes their quota.
- Installs the **public key supplied by the client** and returns address, user and the machine's **host keys** for SSH access, so the client verifies whom it connects to.
- Admits SSH only from the **network the client names** in each request: one address or a small network, within an optional cap set by the operator.
- **Deletes everything** with a single request, repeatable without error: capacity, flavor, machine and surrounding resources.
- **Tells the truth** about the status: every read looks at the real resources, so a machine deleted by hand does not leave behind an orb that lies.

## What it does not do

It does not enter the orb: it does not run commands, does not copy files, does not know what runs inside. It hands over an address and steps aside. It does not decide when an orb must end: whoever asked for it decides. It keeps no tokens or delegations. It does not prepare images, does not act as a proxy, does not manage more than one machine per orb.

---

## Lifecycle of an orb

```mermaid
sequenceDiagram
    autonumber
    actor C as Client
    participant A as orbit
    participant B as Blazar
    participant H as Heat

    C->>A: POST /v1/orbs with size and public key
    A->>B: reserve this capacity from now, with no end
    B-->>A: reservation and private flavor
    A-->>C: 202 Accepted, orb in RESERVING

    Note over A,B: wait: the reservation<br/>must become active
    A->>H: create the stack with the reservation's flavor

    C->>A: GET /v1/orbs/{id}
    A->>H: stack status and address
    A-->>C: ACTIVE, SSH address, user and host keys

    C->>A: DELETE /v1/orbs/{id}
    A->>H: delete the stack
    A->>B: delete the lease
    Note over B: destroys the machine,<br/>then the flavor
    A-->>C: 202 Accepted, orb in DELETING
```

---

## Interface

orbit's client is an agent harness. The agent drives the REST API, `/v1/orbs`, by following the [orbit skill](skills/orbit/SKILL.md); the API itself is described in [docs/design/api.md](docs/design/api.md). People watch the orbs in Horizon, in the read-only **Project → Orbit → Orbs** panel.

The list and orb details update automatically while the tab is visible, including new orbs, deletions and changes to already-active orbs. Returning to the tab refreshes the data immediately. If an update fails, the panel keeps the last data, marks it as potentially out of date and retries; an expired session prompts you to sign in again.

---

## Installation

1. Clone DevStack:

   ```console
   $ git clone https://opendev.org/openstack/devstack
   $ cd devstack
   ```

2. Write `local.conf`, enabling orbit after the Heat and Blazar plugins it depends on:

   ```console
   $ cat > local.conf <<'EOF'
   [[local|localrc]]
   ADMIN_PASSWORD=secret
   DATABASE_PASSWORD=$ADMIN_PASSWORD
   RABBIT_PASSWORD=$ADMIN_PASSWORD
   SERVICE_PASSWORD=$ADMIN_PASSWORD
   enable_plugin heat   https://opendev.org/openstack/heat
   enable_plugin blazar https://opendev.org/openstack/blazar
   enable_plugin orbit  https://github.com/taekwondodev/orbit
   EOF
   ```

3. Install:

   ```console
   $ ./stack.sh
   ```

4. If the agent runs on another machine, make the orbs reachable from there by running `tools/reach-orbs.sh <host>` on it: its header says when to run it again.

5. Give the agent the [orbit skill](skills/orbit/SKILL.md) and the credentials of a project, for example those `source openrc demo demo` sets for `demo`.

6. Watch the agent's orbs in Horizon: at `http://<host>/dashboard`, log in as `demo` with the `ADMIN_PASSWORD`, pick the `demo` project in the project menu at the top, and open **Project → Orbit → Orbs**. DevStack gives `demo` no default project, so Horizon may open `invisible_to_admin` instead, where the list is empty.

What each plugin does and what the installation requires: [docs/architecture.md](docs/architecture.md#installation).

When upgrading an existing Horizon installation, update Orbit and copy its enabled files into Horizon's `openstack_dashboard/local/enabled/`, then run `python manage.py collectstatic --noinput` and `python manage.py compress --force` in Horizon's environment before restarting Horizon. DevStack's fresh-install flow already performs these steps. Already-open tabs must load the updated page once to pick up the new script; subsequent data updates do not reload the page.

Automatic updates follow Horizon's session policy: when `SESSION_REFRESH` is enabled, polling counts as activity, but cannot extend the Keystone token's lifetime.

## Tests

The unit tests need no OpenStack:

```console
$ tox -e py3
$ tox -e dashboard   # the Horizon panel; Python 3.11 or later
```

The dashboard suite covers server-rendered snapshots and error responses. Client-side polling, filtering, sorting and tab visibility also need a browser smoke check; they are not exercised by the Python suite.

---

## Documents

| Document | Content |
| --- | --- |
| [GLOSSARY](GLOSSARY.md) | glossary of the domain and of the OpenStack terms used |
| [Architecture](docs/architecture.md) | ownership boundaries, composition of an orb, full sequence, installation requirements |
| [API contract](docs/design/api.md) | HTTP resources, statuses, errors |
| [orbit skill](skills/orbit/SKILL.md) | how an agent creates, uses and deletes an orb |
| [Stored state](docs/design/state.md) | the service's table and reconciliation |
| [Orb template](orbit/templates/orb.yaml) | Heat description of an orb's resources |
| [Decisions](docs/adr/) | the shape choices, with rejected alternatives and sources |
