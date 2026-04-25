{% macro generate_surrogate_key(columns) -%}
to_hex(md5(concat(
    {%- for column in columns -%}
    'c{{ loop.index0 }}:', coalesce(cast({{ column }} as string), '__null__'){% if not loop.last %}, '||', {% endif %}
    {%- endfor -%}
)))
{%- endmacro %}
