import sqlglot
from sqlglot import exp

query = """
SELECT c.region, SUM(s.amount)
FROM sales s
JOIN customers c
ON s.customer_id = c.id
WHERE c.region='US'
AND s.amount > 1000
GROUP BY c.region
"""

tree = sqlglot.parse_one(query)

tables = [
    t.name
    for t in tree.find_all(exp.Table)
]

print(tables)

join_count = list(tree.find_all(exp.Join))

print(join_count)