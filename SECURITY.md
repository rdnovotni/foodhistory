# Security and Sensitive Material

Do not commit:

- passwords, API keys, tokens, private keys, or populated `.env` files;
- private collector/owner contact details;
- restricted cultural knowledge;
- copyrighted archival scans without permission to redistribute;
- embargoed repository material;
- large production binaries that belong in object storage.

Use `rights_assignment` and application access controls for restricted, embargoed, culturally sensitive, or private records.

If a credential is committed accidentally, revoke/rotate it immediately; deleting it in a later Git commit is not sufficient.
