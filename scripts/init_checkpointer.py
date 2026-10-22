"""One-time checkpointer table bootstrap. Use a dedicated migration role."""
import os
from langgraph.checkpoint.postgres import PostgresSaver

dsn = os.environ["CHECKPOINT_DATABASE_URL"]
with PostgresSaver.from_conn_string(dsn) as saver:
    saver.setup()
print("LangGraph PostgreSQL checkpoint tables initialized")
