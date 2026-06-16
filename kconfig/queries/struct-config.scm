(struct_specifier
  name: (type_identifier) @struct.name
  body: (field_declaration_list
    [
      ; 1. Matches: #ifdef CONFIG_FOO
      (preproc_ifdef
        name: (identifier) @config.name
        (#match? @config.name "^CONFIG_")) @config.block
      ; 2. Matches: #if defined(CONFIG_FOO) AND #if defined CONFIG_FOO
      (preproc_if
        condition: (preproc_defined
          (identifier) @config.name
          (#match? @config.name "^CONFIG_"))) @config.block
      ; 3. Matches: #if CONFIG_FOO
      (preproc_if
        condition: (identifier) @config.name
        (#match? @config.name "^CONFIG_")) @config.block
      ; 4. BONUS: Matches modern kernel #if IS_ENABLED(CONFIG_FOO)
      (preproc_if
        condition: (call_expression
          function: (identifier) @_func
          (#eq? @_func "IS_ENABLED")
          arguments: (argument_list
            (identifier) @config.name
            (#match? @config.name "^CONFIG_")))) @config.block
    ]))
