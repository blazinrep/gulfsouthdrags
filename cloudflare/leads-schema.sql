-- GulfSouthDrags early lead/subscriber store
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL CHECK(kind IN ('tow_report','partner')),
  email TEXT NOT NULL,
  first_name TEXT DEFAULT '',
  business_name TEXT DEFAULT '',
  website TEXT DEFAULT '',
  message TEXT DEFAULT '',
  source TEXT DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(kind, email)
);

CREATE INDEX IF NOT EXISTS leads_kind_created_idx ON leads(kind, created_at DESC);
