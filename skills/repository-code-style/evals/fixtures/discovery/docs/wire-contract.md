# Fixture serialization policy

TaskService.response(2, 123L) currently produces this wire output:

```json
{"count":2,"lastNumber":123}
```

The fixture's API serializer emits Map numeric entries as JSON numbers and keeps
LinkedHashMap insertion order. For bean properties, long/Long values are serialized
as strings by a global policy, and null bean properties are omitted. A private
helper used only to prepare a Map never passes through the bean serializer.

These are stipulated fixture behaviors, not assumptions about a real library.
Changing the service return type from Map to a bean could therefore change the
wire type of lastNumber. The internal object can retain a boundary Map conversion.
Do not add a new serializer configuration or alter the global policy for this task.
