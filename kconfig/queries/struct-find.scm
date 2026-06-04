(struct_specifier
  name: (type_identifier) @struct.name
  (#eq? @struct.name "__STRUCT_NAME__")
  body: (field_declaration_list) @struct.body) @struct.def
