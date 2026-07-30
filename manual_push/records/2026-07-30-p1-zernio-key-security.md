# P1 Zernio key and account-security validation

## Completed

- Zernio Profile endpoints use a non-conflicting authenticated route:
  `/api/user/zernio/connection`.
- Account/profile and analytics endpoints derive identity from the verified
  Cognito principal; no email path/query parameter is accepted for ownership.
- User-supplied Zernio keys are encrypted with Fernet before persistence.
- Existing plaintext values are upgraded to encrypted values on their first
  successful read after encryption is configured.
- Requests fail closed when encryption is not configured; no new plaintext key
  is written as a fallback.

## One-time deployment configuration

Generate and place this secret in the backend deployment environment (or the
untracked local `backend/.env`), then restart the backend:

```powershell
& backend\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```text
ZERNIO_KEY_ENCRYPTION_KEY=<generated value>
```

Do not commit this value, add it to frontend environment variables, or derive
it from the Supabase key. Keep the value stable: rotating it without a planned
key-rewrap migration would make previously encrypted Zernio keys unreadable.

## Validation evidence

- Ciphertext round-trip passed and does not contain plaintext.
- TypeScript check passed.
- Focused frontend lint for changed onboarding/statistics files passed.
- Live backend rejected unauthenticated protected routes with `401`.
- Legacy email-address profile routes returned `404`.
