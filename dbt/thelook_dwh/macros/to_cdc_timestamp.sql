{% macro to_cdc_timestamp(expr) -%}
case 
    when {{ expr }} is null then null
    -- Dùng chuỗi trung gian để tránh lỗi compile-time "Invalid cast from TIMESTAMP to INT64"
    when regexp_contains(cast({{ expr }} as string), r'^\d+$') then 
        cast(cast({{ expr }} as string) as int64)
    else 
        unix_millis(safe_cast(cast({{ expr }} as string) as timestamp))
end
{%- endmacro %}
