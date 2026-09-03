# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# CELL ********************

# Demo ingestion for the marketing solution: land the Bronze CSV files as
# Delta tables. Scheduled by
# prod-schedule.yml through the Job Scheduler API; runs under the calling
# identity. Variable Library access is deliberately not used here — the
# notebookutils.variableLibrary API does not support service principals.
lh = notebookutils.lakehouse.get("lh_bronze")
ws_id = lh["workspaceId"] if isinstance(lh, dict) else lh.workspaceId
lh_id = lh["id"] if isinstance(lh, dict) else lh.id
base = f"abfss://{ws_id}@onelake.dfs.fabric.microsoft.com/{lh_id}"

for name in ["customers", "orders", "payments"]:
    df = spark.read.option("header", True).csv(f"{base}/Files/retail/{name}.csv")
    df.write.mode("overwrite").format("delta").save(f"{base}/Tables/{name}")
    print(f"{name}: {df.count()} rows -> Tables/{name}")

print("ingestion complete")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
