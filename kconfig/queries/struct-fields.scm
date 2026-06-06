(field_declaration
 (type_qualifier)?
 type: _ @field.type
 declarator: [
    (field_identifier) @field.name
    (_ (field_identifier) @field.name)
    (_ (_ (field_identifier) @field.name))
    (_ (_ (_ (field_identifier) @field.name)))
    (_ (_ (_ (_ (field_identifier) @field.name))))
]) @field.def
