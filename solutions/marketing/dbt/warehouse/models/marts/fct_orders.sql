{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id'
) }}

with orders as (
    select * from {{ ref('stg_retail__orders') }}
),

payments as (
    select
        order_id,
        sum(amount) as order_total
    from {{ ref('stg_retail__payments') }}
    group by order_id
)

select
    orders.order_id,
    orders.customer_id,
    orders.order_date,
    orders.order_status,
    coalesce(payments.order_total, 0) as order_total
from orders
left join payments
    on orders.order_id = payments.order_id
{% if is_incremental() %}
where orders.order_date >= dateadd(day, -3, (select max(order_date) from {{ this }}))
{% endif %}
