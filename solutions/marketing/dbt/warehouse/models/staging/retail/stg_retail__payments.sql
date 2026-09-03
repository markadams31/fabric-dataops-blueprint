select
    cast(id as int) as payment_id,
    cast(order_id as int) as order_id,
    cast(payment_method as varchar(30)) as payment_method,
    cast(amount as decimal(18, 2)) as amount
from openrowset(
    bulk '{{ env_var("DBT_LAKEHOUSE_FILES") }}/retail/payments.csv',
    format = 'CSV', header_row = TRUE
) as src
