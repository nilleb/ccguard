pipenv install --three IPython
pytest server/search server/eventstream --cov=server/search --cov=server/eventstream -k test_fallback
ipython -i interpreter.py
