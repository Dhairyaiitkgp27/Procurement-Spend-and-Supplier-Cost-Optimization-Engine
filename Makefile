PY=python -m
.PHONY: all pipeline sql star docs dashboard test clean

all: pipeline sql star docs test  ## run everything end-to-end

pipeline:      ## generate data + run all 11 analytics phases
	$(PY) src.pipeline

sql:           ## execute the DuckDB SQL analysis layer
	$(PY) src.run_sql

star:          ## export the Power BI star schema
	$(PY) src.export_star_schema

docs:          ## regenerate markdown deliverables from outputs
	$(PY) src.generate_docs

dashboard:     ## launch the Streamlit executive dashboard
	streamlit run dashboard/app.py

test:          ## run the pytest validation suite
	pytest -q

clean:         ## remove generated artifacts (keeps source)
	rm -rf outputs/tables/* outputs/powerbi/* outputs/consolidated_kpis.json data/raw/* data/processed/*
	find . -type d -name __pycache__ -exec rm -rf {} +
