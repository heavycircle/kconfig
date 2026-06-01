; Match a true function definition
(function_definition
 declarator: [
   (function_declarator
     declarator: (identifier) @func.name
   )
   (pointer_declarator
     declarator: (function_declarator
                   declarator: (identifier) @func.name
                 )
   )
  ]
  (#eq? @func.name "__SYMBOL_NAME__")
) @func.def

; Match a function-like macro definition (e.g., #define my_func(arg) ...)
(preproc_function_def
 name: (identifier) @func.name
 (#eq? @func.name "__SYMBOL_NAME__")
) @macro.func.def

; Match an object-like macro definition (e.g., #define MY_CONSTANT 42)
(preproc_def
 name: (identifier) @func.name
 (#eq? @func.name "__SYMBOL_NAME__")
) @macro.obj.def
