# Domain glossary

Terms used in the code, in the documents and in commit messages. Where a term belongs to an OpenStack component, the "owner" column says who owns its definition: we are not free to change it.

## The service's domain

| Term | Meaning | Owner |
| --- | --- | --- |
| **Orb** | an ephemeral sandbox: an isolated machine, sized on request, reachable over SSH, that lives until someone deletes it | orbit |
| **Size** | the processors, memory and disk requested for an orb | orbit, translated into a Blazar reservation |
| **Consumer** | the Keystone user who requested the orb; in the original use case it is an agent | Keystone |

An orb is **not** a virtual machine: it is the set of reservation, network, router, machine, key, firewall, port and address, created and destroyed together, plus the status through which the service reports them. This distinction is what makes the service different from a script that calls `openstack server create`.

An orb has no expiry: its life ends with a deletion request. See [docs/adr/0003](docs/adr/0003-no-expiry.md).

## The OpenStack components and what we put in them

| Term | Meaning | Where we use it |
| --- | --- | --- |
| **Keystone** | identity, projects, roles; issues tokens | authenticates requests |
| **Token** | temporary proof of identity attached to every request; lasts about an hour | comes from the client, used to create, read and delete resources on their behalf; the service does not keep it |
| **Project** | the space resources belong to, with its quota | orbs are born in the consumer's project |
| **Blazar** | resource reservation: grants capacity to a project between a start and an end, and takes it back at the end or on deletion | turns the size into guaranteed capacity and a tailored flavor |
| **Lease** | for Blazar, the agreement with a start and an end; contains one or more reservations | one lease per orb, starting "now" with an unlimited end |
| **Reservation** | the capacity granted by a lease; for the `virtual:instance` type it is described by `vcpus`, `memory_mb`, `disk_gb`, `amount` | this is where the orb's size ends up |
| **Reservation flavor** | the non-public Nova flavor Blazar creates for the reservation, with the same identifier; the project can use it only while the reservation is active, and Blazar deletes it with the lease | the orb's machine uses this flavor |
| **Unlimited end** | the lease's end date, set very far away because Blazar requires one but the orb does not expire | not an expiry: the orb ends with `DELETE` |
| **Nova** | starts, stops and destroys virtual machines | no write calls: we reach it through Heat and Blazar |
| **Neutron** | networks, routers, ports, firewalls, reachable addresses | resources declared in the template |
| **Heat** | orchestration: reads a template and creates the listed resources in order, undoing them if something fails | creates and destroys the orb's resources except the lease |
| **Stack** | the set of resources Heat creates from a template | an orb's resources, lease excluded, are a stack |
| **Horizon** | the OpenStack web dashboard, extensible with panels | shows the project's orbs in the read-only Orbs panel |
| **DevStack** | an installation of OpenStack from source for development, extensible with plugins | the environment where the service is installed and tried out |

## Terminology conflicts not to create

Blazar calls its time-bound agreement a **lease**. For us a lease is neither an orb nor an expiry: it is an attribute of the orb, the Blazar object that guarantees its capacity. In the code: `lease` and `reservation` only for Blazar objects.

Heat calls the set of resources a **stack**. In our domain the object is the **orb**, and the stack is one of its attributes. In the code, the fields that hold the identifiers are named `lease_id`, `reservation_id` and `stack_id`, because they identify other components' objects.

**Orbit** is the name of the service, **orb** the name of the resource it manages. Do not use "session" or "sandbox" for an orb.
