{% macro to_bq_timestamp(expr) -%}
case
    when {{ expr }} is null then null
    when regexp_contains(cast({{ expr }} as string), r'^\d+$') then
        case
            when length(cast({{ expr }} as string)) >= 16 then timestamp_micros(cast(cast({{ expr }} as string) as int64))
            when length(cast({{ expr }} as string)) >= 13 then timestamp_millis(cast(cast({{ expr }} as string) as int64))
            else timestamp_seconds(cast(cast({{ expr }} as string) as int64))
        end
    else safe_cast(cast({{ expr }} as string) as timestamp)
end
{%- endmacro %}
