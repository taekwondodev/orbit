# An orb lives until someone deletes it

An orb has no end time: it is born with `POST` and ends with `DELETE`. "Ephemeral" means the orb lasts as long as the work of whoever requested it and then disappears entirely, machine and surrounding resources together; it does not mean it expires by itself. The consumer knows when the work is done, not the service.

The Blazar lease through which the orb reserves capacity ([0004](0004-size-as-blazar-reservation.md)) has an end date because Blazar requires one, but it is set very far away: it is not an expiry and the service does not show it.

## Rejected alternatives

**Expiry governed by Blazar**, the first design: the lease's end was the orb's end time, a renewal moved it forward, and at expiry Blazar took the machine back. Rejected because no requirement asks for expiry, and that safety net cost a lot: a Keystone trust stored encrypted to act after the token expired, a cleaner for the stack Blazar left behind, renewal kept aligned between lease and stack, a separate process for deferred work. It is the path to reread if expiry became a requirement again: [the full design is in the repository history](https://github.com/taekwondodev/orbit/tree/1739781/docs/adr).

**Expiry written in the service**, with an `expires_at` column and a periodic task that deletes what has expired. Cheaper, but it still requires acting on the user's resources when the user is not there, and therefore a stored delegation.

## Accepted risk

A forgotten orb stays on and holds its reserved capacity until someone deletes it. The limit is the project quota ([0002](0002-resources-in-the-users-project.md)) and the capacity Blazar has to grant: when it is exhausted, new orbs are rejected, not half-built.
