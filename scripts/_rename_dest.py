import os
import sys

sys.path.insert(0, r"D:\Progetti\Eureka_AI")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connection

with connection.cursor() as cur:
    cur.execute(
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname='public' AND tablename ILIKE '%dest%cli%'
        """
    )
    print("tables", cur.fetchall())
    cur.execute(
        """
        SELECT indexname FROM pg_indexes
        WHERE schemaname='public' AND (indexname ILIKE '%dest%cli%' OR tablename ILIKE '%dest%cli%')
        """
    )
    print("indexes", cur.fetchall())
