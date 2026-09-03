-- Smoke: the customers mart must serve rows after every deploy.
select 1 as failed where (select count(*) from {{ ref('dim_customers') }}) = 0
