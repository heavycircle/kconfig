; Catch Preprocessor Aliases (#define sockaddr_storage __kernel_sockaddr_storage)
(preproc_def
  name: (identifier) @alias.name
  value: (preproc_arg) @alias.target)

; Catch Typedefs (typedef struct __kernel_foo foo;)
(type_definition
  type: [
    (struct_specifier
      name: (type_identifier) @alias.target)
    (type_identifier) @alias.target
  ]
  declarator: (type_identifier) @alias.name)
