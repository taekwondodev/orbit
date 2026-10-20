# Le operazioni differite usano una trust di Keystone

Alla creazione della sessione il servizio si fa delegare dal consumatore, tramite una *trust* di Keystone, i soli ruoli che gli servono, e conserva il trust ID. Quando più tardi deve cancellare una sandbox scaduta, usa quel trust ID per ottenere un token ristretto e agire al posto dell'utente. Un servizio compromesso può così toccare soltanto ciò che ciascun utente gli ha delegato, invece di tutta l'installazione.

Non è un'invenzione nostra: è il meccanismo che Heat adotta per le proprie operazioni differite, ed è il suo metodo predefinito dal rilascio Kilo (`deferred_auth_method=trusts`). Anche Blazar crea una trust con il proprietario di ogni lease: il trust ID compare fra i campi del lease.

## Alternative scartate

**Una credenziale di servizio con ruolo amministrativo.** Una riga di configurazione e nessun segreto per sessione, ma un servizio capace di cancellare le risorse di chiunque, incluse quelle che non c'entrano con le sessioni. Resta accettabile solo come scorciatoia dichiarata.

**Conservare le credenziali dell'utente cifrate** (`deferred_auth_method=password`). È il metodo storico che Heat offre ancora e non raccomanda più: obbliga a chiedere la password agli utenti e ad assumerne la custodia.

## Conseguenza accettata

Il trust ID è un segreto. Non può stare in un'etichetta di uno stack né in un campo leggibile: richiede una riga in un archivio controllato dal servizio e cifrata, esattamente come Heat lo conserva cifrato nel proprio database. È questa conseguenza, e non altro, a rendere necessaria la tabella descritta in [stato conservato](../design/stato.md).

## Fonti

- Modello di autorizzazione di Heat, trustor/trustee, impersonazione, `trusts_delegated_roles`, conservazione cifrata del trust ID: <https://docs.openstack.org/heat/latest/admin/auth-model.html>
- Trust di Keystone: <https://docs.openstack.org/keystone/latest/user/trusts.html>
- Il campo `trust_id` di un lease Blazar: <https://docs.openstack.org/blazar/latest/cli/instance-reservation.html>
