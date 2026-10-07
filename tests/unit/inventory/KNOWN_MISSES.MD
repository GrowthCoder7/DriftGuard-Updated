# Known Misses in PythonIndexer

- `model=os.environ["MODEL_NAME"]`: Dynamic model parameter evaluation is deliberately skipped. The static AST indexer does not perform deep data-flow analysis or runtime taint tracking to resolve environment variables. An `xfail` test exists to document this gap.