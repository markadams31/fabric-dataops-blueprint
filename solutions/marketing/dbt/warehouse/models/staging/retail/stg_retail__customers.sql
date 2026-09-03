select
    cast(id as int) as customer_id,
    cast(first_name as varchar(100)) as first_name,
    cast(last_name as varchar(100)) as last_name
from openrowset(
    bulk '{{ env_var("DBT_LAKEHOUSE_FILES") }}/retail/customers.csv',
    format = 'CSV', header_row = TRUE
) as src
