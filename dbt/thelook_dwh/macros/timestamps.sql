{% macro to_bq_timestamp(expr) -%}
{%- set col_as_str = "cast(" ~ expr ~ " as string)" -%}
case
    when {{ expr }} is null then null
    -- Chuỗi số nguyên (epoch ms hoặc μs từ Debezium/CDC) → convert theo độ dài
    when regexp_contains({{ col_as_str }}, r'^\d+$') then
        case
            when length({{ col_as_str }}) >= 16
                then timestamp_micros(safe_cast({{ col_as_str }} as int64))
            when length({{ col_as_str }}) >= 13
                then timestamp_millis(safe_cast({{ col_as_str }} as int64))
            else timestamp_seconds(safe_cast({{ col_as_str }} as int64))
        end
    -- TIMESTAMP hoặc ISO string (Parquet external table) → safe_cast qua string
    else safe_cast({{ col_as_str }} as timestamp)
end
{%- endmacro %}
