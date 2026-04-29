# Transfer Processing Mode (`--process-transfers`)

Fetch pending bank transfers queued in the ERP API, confirm each one over
Telegram or XMPP, execute it via FinTS, and PATCH the result back to the API.

This is separate from [`--update-api`](API_MODE.md), which only syncs
balance and transaction data and **never** touches pending transfers.

## Usage

```
transfer-mode.bat
```

Or directly:
```
fints-postbank --process-transfers [--account <name>]
```

| Flag | Purpose |
|------|---------|
| `--account <name>` | Select a specific account in multi-account setups (`.env.<name>`) |

## Required Configuration

The required env vars are identical to `--update-api`. See
[`API_MODE.md`](API_MODE.md#required-configuration) for the full list.

A configured TAN mechanism (`fints-postbank --tan`) and a working bot
(Telegram or XMPP) are mandatory — confirmation prompts and TAN challenges
are delivered through the bot.

## Per-Transfer Flow

For every transfer the API returns with status `pending`:

1. **Listing** — bot reports `Found N pending transfer(s).`
2. **Summary** — bot prints the source IBAN, recipient IBAN/BIC/name,
   amount, and reason.
3. **Confirmation** — bot asks `Confirm transfer? (yes/no):`. Reply `yes`
   or `y` to execute. Anything else skips this transfer.
4. **Verification of Payee (Namensabgleich)** — if the bank's name check
   does not return a clean match, the bot shows the bank-side result
   (`RVMC` partial / `RVNM` no match / `RVNA` not available) along with
   the bank's recorded name when supplied, and asks
   `Confirm transfer despite name check result? (yes/no):`. Decline leaves
   the transfer pending.
5. **TAN challenge** — on confirmation, the bot relays the FinTS TAN
   prompt (e.g. BestSign, photoTAN). Authorize as usual.
6. **Status update** — the bot PATCHes the API:
   - `sent` on FinTS success
   - `failed` with `error_message` on warning or error
7. After all transfers are processed, the bot reports the totals
   (`X executed, Y declined, Z failed`).

## Decline Behaviour

If you reply anything other than `yes` / `y`:

- The transfer stays `pending` in the API.
- No PATCH is sent.
- It will reappear on the next `--process-transfers` run.

To cancel a transfer permanently, do it from the API frontend.

## Failure Handling

If FinTS rejects a transfer (insufficient funds, invalid IBAN at the bank
level, dialog error, …) the bot:

1. Prints the failure to chat.
2. PATCHes `status=failed` with the FinTS response text as `error_message`
   on the API record.
3. Continues with the next pending transfer.

The API allows manually transitioning `failed` → `pending` if you want to
retry later.

## Validation

The ERP API frontend validates IBAN, BIC, amount, and description before
queuing a transfer (same rules as [`SEPA_TRANSFER.md`](SEPA_TRANSFER.md)).
This mode trusts those values and does not re-validate them client-side.

## Security

- No transfer can be triggered without the explicit `yes` confirmation in
  chat **and** a separate TAN authorization at the bank.
- Pressing Enter or replying anything other than `yes` / `y` skips the
  transfer.
- The FinTS session is closed and saved at the end of the run.

## Exit Codes

- `0` — every confirmed transfer succeeded (or no pending transfers found)
- `1` — at least one transfer failed at the bank, or a configuration /
  connectivity error occurred
