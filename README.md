RFID
====

Useful application, that uses MongoDB to control access via RFID cards.
Currently implemented features:
* User roles
  * Developers
  * Administrators
  * Privileged users
  * Common users
  * Guests
* Blocking users
* Expiring users accounts
* Multiple cards for single user
* Different log levels:
  * Visits log
  * Application log
  * Illegal time log
* Connecting to UART (to control lock)
* Importing settings
* Advanced lock mode
* Working with RFID reader (keyboard emulating) in separate thread
