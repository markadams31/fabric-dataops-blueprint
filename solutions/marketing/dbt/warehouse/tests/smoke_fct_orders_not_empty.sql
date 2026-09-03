-- Smoke: the orders mart must serve rows after every deploy.
select 1 as failed where (select count(*) from {{ ref('fct_orders') }}) = 0
