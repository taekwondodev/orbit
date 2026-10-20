# Gli orb nascono nel progetto di chi li chiede

Il servizio crea le risorse a nome del consumatore, inoltrando il token ricevuto nella richiesta, invece di possederle in un proprio progetto di servizio. Così l'isolamento fra utenti e il tetto massimo di macchine li fa rispettare OpenStack, non il nostro database: la quota del progetto risponde "no" senza che il servizio debba contare nulla, e l'utente vede i propri orb con i comandi OpenStack che già conosce.

## Alternativa scartata

**Un unico progetto di servizio proprietario di tutti gli orb.** Più semplice da configurare, una sola credenziale. Scartata perché sposta nel nostro database due cose che OpenStack sa già fare: l'appartenenza di una risorsa a un utente e il limite di consumo. Una violazione di quel database diventerebbe una confusione di proprietà fra utenti diversi.

## Conseguenza accettata

Il token dell'utente vale solo durante la sua richiesta, e basta: poiché un orb non scade ([0003](0003-nessuna-scadenza.md)), ogni operazione sulle risorse dell'utente — creazione, lettura dello stato, cancellazione — avviene mentre l'utente sta facendo una richiesta. Il servizio non agisce mai sulle risorse dell'utente in sua assenza, e quindi non conserva deleghe.

L'eccezione è il flavor dell'orb, che non appartiene al progetto dell'utente e si gestisce con la credenziale del servizio: vedi [0004](0004-flavor-privato-per-ogni-orb.md).

## Fonti

- Il problema delle operazioni differite e il modello di autorizzazione che Heat adotta per risolverlo: <https://docs.openstack.org/heat/latest/admin/auth-model.html>
