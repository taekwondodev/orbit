# Le sandbox nascono nel progetto di chi chiede la sessione

Il servizio crea le risorse a nome del consumatore, inoltrando il token ricevuto nella richiesta, invece di possederle in un proprio progetto di servizio. Così l'isolamento fra utenti e il tetto massimo di macchine li fa rispettare OpenStack, non il nostro database: la quota del progetto risponde "no" senza che il servizio debba contare nulla, e l'utente vede le proprie sandbox con i comandi OpenStack che già conosce.

## Alternativa scartata

**Un unico progetto di servizio proprietario di tutte le sandbox.** Più semplice da configurare, una sola credenziale. Scartata perché sposta nel nostro database due cose che OpenStack sa già fare: l'appartenenza di una risorsa a un utente e il limite di consumo. Una violazione di quel database diventerebbe una confusione di proprietà fra utenti diversi.

## Conseguenza accettata

Il token dell'utente serve solo durante la richiesta. Tutto ciò che il servizio deve fare più tardi — cancellare la sandbox a scadenza, riallineare lo stato — avviene quando quel token è scaduto e l'utente non è presente. Serve quindi un secondo meccanismo di autenticazione per le operazioni differite, che è l'oggetto di [0003](0003-delega-con-trust-di-keystone.md).

## Fonti

- Il problema delle operazioni differite e il modello di autorizzazione che Heat adotta per lo stesso motivo: <https://docs.openstack.org/heat/latest/admin/auth-model.html>
