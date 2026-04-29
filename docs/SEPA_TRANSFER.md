# SEPA Transfer

The interactive console mode supports sending SEPA bank transfers directly from the CLI.

## Usage

1. Start the client in console mode:
   ```
   start.bat
   ```
   Or with a specific account:
   ```
   fints-postbank --account postbank
   ```

2. Select **3. Transfer** from the main menu.

3. Enter the transfer details when prompted:
   - **Recipient IBAN** — validated with full checksum verification
   - **Recipient BIC** — optional, press Enter to skip for domestic German transfers
   - **Recipient name** — required
   - **Amount (EUR)** — positive number with up to 2 decimal places (use `.` or `,` as separator)
   - **Transfer reason/description** — optional

4. Review the **Transfer Summary** and confirm with `yes` or `y`.

5. If the bank's **Verification of Payee** check does not return a clean match, the CLI shows the bank-side result and asks `Confirm transfer despite name check result? (yes/no):`. Decline aborts the transfer.

6. Complete the **TAN challenge** (e.g., confirm in your BestSign app) to authorize the transfer.

## Example

```
--- SEPA Transfer ---
Enter 'cancel' at any prompt to abort.

Recipient IBAN: DE89 3704 0044 0532 0130 00
Recipient BIC (press Enter to skip for domestic):
Recipient name: Max Mustermann
Amount (EUR): 50,00
Transfer reason/description: Invoice 12345

--- Transfer Summary ---
From:        DE30760100850087278859
To IBAN:     DE89370400440532013000
Recipient:   Max Mustermann
Amount:      50.00 EUR
Reason:      Invoice 12345
------------------------

Confirm transfer? (yes/no): yes
```

## Cancellation

Type `cancel` at any input prompt to abort the transfer. You can also decline at the confirmation step by entering anything other than `yes`/`y`.

Transfers are never stored as the "last action" in the menu, so pressing Enter cannot accidentally repeat a transfer.

## Validation

- **IBAN** is validated using the [schwifty](https://github.com/mdomke/schwifty) library (format + checksum)
- **BIC** is validated by schwifty when provided
- **Amount** must be a positive number with at most 2 decimal places

Invalid input is rejected with an error message and the prompt is repeated.

## Security

- Transfers require explicit confirmation of the details summary before the bank is contacted
- The bank then requires a separate TAN confirmation (BestSign, photoTAN, etc.)
- No transfer can be triggered by pressing Enter alone
