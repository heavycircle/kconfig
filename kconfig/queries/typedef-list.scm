; Catch preprocessor typedefs (#define Elf_Sym Elf64_Sym)
(preproc_def
    name: (identifier) @typedef.name
    value: (preproc_arg) @typedef.type)

; Catch true typedefs (typedef struct __kernel_foo foo;)
(type_definition
    type: (_) @typedef.type
    declarator: (type_identifier) @typedef.name)
