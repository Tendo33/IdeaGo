# Settings Cache In Tests

`get_settings()` is cached. Tests that mutate environment variables must clear
or reload settings explicitly before asserting behavior.

## Rule

- Patch environment variables before loading settings.
- Clear the cached settings helper when a test changes env values.
- Avoid test order dependence.
- Keep `main` defaults compatible with anonymous/personal deployment.

## Main Branch Reminder

`main` has many optional provider settings. Tests should assert the specific
behavior under test rather than requiring every optional provider key.
