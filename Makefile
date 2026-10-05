DB ?= freshcart
PY ?= python3

.PHONY: all data analysis sql test

all: data analysis

data:
	$(PY) src/generate_data.py

analysis:
	$(PY) src/analysis.py

# requires a running PostgreSQL and an existing database: createdb $(DB)
sql:
	for f in sql/0*.sql; do psql -d $(DB) -v ON_ERROR_STOP=1 -f $$f || exit 1; done

test:
	$(PY) -m unittest discover -s tests -v
