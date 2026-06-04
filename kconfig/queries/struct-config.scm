(struct_specifier
  name: (type_identifier) @struct.name
  body: (field_declaration_list
    [
      ; Match ifdef CONFIG_FOO
      (preproc_ifdef
        name: (identifier) @config.name
        (#match? @config.name "^CONFIG_")) @config.block
      ; Match #if defined(CONFIG_FOO)
      (preproc_if
        condition: (call_expression
          function: (identifier) @_func
          (#eq? @_func "defined")
          arguments: (argument_list
            (identifier) @config.name
            (#match? @config.name "^CONFIG_")))) @config.block
      ; Match #if CONFIG_FOO
      (preproc_if
        condition: (identifier) @config.name
        (#match? @config.name "^CONFIG_")) @config.block
    ]))
