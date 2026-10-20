# Data model: 137

## Error codes

New codes, `SCREAMING_SNAKE_CASE`, returned before any IRIS call. Each response has `success: false`,
`error_code`, a `message` that states the accepted syntax, and the refused value under a field named
for the parameter.

| Code                     | Parameter kinds                  | Accepted syntax                                                                     |
| ------------------------ | -------------------------------- | ----------------------------------------------------------------------------------- |
| `INVALID_GLOBAL_NAME`    | global names (exists, `ee46c79`) | optional `%`, a letter, letters and digits, single periods between                  |
| `INVALID_CLASS_NAME`     | class and package names          | optional `%`, then identifier segments separated by single periods                  |
| `INVALID_ROUTINE_NAME`   | routine and document names       | a class or routine name plus an allowed extension (`.cls .mac .int .inc .bpl .dtl`) |
| `INVALID_NAMESPACE`      | `namespace` on every tool        | optional `%`, a letter, then letters, digits, `_` and `-`                           |
| `INVALID_METHOD_NAME`    | method and property names        | optional `%`, a letter, then letters and digits                                     |
| `INVALID_SQL_IDENTIFIER` | table and column names           | `Schema.Table` or `Table`, each part an identifier or a `"quoted"` identifier       |
| `INVALID_TIMESTAMP`      | journal `start` / `end`          | `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`                                               |
| `INVALID_PARAMS`         | `body_where` free SQL fragment   | refused: the parameter is replaced by structured filters (existing code)            |

The exact patterns are fixed in the unit tests, which list names IRIS accepts (they must pass) and
crafted ones (they must fail).

## Splice site (research.md)

`file:line`, tool, parameter, placement (ObjectScript literal, bare, SQL literal, SQL identifier, URL
segment, shell argument), escaping today, tier, verdict, and after the fix: the helper used and the
live test that covers it.
