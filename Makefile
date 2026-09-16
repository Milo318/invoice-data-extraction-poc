.PHONY: install test demo proof autonomy-proof
install:
	python3 -m pip install -e .
test:
	python3 -m unittest discover -s tests -v
demo:
	python3 -m invoice_extractor.cli
proof: test demo
	python3 -m invoice_extractor.benchmark
autonomy-proof:
	python3 -m invoice_extractor.autonomous_benchmark --cases 120
