# Contract: refusal of a parameter

A tool that refuses a parameter answers, with no IRIS call made:

```json
{
  "success": false,
  "error_code": "INVALID_CLASS_NAME",
  "message": "'X\" Kill ^Y' is not a class name. A class name is an optional %, then identifiers separated by single periods (MyApp.Patient, %Library.String).",
  "class_name": "X\" Kill ^Y"
}
```

- `error_code` is one of the codes in `data-model.md`.
- `message` says what the syntax is and gives two valid examples.
- The refused value is echoed under the parameter's own name.
- Valid input keeps today's response shape exactly (FR-008).
