(struct_specifier
  name: (type_identifier) @struct.name
  body: (field_declaration_list
          (preproc_ifdef
            name: (identifier) @config.name (#match? @config.name "^CONFIG_")
          ) @config.block
  )
)
