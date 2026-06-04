; Match structs (struct mutex, ...)
(struct_specifier
  name: (type_identifier) @struct.name)

; Match unions (union bpf_attr, ...)
(union_specifier
  name: (type_identifier) @union.name)

; Match typedefs (umode_t, pid_t, ...)
(type_identifier) @typedef.name
