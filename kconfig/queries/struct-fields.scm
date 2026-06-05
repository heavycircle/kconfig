(field_declaration
 (type_quantifier)?
 type: _ @field.type
 declarator: [
    (field_identifer) @field.name
    (_ (field_identifier) @field.name)
    (_ (_ (field_identifier) @field.name))
    (_ (_ (_ (field_identifier) @field.name)))
    (_ (_ (_ (_ (field_identifier) @field.name))))
]) @field.def
