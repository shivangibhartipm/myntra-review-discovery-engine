import sqlite3

c = sqlite3.connect("data/engine.db")
print("checkpoints:", c.execute("select source, cursor, last_observed_at from collector_checkpoints").fetchall())
print("by source:", c.execute("select source, count(*) from raw_documents group by source").fetchall())
q = """
select count(*) from raw_documents where
  lower(text) like '%wishlist%' or lower(text) like '%wish list%'
  or lower(text) like '%saved for later%' or lower(text) like '%shortlist%'
"""
print("wishlist-ish mentions:", c.execute(q).fetchone())
