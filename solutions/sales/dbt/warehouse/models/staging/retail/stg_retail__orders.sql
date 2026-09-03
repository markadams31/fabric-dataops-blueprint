select
    cast(id as int) as order_id,
    cast(user_id as int) as customer_id,
    cast(order_date as date) as order_date,
    cast(status as varchar(20)) as order_status
from openrowset(
    bulk '{{ env_var("DBT_LAKEHOUSE_FILES") }}/retail/orders.csv',
    format = 'CSV', header_row = TRUE
) as src
