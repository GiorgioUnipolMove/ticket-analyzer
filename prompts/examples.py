FEW_SHOT_EXAMPLES = """
Esempio 1:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=ATTIVO, stato_obu=ATTIVO, flag_recesso=N, data_rientro_magazzino=NULL, stato_fattura=NULL, note=NESSUNA FATTURA OBU
POST TICKET: "riconsegna dispositivo aggiuntivo con otp ok, inviata lettera di vettura utile per la restituzione del dispositivo"
NOTE TICKET - Nota Cliente: "Ciao, come da telefonata intercorsa, ti confermiamo di aver finalizzato la richiesta di rimozione dispositivo."
ANALISI: Come mai stato dispositivo attivo, necessario allineare gli stati

Esempio 2:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=ATTIVO, stato_obu=ATTIVO, flag_recesso=N, data_rientro_magazzino=NULL, stato_fattura=NULL
POST TICKET: "riconsegna dispositivo aggiuntivo con otp ok, inviata lettera di vettura utile per la restituzione del dispositivo"
NOTE TICKET - Nota Cliente: "Ho aggiunto questo dispositivo per errore"
ANALISI: Dispositivo attivo, lettera di vettura inviata, ticket chiuso

Esempio 3:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Rejected, stato_dispositivo=ATTIVO, stato_obu=ATTIVO, flag_recesso=N
POST TICKET: "cliente non vuole più procedere con rimozione"
NOTE TICKET - Nota Cliente: "ci ho ripensato"
ANALISI: Cliente ha cambiato idea

Esempio 4:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Rejected, stato_dispositivo=ATTIVO, stato_obu=ATTIVO, flag_recesso=N
POST TICKET: "2 contatti ko, inviata mail"
ANALISI: Mancato ricontatto con cliente, ticket chiuso

Esempio 5:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=CESSATO, stato_obu=ATTIVO, flag_recesso=N
NOTE TICKET - Nota Cliente: "Direct facebook cliente ha problemi con la rimozione obu"
ANALISI: Risolto

Esempio 6:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Rejected, stato_dispositivo=ATTIVO, stato_obu=ATTIVO, flag_recesso=N, tipologia_cliente=Privato
NOTE TICKET - Nota Cliente: "vorrei restituire il dispositivo" - UN SOLO DISPOSITIVO sul contratto
ANALISI: Cliente ha un dispositivo solo deve fare recesso

Esempio 7:
DATI: stato_contratto=CESSATO, pystatuswork=Resolved-Completed, stato_dispositivo=CESSATO, stato_obu=CESSATO
ANALISI: Contratto cessato - non necessaria operazione su rimozione dispositivi aggiuntivi - verificare se fatturazione canoni coerente con richiesta cliente

Esempio 8:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=CESSATO, stato_obu=ATTIVO, data_rientro_magazzino=NULL
ANALISI: Dispositivo cessato, verificare se dispositivo è rientrato

Esempio 9:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=ATTIVO, stato_obu=ATTIVO, stato_fattura=OK
POST TICKET: "inviata lettera di vettura, gestito con otp"
ANALISI: Dispositivo attivo, lettera di vettura inviata, ticket chiuso. Sta pagando il dispositivo

Esempio 10:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=ATTIVO, stato_obu=ATTIVO
POST TICKET: "riconsegna dispositivo aggiuntivo con otp ok"
ANALISI: Stati discordanti - conferma lato IT che gli stati siano allineati

Esempio 11:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=ATTIVO, stato_obu=ATTIVO, stato_fattura=OK
POST TICKET: "aperto ahd per invio lettera di vettura"
ANALISI: Dispositivo risulta ancora attivo, lo sta pagando. Verificare se rientrato a magazzino. Aperto ahd.

Esempio 12:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_obu=CESSATO, flag_recesso=S
ANALISI: Obu cessati per recesso.

Esempio 13:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=ATTIVO, stato_obu=ATTIVO
POST TICKET: "eseguita procedura con OTP"
ANALISI: Eseguita procedura con OTP, ticket chiuso

Esempio 14:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=ATTIVO, stato_obu=ATTIVO
POST TICKET: "mandata mail a cliente"
ANALISI: Mandata mail a cliente. Ticket chiuso

Esempio 15:
DATI: stato_contratto=ATTIVO, pystatuswork=Resolved-Completed, stato_dispositivo=ATTIVO, stato_obu=ATTIVO
NOTE TICKET: "il cliente contesta di aver già fatto la procedura ma non ha ricevuto mail con istruzioni"
POST TICKET: "contatto ko"
ANALISI: Cliente contesta di aver già fatto la procedura ma non ha ricevuto mail con istruzioni. Mancato ricontatto ticket chiuso. Obu attivo. Non lo sta pagando
""".strip()
