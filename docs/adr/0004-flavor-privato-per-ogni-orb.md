# La taglia diventa un flavor privato creato per ogni orb

Per ogni orb il servizio crea un flavor Nova con processori, memoria e disco richiesti, non pubblico e accessibile solo al progetto del consumatore, e lo passa allo stack. È il modo più diretto per sostenere il requisito "ogni orb con risorse diverse" senza un catalogo di taglie prefissate.

Creare un flavor e concederne l'accesso a un progetto sono operazioni riservate all'amministratore nella politica predefinita di Nova. Il servizio le esegue quindi con la propria credenziale, e usa quella credenziale **solo** per i flavor: le risorse dell'utente le tocca sempre con il token dell'utente.

## Alternative scartate

**Un catalogo di flavor prefissati**, con la taglia richiesta arrotondata al più vicino. Nessun privilegio speciale, ma tradisce il requisito: la taglia non sarebbe più quella chiesta.

**Il flavor dentro il template**, con la risorsa `OS::Nova::Flavor`. Un solo oggetto da creare e da cancellare, ma lo stack nasce col token dell'utente, e Heat stesso avverte che la risorsa è utilizzabile solo da amministratori: ogni consumatore dovrebbe esserlo.

**La prenotazione Blazar**, che pubblica un flavor per ogni prenotazione: risolveva la taglia come effetto collaterale della scadenza, ed è caduta con essa ([0003](0003-nessuna-scadenza.md)).

## Conseguenze accettate

- La credenziale del servizio ha privilegi amministrativi su Nova. Su DevStack è la norma per gli utenti dei servizi; restringerla a un ruolo dedicato con una politica Nova sui soli flavor è possibile ed è una scelta aperta.
- Il flavor non va cancellato finché la macchina che lo usa esiste: Nova sconsiglia di cancellare un flavor in uso. La cancellazione del flavor è quindi separata da quella dello stack, e la esegue il pulitore quando nessuna macchina lo usa più.
- I flavor hanno un ambito globale: il nome `orbit-<orb_id>` evita collisioni e permette di riconoscere un flavor orfano.

## Fonti

- Politiche predefinite di Nova: `os_compute_api:os-flavor-manage:create`, `:delete` e `os_compute_api:os-flavor-access:add_tenant_access` valgono `rule:context_is_admin`: <https://docs.openstack.org/nova/latest/configuration/policy.html>
- Cancellazione di un flavor in uso, «not recommended as it can cause incorrect data to be returned»: <https://docs.openstack.org/api-ref/compute/#delete-flavor>
- `OS::Nova::Flavor`, «limited to being used by administrators only»: <https://docs.openstack.org/heat/latest/template_guide/openstack.html#OS::Nova::Flavor>
