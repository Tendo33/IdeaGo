# Settings Cache In Tests

`get_settings()` is cached. Tests that mutate environment variables must clear
or reload settings explicitly before asserting behavior.

## Rule

- Patch environment variables before loading settings.
- Clear the cached settings helper when a test changes env values.
- Avoid test order dependence.
- Keep root `.env` and frontend `.env` roles separate.

## Hosted Branch Reminder

The `saas` branch has many optional hosted settings. Tests should assert the
specific behavior under test rather than requiring every optional provider key.
