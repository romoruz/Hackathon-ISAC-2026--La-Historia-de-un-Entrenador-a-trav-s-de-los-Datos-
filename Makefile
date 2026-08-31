.PHONY: setup test lint demo clean

setup:
	uv venv --python 3.12
	uv pip install -e ".[dev]"

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

demo:
	uv run dtdecoder demo --outdir reports

clean:
	rm -rf data/interim/* data/processed/* reports/figures/* .pytest_cache
